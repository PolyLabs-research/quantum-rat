# Preregistration: the Mattar & Daw rule on a Q learner, step 5 of the M2a remainder

**Written:** 2026-10-25, before any run of the rules below (branch `m2a-step5` from the step-4 tip `d1f5fc5`; the
decisions entry that reports the result is G31). **Scope:** the plan's reference rule as published (Mattar & Daw
2018: prioritised memory access over state-action values, with the forward n-step extension), its one-step ablation,
and the three floors and no replay rerun on the same learner, on step 4's protocol (`docs/prereg/rq1_track_step4.md`:
two sessions per seed, θ in value units scaled by the value scale, the lap-of-origin share), with one addition to the
analysis (G30 C2). The question is G29 C4's: does forward pre-run replay, the one RQ1 bound no afterstate rule can
meet, appear when the gain is read at the acted-from state over its actions and a backup can be extended forward?

## Changes from step 4, stated before the run

1. **The learner.** Every condition of this step acts on a tabular Q learner (`brain/systems/value_learners.TabularQ`):
   Q-learning over the same 0.5-unit cells, target r + γ max_a Q(s′, a) (r alone into the consume, which is terminal),
   α = 0.2, γ = 0.95, the protocol's values; the action backed up is read off each stored transition's geometry (a
   change of the y row is a TURN, anything else a FORWARD, the consume included). The policy is the same softmax as
   before, over FORWARD: prior + 10·Q(s, FORWARD) and TURN: 10·Q(s, TURN) at temperature 0.1, in place of the
   afterstates' V. The floors (uniform, reverse_trajectory, prioritised_td) back up Q through the same transitions
   (their |TD error| is Q-learning's); no replay is the baseline. The step-3 rules (gain × need on V) are not run here:
   a V-based and a Q-based condition are not paired comparisons, and step 4 carries the V results.
2. **The rules** (`brain/systems/replay_mattar_daw.py`). `mattar_daw`: at each backup the argmax of EVB over the
   distinct stored transitions and the extensions; EVB(e) = need(s) × max(gain(e), 10⁻¹⁰), need the successor
   representation's expected discounted occupancy of s from the state the agent acts from next (as in step 3,
   learned online from the agent's own transitions and the inter-lap placements, started from the cyclic structure),
   gain(e) = Σ_a [π_new(a|s) − π_old(a|s)] Q_new(s, a) at the acted-from state s with Q(s, a) moved by α δ (Mattar &
   Daw's gain, with their minimum gain so that need orders the candidates when every gain is negligible). **The
   forward n-step extension**, our reading of their n-step backups: the rule keeps the chain of its backups within a
   pause while each continues the last forward (its state is the last one's successor state); beside the one-step
   candidates, every stored transition t that continues the chain is a candidate as the n-step backup of the chain's
   first transition through the chain and t (target Σ γ^(i−1) r_i + γⁿ max_a Q(s_(n+1), ·), nothing beyond a
   terminal), EVB = need(s₁) × gain of that backup at s₁; when chosen, Q(s₁, a₁) moves toward the n-step target (one
   TD backup, counted as any other), the chain grows by t and the replay record shows t's cell (the state the
   sequence advanced to); when a one-step candidate is chosen the chain restarts at it. Ties go to the extension,
   then to the most recently stored transition. No draw is made. `mattar_daw_1step`: the same without extensions.
3. **A time control for the rate tests** (G30 C2). Beside each preregistered (b) row (east block 2 − block 1 of a
   session), the east change minus the west change, (east block 2 − block 1) − (west block 2 − block 1), paired by
   seed, with the same bounds ("up" at the increase: δ ≥ 0.3 and the interval above 0; "down" at the decrease: δ ≤
   −0.3 and the interval below 0). The single-end row stays the plan's test; the difference row is the one that
   separates the change from the trend, and it is preregistered here for the first time. For a rule whose sweep at a
   west pause covers the changed east-bound lap (any need-weighted rule) the west end is not a control, and the
   difference row is read with that said. Also added: the reverse share at the reward pauses of the changed blocks
   and the forward share at their pre-run pauses (`a_direction_after_change`), secondary.
4. **θ per rule** by step 4's pilot rule (the median of priority / value scale over laps 11–20 of the baseline block
   at seeds 1–3, fixed budget) on this learner (`--pilot`, the table committed as `docs/data/m2a/rq1_step5/rq1_pilot.csv`
   and copied below before the thresholded run). Every rule here has a priority in value units.

## Protocol, metrics, analysis

Step 4's, otherwise unchanged: the 40-cell track, two sessions of 40 laps per seed (*increase*: east 1.0 then 4.0;
*decrease*: east 1.0 then 0.25; west 1.0), both pauses, fixed (20 backups) and thresholded (θ × scale, cap 100)
budgets, the event definition, seeds 1–30, BCa 95% intervals, paired comparisons, Cliff's δ ≥ 0.3, TOST ±20%; (a) on
the baseline block, (d) over the three distinct blocks, (b) per session with the control rows of change 3, (c) within
the baseline block and after each change, learning per session paired against none and prioritised_td,
`from_this_lap_share` beside every direction share. Conditions: none, uniform, reverse_trajectory, prioritised_td,
mattar_daw, mattar_daw_1step, all on the Q learner.

