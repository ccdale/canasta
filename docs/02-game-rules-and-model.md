# 02 — Game Rules & Data Model

[← Architecture](01-architecture.md) | [Next: Testing Strategy →](03-testing.md)

---

## The deck

Canasta uses a **double deck**: two standard 52-card packs plus two jokers each, giving **108 cards** in total.

```
104 standard cards  (13 ranks × 4 suits × 2)
  4 jokers          (no suit)
```

`build_double_deck()` in `model.py` constructs this in a repeatable order.
The deck is shuffled at engine startup (optionally with a fixed seed).

---

## Dealing

Each player receives **11 cards** dealt alternately from the top of the shuffled deck.
One further card is turned face-up to start the **discard pile**.

After dealing:

| Pile | Size |
|------|------|
| Each player's hand | 11 cards |
| Stock (draw pile) | 85 cards |
| Discard pile | 1 card |

---

## Wild cards

A card is **wild** when `Card.is_wild()` returns `True`.
That applies to:

- Any card with `rank == "JOKER"`
- Any card with `rank == "2"` (regardless of suit)

Wild cards can substitute for natural cards in a meld, subject to the ratio constraint below.

---

## Red threes

Red threes (3♥ and 3♦) are special bonus cards — they cannot be melded normally and are never discarded.

### Auto-meld on draw

Whenever a player draws a card that is a red three it is **immediately** moved from the hand to a dedicated `player.red_threes` list, and a replacement card is drawn from the stock.
This chaining loops: if the replacement is also a red three, that is processed too.

The same logic runs at deal time — any red threes in the opening 11-card hand are auto-collected before a player's first turn.

### Red three scoring (`red_three_score`)

| Count held | Score |
|-----------|-------|
| 1, 2, or 3 | 100 pts each |
| All 4 | 200 pts each (800 total) |

Red three scores are combined with meld scores in `CanastaEngine.score()`.

---

## Melds

A **meld** is a set of cards played face-up in front of a player.

### Validity rules (enforced by `validate_meld_cards`)

1. **Minimum size** — at least 3 cards.
2. **At least one natural** — the meld cannot consist entirely of wild cards.
3. **Uniform rank** — all natural cards must share the same rank.
4. **Wild-card cap** — the number of wilds may not exceed the number of naturals.

### Opening meld minimum

A player’s **first meld** of the round must have enough natural-card point value to meet the opening threshold.

| Constant | Value |
|----------|-------|
| `OPENING_MELD_MINIMUM` | 50 points |

`opening_meld_value(cards)` sums only the natural cards (wilds do **not** count).
If the value falls below the threshold the meld is rejected with a `RuleError` that includes the actual and required scores.
Once a player has at least one meld on the table, subsequent melds in the same or future turns are not subject to this check.

Rule 4 means:
- 2 naturals + 1 wild ✓
- 2 naturals + 2 wilds ✓
- 2 naturals + 3 wilds ✗

### Adding cards to an existing meld

`can_add_cards_to_meld` validates the combined set of old + new cards against the same rules. This means you cannot push a meld over its wild-card cap by adding wilds.

### Canasta

A meld becomes a **canasta** when it reaches 7 or more cards (`Meld.is_canasta`).
A canasta earns a **+300 bonus** on top of the face-value score of its cards.

---

## Turn structure

Each turn follows a strict sequence:

```
1. draw_stock() or pickup_discard(indexes)
  - `draw_stock()` draws 2 cards from the stock
  - `pickup_discard(indexes)` takes the discard pile by immediately melding the top discard with the selected hand cards
2. (optional, repeatable)
   create_meld(indexes)   — lay down a new meld from hand cards
   add_to_meld(m, indexes)— add hand cards to an existing meld
3. discard(index)         — place one hand card on the discard pile; turn ends
```

The engine rejects out-of-order actions with a `RuleError`.
For example, calling `discard` before `draw_stock` raises `"draw before discarding"`.

### Picking up the discard pile

