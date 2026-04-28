# Canasta Implementation Handoff (2026-04-28)

## Current status
- Fully implemented standalone Canasta game at `/home/chris/src/canasta`.
- Initialized as git repository with multiple commits.
- Current package/version in `pyproject.toml`: `canasta` / `1.3.6`.
- CLI entry point: `canasta = "canasta.cli:main"`.
- GUI entry point: `canasta-gui = "canasta.gui:main"`.
- Python requirement: `>=3.12`.
- Managed with `uv` (uv.lock included).

## Fully Implemented

### Core Architecture (model.py, rules.py, engine.py)
- Core datatypes: `Card`, `Meld`, `PlayerState`, `GameState`, `PlayerId`.
- Deck builder: `build_double_deck()`.
- Rule functions: meld validation, card adding, discard rules, scoring.
- `CanastaEngine` with full turn flow: draw, meld, add to meld, discard, next round.
- Custom exception: `RuleError`.
- Action response dataclass: `ActionResult`.
- Winner check: empty hand + at least one canasta.

### CLI (cli.py)
- Interactive commands: help, state, draw, meld, add, discard, quit, next_round.
- State rendering with optional colored suit symbols.
- Command validation and error handling.

### GUI (gui.py, GTK4)
- Full GTK4 interface for two-player local play.
- Fanned card display with selection and lift-on-select.
- Meld display with numerical ordering by rank.
- Wild card positioning in canastas (natural on top, wild fanned on bottom).
- New Game dialog with configurable player types and bot seed.
- Stock/discard pile display.
- Auto-refresh game state on every action.

### AI Players (bot_strategies.py, bots.py)
- Five bot types: `random`, `greedy`, `safe`, `aggro`, `planner`.
- Deterministic behavior via `--bot-seed` parameter.
- Configurable via CLI and GUI.

### Game State Persistence (NEW in v1.3.6)
- Auto-save game state to `$HOME/.config/canasta/game.json` after every action.
- Resume prompt on startup if saved game exists.
- Complete state serialization: hands, melds, scores, stock, discard, round number.

### Game Statistics (NEW in v1.3.4)
- Win/loss tracking in `$HOME/.config/canasta/stats.json`.
- All-time record persists across sessions.
- Display: "All-time record: North X wins | South Y wins"

### Development Tools
- **Testing**: 129 pytest tests covering model, rules, engine, bots.
- **Linting**: Ruff integrated for code quality (`uv run ruff check .`).
- **Documentation**: 4 sequential doc files in `docs/`, README, rules.md.

## Known Limitations / Future Work
- No variant rulesets (only standard North American Canasta rules).
- No network play (local two-player only).
- No undo/history.
- Card images optional (text fallback if not found).

## Quick Start for Future Development

```bash
cd ~/src/canasta
uv sync
uv run canasta              # CLI mode
uv run canasta-gui          # GUI mode
uv run pytest -q            # Run tests
uv run ruff check .         # Check code quality
```

## Configuration Files
- `$HOME/.config/canasta/game.json` — Saved game state
- `$HOME/.config/canasta/stats.json` — Win/loss statistics
- Card images: `$HOME/.local/share/canasta/` (symlink from ccacards)
