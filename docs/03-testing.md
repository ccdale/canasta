# 03 — Testing Strategy

[← Game Rules & Data Model](02-game-rules-and-model.md) | [↑ Index](index.md)

---

## Goals

The test suite aims to:

1. Catch regressions as new rules and features are added.
2. Document the intended behaviour of each public function/method as executable examples.
3. Keep tests fast and fully deterministic — no network, no filesystem, no wall-clock time.

All tests live under `tests/` and are discovered automatically by pytest.
Run them with:

```bash
uv run pytest tests/ -v
```

---

## Structure

Three test files mirror the three testable source modules:

| Test file | Source module | What is tested |
|-----------|--------------|----------------|
| `tests/test_model.py` | `canasta/model.py` | Card properties, Meld computed properties, deck construction |
| `tests/test_rules.py` | `canasta/rules.py` | Meld validation, add-to-meld, discard restrictions, scoring |
| `tests/test_engine.py` | `canasta/engine.py` | Engine initialisation, turn flow, error paths |

`cli.py` has no dedicated test file yet; it is covered by the smoke-test described below.

---

## Determinism via fixed seed

`CanastaEngine` accepts an optional `seed` parameter that is forwarded to `random.Random`.
All engine tests construct the engine with `seed=42`:

```python
SEED = 42

def make_engine() -> CanastaEngine:
    return CanastaEngine(seed=SEED)
```

This guarantees that the initial deal is identical across every test run and on every machine, making assertions about hand and stock sizes reliable without depending on particular card values.

Where a test requires specific cards at known positions, it injects them directly into the hand list after construction rather than relying on the shuffle outcome:

```python
def _draw_and_inject(self, eng, cards):
    eng.draw_stock()
    hand = eng.current_hand()
    start = len(hand) - len(cards)
    for i, card in enumerate(cards):
        hand[start + i] = card
    return list(range(start, start + len(cards)))
```

---

## Patterns used

### `(ok, reason)` return value testing

Functions in `rules.py` return a `(bool, str)` tuple.
Tests check both the flag and, where useful, that the reason string contains an expected keyword:

```python
ok, msg = validate_meld_cards([c("K", "S"), c("Q", "H"), c("K", "D")])
assert not ok
assert "same rank" in msg
```

This avoids brittle exact-string comparisons while still verifying that the message is informative.

### Error path coverage

Every `RuleError` branch in the engine has at least one test that triggers it:

```python
def test_double_draw_raises(self):
    eng = make_engine()
    eng.draw_stock()
    with pytest.raises(RuleError, match="already drew"):
        eng.draw_stock()
```

Using `match=` keeps the assertion tied to the specific error rather than catching any `RuleError`.

### State rollback verification

When an invalid meld is attempted the engine must restore the hand to its original state (cards popped during validation are pushed back).
A dedicated test confirms this:

```python
def test_cards_returned_to_hand_on_failure(self):
    eng = make_engine()
    idxs = self._draw_and_inject(eng, [Card("K","S"), Card("Q","H"), Card("J","D")])
    hand_before = len(eng.current_hand())
    with pytest.raises(RuleError):
        eng.create_meld(idxs)
    assert len(eng.current_hand()) == hand_before
```

---

## Coverage summary (124 tests)

| Area | Tests | What they verify |
|------|-------|-----------------|
| `Card.is_red_three` | 4 | red 3♥, red 3♦, black threes, other ranks |
| `Card` | 6 | label formatting, `is_wild`, immutability |
| `Meld` | 5 | `natural_rank`, `natural_count`, `wild_count`, `is_canasta` threshold |
| `build_double_deck` | 3 | total size, joker count, every regular card appears exactly twice |
| `validate_meld_cards` | 7 | all rejection reasons + two acceptance cases |
| `can_add_cards_to_meld` | 3 | valid add, rank mismatch, wild-cap violation after add |
| `can_discard` | 5 | red 3♥, red 3♦, black three, regular card, wild two |
| discard pile freeze helpers | 10 | freeze-card detection, pile frozen/unfrozen status, frozen pickup allowed/rejected cases |
| `opening_meld_value` | 4 | naturals only, wilds excluded, constant value, meets minimum |
| `hand_penalty` | 3 | empty hand, same values as `hand_score`, regular-card examples |
| `hand_score` / `meld_score` | 8 | individual card values, mixed hand, canasta bonus |
| Engine init | 5 | hand sizes, stock size, discard pile, starting player, draw flag |
| `draw_stock` | 4 | hand growth, stock shrinkage, flag set, double-draw error |
| `create_meld` | 4 | success, draw-first gate, invalid meld error, state rollback |
| `add_to_meld` | 3 | success, draw-first gate, invalid meld index |
| `discard` | 6 | hand shrinkage, pile growth, turn rotation, draw-first gate, red-three block, invalid index |
| `pickup_discard` | 12 | meld creation with top discard, pile transfer to hand, turn state, already-drew gate, rollback on invalid pickup, opening-threshold enforcement, opening exemption after first meld, empty pile, frozen-pile allowed/rejected cases |
| Score | 7 | no meld score at start, no pre-round-end hand penalty, losing-hand penalty, winner score unchanged, positive meld score reduced by hand penalty, banked totals before/after round end |
| Opening meld (engine) | 6 | below minimum rejected, cards restored, exactly at minimum, above minimum, wilds excluded from value, subsequent meld exempt |
| Red threes (engine) | 9 | auto-meld at init, hand size preserved, mid-turn trigger, message, `red_three_score` (1/2/4), score integration |
| Winner detection | 3 | winner set only when hand empties with a canasta; winning discard keeps turn on winner |
| Multi-round lifecycle | 6 | initial round number, next-round gate, actions blocked after winner, score banking, round reset, winner starts next round |

---

## Smoke-test

The CLI itself was verified by piping commands through the entry point:

```bash
echo -e "draw\nstate\nquit\n" | uv run canasta
```

Expected output includes the dealt hand, stock/discard sizes, and a clean exit — confirming the full stack from `cli.py` through `engine.py` to `model.py` works end-to-end.

---

## What is not yet tested

- CLI command parsing (argument errors, unknown commands)
- Turn cycling between NORTH and SOUTH over multiple rounds
- Win-condition path (empty hand + canasta)
- Edge cases around stock exhaustion
- ~~Red three auto-meld~~ ✓ now covered
- ~~Opening meld minimum~~ ✓ now covered
- ~~Discard pile pickup~~ ✓ now covered
- ~~Discard pile freeze~~ ✓ now covered
- ~~Hand-card penalties~~ ✓ now covered
- ~~Multi-round scoring~~ ✓ now covered

---

[← Game Rules & Data Model](02-game-rules-and-model.md) | [↑ Index](index.md)
