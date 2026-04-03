"""Turn and round lifecycle management."""

import random

from canasta.model import (
    Card,
    GameState,
    PlayerId,
    PlayerState,
    RuleError,
    build_double_deck,
)


def end_turn(state: GameState) -> None:
    """End the current turn and switch to the other player.

    Args:
        state: The game state (modified in-place).
    """
    state.turn_drawn = False
    state.current_player = (
        PlayerId.SOUTH if state.current_player == PlayerId.NORTH else PlayerId.NORTH
    )


def check_winner(state: GameState) -> None:
    """Set winner if current player empties hand with a canasta.

    Args:
        state: The game state (modified in-place if winner found).
    """
    player = state.players[state.current_player]
    if player.hand:
        return
    if any(meld.is_canasta for meld in player.melds):
        state.winner = state.current_player


def ensure_round_active(state: GameState) -> None:
    """Raise an error if the round has already ended.

    Args:
        state: The game state.

    Raises:
        RuleError: If winner has been set.
    """
    if state.winner is not None:
        raise RuleError("round is over; start next-round or quit")


def collect_red_threes(player: PlayerState, stock: list[Card]) -> int:
    """Move red threes from hand to red_threes list, drawing replacements.

    Loops until no red threes remain in hand (a replacement could itself
    be a red three). Returns total count collected.

    Args:
        player: The player's state (modified in-place).
        stock: The draw stock (depleted as replacements are drawn).

    Returns:
        Total number of red threes collected.
    """
    collected = 0
    while True:
        found = [c for c in player.hand if c.is_red_three()]
        if not found:
            break
        for card in found:
            player.hand.remove(card)
            player.red_threes.append(card)
            collected += 1
            if stock:
                player.hand.append(stock.pop())
    return collected


def build_round_state(
    scores: dict[PlayerId, int],
    starting_player: PlayerId,
    round_number: int,
    rng: random.Random,
    collect_red_threes_fn,
    sort_hand_fn,
) -> GameState:
    """Build a fresh game state for a new round.

    Shuffles deck, deals 11 cards to each player, and initializes discard pile.
    Auto-collects red threes and sorts hands.

    Args:
        scores: Banked scores keyed by PlayerId.
        starting_player: PlayerId who starts this round.
        round_number: The round number (1-based).
        rng: Seeded random.Random for deterministic shuffles.
        collect_red_threes_fn: Callable to auto-meld red threes.
        sort_hand_fn: Callable to sort hands.

    Returns:
        Initialized GameState.
    """
    deck = build_double_deck()
    rng.shuffle(deck)

    north = PlayerState(hand=[], melds=[], score=scores[PlayerId.NORTH])
    south = PlayerState(hand=[], melds=[], score=scores[PlayerId.SOUTH])
    for _ in range(11):
        north.hand.append(deck.pop())
        south.hand.append(deck.pop())

    state = GameState(
        players={PlayerId.NORTH: north, PlayerId.SOUTH: south},
        current_player=starting_player,
        stock=deck,
        discard=[deck.pop()],
        round_number=round_number,
        turn_drawn=False,
        winner=None,
    )

    for player in state.players.values():
        collect_red_threes_fn(player, state.stock)
        sort_hand_fn(player.hand)

    return state
