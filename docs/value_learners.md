# Value learners: tabular TD(0) and linear TD(λ) over Gaussian place features (`brain/systems/value_learners.py`)

Milestone 1's value rule (docs/research_plan.md §4, M1): two learners of V(place), the expected discounted return,
behind one interface, proven on the 12-cell chain of `tools/probes/kernel_value_inflation.py`. Numbers are from
`tests/brain/test_value_learners.py` (lr 0.2, γ 0.9) and `docs/data/m1/value_learners_chain.csv`, which the test
rewrites with `QUANTUM_RAT_WRITE_VALUE_TABLE=1` and otherwise checks against the current code.

## The interface

`ValueFunction` (a `Protocol`): `value(x, y) -> float`; `update(x, y, reward, x_next, y_next, terminal) -> float`
(one TD backup for the transition, reward received on arrival, returns the TD error; `terminal`: the arrival place
bootstraps as 0 and the episode ends); `reset_episode()`; `parameters() -> dict` for the manifest, with
`learning_rate` and `discount`. `ValueMemory` (tabular TD(0) over 0.5-unit bins with the legacy kernel, dwell
extinction and the replay log) is not an instance yet: M2b adapts it, and until then the engine keeps calling it.

- `TabularTD0(bin_size=0.5, learning_rate, discount)`: `V(s) <- V(s) + lr * (r + γ V(s') - V(s))` over
  `(floor(x / bin), floor(y / bin))` cells, `V(terminal) = 0`: the same arithmetic in the same order as
  `ValueMemory` at `generalization_radius = 0` (kernel weight `falloff ** 0 = 1.0`); on the chain the two agree
  to 0.0 after 300 forward episodes (asserted at 1e-12).
- `GaussianPlaceFeatures(centres, width, normalise=True)`, or `.grid(x_min, x_max, y_min, y_max, spacing, width)`
  for centres at the bin centres of a rectangle: `φ_j = exp(-|p - c_j|² / (2 width²))`, divided by its sum when
  normalised, so the features are a partition of unity and `V = Σ w φ` is a convex combination of the weights,
  `min w ≤ V ≤ max w` at every position, between centres and outside the grid included. That is the bound the
  "V ≤ 1/(1 − γ)" acceptance rests on: V never reads above the largest weight, which the table reports (`max w`).
- `LinearTDLambda(features, learning_rate, discount, lam, traces="replacing"|"accumulating")`: `δ = r + γ V(s') −
  V(s)` (`r − V(s)` into a terminal), `e <- γλ e + φ(s)` (accumulating) or `e <- max(γλ e, φ(s))` elementwise
  (replacing), `w <- w + lr δ e`; traces start at zero in every episode (`reset_episode`, and a terminal
  transition). λ = 0 is TD(0) for both trace kinds, and with one-hot features it is `TabularTD0`.

## The chain protocol (`run_chain`)

