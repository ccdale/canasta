# Bot Strength Strategy (Phase 4)

## Purpose
This document describes a practical plan for evolving the existing bots into a single strength-scaled system, where `strength=1` behaves close to current baseline and `strength=100` is very hard to beat for most players.

The focus is not perfect play (which is expensive and likely unnecessary for UX), but controlled, measurable improvement across a `1-100` strength dial.

## Design Goals
- Keep all moves legal and rules-compliant at every strength.
- Preserve deterministic reproducibility with existing seed support.
- Make difficulty feel monotonic: higher strength should usually play better.
- Keep GUI responsiveness acceptable at high strengths.
- Avoid abrupt behavior jumps where possible.

## Current Baseline Summary
Current bot styles (`random`, `greedy`, `safe`, `aggro`, `planner`) are mostly heuristic and shallow.
They are good enough for playable matches, but they do not consistently optimize:
- canasta completion urgency,
- opponent denial (freeze/discard safety),
- pickup risk/reward timing,
- multi-turn planning.

## Proposed Architecture
Introduce one policy engine with tunable parameters and optional lookahead:

1. `BotPolicyConfig`
- Strength-derived knobs (search depth, rollout count, risk weight, bluff tolerance, etc.).

2. `PositionEvaluator`
- Scores a state using weighted features (meld progress, canasta potential, hand liability, opponent threat).

3. `MoveGenerator`
- Enumerates legal action bundles for a turn (draw path, meld/add sequence, discard).

4. `SearchLayer` (adaptive)
- Low strengths: pure heuristic pick.
- Mid strengths: limited beam search or shallow expectimax.
- High strengths: deeper search with pruning + selective rollouts.

5. `StrengthMapper`
- Converts `1-100` to policy knobs using smooth functions and soft bands.

## Strength Gauge Model (1-100)
Use continuous scaling plus behavior bands.

### Band A: 1-20 (Baseline / Casual)
- Minimal lookahead (depth 0-1).
- Simple meld selection, limited opponent modeling.
- Higher tolerance for weak discards.
- Expected outcome: roughly current behavior, beatable by attentive players.

### Band B: 21-40 (Improved Fundamentals)
- Better discard safety filtering.
- Better add-to-existing-meld preference for canasta progress.
- Basic frozen-pile awareness.
- Expected outcome: fewer obvious mistakes, more consistent openings.

### Band C: 41-60 (Solid Intermediate)
- Short lookahead (depth 1-2) over candidate turn lines.
- Better pickup timing and opening-threshold planning.
- Starts preserving key cards for likely next-turn payoff.
- Expected outcome: wins clearly more often than baseline bots.

### Band D: 61-80 (Advanced)
- Deeper selective search (depth 2-3) with beam pruning.
- Opponent threat estimation (likely canasta race, discard punishment).
- Better hand-endgame shaping and tempo control.
- Expected outcome: difficult for most casual/intermediate human players.

### Band E: 81-100 (Expert / Near-Unbeatable in Practice)
- Deeper targeted search with stronger pruning and fallback rollouts.
- Strong denial play (discard suppression, freeze pressure) when high EV.
- Better conversion of lead states into wins.
- Expected outcome: statistically dominant against lower strengths and current bots.

## How Strength Changes Outcomes
Strength should affect outcomes through three primary channels:

1. Error Rate Reduction
- Fewer illegal-attempt fallbacks and fewer low-value legal moves.
- Lower blunder frequency on discard and pickup decisions.

2. Conversion Efficiency
- Higher probability of turning promising meld states into canastas and round wins.
- Better preservation of high-value future lines.

3. Opponent Suppression
- More effective denial via discard choices and freeze dynamics.
- Better timing to avoid giving opponents strong pickup opportunities.

In practical terms, if we run many mirror-ish matches:
- `S60` should significantly outperform `S20`.
- `S80` should significantly outperform `S40`.
- `S100` should dominate `S1-S30` over large samples.

## Strength-to-Parameter Mapping (Initial)
Example knob mapping (to be tuned with telemetry):

- `search_depth`: stepwise by strength (0,1,2,3).
- `beam_width`: linear increase with strength.
- `rollout_count`: near-zero below 60, then ramps sharply.
- `discard_risk_weight`: increases smoothly with strength.
- `canasta_urgency_weight`: increases with strength and game phase.
- `opponent_model_weight`: near-zero below 40, strong above 70.

Use interpolation and clamped ranges to avoid sudden spikes in behavior.

## Performance and Responsiveness
- Set hard per-turn compute budgets (time and node caps).
- Use iterative deepening so a valid move is always available.
- For GUI, keep "thinking" latency in a comfortable range.
- If budget exhausted, return best-so-far candidate from the current frontier.

## Validation Plan

Use **match results** (to 5000 points) as the primary difficulty signal rather than single-round outcomes.
1. Ladder Evaluation
- Run bot-vs-bot matrices across representative strengths (e.g., 1, 20, 40, 60, 80, 100).
- Evaluate using match win rate, average rounds per match, and average final margin.
- Require monotonic trend (allowing small statistical noise).

2. Regression Safety
- Keep current legality/rules tests intact.
- Add targeted tests for policy decisions that should never regress (e.g., obvious add-to-meld improvements).

3. Stability & Determinism
- Verify same seed + same strength => reproducible behavior.
- Verify no pathological latency at high strengths under GUI constraints.

## Rollout Plan
1. Add strength parameter plumbing (CLI + GUI + engine/bot config).
2. Introduce unified policy engine with baseline-equivalent mode.
3. Layer stronger heuristics and discard safety first.
4. Add selective search and opponent modeling for upper bands.
5. Calibrate with ladder data and adjust mapping curves.
6. Finalize acceptance thresholds for v2.x bot-strength milestone.

## Success Criteria
- Strength setting is user-visible and intuitive.
- Higher strengths outperform lower strengths statistically.
- Top strength feels "very hard" without causing UI stalls.
- Existing gameplay correctness remains unchanged.
