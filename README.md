# Canasta

Standalone Canasta project built to teach game architecture incrementally.

## Current Scope

- Pure Python game model and rules.
- Turn-based local two-player engine.
- CLI adapter for interactive play.
- GTK4 GUI adapter for local play.
- Player hands auto-sort by rank/suit for stable command indexing.

## Quick Start

```bash
cd ~/src/canasta
uv sync
uv run canasta
```

Launch the GTK4 GUI:

```bash
uv run canasta-gui
```

Card art is looked up in the XDG data directory for `canasta`.
Symlink the included ccacards image set:

```bash
ln -sfn /path/to/ccacards/data "$HOME/.local/share/canasta"
```

You can override the asset directory explicitly or choose seat controllers:

```bash
uv run canasta-gui --assets-dir /path/to/card-images
uv run canasta-gui --north human --south greedy
uv run canasta-gui --north aggro --south planner --bot-seed 7
```

In the CLI, use `help` for a command list or `help <command>` for detailed help on a specific command:

```
> help
> help pickup
> help meld
```

To display coloured suit symbols (♠ ♥ ♦ ♣ with red for hearts/diamonds):

```bash
uv run canasta --colours
uv run canasta --north human --south random --colours
```

Run with bots (without colors):

```bash
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
5. GTK4 GUI adapter backed by the same engine.
