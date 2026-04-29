# Canasta Implementation Handoff (2026-04-29)

## Current Status
- Repository: /home/chris/src/canasta
- Package: canasta
- Current version: 1.4.5
- Python: >=3.12
- Environment/tooling: uv-managed project
- CLI entry point: canasta = canasta.cli:main
- GUI entry point: canasta-gui = canasta.gui:main
- Test status: 180 tests passing

## What Is Complete

### Core Game
- Full game model/rules/engine implementation for standalone Canasta.
- Multi-round scoring and winner detection.
- Discard freeze logic, pickup validation, opening meld minimum, red-three handling.

### Bots
- Bot variants implemented: random, greedy, safe, aggro, planner.
- Deterministic seeding via --bot-seed.

### Persistence and Stats
- Save game to ~/.config/canasta/game.json.
- Resume flow on startup.
- Win/loss stats in ~/.config/canasta/stats.json.

### GUI Refactor
- Phase 1 complete:
  - src/canasta/gui/bootstrap.py
  - src/canasta/gui/persistence.py
  - src/canasta/gui/utilities.py
  - src/canasta/gui/widgets.py
  - src/canasta/gui/__init__.py and src/canasta/gui/__main__.py
- Phase 2 complete:
  - src/canasta/gui/dialogs.py extracted and used by main window.
  - src/canasta/gui/state.py extracted and integrated (UIState dataclass).
  - src/canasta/gui/main.py now uses extracted dialogs/state instead of inline dialog/state sprawl.
- Current GUI file sizes:
  - src/canasta/gui/main.py: 928 lines
  - src/canasta/gui/dialogs.py: 147 lines
  - src/canasta/gui/state.py: 58 lines

### Version Handling
- Package-level version workflow now centralized in src/canasta/__init__.py.
- __version__ and get_version() resolve from pyproject.toml using git-root fallback, matching tstomkv-style workflow.
- GUI title version path uses this package version source (no more unknown in normal repo runs).

## Recent Milestones
- 68edb32: Phase 1 modularization commit.
- 38243f8: HANDOFF updated for Phase 1 completion.
- 3981f2e: Added gui/__main__.py for python -m canasta.gui execution path.
- fcb8c17 + eb0e902: GUI test updates and explicit desktop-variant coverage.
- df1c0ad: Phase 2 refactor (dialogs/state extraction and integration).
- 2e7386d: Unified version lookup with package __version__.

## Remaining Work

### Phase 3 (next)
Goal: reduce src/canasta/gui/main.py further by extracting rendering and bot automation concerns.

#### Recommended extraction targets
1. src/canasta/gui/renderer.py
- Move refresh pipeline and UI rendering internals:
  - _refresh
  - _refresh_summary
  - _refresh_hand
  - _refresh_melds
  - _refresh_controls

2. src/canasta/gui/bot_runner.py (or gui/bots.py)
- Move bot scheduling/indicator/play-loop methods:
  - _maybe_play_bot_turn
  - _play_one_bot_turn
  - _start_bot_indicator
  - _tick_bot_indicator
  - _stop_bot_indicator
  - _cancel_bot_timer

3. Keep in main.py
- Application/window wiring
- event dispatch hooks
- orchestration glue between engine + renderer + bot runner + dialogs + ui_state

#### Suggested sequence
1. Extract renderer first (lower behavior risk, mostly deterministic display logic).
2. Add/update GUI tests for any moved helper behavior where practical.
3. Extract bot runner second (timer/callback behavior).
4. Re-run full checks and desktop entry command variants.

## Validation Commands
- uv sync
- uv run ruff check .
- uv run pytest tests/ -q
- uv run canasta-gui
- uv run canasta-gui --north random
- uv run canasta-gui --north greedy
- uv run canasta-gui --north safe
- uv run canasta-gui --north aggro
- uv run canasta-gui --north planner

## Workflow Notes
- Commit in small increments.
- For each commit: run uv version --bump patch first.
- Include pyproject.toml and uv.lock in each versioned commit.
- Keep Ruff clean before committing.
