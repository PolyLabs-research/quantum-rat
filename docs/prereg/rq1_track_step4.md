# Preregistration: the protocol and threshold fixes of G29, step 4 of the M2a remainder

**Written:** 2026-10-25, before any run under the changes below (branch `m2a-step4` from the step-3 tip `44f1609`; the
decisions entry that reports the result is G30). **Scope:** the seven conditions of step 3 (none, uniform,
reverse_trajectory, prioritised_td, gain_need, gain_only, need_only; `docs/prereg/rq1_track_gain_need.md`, including
its pre-run amendments) on a revised protocol that removes two confounds G29 C named and adds the reporting G29 C5
asked for. No rule changes. The question is whether the two RQ1 failures that step 3 could not read cleanly, the
signed response to a reward decrease and the decline with familiarity, were the confounds or the rules.

## Changes from step 3 (G29 C2, C3, C5), stated before the run

1. **Two sessions instead of four blocks** (C2). Each seed runs two sessions of 40 laps: *increase* (20 laps at east
   1.0, then 20 at east 4.0) and *decrease* (20 laps at east 1.0, then 20 at east 0.25); west is 1.0 throughout.
   Both sessions run from the same seed, so their baseline blocks are the same 20 laps and the sessions part at
   lap 21. Each change is read against the baseline block that precedes it. In step 3 the decrease followed a
   washout block whose own surprise (|Δr| 3.0 against the decrease's 0.75) let an unsigned rule pass "down" for a
   magnitude reason; a baseline reference cannot. Steps 2 and 3 remain reproducible (`--version step2`, `--version
   step3`); their tables are not re-recorded.
2. **θ in value units is scaled by the learner's value scale** (C3). For a rule whose priority is in value units (a
   |TD error| or a gain: uniform, reverse_trajectory, prioritised_td, gain_need, gain_only; `ReplayRule.value_scaled`),
   the thresholded comparison is priority > θ × scale, where scale is the mean |V| over the distinct states the agent
   has occupied so far, read once before the pause's first backup and held through the pause, floored at 10⁻⁹. A
   rule whose priority is an occupancy (need_only) is compared with θ itself. θ per rule is set by the pilot rule of
   step 3 applied to the *normalised* priority: the median of priority / scale read before the reward pause over
   laps 11–20 of the baseline block at seeds 1–3 in a fixed-budget run (`--pilot`; the table is committed as
   `docs/data/m2a/rq1_step4/rq1_pilot.csv` and copied into "Pilot outcome" below before the thresholded run). In
   step 3 an EVB of order 10⁻⁷ at baseline was exceeded everywhere once V's scale changed, so the cap of 100 bound
   for the rest of the protocol and the (b) and (c) verdicts rested on how many of 100 backups chained into
   sequences. Fixed mode (20 backups per pause) is unchanged and remains the content test.
3. **The lap-of-origin share is reported beside the direction share** (C5). At a reward pause, the share of the
   backups whose transition belongs to the lap just run (`from_this_lap_share`, already in step 3's seed-block
   table) is now also a stop and seed metric of `analysis.replay_metrics` and appears in every direction table of
   the report, because a "reverse" label at the reward window is met both by a sweep of the lap just run and by a
   sweep of the lap ahead backward from its far goal (step 3's gain × need: 0.013 against reverse_trajectory's 1.00).

## Protocol, metrics, analysis

Otherwise `docs/prereg/rq1_track_tabular.md`'s and `docs/prereg/rq1_track_gain_need.md`'s: the 40-cell track, the
agent and its parameters, a pre-run pause at the start of every lap beside the reward pause at its end, fixed (20
backups per pause) and thresholded (up to 100) budgets, the plan's event definition (≥ 4 distinct cells over ≥ 6
cells, direction against the travel of the lap the replayed states belong to, remote > 10 cells from the agent),
seeds 1–30, the seed the unit, BCa 95% intervals (10,000 replicates), paired comparisons within seed, Cliff's δ with
its bound 0.3, TOST at ±20% relative. The tests, with the cells they read (session, block):

