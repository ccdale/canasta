from __future__ import annotations

import argparse

from canasta.bot_strategies import TurnBot
from canasta.bots import build_bot, play_bot_turn
from canasta.engine import CanastaEngine
from canasta.model import Card, PlayerId, RuleError
from canasta.rules import discard_pile_is_frozen

# ANSI color codes
_RED = "\033[91m"
_RESET = "\033[0m"

# Suit symbol mapping
_SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣", None: ""}

HELP_SUMMARY = (
    "Commands:\n"
    "  help [command]      # Show help (optionally for a specific command)\n"
    "  state               # Show current game state\n"
    "  draw                # Draw 2 cards from stock\n"
    "  pickup i j …        # Pick up discard pile by melding top discard with hand indexes\n"
    "  meld i j k …        # Create new meld from hand indexes\n"
    "  add m i j …        # Add hand indexes to meld m\n"
    "  discard i           # Discard a card from hand\n"
    "  next-round          # Start next round after winner is set\n"
    "  quit                # Exit\n"
)

HELP_COMMANDS = {
    "help": (
        "help [command]\n"
        "  Show all available commands or detailed help for a specific command.\n"
        "  Examples: 'help', 'help pickup', 'help meld'\n"
    ),
    "state": (
        "state\n"
        "  Display the current game state including your hand, melds, scores,\n"
        "  stock/discard sizes, and frozen status.\n"
    ),
    "draw": (
        "draw\n"
        "  Draw 2 cards from the stock to your hand.\n"
        "  Must be called exactly once per turn before melding or discarding.\n"
    ),
    "pickup": (
        "pickup i j …\n"
        "  Pick up the discard pile by immediately melding the top discard card\n"
        "  with the specified hand cards (by index).\n"
        "  Example: 'pickup 0 1' melds cards at indexes 0 and 1 with the top discard.\n"
        "  Remaining discard pile cards go into your hand.\n"
        "  If the discard is frozen, requires exact matching pair of naturals.\n"
    ),
    "meld": (
        "meld i j k …\n"
        "  Create a new meld from the specified hand cards (by index).\n"
        "  Example: 'meld 0 1 2' creates a meld from cards at indexes 0, 1, 2.\n"
        "  Rules: ≥3 cards, ≥1 natural, all naturals same rank, wilds ≤ naturals.\n"
        "  First meld must score ≥50 points (naturals only).\n"
        "  Opening melds may be split across multiple natural ranks if each rank\n"
        "  forms its own valid meld in the same action.\n"
    ),
    "add": (
        "add meld_index i j …\n"
        "  Add hand cards to an existing meld.\n"
        "  Example: 'add 0 5 6' adds cards at indexes 5 and 6 to meld 0.\n"
        "  Card must match the meld's natural rank or be a wild.\n"
    ),
    "discard": (
        "discard i\n"
        "  Discard a card from your hand (by index) to end your turn.\n"
        "  Example: 'discard 0' discards the first card in your hand.\n"
        "  Cannot discard red threes (3♥ or 3♦).\n"
    ),
    "next-round": (
        "next-round\n"
        "  Start the next round after a winner is determined.\n"
        "  Banks the current round's scores and resets melds/hand.\n"
        "  The previous round's winner starts the new round.\n"
    ),
    "quit": ("quit\n  Exit the game immediately.\n"),
}


def _card_label(card: Card, colors: bool = False) -> str:
    """Format a card label with optional suit symbols and colors."""
    if card.rank == "JOKER":
        return "JOKER"
    if not colors:
        return card.label()

    symbol = _SUIT_SYMBOLS.get(card.suit, card.suit or "")
    if card.suit in ("H", "D"):
        return f"{_RED}{card.rank}{symbol}{_RESET}"
    return f"{card.rank}{symbol}"


def _hand_labels(hand: list[Card], colors: bool = False) -> list[str]:
    """Get card labels with optional colors."""
    return [_card_label(card, colors) for card in hand]