12 cells along x at bin 0.5 (centres 0.25 … 5.75, y = 0.25), start at cell 0, one cell per transition, reward 1.0
on arriving at cell 11, which is terminal; each pass is one forward episode. d = 10 … 0 counts a cell's zero-reward
steps before the rewarded one, so the exact V is γ^d, [0.3487, 0.3874, …, 0.9, 1.0] for cells 0 … 10, and the goal
bootstraps as 0 (the probe's trailing 0). `run_chain(learner, passes, tol)` returns a `ChainResult`; a run converges
when the largest change in V over the 11 cells in one pass is below `tol` (1e-9 here), capped at 2000 passes.
Width is in cells (`chain_features(width_cells)`, width = cells × 0.5 units).

## Measured

| learner | width (cells) | λ | traces | passes | converged | max \|V − γ^d\| | max V | V read at goal | max w |
|---|---|---|---|---|---|---|---|---|---|
| tabular TD(0) | – | – | – | 185 | yes | 5.1e-9 | 1.000 | 0 | 1.000 |
| linear | 0.125 | 0 / 0.5 / 0.9 | both | 185 / 156 / 113 | yes | 5.1e-9 / 5.0e-9 / 4.1e-9 | 1.000 | 0.000 | 1.000 |
| linear | 0.25 | 0 / 0.5 / 0.9 | both | 185 / 156 / 113 | yes | 5.0e-9 / 5.0e-9 / 4.1e-9 | 1.000 | 0.0007 | 1.0004 |
| linear | 0.5 | 0 | both | 206 | yes | 7.1e-9 | 1.000 | 0.260 | 1.132 |
| linear | 0.5 | 0.5 | repl. / acc. | 182 / 176 | yes | 6.5e-9 / 8.6e-9 | 1.000 | 0.265 / 0.260 | 1.132 |
| linear | 0.5 | 0.9 | repl. / acc. | 171 / 186 | yes | 1.1e-8 / 1.1e-8 | 1.000 | 0.271 / 0.260 | 1.131 / 1.132 |
| linear | 1.0 | 0 | both | 2000 (cap) | no | 1.6e-3 | 0.9994 | 1.007 | 1.222 |
| linear | 1.0 | 0.9 | repl. / acc. | 2000 (cap) | no | 1.1e-3 / 2.9e-3 | 0.9994 / 0.9992 | 1.012 / 0.998 | 1.216 / 1.232 |
| linear | 2.0 | 0 | both | 2000 (cap) | no | 7.1e-3 | 0.9929 | 1.064 | 1.230 |
| linear | 2.0 | 0.9 | repl. / acc. | 2000 (cap) | no | 8.3e-3 / 7.5e-3 | 0.9917 / 0.9951 | 1.062 / 1.065 | 1.221 / 1.213 |

The tabular rule and every width ≤ 0.5 cell reach γ^d to within the convergence floor (about 5e-9, set by the
1e-9 per-pass tolerance), so the test asserts only "all at the floor" for the three narrow widths. Above the floor
the error falls strictly as the width shrinks (2.0 > 1.0 > 0.5 cells, both trace kinds, λ = 0 and 0.9); every width
is within 1e-2 after 2000 passes; V ≤ 1 and the weights ≤ 1.23 everywhere (far under 1/(1 − γ) = 10); V(d) is
monotone in d at every width. Passes to within 1e-2: tabular 87, linear at 0.5 cell 92 (λ = 0) and 38 (λ = 0.9).
The goal column is the features' interpolation (the terminal convention binds only the bootstrap target).

What the wide widths cost on this chain is conditioning, not representation: twelve features over eleven states
represent any value vector, and the batch TD(0) fixed point of the normal equations (solved once, outside the
suite) is γ^d to 4e-13 even at 2.0 cells. The iteration gets there slowly, through an alternating-weight mode the
overlapping features barely see: at 1.0 cell the error is 1.6e-3 after 2000 passes, 3.5e-5 after 20,000 and 1.2e-6
after 40,000; at 2.0 cells 7.1e-3, 1.9e-3 and 1.5e-3, still falling. The table's "bias" at 1.0 and 2.0 cells is
thus the error after a finite budget; M2b's 400 cells over a continuous arena add a representation bias, to measure.

**Normalisation.** Without it the learner still converges on the chain centres (on-policy linear TD converges
either way, Tsitsiklis & Van Roy 1997): 4.9e-4 after 2000 passes at 1.0 cell, V ≤ 1 and monotone; 1.5e-2 at 2.0
cells. The difference is between the centres, which the chain never reads: at 0.25 cell the two neighbouring
features sum to 0.27 halfway between cells 9 and 10, so unnormalised V reads 0.257 there against 0.9 and 1.0 at
the centres, a valley between every pair of cells, while the partition of unity reads 0.950 (at 0.5 cell both
overshoot there by up to 3.2%; from 1.0 cell both interpolate monotonically). It is on because M2b reads V at the
agent's continuous position, where the convex-combination bound is what rules out the valleys.

## The legacy kernel, M2b, and the numpy rule

`ValueMemory` at `generalization_radius = 1` on the same chain (record once, `consolidate(5000)`) converges to
V(goal) = max V = 10.0 = 1/(1 − γ): the kernel writes each cell's bootstrap target into its neighbours, so the goal
is pulled toward `r + γ V(goal)` through its own kernel (6.07 at radius 2, the probe); pinned as a legacy property
within 1e-2, not fixed, since the research profile runs at radius 0, where `ValueMemory` is `TabularTD0`. In M2b
the place population (§2 item 2) is the `GaussianPlaceFeatures` of a 2-D grid, `LinearTDLambda` over it the value
rule, `TabularTD0` over the 0.5-unit bins the ablation baseline and the SR read-out V = M·R the alternative; the
tick supplies `update(x, y, reward, x', y', terminal)` with `reset_episode` at trial boundaries, and replay (an
event object by then) re-applies `update` to stored transitions, as `ValueMemory.replay_backup` does today. The
module uses elementwise multiply, `exp` and `maximum` summed with `numpy.sum` (pairwise), no `dot` or other BLAS
product, float64, no RNG, and `core` before numpy so the thread pin is in force (docs/determinism.md); two runs
give identical floats (asserted). References: Sutton & Barto 2018 (TD(λ), eligibility traces, ch. 12); Tsitsiklis
& Van Roy 1997 (convergence of on-policy linear TD(λ)).