- **(a) direction**, fixed mode, the baseline block (counted once, through the increase session's): reverse share of
  the reward pauses' events > 0.6; forward share of the pre-run pauses' events > 0.6.
- **(d) remote**, fixed mode, the three distinct blocks (baseline, increase, decrease): remote share ≥ 10%, at reward
  and at pre-run pauses.
- **(b) rate and reward change**, thresholded mode, reward pauses, per metric (reverse events, backups, events per
  stop): east end, increase session, block 2 − block 1, "up" (δ ≥ 0.3 and the interval above 0); east end, decrease
  session, block 2 − block 1, "down" (δ ≤ −0.3 and the interval below 0); west end, both sessions, block 2 − block 1,
  "unchanged" (TOST ±20%); forward events per stop at the east end, both sessions, "unchanged". No exploratory row:
  the decrease against its baseline is now the preregistered test.
- **(c) familiarity**, thresholded mode, reward pauses, within the baseline block (the preregistered cell,
  `c_familiarity`): the per-seed slope of backups per stop and of events per stop against lap, "down" when the
  interval on the mean slope excludes 0 from above, and the first lap at which the rate reaches 0, reported. The same
  statistics within each changed block are reported as `c_after_change` (a decline as V re-converges), secondary.
- **Learning speed**, per session (40 laps) and mode: total steps per seed, paired against none and prioritised_td.
- `from_this_lap_share` beside every direction share (change 3).

## Predictions, per rule (written before the run)

The baseline block is the same 20 laps in both sessions by construction (same seed, same rewards); that is a check
on the runner, not a prediction, and it is verified by the tests.

- **gain_need.** (a) reward pauses: reverse share > 0.6, **passes**, with `from_this_lap_share` near 0 (the sweeps
  are of the lap ahead, as in step 3); pre-run pauses: forward share 0, **fails** (afterstate gain chains backward
  by construction, G29 C4; change 2 does not touch the fixed mode). (d) passes. (b) increase, east: backups and
  events per stop up, **passes**, with less confidence than step 3's: the normalised θ no longer binds the cap for
  the whole block, so the rise is the transient while V re-scales. (b) decrease, east: **predicted to fail "down"**:
  the gain of a decrease is the size of the policy's move whatever its sign, so the rate rises against the baseline
  (step 3's exploratory +2.64 events per stop). This is the test the step exists to run cleanly; a pass would
  contradict the structural reading of G29 C1. West end: **not equivalent**, for a structural reason that makes the
  west end no control for this rule: at a west reward pause the sweep covers the lap ahead, which is the east-bound
  lap whose reward changed. (c) baseline: with θ at the median of the late-baseline normalised priority and the scale
  small early in the block, the rate is predicted to fall across the block, **passes**; after each change, down as
  well.
- **gain_only.** (a) reward reverse passes (0.997 in step 3), pre-run forward fails. (d) passes (0.65). (b)
  increase: **falls** (fails "up"), as in step 3: a ×4 reward saturates the softmax at the goal's neighbours and
  gain shrinks. (b) decrease: predicted to fall as well (step 3's exploratory −0.24 events against the baseline), so
  "down" passes for a reason that is not the sign of the change; the pair of verdicts (down at both changes) is the
  reading. West: not shown equivalent. (c) baseline: passes.
- **need_only.** No sequence event (undefined (a), (d)); θ unscaled, the rate follows occupancy: (b) fails at both
  changes, west degenerate or equivalent; (c) fails (no decline; the need of the acting state's own transitions
  grows as laps shorten).
- **reverse_trajectory.** (a) reward reverse 1.00 passes with `from_this_lap_share` 1.00; pre-run forward fails
  (it replays the lap just run backward at both pauses). (d) fails (its sweeps start at the goal). (b) increase up,
  passes; decrease: **rises against the baseline** (step 3's exploratory +10.7 backups), fails "down". West:
  equivalent or degenerate. (c) baseline: passes (step 3: −0.038 per lap, 0 from lap 17).
- **uniform, prioritised_td.** No sequence event (direction and remote undefined). Backups per stop: up at the
  increase, up at the decrease (|δ| follows the size of the surprise), so "down" fails for both; with the scaled θ
  the cap is predicted no longer to bind through the whole changed block (step 3: 100 of 100 for prioritised). (c)
  baseline: predicted to pass for both on backups (a normalised |δ| falls as V fills in).
- **Learning speed.** Fixed mode, per session: the step-3 ordering (gain_only, gain_need faster than prioritised_td;
  need_only identical to none on every seed; uniform the slowest replay condition). Thresholded mode: no
  prediction (the scaled θ changes every rule's budget); reported.

## What would change this document

Only the "Pilot outcome" section below. If a rule cannot run as specified under the scaled θ (a cap that binds at
every pause after θ is set, or a normalised priority that is zero everywhere), the deviation is recorded in G30 and
that rule's thresholded rows are reported as exploratory.

## Pilot outcome (2026-10-25, before the thresholded run; change 2's θ values)

`python3 -m experiments.linear_track_rq1 --pilot --workers 4` (6 s): fixed mode, the baseline block alone (20 laps),
seeds 1–3; for every rule the median over laps 11–20 (30 pauses) of its priority read before the reward pause
divided by the value scale read then (the mean |V| over the occupied states), the raw priority for need_only. These
are the thresholded θ values of step 4 (`THRESHOLDS_STEP4`; the table is `docs/data/m2a/rq1_step4/rq1_pilot.csv`)
and are not changed after this:

| rule | statistic | θ (median) | min – max over the 30 pauses |
|---|---|---|---|
| uniform (mean \|TD error\| in memory) | priority / scale | 0.130951 | 0.0682 – 0.177 |
| reverse_trajectory (largest \|TD error\| over the remaining sweep) | priority / scale | 2.25778 | 1.43 – 4.06 |
| prioritised_td (largest \|TD error\| in memory) | priority / scale | 1.59017 | 0.706 – 4.73 |
| gain_need (largest EVB) | priority / scale | 6.13424 × 10⁻⁶ | 2.28 × 10⁻⁶ – 1.45 × 10⁻⁵ |
| gain_only (largest gain) | priority / scale | 0.0102264 | 0.00588 – 0.0204 |
| need_only (largest need) | priority | 2.71085 | 1.97 – 4.03 |

need_only's θ equals step 3's to the digit (the same pilot on the same laps, unscaled), which checks the pilot against
G29's. The value scale is a property of the run, not of the rule, and the pilot runs each rule under its own
replay, so it differs by condition: the median over the same 30 pauses of the mean |V| over the occupied states is
0.021 under uniform, 0.025 under gain_need, 0.028 under gain_only, 0.061 under reverse_trajectory and 0.099 under
prioritised_td (0.019 under need_only, whose θ it does not enter). The spread between rules, five orders of
magnitude, is unchanged.