The current implementation supports a simplified discard-pile pickup rule:

1. The pickup must be the turn's draw action.
2. The top discard must be used immediately in a **new meld**.
3. The selected hand cards plus the top discard must form a valid meld under the normal meld rules.
4. If this is the player's opening meld, the usual `OPENING_MELD_MINIMUM` still applies.
5. After the meld is created, the rest of the discard pile is added to the player's hand.

### Discard pile freeze

The pile is considered **frozen** if it contains any:

- wild card (`2` or `JOKER`)
- black three (`3♠` or `3♣`)

This freeze state is derived from the current discard pile contents each time it is checked.

### Frozen-pile pickup restriction

When the pile is frozen, the simplified pickup rule becomes stricter:

1. The top discard must be a **natural** card.
2. The player must use **exactly two** hand cards.
3. Those two hand cards must be **natural cards of the same rank** as the top discard.

Examples:

- Frozen pile with top `AD`: pickup allowed with `AS AH`
- Frozen pile with top `AD`: pickup rejected with `AS JOKER`
- Frozen pile with top `AD`: pickup rejected with `AS AH AC`
- Frozen pile with top `3S`: pickup rejected

---

## Discard restrictions

Not every card can be discarded.
`can_discard` currently enforces one restriction:

- **Red threes** (3♥ and 3♦) may never be discarded.

Other discard rules (freeze/unfreeze of the discard pile) are noted in the architecture doc as not yet implemented.

---

## Scoring

During an active round, scores are calculated from melds and red threes only.
Once the round ends (`GameState.winner` is set), cards still left in hand are applied as a negative penalty.

### Card point values

| Rank | Points |
|------|--------|
| JOKER | 50 |
| 2, A | 20 |
| K, Q, J, T, 9, 8 | 10 |
| 7, 6, 5, 4, 3 | 5 |

### Meld bonus

Each canasta (meld ≥ 7 cards) adds **+300** to the meld's total.

`meld_score(melds)` sums everything: card values across all melds plus canasta bonuses.

### Hand-card penalty at round end

`hand_penalty(cards)` uses the same point table as positive card scoring, but subtracts those points from a player's final round score once the round has ended.

Examples:

- Hand left as `JOKER AS` → `-70`
- Hand left as `KH 7D` → `-15`

The current engine applies this penalty only after a winner exists, so in-progress score display remains focused on positive meld/red-three progress.

### Multi-round / cumulative scoring

`PlayerState.score` now stores **banked scores from completed rounds**.

- `engine.score(player_id)` returns the **current round** score
- `engine.total_score(player_id)` returns the **cumulative total**

Before a round ends, `total_score()` shows only banked prior rounds.
After a winner exists, `total_score()` includes the just-finished round as well.

### Starting the next round

Once a winner exists, `next_round()`:

1. Adds each player's finished round score into `PlayerState.score`
2. Builds and shuffles a fresh double deck
3. Deals fresh hands and a new discard pile
4. Clears melds and red threes for the new round
5. Increments `GameState.round_number`
6. Gives the next opening turn to the previous round's winner

---

## Win condition

After a player discards, `_check_winner` tests:

1. The current player's hand is **empty**.
2. The current player has **at least one canasta** among their melds.

Both conditions must hold. If so, `GameState.winner` is set to that player's `PlayerId`. The round then stops accepting further play actions until `next_round()` is called or the user quits.

---

## Known gaps in rule coverage

The following standard Canasta rules are not yet encoded:

| Rule | Status |
|------|--------|
| Red three auto-meld when drawn | ✓ Implemented |
| Opening meld minimum (50 pts natural) | ✓ Implemented |
| Picking up the discard pile | ✓ Implemented |
| Discard pile freeze | ✓ Implemented |
| Hand-card penalties at round end | ✓ Implemented |
| Multi-round scoring | ✓ Implemented |

---

[← Architecture](01-architecture.md) | [Next: Testing Strategy →](03-testing.md)
