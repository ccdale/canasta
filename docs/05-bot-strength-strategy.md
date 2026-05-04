# Bot Strength Strategy (Current Behavior)

## What this page is for
This page explains how bot strength works today in the shipped implementation.

It focuses on a practical question:
- What does a strong bot do differently from a weak bot?

This is intentionally concrete and code-aligned, not a future architecture proposal.

## Quick summary
The strength setting is a heuristic dial, not deep search.

Higher strength mainly improves play through four levers:
1. Better discard choices (preserve wilds and grouped ranks, freeze pressure where useful).
2. Better post-opening meld choices (including wild-assisted melds at higher strength).
3. Discard-pile pickup before stock draw (enabled only at higher strength).
4. Safer opening and conversion behavior that reduces stalls and blunders.

## One important clarification
"Naturals only" does not mean all opening meld cards must be natural.

The naturals-only rule applies to opening-threshold scoring.
- Opening threshold checks count natural card value.
- Wild cards can still be present in valid meld groups as long as meld legality is satisfied.

## Shared strength behavior across bots
These are shared system-level effects:

1. Strength range is 1-100.
2. Discard pickup is attempted before stock draw only when strength >= 50.
3. Pickup legality respects frozen vs unfrozen discard rules.
4. If pickup fails for any reason, bot falls back to stock draw.

### Pickup behavior details
When pickup is considered:
- Frozen pile:
  - Bot only considers a natural matching pair for the top discard rank.
- Unfrozen pile:
  - Bot considers natural pair for top rank.
  - Bot also considers natural + wild for top rank.
- Candidate choice prefers higher opening value, then higher natural density.

## Bot-by-bot: weak vs strong

### Random bot
- Core behavior:
  - Meld/discard choices are random among legal candidates.
- Strength impact:
  - No strategic scaling in meld/discard policy itself.
  - At strength >= 50 it can still use the shared pickup-before-draw logic.

### Greedy bot
- Weak (roughly <34):
  - Discards lowest points first with weak wild preservation.
- Mid (34-66):
  - Avoids discarding wilds more consistently.
- Strong (>=67):
  - Keeps wilds, preserves grouped ranks, applies freeze-pressure preference.
- Meld scaling:
  - After opening, strength >= 50 can include wild-assisted meld candidates.

### Safe bot
- Post-opening meld policy is strongly tiered:
  - <20: never meld after opening.
  - 20-49: meld only large natural groups (4+ cards).
  - 50-69: meld natural groups of 3+ cards.
  - >=70: also consider wild-assisted meld candidates.
- Discard policy:
  - Prefers defensive/safe discards (black threes, singleton shedding, avoid wilds).

### Aggro bot
- Weak (<40):
  - Discards high-point cards aggressively, including wilds more often.
- Strong (>=40):
  - Still aggressive, but preserves wilds more and sheds high-point naturals first.
- Meld scaling:
  - After opening, strength >= 50 includes wild-assisted meld candidates.

### Planner bot
- Weak (<34):
  - Simpler discard risk ordering.
- Strong (>=34):
  - Better preservation of wilds and grouped ranks.
- Meld scaling:
  - After opening, strength >= 50 includes wild-assisted meld candidates.

## Opening meld behavior in practice
Current implementation supports:
1. Split-rank opening melds.
2. Wild cards in split-rank opening melds, as long as each resulting meld group is legal.

Example that is valid:
- A A A plus K K 2

Opening threshold still uses naturals for scoring evaluation.

## Why stronger bots now feel stronger
In ladder play, stronger settings improved by:
1. Converting hands more efficiently after opening (more legal productive melds).
2. Avoiding destructive discards (especially wilds and useful grouped ranks).
3. Using discard pickup when it is legal and favorable.
4. Reducing stock-depletion stall patterns compared to lower-strength play.

## Current limitations
Strength is still heuristic and threshold-driven.

What this means:
1. It is not full lookahead search.
2. Some matchups can still show variance or occasional inversions if thresholds interact oddly.
3. Opening candidate generation for bots is still mostly natural-first, even though engine rules now allow more split-with-wild opening shapes.

## AdaptiveBot — the default opponent
`AdaptiveBot` is the recommended bot kind for casual play. It implements a single-parameter skill curve using four strength bands:

| Strength range | Behaviour |
|---|---|
| 1–25 (random) | Picks a random meld candidate; discards randomly |
| 26–50 (safe) | Post-opening: only melds groups of 4+ naturals; defensive discard (black threes first, avoid wilds, prefer singletons) |
| 51–75 (planner) | Post-opening: uses wild-augmented meld candidates; planner discard (keep wilds and grouped ranks, shed isolated high-pointers) |
| 76–100 (aggro) | Post-opening: picks the longest wild-augmented candidate; sheds highest-point naturals while keeping wilds |

The bot takes an `rng: random.Random` for reproducibility across all band behaviours.

Ladder results with 60 matches per matchup confirm strict monotonic ordering:
- adaptive:20 vs adaptive:80 → 0–60
- adaptive:40 vs adaptive:90 → 0–60
- adaptive:50 vs adaptive:80 → 22–38

## Planned next tuning direction
Continue improving monotonic strength feel by:
1. Expanding pickup candidate generation and ranking depth.
2. Smoothing threshold cliffs where behavior jumps are too abrupt.
3. Adding broader matchup telemetry across bot styles and strengths.

## Deferred next steps (future session)
Two stronger-bot strategies were intentionally deferred:

1. Game-tree look-ahead search.
2. Optional neural/learned evaluator.

### 1) Game-tree look-ahead search
This is algorithmic search over possible future actions (for example depth-limited minimax or expectimax with pruning), not a neural network by itself.

Planned approach:
1. Add depth/time-bounded search at higher strengths.
2. Keep low strengths on the existing fast heuristic policy.
3. Preserve deterministic behavior with seeded tie-breaking.

### 2) Neural/learned evaluator (optional)
This is a model that scores board states/moves and can be used inside search.

Planned approach:
1. Keep the current heuristic evaluator as default fallback.
2. Add learned evaluation behind a feature flag or high-strength gate.
3. Compare gains at equal time budgets before enabling by default.
