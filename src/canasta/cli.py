from __future__ import annotations

import argparse

from canasta.bots import BotKind, TurnBot, build_bot, play_bot_turn
from canasta.engine import CanastaEngine, RuleError
from canasta.model import PlayerId, hand_labels
from canasta.rules import discard_pile_is_frozen

HELP_TEXT = (
    "Commands:\n"
    "  help\n"
    "  state\n"
    "  draw\n"
    "  pickup i j          # Take discard pile by melding the top discard with hand indexes\n"
    "  meld i j k          # Create new meld from hand indexes\n"
    "  add m i j           # Add hand indexes to meld m\n"
    "  discard i\n"
    "  next-round\n"
    "  quit\n"
)


def _render_state(engine: CanastaEngine) -> str:
    state = engine.state
    player = state.players[state.current_player]
    opponent_id = (
        PlayerId.SOUTH if state.current_player == PlayerId.NORTH else PlayerId.NORTH
    )
    opponent = state.players[opponent_id]

    hand = " ".join(f"{i}:{label}" for i, label in enumerate(hand_labels(player.hand)))
    meld_lines = [
        f"{idx}: {' '.join(card.label() for card in meld.cards)}"
        for idx, meld in enumerate(player.melds)
    ]
    meld_block = "\n".join(meld_lines) if meld_lines else "(none)"
    red_three_block = (
        " ".join(c.label() for c in player.red_threes)
        if player.red_threes
        else "(none)"
    )

    return (
        f"Round: {state.round_number}\n"
        f"Current: {state.current_player.value}\n"
        f"Winner: {state.winner.value if state.winner is not None else '(none)'}\n"
        f"Stock: {len(state.stock)}  Discard top: {state.discard[-1].label()}  Frozen: {discard_pile_is_frozen(state.discard)}\n"
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
        "--north", choices=["human", "random", "greedy"], default="human"
    )
    parser.add_argument(
        "--south", choices=["human", "random", "greedy"], default="human"
    )
    parser.add_argument("--bot-seed", type=int, default=0)
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
    print(HELP_TEXT)
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
                print(HELP_TEXT)
            elif cmd == "state":
                print(_render_state(engine))
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
