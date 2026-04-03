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
| `GameState` | The authoritative game snapshot: both `PlayerState`s keyed by `PlayerId`, the `stock`, the `discard` pile, `current_player`, `turn_drawn` flag, and `winner`. |
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
| `opening_meld_value(cards)` | Sums points for natural cards only (wilds excluded) — used to enforce the opening meld threshold. |
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

Every method raises `RuleError` (a `ValueError` subclass) for illegal moves, with a plain-English message suitable for display in the CLI.

`ActionResult` is a small frozen dataclass carrying only a `message` string — it lets callers display feedback without inspecting internal state.

After `discard()` the engine calls `_check_winner()` (empty hand + ≥1 canasta → sets `state.winner`) then `_end_turn()` (flips `current_player`, clears `turn_drawn`).

---

### `cli.py` — Text interface

Implements a REPL loop reading from stdin. Supported commands:

| Command | Action |
|---------|--------|
| `help` | Print command list |
| `state` | Print current game state (hand, melds, scores, stock/discard sizes) |
| `draw` | Call `engine.draw_stock()` |
| `meld i j k …` | Call `engine.create_meld([i, j, k, …])` with hand indexes |
| `add m i j …` | Call `engine.add_to_meld(m, [i, j, …])` |
| `discard i` | Call `engine.discard(i)` |
| `quit` | Exit |

All `RuleError` exceptions are caught and printed as plain messages; the game continues.

---

## What is not yet implemented

- ~~Red three auto-meld on draw~~ ✓ done
- ~~Opening meld minimum point requirement~~ ✓ done
- ~~Picking up the discard pile~~ ✓ done
- Discard pile freeze / unfreeze
- Hand-card penalties at round end
- Multi-round / cumulative scoring
- AI player
- Persistence / save-load

---

[← Index](index.md) | [Next: Game Rules & Data Model →](02-game-rules-and-model.md)
