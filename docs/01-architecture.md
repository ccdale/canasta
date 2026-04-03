# 01 — Project Architecture

[← Index](index.md) | [Next: Game Rules & Data Model →](02-game-rules-and-model.md)

---

## Overview

The project is a pure-Python, zero-dependency CLI implementation of Canasta.
The codebase is divided into focused modules arranged by layering and responsibility:

```
model.py           ← pure data structures + RuleError exception
rules.py           ← pure functions over data (no state)
hands.py           ← hand manipulation utilities (sorting, card selection)
scoring.py         ← round/cumulative scoring calculation
turns.py           ← turn and round lifecycle management
engine.py          ← stateful orchestration (uses all above)
bot_strategies.py  ← bot strategy implementations (protocol + 5 bot types)
bots.py            ← bot factory and turn orchestration
cli.py             ← I/O and command parsing (uses engine + bots)
```

Each module imports only from those listed above it, maintaining separation of concerns.
`model` and `rules` are pure and testable in isolation.
Helpers like `hands`, `scoring`, and `turns` keep `engine` focused on orchestration.
`bot_strategies` contains pure strategy logic; `bots` provides the factory and orchestrator.

---

## Module breakdown

### `model.py` — Data

Defines the canonical types that every other module talks in.

| Type | Purpose |
|------|---------|
| `Card(rank, suit)` | Immutable (`frozen=True`) card value. Rank uses single-char strings (`A 2 … 9 T J Q K`) plus the literal `"JOKER"`. |
| `Meld(cards)` | A group of played cards. Exposes computed properties: `natural_rank`, `natural_count`, `wild_count`, `is_canasta`. |
| `PlayerState` | A player's `hand`, `melds`, `red_threes`, and running `score`. |
| `GameState` | The authoritative game snapshot: both `PlayerState`s keyed by `PlayerId`, the `stock`, the `discard` pile, `current_player`, `round_number`, `turn_drawn` flag, and `winner`. |
| `PlayerId` | `Enum` with values `NORTH` / `SOUTH`. |

`build_double_deck()` returns the canonical 108-card double deck (104 standard + 4 jokers) in a deterministic order before any shuffle.

Constants exported from this module:

- `RANKS` — ordered tuple of all 13 rank strings
- `SUITS` — `("S", "H", "D", "C")`
- `WILD_RANKS` — `{"2", "JOKER"}`
- `DRAW_COUNT_PER_TURN` — `2`

---

### `rules.py` — Pure game logic

All functions are stateless: they take values and return `(bool, str)` tuples (success flag + human-readable reason) or `int` scores.

| Function | What it checks / computes |
|----------|--------------------------|
| `validate_meld_cards(cards)` | New meld validity: ≥3 cards, ≥1 natural, all naturals same rank, wilds ≤ naturals. |
| `can_add_cards_to_meld(meld, cards)` | Delegates to `validate_meld_cards` on the combined card list. |
| `can_discard(card)` | Rejects red threes (3♥ / 3♦). |
| `discard_pile_is_frozen(discard)` | Returns whether any wild card or black three in the pile keeps it frozen. |
| `can_pickup_frozen_discard(top_discard, cards)` | Enforces the stricter pickup rule for a frozen pile: exact natural pair matching a natural top discard. |
| `opening_meld_value(cards)` | Sums points for natural cards only (wilds excluded) — used to enforce the opening meld threshold. |
| `hand_penalty(cards)` | Round-end penalty for cards left in a player's hand. |
| `hand_score(cards)` | Sums point values for a list of cards. |
| `meld_score(melds)` | Sums `hand_score` for all meld cards, adding +300 for each canasta (≥7 cards). |

Point values (from `CARD_POINTS`):

| Cards | Points |
|-------|--------|
| Joker | 50 |
| 2, A | 20 |
| K–8 | 10 |
| 7–3 | 5 |

---

### `hands.py` — Hand utilities

Provides utilities for manipulating player hands:

| Function | Purpose |
|----------|---------|
| `pop_cards_from_hand(hand, indexes)` | Remove cards from hand by index (in original order), with validation for duplicates and out-of-bounds. |
| `sort_hand(hand)` | Sort hand in-place by rank then suit for deterministic display. |

Hand sorting ensures that CLI command indexes are stable across draws, pickups, and failed meld rollbacks.

---

### `scoring.py` — Score calculation

Computes round and cumulative scores:

| Function | Purpose |
|----------|---------|
| `calculate_round_score(player, round_over)` | Sum of meld value + red-three bonus, minus hand penalty if round has ended. |
| `calculate_total_score(player, round_over, round_score)` | Banked score plus the current round score (if round is over). |

These helpers keep scoring logic separate from engine orchestration.

---

### `turns.py` — Turn and round lifecycle

Manages turn flow and round initialization:

