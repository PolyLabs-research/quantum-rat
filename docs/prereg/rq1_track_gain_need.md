# Preregistration: gain × need on the tabular linear track, step 3 of the M2a remainder

**Written:** 2026-10-25, before any run of the rules below (branch `m2a-gain-need` from the merge `aaaf133`; the
decisions entry that reports the result is G29). **Scope:** the plan's reference rule, gain × need (Mattar & Daw
2018), and its two ablations, gain-only and need-only, on the protocol of `docs/prereg/rq1_track_tabular.md` (four
reward blocks, a pre-run pause beside the reward pause, fixed and thresholded budgets, the plan's event metrics),
beside the three floors and no replay. This is the rule the RQ1 bounds were written for. Three changes recorded in
G28 C are made here and stated first.

## Changes from step 2 (G28 C1–C3), stated before the run

1. **The trajectory rule's thresholded priority** is the largest |TD error| over the remaining part of its one-pass
   sweep (not the next transition's alone), so a sweep is not stopped by an error-free consume when error lies deeper
   in the lap. A constructor option; step 2's rule and its committed tables are unchanged.
2. **θ per rule.** Each rule's thresholded θ is the median of its own priority, read before the reward pause, over laps
   11–20 of block 1 at seeds 1–3 in a fixed-budget pilot (the quantity `reward_priority_before` the lap record now
   carries), so that every rule starts the thresholded run replaying at about half its baseline pauses. The values are
   written into this document's "Pilot outcome" before the thresholded run and never changed after it.
3. **Familiarity (c)** is read over blocks 1 and 3 together (the two blocks whose rewards did not change at their start
   from the preceding block's end, baseline and washout), as the per-seed slope of backups per stop against lap within
   each, and beside it the first lap in each block at which the rate reaches 0, if it does.

## The rules

All three share one machinery (`brain/systems/replay_gain_need.py`, `brain/systems/successor.py`):

- **Need** is a tabular successor representation M over the 160 states, learned online by TD from the agent's own
  transitions (α = 0.2, γ = 0.95, the task's; M starts at the identity; the SR is learned in every condition, since
  it reads nothing back into V or the policy, and is used only by the three rules here): need(s) = M(s₀, s), the
  expected discounted future occupancy of s from s₀, the state the agent will act from next (the start state of the
  next lap, at both pauses: at the reward pause the agent stands on a terminal state and its next decision is from the
  turned-around start).
- **Gain** of backing up a stored transition e = (s → s′, r) is the plan's "softmax place-to-neighbour policy" read on
  this track: the backup moves V(s) to V(s) + α δ; the decisions that read V(s) are those at s's predecessors p (the
  states with an action into s: FORWARD from the cell behind, TURN from the same cell facing away, and the state
  itself where FORWARD is blocked by a wall); at each p the policy is the softmax over FORWARD: prior + 10·V(s′_F) and
  TURN: 10·V(s′_T) as everywhere in this protocol; gain(e) = Σ_p Σ_a [π_new(a|p) − π_old(a|p)] V_new(s′_a), the
  expected value of acting at p under the new policy minus under the old, both evaluated with the updated values
  (Mattar & Daw's gain, with Q(p, a) = V(s′(p, a))). It is non-negative.
- **gain × need**: EVB(e) = need(s) · gain(e). **gain-only**: gain(e). **need-only**: need(s).
- **Selection**: at each backup, the transition with the largest priority among the distinct stored transitions (the
  track is deterministic, so a memory of 2,000 holds at most 320 distinct (s, s′, r, terminal) tuples; duplicates are
  one candidate), ties to the most recently stored, recomputed after every backup (Mattar & Daw's argmax). No draw is
  made: these three rules consume nothing from the `replay` stream. Fixed mode: 20 backups per pause; thresholded:
  while the largest priority exceeds the rule's θ, up to 100.

## Protocol, metrics, analysis

Exactly `docs/prereg/rq1_track_tabular.md`'s: 40-cell track, the agent and its parameters, four blocks of 20 laps (east
1.0 / 4.0 / 1.0 / 0.25, west 1.0), both pauses, the event definition (≥ 4 distinct cells over ≥ 6, direction against
the lap the replayed states belong to, remote > 10 cells from the agent), seeds 1–30, the seed the unit, BCa 95%
intervals, paired comparisons within seed, TOST at ±20%. Conditions: none, uniform, reverse_trajectory (priority
option of change 1), prioritised_td, gain_need, gain_only, need_only. The tests are the tabular prereg's (a)–(d) with
change 3; the thresholded θ per rule is change 2.

## Predictions, per rule (written before the run)

- **gain_need.** (a) Reward pauses: the consume's backup has the largest gain and its predecessor's the next, so the
  argmax walks the lap backward from the goal: reverse share > 0.6, **predicted to pass**. Pre-run pauses: with the
  goal's value learned, gains are small everywhere and need is largest along the upcoming lap, so the argmax follows
  need forward from the start state: forward share > 0.6, **predicted to pass**, with less confidence (the gain of a
  near-zero-error backup is near zero for every candidate and the order among them is decided by small numbers).
  (b) Up after the ×4 increase: passes. **After the ×0.25 decrease the plan's bound is "down"; in this variant the gain
  of a decrease is not derivable without running**: a decrease also moves the softmax at the goal's predecessors, and
  gain is the size of that move whatever its sign. This is the test, not a prediction; it is reported whichever way
  it falls, and the comparison with the floors' unsigned response (G28) is the point. (c) Gains shrink as V converges:
  rate falls within blocks 1 and 3, passes. (d) Need-weighting favours states on the lap ahead, many of them far
  from the agent: ≥ 10% remote, **predicted to pass**.
- **gain_only.** Reverse at reward pauses (passes (a) there), no forward pre-run bias (fails (a) pre-run), rate
  tracking |Δr| like the floors (the signed test fails), few remote starts (fails (d)).
- **need_only.** Content follows occupancy with no regard to error: direction at chance or forward at both pauses
  (fails (a) at reward pauses), rate not tracking the reward change (fails (b)), remote starts plentiful (passes (d)).
- **The floors** behave as in G28; the trajectory rule's new priority (change 1) is predicted to turn its thresholded
  rate from a step function into one that follows the lap's residual error, so (c) is now predicted to pass for it
  over blocks 1 and 3.
- **Learning speed** (total steps over the 80 laps, paired against none): gain_need and gain_only are predicted to be
  at least as fast as prioritised_td (they back up where the policy changes most); need_only slower than the sequence
  rules and faster than uniform.

## What would change this document

Only the "Pilot outcome" section below (the θ values of change 2). If a rule cannot run as specified (a cap that binds
at every pause after θ is set, or a priority that is zero everywhere), the deviation is recorded in G29 and that rule's
thresholded rows are reported as exploratory.

## Pre-run amendment (2026-10-25, before the pilot and the evaluation)

A smoke run on an 8-cell track showed the need term as written to be zero for every candidate at every reward pause:
the state the agent acts from next lies in the other goal row, and the successor representation as specified never
links the rows (the consume is terminal and the turn-around is a protocol placement, not an experienced transition),
so M(s₀, s) = 0 for every state of the lap just run and gain × need degenerates to ties. The definition is amended
before any evaluation run: the SR learns every state change the agent lives through, the steps within a lap, the
turn-around from the goal state to the next lap's start, and the return to the start end after a capped lap; the
consume, terminal for V, contributes no SR update (the goal state's successor is the next start). Need is then the
expected discounted occupancy over the cyclic lap structure, so the states of the lap just run carry a need of about
γ^(a lap) from the next start, nonzero, and the states of the lap ahead a larger one.

The same smoke run showed that learning alone leaves that need at exactly zero until the occupancy has propagated
round the cycle by TD, several laps into every block, during which the argmax is a tie and the rule replays the most
recently stored transition over and over. Mattar & Daw's agent has the environment's transition structure; the
tabular equivalent is taken here: the SR starts as the SR of the known cyclic lap structure under a uniform-random
policy (FORWARD and TURN one half each from every state; from a goal state the turn-around to the next start with
probability one; iterated to convergence with elementwise row sums, no matrix product), and TD then learns on
experience from there. Under a random walk the far lap is hundreds of steps away, so the prior need of the just-run
states is tiny but positive, which is what the argmax requires; experience then raises it as the agent's laps shorten.
Nothing else changes; the predictions stand.

## Pilot outcome (2026-10-25, before the thresholded run; change 2's θ values)

Fixed mode, block 1 only (20 laps), seeds 1–3, the trajectory rule with change 1's priority; for every rule the median
of its priority read before the reward pause over laps 11–20 (30 pauses). These are the thresholded θ values of
step 3 and are not changed after this:

| rule | θ (median late-baseline priority) | min – max over the 30 pauses |
|---|---|---|
| uniform (mean \|TD error\| in memory) | 0.0027462 | 0.00138 – 0.00413 |
| reverse_trajectory (largest \|TD error\| over the remaining sweep) | 0.137277 | 0.111 – 0.176 |
| prioritised_td (largest \|TD error\| in memory) | 0.155972 | 0.0765 – 0.465 |
| gain_need (largest EVB) | 1.59024 × 10⁻⁷ | 4.16 × 10⁻⁸ – 3.88 × 10⁻⁷ |
| gain_only (largest gain) | 0.000269043 | 0.0002 – 0.000483 |
| need_only (largest need) | 2.71085 | 1.97 – 4.03 |

Five orders of magnitude between rules: the point of change 2. One observation from the pilot, recorded because the
prediction for (a) rests on it: with the goal's value already backed up online by the time the pause comes, the
policy at the goal's neighbour is near-deterministic and the largest gain sits one transition back along the lap,
so the argmax begins its backward walk there rather than at the consume; the predicted direction is the same.
