# Canasta

Standalone Canasta project built to teach game architecture incrementally.

## Current Scope

- Pure Python game model and rules.
- Turn-based local two-player engine.
- CLI adapter for interactive play.
- Player hands auto-sort by rank/suit for stable command indexing.

## Quick Start

```bash
cd ~/src/canasta
uv sync
uv run canasta
```

Run with bots:

```bash
uv run canasta --north human --south random
uv run canasta --north greedy --south random --bot-seed 7
uv run canasta --north safe --south greedy
uv run canasta --north aggro --south planner
```

Run tests:

```bash
uv run pytest -q
```

## Learning Milestones

1. Model and rules as pure functions.
2. Engine command handlers that mutate game state safely.
3. CLI layer that delegates all logic to the engine.
4. Configurable AI opponents (`random`, `greedy`, `safe`, `aggro`, `planner`) with deterministic seeds.
5. Optional GUI adapter later.
