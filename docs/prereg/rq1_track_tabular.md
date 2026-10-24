# Preregistration: RQ1 on the tabular linear track, step 2 of the M2a remainder

**Written:** 2026-10-24, before any run of the protocol below (commit on branch `m2a-track-rq1`; the decisions
entry that reports the result is G28). **Scope:** the plan's RQ1 windows, reward schedule and budget modes
(docs/research_plan.md §2, §3 RQ1, §4 M2a row) run with the three replay rules and the no-replay floor that exist
at this commit (uniform, reverse-trajectory, |TD error|-prioritised; `brain/systems/replay_rules.py`), plus a
dose-response check of the fixed-budget effect. The plan's test rule, gain × need, and its ablations are step 3; the
rules here are the plan's floors. So this document preregisters, for each floor, **which RQ1 bounds it is predicted
to fail**, and the one prediction where an unsigned rule and the signed rule of step 3 are expected to part.

## Protocol (`experiments/linear_track_rq1.py`)

Everything of the fixed evaluation (docs/m2a_linear_track.md: 40-cell track, tabular state with heading and goal
end, FORWARD / TURN, TD(0) at learning rate 0.2 and discount 0.95, softmax at temperature 0.1 over the one-step
lookahead with prior 0.1386 and gain 10, memory of 2,000 transitions, lap cap 2,000, streams `track_action` and
`replay`, seeds 1–30), with these additions:

- **Reward schedule**, four blocks of 20 laps, 80 laps per seed: block 1 baseline (east 1.0, west 1.0); block 2
  increase (east 4.0, west 1.0); block 3 washout (1.0, 1.0); block 4 decrease (east 0.25, west 1.0). The east end's
  reward changes; the west end is the within-seed control end. Odd laps run east and end at the east end, even laps
  at the west end, so each block has 10 pauses at each end. The exact V\* used for the value error follows the
  block's rewards.
- **Two pauses per lap.** The *reward pause* after the consume transition (as before) and a *pre-run pause* after the
  turn-around, before the first step of the next lap, both at the end just reached; the plan's "reward window" and
  "pre-run window" are these two pauses (the model has no time inside a pause). The pre-run pause of lap 1 has an
  empty memory and makes no backup. Both pauses run the condition's rule on the same memory; the reverse-trajectory
  rule replays the most recently completed lap at either pause (newest transition first), so at a pre-run pause it
  replays the lap just run again.
- **Two budget modes.** *Fixed*: exactly 20 backups at every pause (40 per lap; the plan's Poisson(λ) count is
  replaced by the fixed count, as in the fixed evaluation, so that the rules differ in content only). *Thresholded*:
  the rule keeps replaying while its priority exceeds θ = 0.02, up to a cap of 100 backups per pause, and makes none
  when the priority starts below θ. Priority per rule: reverse-trajectory, the |TD error| of the next transition in
  its backward sweep (one pass over the lap, no cycling); prioritised, the largest |TD error| in memory; uniform, the
  mean |TD error| in memory (a property of the memory, like the others). θ is 2% of the baseline reward. **Pilot
  rule for θ** (the only calibration): the reverse rule in thresholded mode, block 1 only, seeds 1–3; if the mean
  backups per reward pause over laps 11–20 is not inside (2, 50), θ is set once to the median online |TD error| of
  laps 11–20 of the no-replay pilot, and the change is recorded in G28. No other parameter is touched after this
  document.
- **Direction of an event** (`analysis/replay_metrics.py`): the plan's slope sign over the event's cells, read
  against the travel direction of the lap the replayed transitions belong to, taken from their goal row (the state
  carries the goal end, so a replayed transition is direction-selective like a track place cell; a segment mixing
  rows takes the majority row). Forward: the sequence runs the way the body ran on that lap; reverse: the opposite.
  Events are the plan's: a linked run (adjacent-or-same cells) of ≥ 4 distinct cells spanning ≥ 6 cells (0.3 m);
  remote: the start more than 10 cells (0.5 m) from the agent's cell at the pause.
- **Dose-response** (`experiments/linear_track_dose_response.py`): the fixed evaluation's 40-lap stable-reward
  protocol (reward pause only), fixed budget B ∈ {5, 10, 20, 40} backups per pause, all four conditions at seeds
  1–30; B = 20 reproduces the fixed evaluation to the digit.

## Metrics and analysis

The seed is the unit. Per seed, per block, per end and per pause kind, the 10 pauses are pooled into: backups per
stop; events per stop; reverse, forward and remote events per stop; shares among events where events exist.
Intervals are BCa 95% with 10,000 replicates (`analysis.stats`); paired comparisons are within seed
(`paired_effect`, `cliffs_delta`); equivalence is `tost` at ±20% of the comparison mean (reported with its
degeneracy note where a rate is 0). Every number is written to `docs/data/m2a/rq1/` with a manifest.

