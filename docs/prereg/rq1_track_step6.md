# Preregistration: need over positions and a seeded priority, step 6 of the M2a remainder

**Written:** 2026-10-25, before the pilot and the evaluation (branch `m2a-step6` from the merge `be287a7`; the decisions
entry that reports the result is G32). **Scope:** step 5's protocol and conditions (`docs/prereg/rq1_track_mattar_daw.md`:
the Q learner, two sessions, the floors, `mattar_daw` and `mattar_daw_1step`, the east − west rate rows) plus the two
items G31 C2 and C3 named, and nothing else. This is the last step on the track: the row closes on its reading.

**Disclosure.** A six-lap run at one seed of the two new conditions was made to check that the code runs end to end
(the test suite's quick runs are of the same kind). In it `mattar_daw_1step_pos` replayed the lap just run backward at
every reward pause and `mattar_daw_pos` did so at four of six. The predictions below were written after seeing that
run; they are predictions about the 30-seed protocol, which it is not.

## Changes from step 5, stated before the run

1. **Need over positions** (G31 C2). Two further conditions, `mattar_daw_pos` and `mattar_daw_1step_pos`, are the
   step-5 rules with the need term read over positions: need(s) is the summed need of the four states (heading ×
   goal) that share s's cell, the expected discounted occupancy of the cell from the state the agent acts from next.
   Nothing else changes: the same successor representation over the 160 states, the same gain, the same extension,
   the same acting state. In step 5 the state carried heading and goal, so the lap just run and the lap ahead were
   different states and need from the next lap's start weighted the lap ahead by about γ^(−lap) over the lap just run;
   Mattar & Daw's track states are positions, which the two laps share, so from the goal end the cells just run are
   also the cells about to be run and have the largest need. The question is whether, with that representation,
   the reward pause's replay is of the lap just run and reverse, as the plan's bound and the published model say.
2. **The extension rule's first-backup priority is seeded** (G31 C3; `TrackConfig.mattar_daw_priority = "seeded"`).
   Step 5's `mattar_daw` made no thresholded backup at any pause under its preregistered θ, and ran at the cap under
   the ablation's θ, because the priority read before a pause's first backup, when the chain is empty, is the largest
   one-step EVB, orders of magnitude below the EVBs the rule reaches once a chain exists. Under "seeded" the priority
   before the first backup is the largest EVB over the one-step candidates *and* the extensions of a would-be chain
   seeded with the acting state's most recent outgoing transition (the chain the rule's first forward step would
   build); the seed is read, not backed up, and `choose` is unchanged, so the fixed mode of step 5 is reproduced
   exactly. θ per rule is set by the step-4 pilot rule on this priority (`--pilot`; the table committed as
   `docs/data/m2a/rq1_step6/rq1_pilot.csv` and copied below before the thresholded run). The one-step rules are
   unaffected by the setting (they have no extensions); their θ values are re-piloted with everyone else's, and
   step 5's are not re-recorded.
3. Everything else is step 5's: the protocol, the tests with the east − west rows and `a_direction_after_change`,
   the learning table, `from_this_lap_share` beside every direction share. Eight conditions on the Q learner: none,
   uniform, reverse_trajectory, prioritised_td, mattar_daw, mattar_daw_1step, mattar_daw_pos, mattar_daw_1step_pos.
   The first six reproduce step 5's fixed-mode rows exactly (same seeds, same code paths; a test pins the two
   Mattar & Daw conditions' per-lap rows on seed 1); their thresholded rows move with the re-piloted θ.

## Predictions, per rule (written before the run)

The primary tests of the step are **(a) at the reward pauses for `mattar_daw_pos` and `mattar_daw_1step_pos`**, read
with `from_this_lap_share`, and **the thresholded (b) and (c) rows of `mattar_daw` under the seeded priority**.

