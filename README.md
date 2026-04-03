# Canasta

Standalone Canasta project built to teach game architecture incrementally.

## Current Scope

- Pure Python game model and rules.
- Turn-based local two-player engine.
- CLI adapter for interactive play.

## Quick Start

```bash
cd ~/src/canasta
uv venv .venv
uv pip install --python .venv/bin/python -e .
uv run canasta
```

Run with bots:

```bash
uv run canasta --north human --south random
uv run canasta --north greedy --south random --bot-seed 7
```

Run tests:

```bash
uv run pytest -q
```

## Learning Milestones

1. Model and rules as pure functions.
2. Engine command handlers that mutate game state safely.
3. CLI layer that delegates all logic to the engine.
4. Configurable AI opponents (`random`, `greedy`) with deterministic seeds.
5. Optional GUI adapter later.
