# Preregistration: the RQ4(a) gate relative to the visible-goal ceiling, step 4 of M2b

**Written:** 2026-10-25, before the evaluation run (branch `m2b-gate` stacked on step 3's `m2b-sr` at `b9b9ead`; the
decisions entry that reports the result is G36). **Scope:** step 4 of the four in `docs/prereg/m2b_estimate.md`: the
SR's value read-out as a steering source, and the plan's RQ4(a) gate.

**The owner's decision (2026-10-25).** A probe (docs/m2b_place_code.md, "Before step 4") found the research agent
reaching a *visible* goal at (0.5 m, 0.5 m) within 60 s on 13 of 20 trials, so the plan's absolute bound (80% of
trials with a hidden goal) measures the motor policy first. Of three options set out there, the owner chose the
second: **the gate is the hidden-goal success rate after 20 trials as a share of the same agent's visible-goal success
rate from the same starts, at least 0.8, with both absolute rates reported.** The arrival-error bound (median < 0.2 m)
is kept as written. docs/research_plan.md's RQ4(a) and row 2b record the change.

**Disclosure.** The probe above; development checks that the tabular path is unchanged (the suite's hash tests) and
that the SR source runs at about 2,200 ticks/s; and a smoke of the experiment below at 8 trials and two seeds, whose
second-half numbers were seen: SR hidden 0.38 against visible 0.88 (ratio 0.43), tabular hidden 0 against 0.5, no
value steering 0.13 against 0.63, arrival error 0.20 units. Four test trials per seed mean little; the predictions
below were written after seeing them.

## What is implemented (off by default; every earlier hash and table unchanged)

- **The SR value source** (`value_memory.source = "sr"`, `core/engine.py`): with the place population on, the engine
  learns online, every tick, successor features over the normalised rates (step 3's learner: from the identity, TD(0),
  α 0.1, γ 0.95) and reward weights R by normalised least mean squares on the map reward received on arrival
  (R += 0.5 (r − φ·R) φ / |φ|²). The steering reads V(p) = φ(p)·(Mᵀ R) where it read the tabular map, at the estimate
  and at the same lookahead points, through the same relative signals. `"tabular"` (the default) reads the value map
  as before; `"none"` gives no value steering. Every value learner learns in every condition; only the read changes.
  An episode boundary (`Engine.reset_value_episode`) cuts every learner's transitions at a protocol's trial start.
- **The protocol** (`experiments/rq4a_gate.py`): below.

## Protocol

The research profile with step 1's M2b estimate and step 2's 400-cell population, the 2 m box, a goal of radius
1 unit (0.1 m) at (5, 5) units (0.5 m from two walls, the probe's), seeds 1–30. Four start poses, 1 unit from each
wall's midpoint, facing the centre; their order shuffled per block of four from a protocol stream, the same order in
every session and source of a seed. At each start the body is placed and the estimate re-anchored there (the agent
knows where it is put down: declared, like the plan's start-pose lists), with an episode boundary. 40 trials of up to
300 ticks (60 s). **Hidden session**: the goal is hidden (it rewards on contact but is not seen); after a 60 s miss it
becomes visible for up to 300 more ticks (guidance: the water maze's convention, for an agent that cannot be
carried). **Visible session**: the goal is visible from each trial's start; a miss ends the trial. Value sources:
`sr` (the gate's), `tabular` (the plan's ablation) and `none` (the control). A trial succeeds when the body is within
the goal's radius within 60 s without guidance. The seed is the unit; BCa 95% intervals (10,000 replicates); the
ratio's interval resamples seeds, keeping each seed's hidden and visible sessions together.

## Preregistered tests

1. **The gate** (`g1_relative_success`): for `sr`, the mean over seeds of the hidden session's success share over
   trials 21–40, divided by the mean over seeds of the visible session's, is at least 0.80 (the point estimate; the
   interval reported).
2. **Arrival error** (`g2_arrival_error`): for `sr`'s hidden successes on trials 21–40, the per-seed median estimate
   error at arrival, averaged over seeds, is below 2 units (0.2 m), the interval's upper end below 2.

Reported: every source's absolute success in both sessions; the ratio for `tabular` and `none`; the paired hidden
success of `sr` against `none` (whether the value helps at all) and against `tabular`; success by block of four.

## Predictions (written before the run)

- **The visible ceiling** is about two thirds (the probe's 13 of 20), perhaps higher with value learnt along the way.
- **g1 fails**, with low confidence: the SR's value spreads only along the paths the agent took to the goal (guided
  or found), and steering by a lookahead gradient from a wall start has to find those paths; a ratio between 0.3 and
  0.7. The smoke's 0.43 sits in that range.
- **g2 passes**: arrivals are within 0.2 m of the estimate (step 1's level, 0.07 m).
- **`sr` beats `none`** on hidden success (the value helps), and **`sr` beats `tabular`** (the tabular map spreads
  value only by TD along visited bins at γ 0.9, more slowly than the SR's predictive spread at γ 0.95).
- **`none`'s hidden success** is low, under 20%: a wall-hugging agent rarely passes 0.1 m from a point 0.5 m from
  two walls by chance.

## What would change this document

Nothing after the run. A deviation is recorded in G36.