def _render_state(engine: CanastaEngine, colors: bool = False) -> str:
    state = engine.state
    player = state.players[state.current_player]
    opponent_id = (
        PlayerId.SOUTH if state.current_player == PlayerId.NORTH else PlayerId.NORTH
    )
    opponent = state.players[opponent_id]

    hand = " ".join(
        f"{i}:{label}" for i, label in enumerate(_hand_labels(player.hand, colors))
    )
    meld_lines = [
        f"{idx}: {' '.join(_card_label(card, colors) for card in meld.cards)}"
        for idx, meld in enumerate(player.melds)
    ]
    meld_block = "\n".join(meld_lines) if meld_lines else "(none)"
    red_three_block = (
        " ".join(_card_label(c, colors) for c in player.red_threes)
        if player.red_threes
        else "(none)"
    )

    return (
        f"Round: {state.round_number}\n"
        f"Current: {state.current_player.value}\n"
        f"Winner: {state.winner.value if state.winner is not None else '(none)'}\n"
        f"Match winner: {engine.match_winner().value if engine.match_winner() is not None else '(none)'}\n"
        f"Opening meld minimum for current player: {engine.opening_meld_minimum()}\n"
        f"Stock: {len(state.stock)}  Discard top: {_card_label(state.discard[-1], colors)}  Frozen: {discard_pile_is_frozen(state.discard)}\n"
        f"Your hand: {hand or '(empty)'}\n"
        f"Your melds:\n{meld_block}\n"
        f"Your red threes: {red_three_block}\n"
        f"Opponent meld count: {len(opponent.melds)}\n"
        f"Turn drawn: {state.turn_drawn}\n"
        f"Round scores north={engine.score(PlayerId.NORTH)} south={engine.score(PlayerId.SOUTH)}\n"
        f"Total scores north={engine.total_score(PlayerId.NORTH)} south={engine.total_score(PlayerId.SOUTH)}"
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canasta CLI")
    parser.add_argument(
        "--north",
        choices=["human", "random", "greedy", "safe", "aggro", "planner"],
        default="human",
    )
    parser.add_argument(
        "--south",
        choices=["human", "random", "greedy", "safe", "aggro", "planner"],
        default="human",
    )
    parser.add_argument("--bot-seed", type=int, default=0)
    parser.add_argument(
        "--colours",
        action="store_true",
        help="Use coloured suit symbols in card display",
    )
    return parser.parse_args(argv)


def _build_controllers(args: argparse.Namespace) -> dict[PlayerId, TurnBot | None]:
    controllers: dict[PlayerId, TurnBot | None] = {
        PlayerId.NORTH: None,
        PlayerId.SOUTH: None,
    }
    if args.north != "human":
        controllers[PlayerId.NORTH] = build_bot(args.north, seed=args.bot_seed + 1)
    if args.south != "human":
        controllers[PlayerId.SOUTH] = build_bot(args.south, seed=args.bot_seed + 2)
    return controllers


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    engine = CanastaEngine()
    controllers = _build_controllers(args)

    print("Canasta CLI")
    print(HELP_SUMMARY)
    print(f"Controllers: north={args.north} south={args.south}")

    while True:
        current = engine.state.current_player
        controller = controllers[current]
        if engine.state.winner is None and controller is not None:
            try:
                actions = play_bot_turn(engine, controller)
            except RuleError as exc:
                print(f"[{current.value}:{controller.name}] error: {exc}")
                return 1
            for action in actions:
                print(f"[{current.value}:{controller.name}] {action}")
            continue

        raw = input("> ").strip()
        if not raw:
            continue
        parts = raw.split()
        cmd = parts[0].lower()

        try:
            if cmd == "help":
                if len(parts) > 1:
                    subcmd = parts[1].lower()
                    if subcmd in HELP_COMMANDS:
                        print(HELP_COMMANDS[subcmd])
                    else:
                        print(f"unknown command: {subcmd}")
                        print(HELP_SUMMARY)
                else:
                    print(HELP_SUMMARY)
            elif cmd == "state":
                print(_render_state(engine, colors=args.colours))
            elif cmd == "draw":
                print(engine.draw_stock().message)
            elif cmd == "pickup":
                indexes = [int(x) for x in parts[1:]]
                print(engine.pickup_discard(indexes).message)
            elif cmd == "meld":
                indexes = [int(x) for x in parts[1:]]
                print(engine.create_meld(indexes).message)
            elif cmd == "add":
                if len(parts) < 3:
                    raise RuleError("usage: add meld_index card_indexes...")
                meld_index = int(parts[1])
                indexes = [int(x) for x in parts[2:]]
                print(engine.add_to_meld(meld_index, indexes).message)
            elif cmd == "discard":
                if len(parts) != 2:
                    raise RuleError("usage: discard index")
                print(engine.discard(int(parts[1])).message)
            elif cmd == "next-round":
                print(engine.next_round().message)
            elif cmd == "quit":
                return 0
            else:
                print("unknown command")
        except (ValueError, RuleError) as exc:
            print(f"error: {exc}")
