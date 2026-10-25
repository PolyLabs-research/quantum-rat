# Preregistration: the RQ4(a) gate, confirmatory, with the per-feature reward rule (M2b step 4b)

**Written:** 2026-10-25, after the preregistered gate (`docs/prereg/m2b_gate.md`) failed for the SR source and an
exploratory run showed why, and before this run (branch `m2b-gate` at the commit that adds this document; the
decisions entry is G36). **Scope:** one change to the SR value source, tested on fresh seeds with the gate, tests,
bounds and protocol of `docs/prereg/m2b_gate.md` unchanged.

## What happened before this document

- **The preregistered gate failed for the SR source** (seeds 1–30, committed in `docs/data/m2b/gate/`): hidden success
  13% against visible 46% over trials 21–40, a ratio of 0.29 against the bound 0.8. The tabular ablation's ratio was
  1.03 (hidden 84%); no value steering, 0.09.
- **The cause, diagnosed at seed 1.** The SR source learned its reward weights R by normalised least mean squares, a
  regression of the point reward on overlapping place fields. The many unrewarded ticks near the goal are fitted with
  negative weights, so R rings the goal (2.2 at the goal, −1.0 beside it). The value V = φ·(Mᵀ R) then has a trough
  around the goal (−0.37), and near the goal its gradient points away from it. The SR's hidden success began at 0.53
  and fell to about 0.12 as the ring formed.
- **An exploratory run** (seeds 1–30, SR source only, `docs/data/m2b/gate/exploratory_per_feature_reward/`, not a
  preregistered result) replaced the rule with a per-feature one: each weight moves toward the reward seen while its
  cell is active, R += 0.5 φ (r − R), which cannot go negative when rewards do not. Hidden success was 99.5% and
  visible 100% over trials 21–40, a ratio of 0.995, arrival error 0.21 units.

## What this run tests

The gate of `docs/prereg/m2b_gate.md`, unchanged in every respect but two: **the SR source's reward rule is
`per_feature`** (`PlaceConfig.reward_rule`, rate 0.5), and **the seeds are 31–60**, none of which has been run. All
three sources run (`tabular` and `none` are untouched by the rule and replicate the first run on new seeds).
Command: `python3 -m experiments.rq4a_gate --workers 4 --seed-start 31 --reward-rule per_feature --prereg
docs/prereg/m2b_gate_confirmatory.md --out docs/data/m2b/gate_confirmatory`.

1. **The gate** (`g1_relative_success`): for `sr`, mean hidden success over trials 21–40 ÷ mean visible success, at
   least 0.80.
2. **Arrival error** (`g2_arrival_error`): for `sr`'s hidden successes on trials 21–40, the mean of per-seed median
   estimate errors at arrival below 2 units, the interval's upper end below 2.

## Predictions (written before the run)

- **g1 passes** with a ratio above 0.95; hidden and visible success above 95% for `sr` (the exploratory run's values).
- **g2 passes**, about 0.2 units.
- `tabular` and `none` replicate the first run: tabular ratio near 1 with hidden success 75–90%; `none`'s hidden
  success under 10%.

## What would change this document

Nothing after the run. If the gate fails here, the SR source fails RQ4(a) and that is the reading.
