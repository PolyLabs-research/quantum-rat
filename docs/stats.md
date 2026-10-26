# Statistics for claims over seeds (`analysis/stats.py`)

Every behavioural number in the plan is a sample over seeds and carries n, an interval and the seed set
(docs/research_plan.md §2 item 4, §4, §5 item 10). `analysis/stats.py` is the one place those intervals
come from. Pure functions: numpy arrays in, Python floats and dicts out. Each resampling function takes a
`seed` and builds its own `numpy.random.Generator(PCG64(seed))`, nothing is kept between calls, and no
BLAS product is involved, so a call gives the same interval on any machine. scipy is not imported; the
normal quantile is Wichura's AS 241, within 1.3e-15 of `scipy.special.ndtri` on 10,000 probabilities.

## Which function for which claim

| Claim | Function | What comes back |
|---|---|---|
| "the rate is X (95% CI a to b)" over seeds | `bootstrap_ci(x, statistic=np.mean)` | `CI`: `estimate, low, high` (unpacks as a triple), plus `method`, `n`, `n_boot`, `note`. BCa by default (Efron & Tibshirani 1993 ch. 14: bias correction from the bootstrap distribution, acceleration from the jackknife); `method="percentile"` is the plain alternative |
| "rule B beats rule A on the same seeds" | `paired_effect(a, b)` | mean of b - a with its BCa CI, the fraction of seeds with b > a, `mean_a`, `mean_b`. Pairing by seed removes the between-seed variance an unpaired comparison carries |
| "B tends to exceed A" as an ordering (M2a: δ ≥ 0.3 with a 95% BCa CI excluding 0) | `cliffs_delta(a, b)` | δ = P(b > a) - P(b < a) over all pairs, its label (negligible < 0.147, small < 0.33, medium < 0.474, large; Romano et al. 2006) and CI from independent resampling of the two samples |
| "how often does B beat A" | `probability_of_improvement(a, b)` | P(b > a) + P(b = a)/2 with its CI; equals (1 + δ)/2 (Agarwal et al. 2021) |
| an aggregate one outlier seed cannot move | `iqm(x)`, `iqm_ci(x)` | the mean of the middle half of the sorted values (floor(n/4) dropped from each end), with its CI (Agarwal et al. 2021) |
| "no effect": the forward rate is unchanged within ±20% (M2a) | `tost(a, b, -0.2, 0.2, relative=True)` | the (1 - 2α) CI of mean(b) - mean(a), the bounds in data units, and `equivalent`; `paired=True` uses the per-seed differences |
| any claim over several seeds | `pseudo_replication_guard(runs)` first | the number of distinct outcomes, or `PseudoReplicationError` naming the seeds that produced identical ones (`allow=True` returns the message instead) |
| the one table a runner writes | `tidy_table(rows)`, `summarise(df, by)` | the long table (condition, task, seed, metric, value), sorted; one row per group with n, mean, low, high, iqm, ci_method |

Every result carries a `note`; it is empty when the interval is exactly what was asked for. A non-empty
note means the input was degenerate (one value, or all values equal: nothing is resampled and the estimate
is both ends), or BCa fell back to the percentile levels (one-value sample, or every replicate on one side
of the estimate). Print the note with the number.

## TOST, read from a confidence interval

Two one-sided tests at level α (Schuirmann 1987) both reject, and equivalence is concluded, exactly when
the (1 - 2α) confidence interval of the difference lies inside the equivalence bounds. `tost` therefore
builds that bootstrap interval (90% at α = 0.05) and compares its ends with the bounds; `ci_level` and the
bounds in data units are returned so the decision can be checked by eye. "Not equivalent" means the data
do not show equivalence at this n; it is not evidence of a difference.

## The guard before any multi-seed claim

`tools/probes/seed_pseudoreplication` measured the failure the guard exists for: at sensor noise 0 the
legacy engine gives bit-identical trajectories at every seed, so "seeds 1 to 8" is one sample. Pass the
per-seed outcomes (numbers, dicts, sequences or trace digests; `key=` picks a field) through
`pseudo_replication_guard` before `bootstrap_ci`, `paired_effect` or `summarise`. Outcomes are compared
exactly after canonicalisation: dict key order and array-versus-list do not matter, NaN equals NaN.

## How many seeds

The plan uses 30 seeds per condition (§4). Measured with this module at n_boot = 1000. The coverage rows
are 200 replications at each of five sampling seeds (0 to 4; the range is across seeds); the effect rows
are 100 replications from one sampling stream, with the BCa 95% CI of each replication:

| Setting | n = 8 | n = 30 |
|---|---|---|
| 95% BCa CI on a normal mean: fraction covering the truth | 0.865 to 0.905 | 0.915 to 0.935 |
| 95% BCa CI on a lognormal(0, 1) mean: fraction covering the truth | 0.75 to 0.83 | 0.85 to 0.91 |
| Cliff's δ, two normal conditions 0.8 SD apart (true δ ≈ 0.43, "medium"): mean CI width; CI excludes 0 | 1.05; 15 of 100 | 0.52; 80 of 100 |
| Paired effect, true difference 0.5 at SD 1: mean CI width; CI excludes 0 | 1.24; 36 of 100 | 0.69; 83 of 100 |

So 8 seeds give a nominal 95% interval that misses the truth 17 to 25 times in 100 on a skewed metric, an
interval on δ that spans half of its whole range and finds a medium effect 15 times in 100, and a paired
interval nearly as wide as two true effects. Arithmetic, not simulation: 8 seeds all in one direction give a
two-sided sign-test p of 2 × (1/2)^8 = 0.0078, and 7 of 8 give 0.070, so one contrary seed takes a
unanimous "b > a" from significant to not. Thirty seeds bring the normal-mean coverage to 0.915 to 0.935
and find the medium δ 80 times in 100. Heavy skew still under-covers at 30 (0.85 to 0.91 for lognormal(0, 1)):
for a heavy-tailed metric report the IQM, or transform before the interval, and say which.

Tests: `tests/analysis/test_stats.py` (27 tests, about 1.5 s): known values, coverage at n = 30 over 200
replications (normal: BCa 0.93, percentile 0.92; lognormal(0, 0.5): BCa 0.935, percentile 0.905), the
n = 8 under-coverage above, determinism, TOST, the guard, tidy tables, degenerate inputs.