| test | mode | statistic | the plan's bound |
|---|---|---|---|
| (a) direction by window | fixed | reverse share of reward-pause events; forward share of pre-run-pause events (blocks 1 and 3 pooled, both ends) | each > 0.6 |
| (b) rate and reward change | thresholded | reverse events per stop and backups per stop at the **east** end: block 2 − block 1 and block 4 − block 3, paired by seed; the same at the **west** end as the control | up at ×4 and down at ×0.25 with Cliff's δ ≥ 0.3, interval excluding 0; forward rate unchanged (TOST ±20%); west end unchanged |
| (c) familiarity | thresholded | per-seed slope of backups per stop (and events per stop) against lap within block 1 | negative, interval excluding 0 |
| (d) remote events | fixed | share of events starting > 10 cells from the agent | ≥ 10% |
| dose | fixed, stable reward | paired effect on total steps against `none` at each B; per-seed slope of total steps on log₂ B | sequence rules: slope < 0 with interval excluding 0 and effect growing with B; uniform: interval including 0 at every B |

## Predictions, per rule (written before the run)

- **reverse_trajectory.** (a) Reverse share at reward pauses ≈ 1 (by construction): passes. At pre-run pauses it
  replays the completed lap backward, read against that lap: reverse share ≈ 1, forward share ≈ 0: **fails** the
  pre-run bound. (b) Thresholded: the sweep runs as far as the error is large, so backups and reverse events per
  stop **rise** after the ×4 increase at the east end; after the ×0.25 decrease the TD error is also large (|−0.75|),
  so the rate **rises there too**: the plan's "down at the reduced end" is predicted to **fail** for this unsigned
  rule (RQ5's discriminating prediction, which step 3's signed gain × need is predicted to pass). West end: unchanged
  within the TOST bounds. Forward events: none (TOST degenerate, reported). (c) Falls within block 1: passes.
  (d) Every event starts at the goal: 0% remote, **fails**.
- **prioritised_td.** No events by the plan's definition at baseline (G27: its backups jump between the two ends). Under
  a reward change the error concentrates at one end; whether chains of adjacent backups then form is open and is
  reported, not predicted. (b) Backups per stop rise after both changes (unsigned). (c) Falls. (a), (d) undefined or
  fail for want of events.
- **uniform.** No events; thresholded backups ≈ 0 (the mean |TD error| of 2,000 transitions sits below θ except right
  after a change); (b) and (c) near-degenerate, reported. Fails (a), (d).
- **none.** No pauses with replay; its learning curve across the blocks is the baseline against which the reward-change
  adaptation of the others is read (steps to reward in the first laps of blocks 2 and 4, reported, no bound).
- **Dose-response.** Reverse and prioritised: total steps fall monotonically with B (slope on log₂ B negative,
  interval excluding 0; effect at 40 larger than at 5); uniform: no monotone trend, every effect's interval includes
  0. A sequence rule whose effect does not grow with B would contradict the causal reading of G26/G27 (that the
  effect is the error-carrying backups) and would be reported as such.

## What would change this document

Nothing after the pilot rule above. If the protocol cannot run as specified (a cap that binds on every pause, a
block too short to re-learn the changed reward), the deviation and its reason are recorded in G28 and the run is
reported as exploratory, not confirmatory.

## Pilot outcome (2026-10-24, before the evaluation; the one change this document allows)

The θ pilot ran as specified: reverse-trajectory rule, thresholded mode, block 1 only, seeds 1–3, θ = 0.02. Backups
per reward pause over laps 11–20 averaged 1.80 at each of the three seeds (per lap 9, 9, 0, 0, 0, 0, 0, 0, 0, 0; laps
1–10: 3, 3, 5, 5, 6, 6, 7, 7, 8, 8, the same at every seed, because the errors the sweep meets first are those of
the states next to the goal, whose values move with the lap count and not with the path), outside the (2, 50)
criterion: once V(goal) exceeds 1 − θ the consume carries less error than θ and the sweep never starts, so a
converged baseline makes no thresholded replay at all. By the rule, θ is set once to the median online |TD error| of
laps 11–20 of the no-replay pilot, read as the median over those laps of each lap's mean |TD error| (the quantity
the run records): **θ = 0.0035**. The structural point stands at any θ and is itself a finding to report: the
reverse rule's thresholded rate at a converged baseline is 0, so RQ1(b)'s "up after the ×4 increase" is predicted
to hold trivially (from 0) and (c)'s fall with familiarity to hold as the fall to 0; both are reported with the
rates themselves. Nothing else changed; the dose-response and fixed-mode parts of the protocol are unaffected.
