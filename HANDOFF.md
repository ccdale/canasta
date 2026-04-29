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

## GUI Refactoring Opportunity

The main `gui.py` file is currently **~1300 lines** with many responsibilities mixed together, making it difficult to read and maintain. Below is a proposed modularization strategy:

### Current Structure Issues
The `CanastaWindow` class mixes:
- Widget construction and layout (~380 lines of `__init__`)
- Rendering/refresh logic (_refresh, _refresh_hand, _refresh_melds, _refresh_controls, _refresh_summary)
- Event handlers (_on_draw, _on_pickup, _on_meld, _on_discard, etc.)
- Bot management and timers (_maybe_play_bot_turn, _play_one_bot_turn, _start_bot_indicator, etc.)
- Draw preview state management (_clear_draw_preview, _cancel_draw_preview)
- Game state management (_reset_game, _load_saved_game)
- Dialog creation and callbacks
- UI state tracking (selected_hand_indexes, meld_index_mapping, draw preview state, bot indicator state)

### Proposed Modularization

#### 1. **gui/widgets.py** — Reusable widget builders
```
_build_card_picture()
_build_card_widget()
_build_fanned_cards()
_build_pile_picture()
```
Reason: These are pure UI construction functions with no dependencies on game logic.

#### 2. **gui/persistence.py** — Save/load game and stats
```
_get_config_dir()
_load_game_stats()
_save_game_stats()
_game_state_to_dict() / _game_state_from_dict()
_save_game()
_load_game()
_has_saved_game()
```
Reason: Isolates all file I/O and serialization logic; testable independently.

#### 3. **gui/dialogs.py** — Modal dialogs
- `ResumeGameDialog` class (wraps _check_saved_game_on_startup)
- `NewGameDialog` class (wraps _show_new_game_dialog)

Reason: Dialogs are complex, multi-step UI with their own state and callbacks. Extracting as classes makes them reusable and easier to test.

#### 4. **gui/utilities.py** — Card/meld helpers
```
_format_card()
_resolve_target_meld_index()
_card_key()
_new_cards_in_hand()
_reorganize_meld_cards()
_rank_sort_key()
```
Reason: Pure functions for card manipulation logic; no UI dependencies.

#### 5. **gui/bootstrap.py** — Python discovery
```
_parse_args()
_python_candidates()
_find_python_with_gtk()
_reexec_with_system_python()
_find_python_with_gtk()
```
Reason: Only used during startup; separating makes `main()` cleaner.

#### 6. **gui/state.py** — UI state management (optional)
```
class UIState:
    selected_hand_indexes: set[int]
    meld_index_mapping: list[int]
    draw_preview_base_hand: list[Card] | None
    draw_preview_inserted_cards: list[Card] | None
    draw_preview_restore_scroll: float | None
    draw_preview_timeout_id: int | None
```
Reason: Groups all transient UI state separately from game state; makes CanastaWindow easier to understand.

#### 7. **gui/bots.py** — Bot automation (optional helper class)
```
class BotController:
    def __init__(self, engine, controllers)
    def start_turn()
    def play_turn() -> bool
    def stop()
    def _tick_indicator()
```
Reason: Encapsulates bot turn scheduling and indicator updates; currently spread across _maybe_play_bot_turn, _play_one_bot_turn, _start_bot_indicator, _tick_bot_indicator, _stop_bot_indicator.

#### 8. **gui/renderer.py** — Rendering logic
```
class GameRenderer:
    def refresh(window, engine, state)
    def refresh_summary()
    def refresh_hand()
    def refresh_melds()
    def refresh_controls()
```
Reason: All the `_refresh_*` methods are tightly coupled; extracting with a clear API reduces CanastaWindow's size.

### Suggested Migration Path

**Phase 1 (Low-risk):**
1. Extract `bootstrap.py` (no internal dependencies)
2. Extract `persistence.py` (only depends on model)
3. Extract `utilities.py` (pure functions)
4. Extract `widgets.py` (pure UI builders)

**Phase 2 (Medium-risk):**
5. Extract `dialogs.py` (new classes that take GTK objects)
6. Extract `state.py` (just a dataclass; improves readability)

**Phase 3 (Higher-risk, higher-reward):**
7. Extract `bots.py` helper class
8. Extract `renderer.py` helper class
9. Refactor CanastaWindow.__init__() to use injected dependencies

### Post-Refactoring Result
- **gui.py**: ~150–200 lines (main entry point, CanastaWindow layout & event dispatch)
- **dialogs.py**: ~100–120 lines per dialog class
- **renderer.py**: ~200–250 lines (rendering logic)
- **persistence.py**: ~100–150 lines
- **widgets.py**: ~60–80 lines
- **utilities.py**: ~80–100 lines
- **bots.py**: ~60–80 lines (helper class)
- **bootstrap.py**: ~60–80 lines
- Plus **state.py**: ~30–40 lines (dataclass)

**Total code is redistributed but not duplicated; each file has a single clear responsibility.**

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