- **mattar_daw_1step_pos.** (a) reward pauses: reverse share > 0.6, **predicted to pass, with `from_this_lap_share`
  above 0.5** (the just-run transitions near the goal now carry the largest need and, after the online consume, a
  residual error, so the one-step argmax starts there and chains backward through gain at predecessors along the lap
  just run); pre-run pauses: forward share fails (no extension). (d) remote: with the sweeps starting near the agent,
  **predicted to fail** (below 10%) at reward pauses; at pre-run pauses uncertain. (b) increase: up; decrease:
  unsigned (a rise), fails "down"; the west end is now a control for the single-end rows only in part (the lap ahead
  shares the changed lap's cells), so east − west uncertain. (c) baseline: need over positions still grows with
  familiarity, fails. Learning: close to `mattar_daw_1step`.
- **mattar_daw_pos.** (a) pre-run pauses: forward share passes (the extension mechanism is unchanged and the acting
  state's own transition still has the largest need). (a) reward pauses, baseline block: the two mechanisms now
  compete at the same cells, a forward chain of the lap ahead (need-ordered, gains near the floor) against a backward
  chain of the lap just run (gain-driven from the residual error at the goal): **predicted mixed, below the 0.6 bound
  for both directions at baseline**, and after a reward change (`a_direction_after_change`) **reverse, predicted to
  pass**, since the error at the consume then gives the just-run states a gain the floor cannot match. `from_this_lap`
  rises from step 5's 0.00 to above 0.3. (d) passes at pre-run pauses, uncertain at reward pauses. (b), (c): as
  `mattar_daw` below. Learning: at least as fast as prioritised_td; slower than `mattar_daw` if backward chains
  displace the n-step forward backups that carried its speed.
- **mattar_daw (seeded priority).** Fixed mode identical to step 5's rows. Thresholded: **the rule now runs** (backups
  per stop between 1 and 99 at the baseline block's pauses, neither 0 nor the cap), the pilot's statistic being on the
  scale of the EVBs it reaches. (b) increase: up, less confident; decrease: unsigned, fails "down"; east − west: not a
  control for a need-weighted rule. (c) baseline: need grows with familiarity, fails; the first lap at 0 later than
  lap 1.
- **mattar_daw_1step, the floors.** As in step 5 (their fixed-mode rows reproduce exactly; thresholded rows move
  only with the re-piloted θ, which is predicted within a few per cent of step 5's for each).

## What would change this document

Only the "Pilot outcome" section below. If a rule cannot run as specified under the scaled θ (a cap that binds at
every pause after θ is set, or a priority that is zero everywhere), the deviation is recorded in G32 and that rule's
thresholded rows are reported as exploratory.

## Pre-run amendment (2026-10-25, after the first pilot, before any evaluation run)

The first pilot, run as change 2 specified (fixed mode, the extension rule's priority seeded), returned for
`mattar_daw` the same θ as step 5's to the digit (3.90938 × 10⁻⁵): at the late-baseline pauses of a fixed-mode run the
seeded extension's EVB never exceeded the largest one-step EVB, so the seeding changed nothing there. A 40-lap
diagnostic at seed 1 (one thresholded session from scratch under that θ, disclosed here) then showed the seeded
priority never exceeding θ × scale at any pause (the ratio peaked at 0.67 at lap 2 and sat between 0.05 and 0.31
afterwards): the rule would again have made no backup. The cause is not the first-backup priority but the pilot's
agent: a fixed-mode pilot reads a rule on the agent its own twenty backups per pause have produced, and for the
extension rule that agent's one-step errors are an order of magnitude larger than those of the no-replay agent the
thresholded run starts from. Change 2 of step 3 set θ so that "every rule starts the thresholded run replaying at about
half its baseline pauses"; for this rule the fixed-mode pilot does not deliver that.

**Amendment.** For the four Mattar & Daw conditions (`mattar_daw`, `mattar_daw_1step`, `mattar_daw_pos`,
`mattar_daw_1step_pos`) the pilot statistic is read in a new budget mode, **observe**, in which the rule's priority and
the value scale are recorded at every pause and nothing is backed up: the agent the thresholded run starts from. The
statistic and the window are unchanged (the median of priority / scale over laps 11–20 of the baseline block at
seeds 1–3). The floors keep the fixed-mode pilot of steps 3–5 (their values are step 5's to the digit, and their
fixed-mode replay does not move the regime their priority is read on). The seeded priority (change 2) stays in force
for the run, since it is defined for the comparison the thresholded loop makes and costs nothing; the pilot shows it
inert at the no-replay agent's late-baseline pauses (the two one-step and extension pairs below share a θ because the
no-replay agent is the same run for both and the seeded extension never beat the one-step maximum). Predictions
unchanged.

## Pilot outcome (2026-10-25, before the thresholded run)

`python3 -m experiments.linear_track_rq1 --pilot --workers 4` (6 s): the baseline block alone (20 laps), seeds 1–3,
the median over laps 11–20 (30 pauses) of priority / value scale; fixed mode for the floors, observe mode for the
Mattar & Daw conditions (amendment). These are the thresholded θ values of step 6 (`THRESHOLDS_STEP6`; the table is
`docs/data/m2a/rq1_step6/rq1_pilot.csv`) and are not changed after this:

| rule | pilot mode | θ (median of priority / scale) | min – max over the 30 pauses |
|---|---|---|---|
| uniform | fixed | 0.124286 | 0.0896 – 0.268 |
| reverse_trajectory | fixed | 2.25714 | 1.44 – 4.08 |
| prioritised_td | fixed | 0.940048 | 0.556 – 1.46 |
| mattar_daw (seeded priority) | observe | 5.23727 × 10⁻⁶ | 1.70 × 10⁻⁶ – 1.12 × 10⁻⁵ |
| mattar_daw_1step | observe | 5.23727 × 10⁻⁶ | 1.70 × 10⁻⁶ – 1.12 × 10⁻⁵ |
| mattar_daw_pos (seeded priority) | observe | 0.0592202 | 0.0281 – 0.177 |
| mattar_daw_1step_pos | observe | 0.0592202 | 0.0281 – 0.177 |

The positional rules' θ is four orders of magnitude above the state-based rules': from the goal cell the positional
need of the cells just run is of order one, and the residual error of the consume gives them a gain the state-based
need discounted by γ^lap. Under the first pilot's θ the extension rule would not have started; under this one the
diagnostic run's ratios, rescaled, exceed 1 at about half the baseline pauses, change 2's intent.
