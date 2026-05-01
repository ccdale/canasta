# Canasta Implementation Handoff (2026-05-01)

## Current Status
- Repository: /home/chris/src/canasta
- Package: canasta
- Current version: 2.0.0
- Python: >=3.12
- Environment/tooling: uv-managed project
- CLI entry point: canasta = canasta.cli:main
- GUI entry point: canasta-gui = canasta.gui:main
- Test status: 181 tests passing

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
- Phase 3 complete:
  - src/canasta/gui/renderer.py extracted and integrated.
  - src/canasta/gui/bot_runner.py extracted and integrated.
  - src/canasta/gui/layout.py extracted and integrated.
  - src/canasta/gui/lifecycle.py extracted and integrated.
  - src/canasta/gui/actions.py extracted and integrated.
  - src/canasta/gui/theme.py extracted and integrated.
  - src/canasta/gui/main.py reduced to orchestration/wiring.

### Version Handling
- Package-level version workflow now centralized in src/canasta/__init__.py.
- __version__ and get_version() resolve from pyproject.toml using git-root fallback, matching tstomkv-style workflow.
- GUI title version path uses this package version source (no more unknown in normal repo runs).

## Recent Milestones
- 8e73fa4: Extracted GUI renderer and bot runner.
- fc5e012: Extracted GUI layout builder.
- 3b626b3: Extracted GUI lifecycle helpers.
- 98b6f5a: Extracted GUI action handlers.
- 8d645ac: Shared GUI controller builder.
- 6d55ffc: Extracted GUI theme and removed dead bot wrappers.
- 6a612f7: Added clickable discard-pile pickup UX improvement.
- 6c663fa: Fixed bot meld routing (extends existing same-rank meld).
- 5909d8e: Release v2.0.0 baseline.

## Remaining Work

### Phase 4 (next)
Goal: strengthen bot play toward effectively unbeatable performance for strong human players, while exposing a single, continuous strength control.

#### Strength control requirement
- Add a bot strength setting from 1-100.
- Strength 1 should preserve current bot behavior baseline.
- Strength 100 should target practically unbeatable play.
- Surface this control in both CLI and GUI:
  - CLI: add an argument like --bot-strength with range validation.
  - GUI: add a numeric control (slider or spinbutton) in New Game dialog.

#### Suggested implementation approach
1. Introduce a unified bot policy layer with tunable decision depth/risk profile.
2. Map strength bands to behavior:
   - 1-20: current heuristic behavior with limited lookahead.
   - 21-60: stronger meld planning, discard safety, freeze-aware pickup logic.
   - 61-90: deeper lookahead with opponent-model heuristics.
   - 91-100: highest search depth, strongest pruning/evaluation, conservative error tolerance.
3. Keep deterministic reproducibility with existing --bot-seed support.
4. Add telemetry hooks (optional): move quality score, blunder count, average search depth.

#### Validation and acceptance criteria
- Add automated bot-vs-bot ladder tests across strength bands (higher strength should outperform lower strength over large samples).
- Add regression tests for existing legal-move/rules behavior so stronger bots do not break correctness.
- Add performance guardrails so high strength remains responsive in GUI turn timing.
- Define "unbeatable" operationally as statistically dominant versus current human-like baseline and lower-strength bots, not mathematically perfect play.

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
