"""analysis/stats.py: known values, bootstrap coverage, determinism, TOST, the guard, tidy tables.

Each test is named for what it proves. Resampling tests use a small n_boot
where the assertion allows; the coverage tests (200 replications each,
n_boot = 1000 or 2000) are the slow part, under a second together. Every
number quoted in a comment was measured with the seeds in this file.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from analysis.stats import (
    CI,
    TIDY_COLUMNS,
    PseudoReplicationError,
    bootstrap_ci,
    cliffs_delta,
    cliffs_magnitude,
    iqm,
    iqm_ci,
    paired_effect,
    probability_of_improvement,
    pseudo_replication_guard,
    summarise,
    tidy_table,
    tost,
)

# --- known values -----------------------------------------------------------


def test_cliffs_delta_is_plus_one_when_every_b_exceeds_every_a_and_minus_one_reversed() -> None:
    up = cliffs_delta([1.0, 2.0, 3.0], [4.0, 5.0, 6.0], n_boot=200)
    down = cliffs_delta([4.0, 5.0, 6.0], [1.0, 2.0, 3.0], n_boot=200)
    assert up["delta"] == 1.0 and up["magnitude"] == "large"
    assert down["delta"] == -1.0 and down["magnitude"] == "large"
    # Every resample of two separated samples is still separated, so the
    # interval collapses to the estimate and the result says so.
    assert (up["low"], up["high"]) == (1.0, 1.0)
    assert "replicates equal" in up["note"]


def test_cliffs_delta_is_zero_for_identical_samples_and_labels_follow_the_thresholds() -> None:
    assert cliffs_delta([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], ci=False)["delta"] == 0.0
    assert cliffs_delta([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], ci=False)["low"] is None
    assert cliffs_magnitude(0.0) == "negligible"
    assert cliffs_magnitude(0.146) == "negligible"
    assert cliffs_magnitude(0.147) == "small"
    assert cliffs_magnitude(0.33) == "medium"
    assert cliffs_magnitude(0.474) == "large"
    assert cliffs_magnitude(-0.5) == "large"


def test_iqm_of_one_to_eight_is_the_mean_of_three_to_six() -> None:
    assert iqm(np.arange(1, 9)) == 4.5
    assert iqm([1.0, 2.0, 3.0]) == 2.0  # nothing trimmed below n = 4
    assert iqm([5.0]) == 5.0
    matrix = np.array([[8, 1, 7, 2, 6, 3, 5, 4], [1, 1, 1, 1, 1, 1, 1, 100]], dtype=float)
    np.testing.assert_array_equal(iqm(matrix, axis=-1), np.array([4.5, 1.0]))


def test_probability_of_improvement_is_one_for_disjoint_samples_and_half_for_identical_ones() -> None:
    assert probability_of_improvement([1.0, 2.0, 3.0], [4.0, 5.0, 6.0], n_boot=200)["poi"] == 1.0
    assert probability_of_improvement([1.0, 2.0], [1.0, 2.0], ci=False)["poi"] == 0.5
    rng = np.random.default_rng(3)
    a, b = rng.normal(0, 1, 12), rng.normal(0.5, 1, 15)
    poi = probability_of_improvement(a, b, ci=False)["poi"]
    delta = cliffs_delta(a, b, ci=False)["delta"]
    assert poi == pytest.approx((1.0 + delta) / 2.0)


def test_paired_fraction_is_one_when_b_is_a_plus_one() -> None:
    a = np.array([1.0, 2.0, 3.0, 4.0])
    effect = paired_effect(a, a + 1.0, n_boot=200)
    assert effect["fraction_b_gt_a"] == 1.0
    assert effect["fraction_ties"] == 0.0
    assert effect["mean_diff"] == 1.0
    assert effect["mean_a"] == 2.5 and effect["mean_b"] == 3.5
    # All four differences equal 1, so there is nothing to resample.
    assert (effect["low"], effect["high"], effect["n_boot"]) == (1.0, 1.0, 0)
    assert effect["note"].startswith("degenerate")


def test_paired_effect_interval_brackets_the_mean_difference() -> None:
    rng = np.random.default_rng(11)
    a = rng.normal(0, 1, 30)
    b = a + rng.normal(0.4, 0.5, 30)
    effect = paired_effect(a, b, n_boot=500, seed=1)
    assert effect["low"] < effect["mean_diff"] < effect["high"]
    assert effect["fraction_b_gt_a"] == float(np.mean(b > a))
    assert effect["method"] == "bca" and effect["n"] == 30


# --- bootstrap coverage -----------------------------------------------------


def _coverage(draw, true_mean: float, method: str, reps: int = 200, n: int = 30, n_boot: int = 2000, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    hits = 0
    for r in range(reps):
        ci = bootstrap_ci(draw(rng, n), np.mean, n_boot=n_boot, method=method, seed=r)
        hits += ci.low <= true_mean <= ci.high
    return hits / reps


def _normal(rng: np.random.Generator, n: int) -> np.ndarray:
    return rng.normal(0.0, 1.0, n)


def _lognormal_half(rng: np.random.Generator, n: int) -> np.ndarray:
    return rng.lognormal(0.0, 0.5, n)


def test_bca_interval_covers_the_mean_of_normal_samples_between_90_and_99_percent() -> None:
    # Observed 0.93 at this seed (0.92-0.935 over seeds 0-4).
    assert 0.90 <= _coverage(_normal, 0.0, "bca") <= 0.99


def test_percentile_interval_covers_the_mean_of_normal_samples_between_90_and_99_percent() -> None:
    # Observed 0.92 at this seed (0.91-0.93 over seeds 0-4).
    assert 0.90 <= _coverage(_normal, 0.0, "percentile") <= 0.99


def test_bca_interval_covers_the_mean_of_skewed_samples_at_least_90_percent() -> None:
    # Lognormal(0, 0.5), true mean exp(0.125). Observed BCa 0.935 and percentile
    # 0.905 at this seed; over seeds 0-4 BCa 0.895-0.945 and percentile
    # 0.90-0.925, BCa above percentile in 4 of the 5 (the ordering is within
    # the 0.02 binomial noise of 200 replications, so only the floor is
    # asserted). At the heavier skew lognormal(0, 1) both methods under-cover
    # at n = 30 (BCa 0.85-0.91, percentile 0.845-0.895 over seeds 0-4): the
    # known small-sample failure of bootstrap intervals on a heavy-tailed mean.
    true_mean = math.exp(0.5 ** 2 / 2.0)
    bca = _coverage(_lognormal_half, true_mean, "bca")
    percentile = _coverage(_lognormal_half, true_mean, "percentile")
    assert bca >= 0.90
    assert 0.85 <= percentile <= 0.99


def test_eight_seeds_under_cover_a_skewed_mean_and_thirty_do_better() -> None:
    # The docs/stats.md rule of thumb. Lognormal(0, 1), n_boot = 1000, seed 0:
    # observed 0.75 at n = 8 and 0.865 at n = 30 (0.75-0.83 and 0.85-0.91 over
    # seeds 0-4). Neither reaches the nominal 0.95; eight is far from it.
    true_mean = math.exp(0.5)

    def lognormal(rng: np.random.Generator, n: int) -> np.ndarray:
        return rng.lognormal(0.0, 1.0, n)

    eight = _coverage(lognormal, true_mean, "bca", n=8, n_boot=1000)
    thirty = _coverage(lognormal, true_mean, "bca", n=30, n_boot=1000)
    assert eight < 0.85
    assert thirty > eight


def test_bca_interval_is_shifted_toward_the_long_tail_of_a_skewed_sample() -> None:
    rng = np.random.default_rng(1)
    x = rng.lognormal(0.0, 1.0, 30)
    bca = bootstrap_ci(x, np.mean, n_boot=2000, method="bca", seed=0)
    pct = bootstrap_ci(x, np.mean, n_boot=2000, method="percentile", seed=0)
    assert bca.estimate == pct.estimate == float(x.mean())
    # Same replicates, different levels: BCa pushes both ends up the right tail.
    assert bca.low > pct.low and bca.high > pct.high


# --- determinism ------------------------------------------------------------


def test_same_seed_gives_the_same_interval_and_different_seeds_differ() -> None:
    rng = np.random.default_rng(5)
    x = rng.normal(0, 1, 25)
    first = bootstrap_ci(x, np.mean, n_boot=300, seed=7)
    second = bootstrap_ci(x, np.mean, n_boot=300, seed=7)
    assert first == second
    assert tuple(first) == (first.estimate, first.low, first.high)
    other = bootstrap_ci(x, np.mean, n_boot=300, seed=8)
    assert other.estimate == first.estimate
    assert (other.low, other.high) != (first.low, first.high)


def test_two_sample_functions_are_seed_deterministic() -> None:
    rng = np.random.default_rng(6)
    a, b = rng.normal(0, 1, 20), rng.normal(0.3, 1, 22)
    assert cliffs_delta(a, b, n_boot=300, seed=2) == cliffs_delta(a, b, n_boot=300, seed=2)
    assert probability_of_improvement(a, b, n_boot=300, seed=2) == probability_of_improvement(a, b, n_boot=300, seed=2)
    assert tost(a, b, -1, 1, n_boot=300, seed=2) == tost(a, b, -1, 1, n_boot=300, seed=2)
    assert cliffs_delta(a, b, n_boot=300, seed=2)["low"] != cliffs_delta(a, b, n_boot=300, seed=3)["low"]


def test_resampling_does_not_touch_the_global_numpy_rng() -> None:
    np.random.seed(0)
    before = np.random.random(3)
    np.random.seed(0)
    np.random.random(3)
    bootstrap_ci(np.arange(10.0), np.mean, n_boot=100, seed=1)
    cliffs_delta(np.arange(5.0), np.arange(5.0) + 0.5, n_boot=100, seed=1)
    after = np.random.random(3)
    np.random.seed(0)
    np.random.random(3)
    np.testing.assert_array_equal(after, np.random.random(3))
    assert before.shape == (3,)


def test_a_statistic_without_an_axis_keyword_gives_the_same_interval_as_its_vectorised_form() -> None:
    rng = np.random.default_rng(9)
    x = rng.normal(0, 1, 15)
    looped = bootstrap_ci(x, lambda v: float(np.median(v)) ** 2, n_boot=200, seed=4)
    vectorised = bootstrap_ci(x, lambda v, axis=-1: np.median(v, axis=axis) ** 2, n_boot=200, seed=4)
    assert looped == vectorised


# --- TOST -------------------------------------------------------------------


def _two_conditions(shift: float, scale: float = 1.0, n: int = 40, seed: int = 21):
    rng = np.random.default_rng(seed)
    a = rng.normal(10.0, scale, n)
    b = rng.normal(10.0 + shift, scale, n)
    return a, b


def test_tost_concludes_equivalence_when_the_difference_is_clearly_inside_the_bounds() -> None:
    a, b = _two_conditions(0.0)
    result = tost(a, b, -1.0, 1.0, n_boot=500, seed=0)
    assert result["equivalent"] is True
    assert result["bound_low"] == -1.0 and result["bound_high"] == 1.0
    assert result["ci_level"] == pytest.approx(0.90)
    assert -1.0 <= result["ci_low"] <= result["estimate"] <= result["ci_high"] <= 1.0


def test_tost_refuses_equivalence_when_the_difference_is_clearly_outside_the_bounds() -> None:
    a, b = _two_conditions(3.0)
    result = tost(a, b, -1.0, 1.0, n_boot=500, seed=0)
    assert result["equivalent"] is False
    assert result["ci_low"] > 1.0  # the whole interval sits beyond the upper bound


def test_tost_relative_bounds_are_fractions_of_mean_a() -> None:
    a, b = _two_conditions(0.1)
    wide = tost(a, b, -0.2, 0.2, relative=True, n_boot=500, seed=0)
    assert wide["bound_low"] == pytest.approx(-0.2 * a.mean())
    assert wide["bound_high"] == pytest.approx(0.2 * a.mean())
    assert wide["equivalent"] is True
    narrow = tost(a, b, -0.005, 0.005, relative=True, n_boot=500, seed=0)
    assert narrow["equivalent"] is False  # +/-0.05 around 10 is narrower than the interval
    with pytest.raises(ValueError):
        tost([0.0, 0.0, 0.0], [1.0, 2.0, 3.0], -0.2, 0.2, relative=True, n_boot=50)


def test_tost_paired_uses_the_one_minus_two_alpha_interval_of_the_differences() -> None:
    rng = np.random.default_rng(22)
    a = rng.normal(10.0, 1.0, 30)
    b = a + rng.normal(0.0, 0.1, 30)
    result = tost(a, b, -0.5, 0.5, paired=True, n_boot=500, seed=3)
    assert result["equivalent"] is True and result["paired"] is True
    # Two one-sided tests at alpha equal the (1 - 2 alpha) interval of the
    # mean difference: the same call bootstrap_ci makes, replicate for replicate.
    direct = bootstrap_ci(b - a, np.mean, n_boot=500, alpha=0.10, seed=3)
    assert (result["estimate"], result["ci_low"], result["ci_high"]) == tuple(direct)
    unpaired = tost(a, b, -0.5, 0.5, paired=False, n_boot=500, seed=3)
    assert unpaired["ci_high"] - unpaired["ci_low"] > result["ci_high"] - result["ci_low"]
    with pytest.raises(ValueError):
        tost(a, b[:-1], -0.5, 0.5, paired=True, n_boot=50)


# --- the pseudo-replication guard ------------------------------------------


def test_identical_runs_raise_and_the_error_is_a_value_error() -> None:
    with pytest.raises(PseudoReplicationError, match="run 0 = run 1"):
        pseudo_replication_guard([1.0, 1.0, 2.0])
    with pytest.raises(ValueError):
        pseudo_replication_guard([[1, 2], [1, 2]])


def test_distinct_runs_pass_and_return_their_count() -> None:
    assert pseudo_replication_guard([1.0, 2.0, 3.0]) == 3
    assert pseudo_replication_guard([{"score": 1}, {"score": 2}], key="score") == 2
    assert pseudo_replication_guard(["a1b2", "c3d4", "e5f6"]) == 3
    assert pseudo_replication_guard([np.array([1.0, 2.0]), np.array([1.0, 2.5])]) == 2
    assert pseudo_replication_guard([]) == 0


def test_allow_flag_returns_the_warning_as_a_string_and_names_the_seeds() -> None:
    runs = [{"seed": 1, "digest": "abc"}, {"seed": 2, "digest": "abc"}, {"seed": 3, "digest": "xyz"}]
    message = pseudo_replication_guard(runs, key="digest", allow=True)
    assert isinstance(message, str)
    assert "pseudo-replication" in message and "seed 1 = seed 2" in message
    with pytest.raises(PseudoReplicationError, match="seed 1 = seed 2"):
        pseudo_replication_guard(runs, key=lambda r: r["digest"])


def test_guard_compares_outcomes_by_value_not_by_type_or_key_order() -> None:
    with pytest.raises(PseudoReplicationError):
        pseudo_replication_guard([{"a": 1, "b": 2.0}, {"b": 2, "a": 1.0}])
    with pytest.raises(PseudoReplicationError):
        pseudo_replication_guard([np.array([1.0, 2.0]), [1, 2]])
    with pytest.raises(PseudoReplicationError):
        pseudo_replication_guard([float("nan"), float("nan")])
    with pytest.raises(TypeError):
        pseudo_replication_guard([object(), object()])


# --- tidy tables ------------------------------------------------------------


def _wide_rows():
    rows = []
    for condition in ("gain_need", "random"):
        for seed in (1, 2, 3):
            offset = 1.0 if condition == "gain_need" else 0.0
            rows.append({"rule": condition, "task": "track", "seed": seed, "reverse_rate": offset + seed, "forward_rate": 2.0 * seed})
    return rows


def test_tidy_table_melts_wide_rows_and_round_trips_through_long_rows() -> None:
    df = tidy_table(_wide_rows())
    assert list(df.columns) == list(TIDY_COLUMNS)
    assert len(df) == 12
    assert df["seed"].dtype == np.int64 and df["value"].dtype == np.float64
    assert df.iloc[0].tolist() == ["gain_need", "track", 1, "forward_rate", 2.0]
    again = tidy_table(reversed(df.to_dict("records")))
    pd.testing.assert_frame_equal(again, df)
    with pytest.raises(ValueError):
        tidy_table([{"condition": "x", "task": "t", "seed": 1, "metric": "m", "value": 1.0, "extra": 2}])
    with pytest.raises(ValueError):
        tidy_table([{"task": "t", "seed": 1, "m": 1.0}])


def test_summarise_gives_one_row_per_group_with_n_mean_interval_and_iqm() -> None:
    df = tidy_table(_wide_rows())
    table = summarise(df, ["condition", "task"], n_boot=300, seed=0)
    assert list(table.columns) == ["condition", "task", "metric", "n", "mean", "low", "high", "iqm", "ci_method"]
    assert len(table) == 4
    row = table[(table["condition"] == "gain_need") & (table["metric"] == "reverse_rate")].iloc[0]
    assert row["n"] == 3 and row["mean"] == 3.0 and row["iqm"] == 3.0
    assert row["low"] <= row["mean"] <= row["high"] and row["ci_method"] == "bca"
    pd.testing.assert_frame_equal(table, summarise(df, ["condition", "task"], n_boot=300, seed=0))
    plain = summarise(df, "condition", ci=None)
    assert plain["low"].isna().all() and (plain["ci_method"] == "none").all()
    assert list(plain.columns[:2]) == ["condition", "metric"]


# --- degenerate inputs ------------------------------------------------------


def test_one_value_and_constant_data_give_the_estimate_as_both_ends_without_resampling() -> None:
    single = bootstrap_ci([3.0])
    assert tuple(single) == (3.0, 3.0, 3.0)
    assert single.n_boot == 0 and single.method == "none" and "fewer than two" in single.note
    constant = bootstrap_ci([2.0, 2.0, 2.0], method="percentile")
    assert tuple(constant) == (2.0, 2.0, 2.0) and "all values equal" in constant.note
    assert isinstance(single, CI) and single.as_dict()["note"] == single.note
    assert tuple(iqm_ci([4.0, 4.0])) == (4.0, 4.0, 4.0)


def test_two_sample_and_table_functions_survive_degenerate_inputs() -> None:
    one_vs_many = cliffs_delta([1.0], [0.5, 2.0, 3.0], n_boot=100)
    assert one_vs_many["delta"] == pytest.approx(1.0 / 3.0)
    assert one_vs_many["method"] == "percentile" and "jackknife" in one_vs_many["note"]
    flat = probability_of_improvement([1.0, 1.0], [1.0, 1.0], n_boot=100)
    assert flat["poi"] == 0.5 and (flat["low"], flat["high"]) == (0.5, 0.5) and flat["n_boot"] == 0
    assert paired_effect([1.0], [2.0], n_boot=100)["note"].startswith("degenerate")
    same = tost([1.0, 1.0], [1.0, 1.0], -1.0, 1.0, n_boot=100)
    assert same["equivalent"] is True and same["n_boot"] == 0
    assert tidy_table([]).shape == (0, 5)
    lonely = summarise(tidy_table([{"condition": "c", "task": "t", "seed": 1, "m": 2.0}]), "condition", n_boot=100)
    assert lonely.loc[0, ["n", "mean", "low", "high", "iqm"]].tolist() == [1, 2.0, 2.0, 2.0, 2.0]
    with pytest.raises(ValueError):
        bootstrap_ci([1.0, float("nan")])
    with pytest.raises(ValueError):
        bootstrap_ci([1.0, 2.0], method="basic")
