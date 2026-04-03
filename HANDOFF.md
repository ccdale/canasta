# Canasta Implementation Handoff (2026-04-03)

## Current status
- Standalone project exists at `/home/chris/src/canasta`.
- Project is **not** initialized as a git repository yet.
- Current package/version in `pyproject.toml`: `canasta` / `0.1.0`.
- CLI entry point: `canasta = "canasta.cli:main"`.
- Python requirement: `>=3.12`.

## Implemented modules
- `src/canasta/model.py`
  - Core datatypes: `Card`, `Meld`, `PlayerState`, `GameState`, `PlayerId`.
  - Deck builder: `build_double_deck()`.
  - Helpers/constants: rank/suit constants, wild cards, draw count.
- `src/canasta/rules.py`
  - Rule functions: `validate_meld_cards`, `can_add_cards_to_meld`, `can_discard`.
  - Scoring helpers: `hand_score`, `meld_score`.
- `src/canasta/engine.py`
  - `CanastaEngine` with turn flow: `draw_stock`, `create_meld`, `add_to_meld`, `discard`.
  - Custom exception: `RuleError`.
  - Action response dataclass: `ActionResult`.
  - Winner check requires empty hand and at least one canasta.
- `src/canasta/cli.py`
  - Interactive commands: `help`, `state`, `draw`, `meld`, `add`, `discard`, `quit`.
  - State rendering + command validation + error handling.

## Not yet implemented
- No tests present yet in project tree.
- No CI/lint config yet (beyond basic pyproject fields).
- No variant/ruleset configuration.
- No GUI adapter.
- No persistence/save-load.

## Suggested immediate next step
1. Add `tests/` with baseline unit tests for `rules.py` and deterministic engine initialization.
2. Initialize git repo and commit scaffold.
3. Run `uv sync` then `uv run canasta` to smoke-test CLI loop.