| Function | Purpose |
|----------|---------|
| `end_turn(state)` | Switch current player and clear `turn_drawn` flag. |
| `check_winner(state)` | Set winner if current player has empty hand + ≥1 canasta. |
| `ensure_round_active(state)` | Raise `RuleError` if round is already over. |
| `collect_red_threes(player, stock)` | Move red threes from hand to red_threes list, drawing replacements until none remain. |
| `build_round_state(scores, starting_player, round_number, rng, …)` | Construct a fresh `GameState` for a new round: shuffle, deal 11 to each player, auto-collect red threes, sort hands. |

---

### `engine.py` — Stateful orchestration

`CanastaEngine` owns the single `GameState` instance and exposes the turn-by-turn API.
It delegates hand manipulation to `hands.py`, scoring to `scoring.py`, and turn/round lifecycle to `turns.py`.

**Construction** (`__init__(seed=None)`):
Initializes the first round by calling `turns.build_round_state`.

**Turn flow** (enforced by the engine):

```
draw_stock() or pickup_discard()   # exactly one draw action first each turn
  → (optionally) create_meld() / add_to_meld()   # any number of times
discard()             # ends the turn via check_winner() and end_turn()
```

`pickup_discard(hand_indexes)` takes the entire discard pile into the player's turn, but requires the top discard card to be used immediately in a newly created meld with the selected hand cards. The remainder of the pile goes into the player's hand.

The discard pile's frozen state is derived from its contents rather than stored separately: if any wild card or black three exists anywhere in the pile, the pile is considered frozen. In that state, pickup is restricted to an exact natural pair matching a natural top discard.

**Round flow**:

```
play turns until winner is set
  → score() reports final round score including hand penalties
  → total_score() reports banked totals plus the finished round
next_round()          # banks scores, redeals, increments round number, winner starts
```

Every method raises `RuleError` (a `ValueError` subclass) for illegal moves, with a plain-English message suitable for display in the CLI.

`ActionResult` is a small frozen dataclass carrying only a `message` string — it lets callers display feedback without inspecting internal state.

---

### `cli.py` — Text interface

Implements a REPL loop reading from stdin. Supported commands:

| Command | Action |
|---------|--------|
| `help` | Print command list |
| `state` | Print current game state (hand, melds, scores, stock/discard sizes) |
| `draw` | Call `engine.draw_stock()` |
| `pickup i j …` | Call `engine.pickup_discard([i, j, …])` |
| `meld i j k …` | Call `engine.create_meld([i, j, k, …])` with hand indexes |
| `add m i j …` | Call `engine.add_to_meld(m, [i, j, …])` |
| `discard i` | Call `engine.discard(i)` |
| `next-round` | Call `engine.next_round()` after a winner exists |
| `quit` | Exit |

All `RuleError` exceptions are caught and printed as plain messages; the game continues.

`cli.py` also supports per-seat controller selection:

- `--north human|random|greedy|safe|aggro|planner`
- `--south human|random|greedy|safe|aggro|planner`
- `--bot-seed <int>` for deterministic random bot behavior

When the current player is bot-controlled, the CLI auto-plays that full turn via `play_bot_turn` from `bots.py`.

### `bot_strategies.py` — Bot strategy implementations

Defines the `TurnBot` protocol and five concrete bot strategy classes:

| Bot | Behavior |
|-----|----------|
| `RandomBot` | Chooses legal meld/discard actions stochastically using a seeded RNG. |
| `GreedyBot` | Prioritizes highest immediate meld value and lowest-point legal discard. |
| `SafeBot` | Conservative play: opens minimally, then prefers defensive/low-risk discards (black threes, low singleton naturals). |
| `AggroBot` | Aggressive play: prefers large melds quickly and sheds high-point cards early. |
| `PlannerBot` | Balanced heuristic play: favors high-value meld opportunities and preserves wild/synergy cards when discarding. |

Each bot implements `choose_meld_indexes(hand, opening_required)` and `choose_discard_index(hand)`.

Helper functions: `_eligible_natural_meld_candidates()` (finds valid meld candidates) and `_natural_density()` (counts natural cards in a list).

---

### `bots.py` — Bot factory and turn orchestration

Factory and orchestration functions for running bot turns:

| Function | Purpose |
|----------|---------|
| `build_bot(kind, seed)` | Instantiate a bot of the given type. |
| `play_bot_turn(engine, bot)` | Execute one full legal turn sequence (draw → meld attempts → discard), returning action summaries. |

Exports `BotKind` type alias for valid bot strategy names.

---

## What is not yet implemented

- ~~Red three auto-meld on draw~~ ✓ done
- ~~Opening meld minimum point requirement~~ ✓ done
- ~~Picking up the discard pile~~ ✓ done
- ~~Discard pile freeze / unfreeze~~ ✓ done
- ~~Hand-card penalties at round end~~ ✓ done
- ~~Multi-round / cumulative scoring~~ ✓ done
- ~~AI player~~ ✓ done (`random`, `greedy`, `safe`, `aggro`, `planner`)
- Persistence / save-load

---

[← Index](index.md) | [Next: Game Rules & Data Model →](02-game-rules-and-model.md)
