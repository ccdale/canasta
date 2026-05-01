# Canasta — Development Timeline (3 April 2026)

Note: this file is a historical timeline for the initial build day.
For current baseline status and next steps, refer to `HANDOFF.md`.

All work below took place on 3 April 2026 in a single session, starting from
scratch and ending with a fully playable GTK4 GUI.

---

## 10:28 — v0.1.0 · Initial scaffold

- Created project skeleton (`pyproject.toml`, `src/canasta/`, `tests/`)
- Implemented core data model: `Card`, `Meld`, `PlayerState`, `GameState`
- Wrote `rules.py` with pure stateless rule functions
- Implemented `CanastaEngine` orchestrating a full two-player game
- **61 baseline tests passing**

## 10:33 — v0.1.1 · Architecture docs

- Added `docs/` with `index.md`, `01-architecture.md`, `02-rules.md`,
  `03-testing.md`

## 10:39 — v0.1.2 · Red three auto-meld

- Red threes are now automatically extracted from the hand and placed in the
  meld area on draw, then scored at round end
- New tests covering red three handling

## 10:45 — v0.1.3 · Opening meld minimum

- Enforced the 50-point natural-card minimum for a side's first meld
- 10 new tests for opening meld validation

## 12:17 — v0.1.4 · Discard pile pickup

- Implemented the full discard pile pickup flow (top-card matching in hand,
  taking the whole pile)
- Tests for valid and invalid pickup scenarios

## 12:26 — v0.1.5 · Discard pile freeze

- Added frozen pile logic: two black threes or a wild card on top freezes the
  pile, requiring a natural pair to pick up
- Tests for frozen/unfrozen pile states

## 12:33 — v0.1.6 · Round-end hand penalties

- Cards remaining in hand at round end are scored as negative penalties
- Tests for penalty calculation

## 12:36 — v0.1.7 · Multi-round cumulative scoring

- `CanastaEngine` now supports multiple rounds via `next_round()`
- Cumulative scores tracked across rounds
- Tests for multi-round lifecycle

## 12:38 — v0.1.8 · Test hygiene

- Formatted engine test block; removed unused imports from `test_model`

## 12:43 — v0.1.9 · AI players (random & greedy)

- Added `bots.py` with `RandomBot` and `GreedyBot` strategies
- `--north` / `--south` CLI flags to assign bot or human to each seat

## 12:47 — v0.1.10 · Lint fix

- Removed leftover unused imports from `test_model`

## 12:47 — v0.1.11 · SafeBot

- Added `SafeBot` — avoids risky discards, conserves wilds

## 12:49 — v0.1.12 · Docs update

- Simplified quickstart in README to `uv sync`

## 12:52 — v0.1.13 · AggroBot & PlannerBot

- Added `AggroBot` — maximises meld points aggressively
- Added `PlannerBot` — looks ahead at potential meld combinations
- All five bots available as CLI options

## 12:57 — v0.1.14 · Default hand sorting

- `CanastaEngine` now sorts each player's hand by rank then suit after every
  action, so the CLI always shows a consistent ordered hand

## 13:00 — v0.1.15 · Subcommand help

- Added `help <command>` to the CLI REPL (e.g. `help pickup`, `help meld`)
- Each command has a short description and usage hint

## 13:03 — v0.1.16 · Coloured suit symbols

- Added `--colors` flag to the CLI
- Suit symbols rendered in ANSI colour: ♠ white, ♥ red, ♦ red, ♣ white

## 13:06 — v0.1.17 · British spelling

- Renamed flag to `--colours` (British spelling)

## 13:13 — v0.1.18 · Engine refactor

- Split the monolithic `engine.py` into focused modules:
  - `hands.py` — hand manipulation utilities (`pop_cards_from_hand`, `sort_hand`)
  - `scoring.py` — round and cumulative score calculation
  - `turns.py` — turn/round lifecycle (`end_turn`, `check_winner`,
    `ensure_round_active`, `collect_red_threes`, `build_round_state`)
- `RuleError` moved to `model.py` to break circular imports
- `engine.py` retained as thin orchestration layer (~234 lines)

## 13:19 — v0.1.19 · Bot module split

- Split `bots.py` into:
  - `bot_strategies.py` — `TurnBot` protocol + 5 concrete strategy classes
    + helpers (`_eligible_natural_meld_candidates`, `_natural_density`)
  - `bots.py` — factory (`build_bot`) + turn orchestration (`play_bot_turn`)

## Later — v0.1.20/21 · GTK4 GUI (`canasta-gui`)

- Created `card_assets.py`: pure path-resolution module for ccacards image set
  - `asset_dir()` (respects `CANASTA_CARD_ASSET_DIR` env var or XDG data dir)
  - `card_image_path()`, `joker_image_path()` (multi-candidate lookup),
    `back_image_path()`
  - XDG symlink `~/.local/share/canasta` → `/home/chris/src/ccacards/data`
- Created `gui.py`: GTK4 application (`canasta-gui` entrypoint)
  - Green-felt CSS theme (light + dark mode)
  - Card images at 90×126 px (ccacards PNG set)
  - Fan/stacked hand display: cards overlap with only the left edge visible;
    selected cards lift upward
  - Toggle-select cards from hand; Draw / Pickup / Meld / Add to Meld /
    Discard / Next Round controls
  - `Gtk.DropDown` meld selector (no deprecated `ComboBoxText`)
  - Meld display for both players, red three display, score panel
  - Bot auto-play chaining (`_maybe_play_bot_turn`)
  - `--north`, `--south`, `--bot-seed`, `--assets-dir` arguments
  - Auto-re-exec with system Python when `gi` is unavailable in the uv venv
- Added `platformdirs` as a runtime dependency
- 10 new tests for `card_assets` — 154 tests total

## 16:11 — v0.1.22 · GUI setup polish and opening-meld fixes

- Added `canasta.desktop` for GNOME desktop launching
  - Runs `uv run canasta-gui`
  - Uses the card-back image as the desktop icon
- Added a GUI `New Game…` dialog
  - Choose north/south controllers without using command-line flags
  - Configure bot seed from the GUI
- Changed GUI defaults to start as:
  - North: `random`
  - South: `human`
- Improved the hand interaction model
  - Current hand uses a stacked/fanned layout to conserve horizontal space
  - Hand cards no longer show text labels under each image
- Improved meld targeting in the GUI
  - Adding natural cards to an existing meld now auto-selects the destination meld by rank
  - The meld selector is only needed when a wild card is selected
- Fixed GTK deprecations by replacing `Gtk.ComboBoxText` usage with `Gtk.DropDown`
- Corrected the opening-meld rule implementation
  - First meld may now be split across multiple natural ranks in a single action
    (for example, `6666QQQ`)
  - Split-rank opening melds with wild cards remain rejected in one action because
    wild assignment would be ambiguous
- Updated CLI help text to document split-rank opening melds
- Added GUI and rules/engine coverage for the new behavior
- Test count increased to **164 passing**

---

## End-of-day state

| Item | Value |
|---|---|
| Version | 0.1.22 |
| Tests | 164 passing |
| Entrypoints | `canasta` (CLI REPL), `canasta-gui` (GTK4) |
| Bot strategies | random, greedy, safe, aggro, planner |
| Remote | https://github.com/ccdale/canasta.git (pushed) |
