# 01 — Project Architecture

[← Index](index.md) | [Next: Game Rules & Data Model →](02-game-rules-and-model.md)

---

## Overview

The project is a pure-Python, zero-dependency CLI implementation of Canasta.
The codebase is divided into four strictly-layered modules:

```
model.py   ← pure data structures (no logic)
rules.py   ← pure functions over data (no state)
engine.py  ← stateful orchestration (uses rules)
bots.py    ← pluggable turn strategies (random/greedy)
cli.py     ← I/O and command parsing (uses engine)
```

Each layer may only import from the layer(s) below it.
This makes `model` and `rules` trivially testable in isolation and keeps the game engine independent of any display concerns.

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

### `engine.py` — Stateful orchestration

`CanastaEngine` owns the single `GameState` instance and exposes the turn-by-turn API.

**Construction** (`__init__(seed=None)`):
1. Builds a double deck.
2. Shuffles with `random.Random(seed)` — passing a seed makes the game deterministic for testing.
3. Deals 11 cards to each player (alternating pops from the top of the shuffled deck).
4. Pops one card to start the discard pile.

**Turn flow** (enforced by the engine):

```
draw_stock() or pickup_discard()   # exactly one draw action first each turn
  → (optionally) create_meld() / add_to_meld()   # any number of times
discard()             # ends the turn
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

After `discard()` the engine calls `_check_winner()` (empty hand + ≥1 canasta → sets `state.winner`). If no winner exists, it then calls `_end_turn()` (flips `current_player`, clears `turn_drawn`).

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

### `bots.py` — AI turn strategies

Defines a small strategy protocol plus concrete bot types:

| Bot | Behavior |
|-----|----------|
| `RandomBot` | Chooses legal meld/discard actions stochastically using a seeded RNG. |
| `GreedyBot` | Prioritizes highest immediate meld value and lowest-point legal discard. |
| `SafeBot` | Conservative play: opens minimally, then prefers defensive/low-risk discards (black threes, low singleton naturals). |
| `AggroBot` | Aggressive play: prefers large melds quickly and sheds high-point cards early. |
| `PlannerBot` | Balanced heuristic play: favors high-value meld opportunities and preserves wild/synergy cards when discarding. |

`build_bot(kind, seed)` instantiates bot implementations and `play_bot_turn(engine, bot)` executes one full legal turn (`draw` → meld attempts → `discard`).

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
