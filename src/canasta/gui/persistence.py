"""Game state persistence: save/load games and statistics."""

from __future__ import annotations

import json
from pathlib import Path

from canasta import __version__
from canasta.model import Card, GameState, Meld, PlayerId, PlayerState


def get_config_dir() -> Path:
    """Return the canasta config directory, creating it if needed."""
    config_dir = Path.home() / ".config" / "canasta"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_version() -> str:
    """Return the package version used in the app title."""
    return __version__


def load_game_stats() -> dict[str, int]:
    """Load game win/loss statistics from config file.

    Returns dict with keys 'north_wins' and 'south_wins'.
    """
    stats_file = get_config_dir() / "stats.json"
    if stats_file.exists():
        try:
            with open(stats_file) as f:
                data = json.load(f)
                return {
                    "north_wins": data.get("north_wins", 0),
                    "south_wins": data.get("south_wins", 0),
                }
        except (json.JSONDecodeError, IOError):
            pass
    return {"north_wins": 0, "south_wins": 0}


def save_game_stats(north_wins: int, south_wins: int) -> None:
    """Save game win/loss statistics to config file."""
    stats_file = get_config_dir() / "stats.json"
    with open(stats_file, "w") as f:
        json.dump({"north_wins": north_wins, "south_wins": south_wins}, f)


def game_state_to_dict(state: GameState) -> dict:
    """Convert GameState to a JSON-serializable dictionary."""

    def card_to_dict(card: Card) -> dict:
        return {"rank": card.rank, "suit": card.suit}

    def meld_to_dict(meld: Meld) -> dict:
        return {"cards": [card_to_dict(c) for c in meld.cards]}

    def player_state_to_dict(ps: PlayerState) -> dict:
        return {
            "hand": [card_to_dict(c) for c in ps.hand],
            "melds": [meld_to_dict(m) for m in ps.melds],
            "red_threes": [card_to_dict(c) for c in ps.red_threes],
            "score": ps.score,
        }

    return {
        "players": {
            player_id.value: player_state_to_dict(ps)
            for player_id, ps in state.players.items()
        },
        "current_player": state.current_player.value,
        "stock": [card_to_dict(c) for c in state.stock],
        "discard": [card_to_dict(c) for c in state.discard],
        "round_number": state.round_number,
        "turn_drawn": state.turn_drawn,
        "winner": state.winner.value if state.winner is not None else None,
    }


def game_state_from_dict(data: dict) -> GameState:
    """Reconstruct GameState from a dictionary."""

    def dict_to_card(d: dict) -> Card:
        return Card(rank=d["rank"], suit=d["suit"])

    def dict_to_meld(d: dict) -> Meld:
        return Meld(cards=[dict_to_card(c) for c in d["cards"]])

    def dict_to_player_state(d: dict) -> PlayerState:
        return PlayerState(
            hand=[dict_to_card(c) for c in d["hand"]],
            melds=[dict_to_meld(m) for m in d["melds"]],
            red_threes=[dict_to_card(c) for c in d["red_threes"]],
            score=d["score"],
        )

    player_dict = {
        PlayerId(pid): dict_to_player_state(ps) for pid, ps in data["players"].items()
    }
    winner = PlayerId(data["winner"]) if data["winner"] is not None else None
    return GameState(
        players=player_dict,
        current_player=PlayerId(data["current_player"]),
        stock=[dict_to_card(c) for c in data["stock"]],
        discard=[dict_to_card(c) for c in data["discard"]],
        round_number=data["round_number"],
        turn_drawn=data["turn_drawn"],
        winner=winner,
    )


def save_game(state: GameState) -> None:
    """Save the current game state to a file."""
    game_file = get_config_dir() / "game.json"
    with open(game_file, "w") as f:
        json.dump(game_state_to_dict(state), f)


def load_game() -> GameState | None:
    """Load a saved game state from file. Returns None if no save exists."""
    game_file = get_config_dir() / "game.json"
    if game_file.exists():
        try:
            with open(game_file) as f:
                data = json.load(f)
                return game_state_from_dict(data)
        except (json.JSONDecodeError, IOError, KeyError, ValueError):
            pass
    return None


def has_saved_game() -> bool:
    """Check if a saved game exists."""
    return (get_config_dir() / "game.json").exists()
