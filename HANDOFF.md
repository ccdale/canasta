# Canasta Implementation Handoff (2026-05-04)

## Current Status
- Repository: /home/chris/src/canasta
- Package: canasta
- Current version: 2.1.6
- Python: >=3.12
- Environment/tooling: uv-managed project
- CLI entry point: canasta = canasta.cli:main
- GUI entry point: canasta-gui = canasta.gui:main
- Test status: 235 tests passing

## What Is Complete

### Core Game
- Full game model/rules/engine implementation for standalone Canasta.
- Multi-round scoring with match-end detection.
- Discard freeze logic, pickup validation, dynamic opening meld minimums, red-three handling.
- Match play to 5000 points (highest total wins if both pass 5000 in the same round).

### Bots
- Bot variants implemented: random, greedy, safe, aggro, planner, adaptive.
- Deterministic seeding via --bot-seed.
- Strength scaling implemented across heuristics and pickup behavior.

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
- ede30fc: Added Phase 4 bot-strength strategy document.
- 13a26ea: Added match thresholds (15/50/90/120) and match-end logic.

### Remaining Work

### Deferred next steps (for future session)
Goal: continue strengthening high-end bot play beyond current heuristic tiers.

1. Add game-tree look-ahead search for stronger decision quality.
2. Add optional learned/neural position evaluation to improve move ranking.

#### 1) Game-tree look-ahead (search)
Scope for first pass:
1. Add a search module for bot turn simulation (depth-limited expectimax/minimax-style search).
2. Reuse existing rules/engine legality checks for generated actions.
3. Add pruning and strict time budget per bot turn so GUI remains responsive.
4. Gate usage by strength (higher strengths use deeper search).

Acceptance criteria:
1. Higher search depths outperform shallower settings in ladder runs.
2. No rule regressions in existing engine/rules tests.
3. UI still clearly communicates bot thinking state during longer turns.

#### 2) Neural/learned evaluation (optional layer)
Scope for first pass:
1. Keep search deterministic and use a pluggable evaluator interface.
2. Start with heuristic evaluator baseline; add optional learned evaluator behind a feature flag.
3. Use learned evaluator only at higher strengths or when explicitly enabled.

Acceptance criteria:
1. Learned evaluator does not reduce rules correctness (same legal move set).
2. Measured ladder gain versus heuristic-only at matched time budgets.
3. Graceful fallback to heuristic evaluator if model/artifact is unavailable.

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
- uv run canasta-gui --north adaptive

## Workflow Notes
- Commit in small increments.
- For each commit: run uv version --bump patch first.
- Include pyproject.toml and uv.lock in each versioned commit.
- Keep Ruff clean before committing.
