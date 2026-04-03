"""Scoring helpers for Canasta."""

from canasta.model import PlayerId, PlayerState
from canasta.rules import hand_penalty, meld_score, red_three_score


def calculate_round_score(player: PlayerState, round_over: bool) -> int:
    """Calculate score for a player in the current round.

    Args:
        player: The player's current state.
        round_over: Whether the round has ended (triggers hand penalties).

    Returns:
        Round score including meld value, red-three bonus, and penalties.
    """
    total = meld_score(player.melds) + red_three_score(player.red_threes)
    if round_over:
        total -= hand_penalty(player.hand)
    return total


def calculate_total_score(
    player: PlayerState, round_over: bool, round_score: int
) -> int:
    """Calculate banked + current score.

    Args:
        player: The player's current state.
        round_over: Whether the round has ended.
        round_score: The computed round score from calculate_round_score.

    Returns:
        Banked score plus the round score (if round is over).
    """
    total = player.score
    if round_over:
        total += round_score
    return total