## Predictions, per rule (written before the run)

The primary test of the step is **(a) at the pre-run pauses for mattar_daw against mattar_daw_1step**: the extension
is the mechanism G29 C4 named, and the pair isolates it.

- **mattar_daw.** (a) pre-run pauses, baseline block: **forward share > 0.6, predicted to pass.** With the reward
  stable, gains are near their floor everywhere, EVB is ordered by need, the highest need from the start state is
  the start state's own transition, and its extension (need of the same start state, the next transition forward)
  ties with it and wins the tie, so the chain advances forward along the lap ahead for the budget. (a) reward
  pauses, baseline block: the same mechanism from the next lap's start makes **forward** sweeps of the lap ahead, so
  the reverse share is **predicted to fail** the 0.6 bound there, the opposite of the afterstate rule; after a reward
  change (`a_direction_after_change`) the error at the consume gives gain to the goal state and its predecessors in
  turn, and the reward-pause share is predicted reverse, with less confidence (the softmax at the goal's neighbours
  is near-deterministic and a magnitude change moves it little, G30 C3). (d) ≥ 10% remote, passes (need-ordered
  sweeps start at the far start state). (b) increase: up, less confident than step 4's for gain × need (the gain of a
  magnitude change is small once decisions are made); decrease: unsigned, a rise or no change, fails "down"; the
  east − west rows: the west end is no control for a need-weighted rule, not equivalent. (c) baseline: the rate does
  not fall (need grows with familiarity, G30), fails. Learning, fixed: at least as fast as prioritised_td (gain
  targets the decisions that matter); no prediction in thresholded mode.
- **mattar_daw_1step.** (a) pre-run: **forward share fails** (without the extension a backup of the start state's
  transition lowers its own EVB and the argmax moves to the next-highest need, the predecessor-side chaining of gain
  then runs backward, as for the afterstate rule); reward pauses: reverse at baseline predicted to pass, less
  confident (the one-step argmax over near-floor gains is need's order, which is forward). (d) passes. (b) and (c) as
  for mattar_daw. Learning: close to mattar_daw.
- **The floors on Q.** As on V in step 4: reverse_trajectory reverse at reward (1.00, `from_this_lap` 1.00), no
  forward pre-run, no remote, up at the increase on reverse events, a fall at the decrease that the east − west row
  turns into a rise (|Δr|); uniform and prioritised no sequence events, backups up at both changes, falling to zero
  within the baseline block under the scaled θ. Learning on Q: prioritised_td fastest of the floors; the absolute
  totals differ from the V learner's and are not compared with them.
- **Identical first laps** across the six conditions at every seed (Q = 0 and V = 0 give the same softmax), and
  identical baseline blocks across the two sessions: checks on the runner, verified by the tests.

## What would change this document

Only the "Pilot outcome" section below. If a rule cannot run as specified under the scaled θ (a cap that binds at
every pause after θ is set, or a priority that is zero everywhere), the deviation is recorded in G31 and that rule's
thresholded rows are reported as exploratory.

## Pilot outcome (2026-10-25, before the thresholded run; change 4's θ values)

`python3 -m experiments.linear_track_rq1 --pilot --workers 4` (6 s): fixed mode, the baseline block alone (20 laps),
seeds 1–3, every condition on the Q learner; for every rule the median over laps 11–20 (30 pauses) of its priority
read before the reward pause divided by the value scale read then (the mean of max_a Q over the occupied states).
These are the thresholded θ values of step 5 (`THRESHOLDS_STEP5`; the table is `docs/data/m2a/rq1_step5/rq1_pilot.csv`)
and are not changed after this:

| rule | θ (median of priority / scale) | min – max over the 30 pauses |
|---|---|---|
| uniform (mean \|TD error\| in memory) | 0.124286 | 0.0896 – 0.268 |
| reverse_trajectory (largest \|TD error\| over the remaining sweep) | 2.25714 | 1.44 – 4.08 |
| prioritised_td (largest \|TD error\| in memory) | 0.940048 | 0.556 – 1.46 |
| mattar_daw (largest EVB, extensions included) | 3.90938 × 10⁻⁵ | 1.55 × 10⁻⁵ – 1.13 × 10⁻⁴ |
| mattar_daw_1step (largest one-step EVB) | 1.04689 × 10⁻⁶ | 5.27 × 10⁻⁷ – 3.06 × 10⁻⁶ |

uniform's and reverse_trajectory's values are within a few per cent of step 4's on the V learner (0.131, 2.26);
prioritised_td's is lower (0.94 against 1.59). The extension's candidates raise the largest EVB about forty-fold over
the one-step rule's at the same pauses: an n-step target reaches further than a one-step one, so its error, and the
gain at the chain's start, is larger.
