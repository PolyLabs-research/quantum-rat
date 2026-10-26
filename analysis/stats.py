"""Statistics for claims made over seeds (docs/research_plan.md section 5 item 10; docs/stats.md).

Pure functions: numpy arrays or plain sequences in; Python floats, dicts and
one small frozen record (``CI``, which unpacks as ``estimate, low, high``) out.
Every function that resamples takes a ``seed`` and builds its own
``numpy.random.Generator(PCG64(seed))`` for that one call. Nothing here keeps
state between calls, nothing reads the global numpy RNG, and no BLAS product
is involved, so results are bit-identical across thread counts. Degenerate
inputs (fewer than two values, or all values equal) do not resample at all:
the point estimate is returned as both ends of the interval and the result's
``note`` says so.

The bootstrap follows Efron & Tibshirani, *An Introduction to the Bootstrap*
(1993), chapters 13 to 14: the percentile interval, and the bias-corrected and
accelerated (BCa) interval whose bias correction is read from the bootstrap
distribution and whose acceleration comes from the jackknife (their eq. 14.15).
Two-sample statistics (Cliff's delta, probability of improvement, the unpaired
mean difference) resample each sample independently and combine the two
jackknives in the normalised form their section 14.3 gives for several
samples. scipy is not imported: the normal quantile function is Wichura's
algorithm AS 241 (1988), compared against ``scipy.special.ndtri`` on 10,000
probabilities in (1e-12, 1 - 1e-12) when this module was written (largest
absolute difference 1.3e-15, relative 8.2e-16; the CDF through ``erfc`` is
within 2.2e-16 of ``scipy.special.ndtr`` on [-8, 8]). On a lognormal sample
of 30 the BCa and percentile intervals agreed with ``scipy.stats.bootstrap``
at 20,000 replicates to within 0.003 at each end (different resampling
streams, so not bit-identical).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, Hashable, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

__all__ = [
    "CI",
    "PseudoReplicationError",
    "TIDY_COLUMNS",
    "bootstrap_ci",
    "cliffs_delta",
    "cliffs_magnitude",
    "iqm",
    "iqm_ci",
    "paired_effect",
    "probability_of_improvement",
    "pseudo_replication_guard",
    "summarise",
    "tidy_table",
    "tost",
]

ArrayLike = Union[Sequence[float], np.ndarray]
Statistic = Callable[..., Any]

METHODS = ("bca", "percentile")

# Conventional |delta| thresholds for the magnitude label (Romano et al. 2006).
CLIFFS_DELTA_SMALL = 0.147
CLIFFS_DELTA_MEDIUM = 0.33
CLIFFS_DELTA_LARGE = 0.474


# --------------------------------------------------------------------------- helpers


def _generator(seed: int) -> np.random.Generator:
    """One PCG64 generator per call: the only source of randomness in this module."""
    return np.random.Generator(np.random.PCG64(int(seed)))


def _child_seed(seed: int, name: str) -> int:
    """A child seed from a base seed and a name, by the same idea as ``core.rng``: hash, do not add."""
    digest = hashlib.sha256(f"{int(seed)}:{name}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def _as_1d(x: ArrayLike, name: str = "x") -> np.ndarray:
    arr = np.atleast_1d(np.asarray(x, dtype=np.float64))
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains a non-finite value (NaN or inf)")
    return arr


def _check_method(method: str) -> str:
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}, got {method!r}")
    return method


def _check_alpha(alpha: float) -> float:
    alpha = float(alpha)
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must lie in (0, 1), got {alpha}")
    return alpha


def _check_n_boot(n_boot: int) -> int:
    n_boot = int(n_boot)
    if n_boot < 1:
        raise ValueError(f"n_boot must be at least 1, got {n_boot}")
    return n_boot


def _norm_cdf(z: float) -> float:
    """Standard normal CDF through erfc (accurate in both tails)."""
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def _norm_ppf(p: float) -> float:
    """Inverse of the standard normal CDF: Wichura (1988), algorithm AS 241, PPND16."""
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    q = p - 0.5
    if abs(q) <= 0.425:
        r = 0.180625 - q * q
        num = (((((((2.5090809287301226727e3 * r + 3.3430575583588128105e4) * r
                    + 6.7265770927008700853e4) * r + 4.5921953931549871457e4) * r
                  + 1.3731693765509461125e4) * r + 1.9715909503065514427e3) * r
                + 1.3314166789178437745e2) * r + 3.3871328727963666080e0)
        den = (((((((5.2264952788528545610e3 * r + 2.8729085735721942674e4) * r
                    + 3.9307895800092710610e4) * r + 2.1213794301586595867e4) * r
                  + 5.3941960214247511077e3) * r + 6.8718700749205790830e2) * r
                + 4.2313330701600911252e1) * r + 1.0)
        return q * num / den
    r = p if q < 0.0 else 1.0 - p
    r = math.sqrt(-math.log(r))
    if r <= 5.0:
        r -= 1.6
        num = (((((((7.74545014278341407640e-4 * r + 2.27238449892691845833e-2) * r
                    + 2.41780725177450611770e-1) * r + 1.27045825245236838258e0) * r
                  + 3.64784832476320460504e0) * r + 5.76949722146069140550e0) * r
                + 4.63033784615654529590e0) * r + 1.42343711074968357734e0)
        den = (((((((1.05075007164441684324e-9 * r + 5.47593808499534494600e-4) * r
                    + 1.51986665636164571966e-2) * r + 1.48103976427480074590e-1) * r
                  + 6.89767334985100004550e-1) * r + 1.67638483018380384940e0) * r
                + 2.05319162663775882187e0) * r + 1.0)
    else:
        r -= 5.0
        num = (((((((2.01033439929228813265e-7 * r + 2.71155556874348757815e-5) * r
                    + 1.24266094738807843860e-3) * r + 2.65321895265761230930e-2) * r
                  + 2.96560571828504891230e-1) * r + 1.78482653991729133580e0) * r
                + 5.46378491116411436990e0) * r + 6.65790464350110377720e0)
        den = (((((((2.04426310338993978564e-15 * r + 1.42151175831644588870e-7) * r
                    + 1.84631831751005468180e-5) * r + 7.86869131145613259100e-4) * r
                  + 1.48753612908506148525e-2) * r + 1.36929880922735805310e-1) * r
                + 5.99832206555887937690e-1) * r + 1.0)
    value = num / den
    return -value if q < 0.0 else value


# --------------------------------------------------------------------------- the CI record


@dataclass(frozen=True)
class CI:
    """A point estimate with its interval. Unpacks as ``estimate, low, high``.

    ``method`` is the method actually used ("bca", "percentile" or "none"),
    ``n_boot`` the number of replicates actually drawn (0 when nothing was
    resampled), and ``note`` is non-empty whenever the interval is not the
    requested method's at the requested level: a degenerate input, a fallback
    from BCa to percentile, or an acceleration set to zero.
    """

    estimate: float
    low: float
    high: float
    method: str
    n: int
    n_boot: int
    alpha: float
    note: str = ""

    def __iter__(self):
        return iter((self.estimate, self.low, self.high))

    @property
    def level(self) -> float:
        """The confidence level, 1 - alpha."""
        return 1.0 - self.alpha

    def as_dict(self) -> Dict[str, Any]:
        return {
            "estimate": self.estimate,
            "low": self.low,
            "high": self.high,
            "method": self.method,
            "n": self.n,
            "n_boot": self.n_boot,
            "alpha": self.alpha,
            "note": self.note,
        }


def _degenerate(estimate: float, n: int, alpha: float, note: str) -> CI:
    return CI(float(estimate), float(estimate), float(estimate), "none", int(n), 0, alpha, note)


# --------------------------------------------------------------------------- bootstrap engine


def _evaluate(statistic: Statistic, matrix: np.ndarray) -> np.ndarray:
    """``statistic`` over each row of a (k, n) matrix, as a (k,) float array.

    Tries the vectorised call ``statistic(matrix, axis=-1)`` first (numpy
    reductions and :func:`iqm` accept it); a statistic that rejects the
    keyword or returns the wrong shape is called once per row instead.
    """
    k = matrix.shape[0]
    try:
        out = np.asarray(statistic(matrix, axis=-1), dtype=np.float64)
        if out.shape == (k,):
            return out
    except TypeError:
        pass
    return np.array([float(statistic(row)) for row in matrix], dtype=np.float64)


def _leave_one_out(x: np.ndarray) -> np.ndarray:
    """The (n, n - 1) matrix whose row i is x without x[i], in the original order."""
    n = x.size
    mask = ~np.eye(n, dtype=bool)
    return np.broadcast_to(x, (n, n))[mask].reshape(n, n - 1)


def _bca_levels(
    theta_hat: float, theta_boot: np.ndarray, jackknives: Sequence[np.ndarray], alpha: float
) -> Tuple[float, float, str]:
    """The two quantile levels of the BCa interval (Efron & Tibshirani eq. 14.10).

    Bias correction z0 from the fraction of replicates below the estimate
    (ties count one half); acceleration from the jackknife values, summed
    over samples in the normalised form of their section 14.3. Returns a
    non-empty note instead of levels when the formula is undefined.
    """
    n_boot = theta_boot.size
    prop = ((theta_boot < theta_hat).sum() + (theta_boot <= theta_hat).sum()) / (2.0 * n_boot)
    if prop <= 0.0 or prop >= 1.0:
        return math.nan, math.nan, "BCa bias correction undefined (every replicate on one side of the estimate)"
    z0 = _norm_ppf(float(prop))
    num = 0.0
    den = 0.0
    for jk in jackknives:
        n = jk.size
        u = (n - 1) * (jk.mean() - jk)
        num += float((u ** 3).sum()) / n ** 3
        den += float((u ** 2).sum()) / n ** 2
    note = ""
    if den == 0.0:
        a_hat = 0.0
        note = "BCa acceleration set to 0 (jackknife values all equal)"
    else:
        a_hat = num / (6.0 * den ** 1.5)
    z_low = _norm_ppf(alpha / 2.0)
    z_high = -z_low
    levels = []
    for z in (z_low, z_high):
        d = 1.0 - a_hat * (z0 + z)
        if d <= 0.0:
            return math.nan, math.nan, "BCa undefined (acceleration too large for the level adjustment)"
        levels.append(_norm_cdf(z0 + (z0 + z) / d))
    return levels[0], levels[1], note


def _interval(
    estimate: float,
    theta_boot: np.ndarray,
    jackknives: Sequence[np.ndarray],
    alpha: float,
    method: str,
    n: int,
    note: str = "",
) -> CI:
    """Turn a bootstrap distribution into a CI by the requested method, with fallbacks."""
    n_boot = theta_boot.size
    if theta_boot.min() == theta_boot.max():
        return CI(float(estimate), float(estimate), float(estimate), "none", n, n_boot, alpha,
                  _join(note, "all bootstrap replicates equal; interval collapsed to the estimate"))
    used = method
    if method == "bca":
        lo, hi, bca_note = _bca_levels(estimate, theta_boot, jackknives, alpha)
        if math.isnan(lo):
            used = "percentile"
            note = _join(note, bca_note + "; percentile interval returned")
        else:
            note = _join(note, bca_note)
    if used == "percentile":
        lo, hi = alpha / 2.0, 1.0 - alpha / 2.0
    low, high = np.quantile(theta_boot, [lo, hi])
    return CI(float(estimate), float(low), float(high), used, n, n_boot, alpha, note)


def _join(*notes: str) -> str:
    return "; ".join(s for s in notes if s)


def bootstrap_ci(
    x: ArrayLike,
    statistic: Statistic = np.mean,
    n_boot: int = 10_000,
    alpha: float = 0.05,
    method: str = "bca",
    seed: int = 0,
) -> CI:
    """Bootstrap confidence interval of ``statistic(x)``; returns ``(estimate, low, high)`` as a :class:`CI`.

    ``method`` is "bca" (default: bias-corrected and accelerated, with the
    jackknife acceleration) or "percentile". ``statistic`` maps a 1-D array
    to a number; if it also accepts ``axis`` it is evaluated once on the
    (n_boot, n) resample matrix, otherwise once per replicate. Resampling
    draws ``n_boot * n`` indices from ``Generator(PCG64(seed))`` in one call,
    so the same seed gives the same interval. With fewer than two values, or
    all values equal, nothing is drawn: the estimate is returned as both ends
    and ``note`` says why. The BCa levels are also abandoned, for the
    percentile levels and a note, when the bias correction is undefined
    (every replicate on one side of the estimate).
    """
    x = _as_1d(x)
    method = _check_method(method)
    alpha = _check_alpha(alpha)
    n_boot = _check_n_boot(n_boot)
    estimate = float(statistic(x))
    n = int(x.size)
    if n < 2:
        return _degenerate(estimate, n, alpha, "degenerate: fewer than two values, nothing resampled")
    if bool(np.all(x == x[0])):
        return _degenerate(estimate, n, alpha, "degenerate: all values equal, nothing resampled")
    rng = _generator(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    theta_boot = _evaluate(statistic, x[idx])
    jackknives = [_evaluate(statistic, _leave_one_out(x))] if method == "bca" else []
    return _interval(estimate, theta_boot, jackknives, alpha, method, n)


TwoSampleStatistic = Callable[[np.ndarray, np.ndarray], np.ndarray]


def _bootstrap_two_sample(
    a: np.ndarray,
    b: np.ndarray,
    statistic: TwoSampleStatistic,
    n_boot: int,
    alpha: float,
    method: str,
    seed: int,
) -> CI:
    """Independent two-sample bootstrap of ``statistic(A, B)`` over (k, n_a) and (k, n_b) matrices.

    ``a``'s indices are drawn first, then ``b``'s, from one generator. The
    BCa acceleration combines the two leave-one-out jackknives; when either
    sample has fewer than two values the percentile interval is returned
    with a note.
    """
    method = _check_method(method)
    alpha = _check_alpha(alpha)
    n_boot = _check_n_boot(n_boot)
    n_a, n_b = int(a.size), int(b.size)
    estimate = float(statistic(a[None, :], b[None, :])[0])
    n = n_a + n_b
    a_const = bool(np.all(a == a[0]))
    b_const = bool(np.all(b == b[0]))
    if a_const and b_const:
        return _degenerate(estimate, n, alpha, "degenerate: both samples constant, nothing resampled")
    rng = _generator(seed)
    ia = rng.integers(0, n_a, size=(n_boot, n_a))
    ib = rng.integers(0, n_b, size=(n_boot, n_b))
    theta_boot = np.asarray(statistic(a[ia], b[ib]), dtype=np.float64)
    note = ""
    jackknives: List[np.ndarray] = []
    if method == "bca":
        if n_a < 2 or n_b < 2:
            method = "percentile"
            note = "a sample with one value has no jackknife; percentile interval returned"
        else:
            jackknives = [
                np.asarray(statistic(_leave_one_out(a), np.broadcast_to(b, (n_a, n_b))), dtype=np.float64),
                np.asarray(statistic(np.broadcast_to(a, (n_b, n_a)), _leave_one_out(b)), dtype=np.float64),
            ]
    return _interval(estimate, theta_boot, jackknives, alpha, method, n, note)


def _mean_difference(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    return B.mean(axis=1) - A.mean(axis=1)


def _pairwise_counts(A: np.ndarray, B: np.ndarray, pairs_per_chunk: int = 4_000_000) -> Tuple[np.ndarray, np.ndarray]:
    """Per row: the number of (a_i, b_j) pairs with b > a and with b < a, over all n_a * n_b pairs."""
    k, n_a = A.shape
    n_b = B.shape[1]
    rows = max(1, pairs_per_chunk // max(1, n_a * n_b))
    gt = np.empty(k, dtype=np.float64)
    lt = np.empty(k, dtype=np.float64)
    for start in range(0, k, rows):
        stop = min(k, start + rows)
        a = A[start:stop, :, None]
        b = B[start:stop, None, :]
        gt[start:stop] = (b > a).sum(axis=(1, 2))
        lt[start:stop] = (b < a).sum(axis=(1, 2))
    return gt, lt


def _delta_stat(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    gt, lt = _pairwise_counts(A, B)
    return (gt - lt) / (A.shape[1] * B.shape[1])


def _poi_stat(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    total = A.shape[1] * B.shape[1]
    gt, lt = _pairwise_counts(A, B)
    return (gt + 0.5 * (total - gt - lt)) / total


# --------------------------------------------------------------------------- paired effects


def paired_effect(
    a: ArrayLike,
    b: ArrayLike,
    n_boot: int = 10_000,
    alpha: float = 0.05,
    method: str = "bca",
    seed: int = 0,
) -> Dict[str, Any]:
    """Per-seed effect of condition ``b`` over condition ``a``, same seed order in both.

    Returns a dict with the mean difference ``mean_diff`` (= mean of b - a)
    and its bootstrap CI (``low``, ``high``), ``fraction_b_gt_a`` (seeds
    where b > a), ``fraction_ties``, ``mean_a``, ``mean_b``, ``n``, and the
    CI's ``method``, ``n_boot`` and ``note``. Pairing removes the between-seed
    variance that an unpaired comparison would carry, which is why the plan's
    rule comparisons are paired by seed (docs/research_plan.md section 4, M3).
    """
    a = _as_1d(a, "a")
    b = _as_1d(b, "b")
    if a.size != b.size:
        raise ValueError(f"paired samples need the same length, got {a.size} and {b.size}")
    diff = b - a
    ci = bootstrap_ci(diff, np.mean, n_boot=n_boot, alpha=alpha, method=method, seed=seed)
    n = int(diff.size)
    return {
        "n": n,
        "mean_a": float(a.mean()) if n else math.nan,
        "mean_b": float(b.mean()) if n else math.nan,
        "mean_diff": ci.estimate,
        "low": ci.low,
        "high": ci.high,
        "fraction_b_gt_a": float((diff > 0).sum() / n) if n else math.nan,
        "fraction_ties": float((diff == 0).sum() / n) if n else math.nan,
        "alpha": ci.alpha,
        "method": ci.method,
        "n_boot": ci.n_boot,
        "note": ci.note,
    }


# --------------------------------------------------------------------------- ordering statistics


def cliffs_magnitude(delta: float) -> str:
    """The conventional label for |delta|: negligible < 0.147, small < 0.33, medium < 0.474, else large."""
    d = abs(float(delta))
    if d < CLIFFS_DELTA_SMALL:
        return "negligible"
    if d < CLIFFS_DELTA_MEDIUM:
        return "small"
    if d < CLIFFS_DELTA_LARGE:
        return "medium"
    return "large"


def cliffs_delta(
    a: ArrayLike,
    b: ArrayLike,
    ci: bool = True,
    n_boot: int = 10_000,
    alpha: float = 0.05,
    method: str = "bca",
    seed: int = 0,
) -> Dict[str, Any]:
    """Cliff's delta (1993): P(b > a) - P(b < a) over all n_a * n_b pairs, positive when b tends to exceed a.

    Returns ``delta``, its ``magnitude`` label (:func:`cliffs_magnitude`),
    the bootstrap ``low`` and ``high`` (independent resampling of the two
    samples; ``None`` when ``ci`` is False), ``n_a``, ``n_b`` and the CI's
    ``method``, ``n_boot`` and ``note``. Fully separated samples give +1 or
    -1 with every replicate equal, so their interval collapses to the
    estimate and the note says so. The plan's M2a acceptance asks for
    delta >= 0.3 with a BCa 95% CI excluding zero.
    """
    a = _as_1d(a, "a")
    b = _as_1d(b, "b")
    delta = float(_delta_stat(a[None, :], b[None, :])[0])
    out: Dict[str, Any] = {
        "delta": delta,
        "magnitude": cliffs_magnitude(delta),
        "low": None,
        "high": None,
        "n_a": int(a.size),
        "n_b": int(b.size),
        "alpha": _check_alpha(alpha),
        "method": "none",
        "n_boot": 0,
        "note": "",
    }
    if ci:
        c = _bootstrap_two_sample(a, b, _delta_stat, n_boot, alpha, method, seed)
        out.update({"low": c.low, "high": c.high, "method": c.method, "n_boot": c.n_boot, "note": c.note})
    return out


def iqm(x: ArrayLike, axis: Optional[int] = None) -> Union[float, np.ndarray]:
    """Interquartile mean: the mean of the middle half of the sorted values.

    The aggregate Agarwal et al. (2021, "Deep reinforcement learning at the
    edge of the statistical precipice") recommend over the mean (which one
    outlier seed moves) and the median (which ignores most of the sample).
    ``floor(n / 4)`` values are dropped from each end, as their ``rliable``
    code does through a 25% trimmed mean, so for n < 4 nothing is trimmed
    and the IQM is the mean. With ``axis`` it reduces a matrix row-wise,
    which is what lets :func:`bootstrap_ci` evaluate it in one call.
    """
    arr = np.asarray(x, dtype=np.float64)
    if axis is None:
        arr = _as_1d(arr)
        axis = -1
    s = np.sort(arr, axis=axis)
    n = s.shape[axis]
    cut = n // 4
    index = [slice(None)] * s.ndim
    index[axis] = slice(cut, n - cut)
    out = np.mean(s[tuple(index)], axis=axis)
    return float(out) if np.ndim(out) == 0 else out


def iqm_ci(
    x: ArrayLike, n_boot: int = 10_000, alpha: float = 0.05, method: str = "bca", seed: int = 0
) -> CI:
    """Bootstrap CI of the interquartile mean (Agarwal et al. 2021 report IQM with such intervals)."""
    return bootstrap_ci(x, iqm, n_boot=n_boot, alpha=alpha, method=method, seed=seed)


def probability_of_improvement(
    a: ArrayLike,
    b: ArrayLike,
    ci: bool = True,
    n_boot: int = 10_000,
    alpha: float = 0.05,
    method: str = "bca",
    seed: int = 0,
) -> Dict[str, Any]:
    """Probability of improvement of ``b`` over ``a``: P(b > a) + P(b = a) / 2 over all pairs.

    The Mann-Whitney probability Agarwal et al. (2021) recommend for "how
    often does the new condition beat the old one"; 0.5 means no ordering,
    1.0 means every b exceeds every a. It equals (1 + Cliff's delta) / 2.
    Returns ``poi``, bootstrap ``low`` and ``high`` (``None`` when ``ci`` is
    False), ``n_a``, ``n_b`` and the CI's ``method``, ``n_boot`` and ``note``.
    """
    a = _as_1d(a, "a")
    b = _as_1d(b, "b")
    poi = float(_poi_stat(a[None, :], b[None, :])[0])
    out: Dict[str, Any] = {
        "poi": poi,
        "low": None,
        "high": None,
        "n_a": int(a.size),
        "n_b": int(b.size),
        "alpha": _check_alpha(alpha),
        "method": "none",
        "n_boot": 0,
        "note": "",
    }
    if ci:
        c = _bootstrap_two_sample(a, b, _poi_stat, n_boot, alpha, method, seed)
        out.update({"low": c.low, "high": c.high, "method": c.method, "n_boot": c.n_boot, "note": c.note})
    return out


# --------------------------------------------------------------------------- equivalence


def tost(
    a: ArrayLike,
    b: ArrayLike,
    low: float,
    high: float,
    alpha: float = 0.05,
    paired: bool = False,
    relative: bool = False,
    n_boot: int = 10_000,
    method: str = "bca",
    seed: int = 0,
) -> Dict[str, Any]:
    """Two one-sided tests of equivalence for mean(b) - mean(a) within [low, high].

    The two one-sided tests at level ``alpha`` (Schuirmann 1987) both reject,
    and equivalence is concluded, exactly when the (1 - 2 alpha) confidence
    interval of the difference lies inside the equivalence bounds; this
    function reads the decision from that bootstrap interval. With ``paired``
    the difference is the mean of the per-seed differences b - a (same seed
    order); otherwise ``a`` and ``b`` are resampled independently. With
    ``relative`` the bounds are fractions of mean(a), so ``low=-0.2,
    high=0.2`` is the plan's "within +/-20%"; mean(a) must then be non-zero,
    and a negative mean(a) swaps the bounds so that low <= high.

    Returns ``estimate``, ``ci_low``, ``ci_high``, ``ci_level`` (= 1 - 2 alpha),
    ``bound_low``, ``bound_high`` (in the units of the data), ``equivalent``
    (bool), ``mean_a``, ``mean_b``, ``n_a``, ``n_b`` and the CI's ``method``,
    ``n_boot`` and ``note``. "Not equivalent" means the data do not show
    equivalence at this n; it is not evidence of a difference.
    """
    a = _as_1d(a, "a")
    b = _as_1d(b, "b")
    alpha = _check_alpha(alpha)
    if alpha >= 0.5:
        raise ValueError("alpha must be below 0.5 for a (1 - 2 alpha) interval")
    low, high = float(low), float(high)
    if not low < high:
        raise ValueError(f"equivalence bounds need low < high, got {low} and {high}")
    mean_a, mean_b = float(a.mean()), float(b.mean())
    if relative:
        if mean_a == 0.0:
            raise ValueError("relative bounds need a non-zero mean(a)")
        bound_low, bound_high = sorted((low * mean_a, high * mean_a))
    else:
        bound_low, bound_high = low, high
    ci_alpha = 2.0 * alpha
    if paired:
        if a.size != b.size:
            raise ValueError(f"paired samples need the same length, got {a.size} and {b.size}")
        ci = bootstrap_ci(b - a, np.mean, n_boot=n_boot, alpha=ci_alpha, method=method, seed=seed)
    else:
        ci = _bootstrap_two_sample(a, b, _mean_difference, n_boot, ci_alpha, method, seed)
    return {
        "estimate": ci.estimate,
        "ci_low": ci.low,
        "ci_high": ci.high,
        "ci_level": 1.0 - ci_alpha,
        "bound_low": float(bound_low),
        "bound_high": float(bound_high),
        "equivalent": bool(bound_low <= ci.low and ci.high <= bound_high),
        "alpha": alpha,
        "paired": bool(paired),
        "relative": bool(relative),
        "mean_a": mean_a,
        "mean_b": mean_b,
        "n_a": int(a.size),
        "n_b": int(b.size),
        "method": ci.method,
        "n_boot": ci.n_boot,
        "note": ci.note,
    }


# --------------------------------------------------------------------------- pseudo-replication guard


class PseudoReplicationError(ValueError):
    """Two or more seeds produced identical outcomes: they are one sample, not several."""


def _canonical(value: Any) -> Hashable:
    """A hashable, order-independent form of an outcome, for exact comparison."""
    if value is None or isinstance(value, (str, bytes)):
        return value
    if isinstance(value, (bool, np.bool_)):
        return ("bool", bool(value))
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        f = float(value)
        return "nan" if math.isnan(f) else f
    if isinstance(value, np.ndarray):
        return _canonical(value.tolist())  # an array and a list of the same numbers are the same outcome
    if isinstance(value, Mapping):
        items = sorted(((str(k), _canonical(v)) for k, v in value.items()), key=lambda kv: kv[0])
        return ("map", tuple(items))
    if isinstance(value, (list, tuple)):
        return ("seq", tuple(_canonical(v) for v in value))
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted((_canonical(v) for v in value), key=repr)))
    raise TypeError(
        f"cannot compare outcomes of type {type(value).__name__}; pass key= to select a number, "
        "sequence, dict or digest"
    )


def _run_label(run: Any, index: int) -> str:
    if isinstance(run, Mapping) and "seed" in run:
        return f"seed {run['seed']}"
    return f"run {index}"


def pseudo_replication_guard(
    runs: Iterable[Any], key: Union[None, str, Callable[[Any], Any]] = None, allow: bool = False
) -> Union[int, str]:
    """Refuse a multi-seed claim when two or more seeds produced identical outcomes.

    ``runs`` is one outcome per seed: a number, a sequence, a dict, a trace
    digest, or a record from which ``key`` (a dict key or a callable) picks
    the outcome. Outcomes are compared exactly after canonicalisation (dict
    key order and numpy-versus-Python types do not matter; NaN equals NaN).
    Returns the number of distinct outcomes when all differ. When any two
    are identical it raises :class:`PseudoReplicationError` naming them, or,
    with ``allow=True``, returns that message as a string instead so the
    caller can log it. The probe ``tools/probes/seed_pseudoreplication``
    is the case this guards against: at sensor noise 0 the legacy engine
    gives bit-identical trajectories for every seed.
    """
    runs = list(runs)
    if key is None:
        pick: Callable[[Any], Any] = lambda r: r
    elif callable(key):
        pick = key
    else:
        pick = lambda r: r[key]
    groups: Dict[Hashable, List[int]] = {}
    for i, run in enumerate(runs):
        groups.setdefault(_canonical(pick(run)), []).append(i)
    duplicates = [idx for idx in groups.values() if len(idx) > 1]
    if not duplicates:
        return len(groups)
    described = "; ".join(
        " = ".join(_run_label(runs[i], i) for i in idx) for idx in duplicates
    )
    message = (
        f"pseudo-replication: {len(runs)} runs but only {len(groups)} distinct outcomes "
        f"({described}); identical runs are one sample, not several, so no interval over them is valid"
    )
    if allow:
        return message
    raise PseudoReplicationError(message)


# --------------------------------------------------------------------------- tidy tables


TIDY_COLUMNS = ("condition", "task", "seed", "metric", "value")


def tidy_table(rows: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    """One long-format table from per-run records: columns ``condition, task, seed, metric, value``.

    Each row carries ``condition`` (or ``rule``, the plan's name for a replay
    rule), ``task`` and ``seed``, and either a ``metric`` / ``value`` pair or
    one key per metric (wide form, melted here). Any other key in a long-form
    row is an error, so nothing is dropped silently. Rows are sorted by
    (condition, task, metric, seed), so the table does not depend on the
    order the runs finished in.
    """
    records: List[Tuple[str, str, int, str, float]] = []
    for row in rows:
        row = dict(row)
        condition = row.pop("condition", None)
        rule = row.pop("rule", None)
        if condition is None:
            condition = rule
        elif rule is not None and rule != condition:
            raise ValueError(f"row carries both condition={condition!r} and rule={rule!r}")
        if condition is None or "task" not in row or "seed" not in row:
            raise ValueError(f"row needs condition (or rule), task and seed: {sorted(row)}")
        task = str(row.pop("task"))
        seed = int(row.pop("seed"))
        if "metric" in row or "value" in row:
            if "metric" not in row or "value" not in row:
                raise ValueError("a long-form row needs both metric and value")
            metric = str(row.pop("metric"))
            value = float(row.pop("value"))
            if row:
                raise ValueError(f"unexpected keys in long-form row: {sorted(row)}")
            records.append((str(condition), task, seed, metric, value))
        else:
            for metric in sorted(row):
                records.append((str(condition), task, seed, str(metric), float(row[metric])))
    df = pd.DataFrame.from_records(records, columns=list(TIDY_COLUMNS))
    df["seed"] = df["seed"].astype("int64")
    df["value"] = df["value"].astype("float64")
    df = df.sort_values(["condition", "task", "metric", "seed"], kind="mergesort").reset_index(drop=True)
    return df


def summarise(
    df: pd.DataFrame,
    by: Union[str, Sequence[str]],
    ci: Optional[str] = "bca",
    n_boot: int = 10_000,
    alpha: float = 0.05,
    seed: int = 0,
) -> pd.DataFrame:
    """One row per group of a tidy table: the ``by`` columns, then ``n, mean, low, high, iqm, ci_method``.

    ``ci`` is the bootstrap method for the interval on the mean ("bca" or
    "percentile"), or ``None`` for no interval (``low`` and ``high`` NaN).
    ``metric`` is added to ``by`` when the table has that column, so a
    group never mixes metrics. Groups come out in sorted key order and each
    draws from its own child seed of ``seed`` (hashed from the group key),
    so adding a group leaves the others' intervals unchanged.
    """
    by = [by] if isinstance(by, str) else list(by)
    if "value" not in df.columns:
        raise ValueError("summarise needs a 'value' column (see tidy_table)")
    if "metric" in df.columns and "metric" not in by:
        by = by + ["metric"]
    if ci is not None:
        _check_method(ci)
    out: List[Dict[str, Any]] = []
    for key, group in df.groupby(by, sort=True, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        values = group["value"].to_numpy(dtype=np.float64)
        row: Dict[str, Any] = dict(zip(by, key))
        row["n"] = int(values.size)
        row["mean"] = float(values.mean()) if values.size else math.nan
        if ci is None or values.size == 0:
            row["low"], row["high"], row["ci_method"] = math.nan, math.nan, "none"
        else:
            c = bootstrap_ci(values, np.mean, n_boot=n_boot, alpha=alpha, method=ci, seed=_child_seed(seed, repr(key)))
            row["low"], row["high"], row["ci_method"] = c.low, c.high, c.method
        row["iqm"] = iqm(values) if values.size else math.nan
        out.append(row)
    columns = by + ["n", "mean", "low", "high", "iqm", "ci_method"]
    return pd.DataFrame(out, columns=columns)
