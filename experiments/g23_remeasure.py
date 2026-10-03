"""G23, "what survives 30 seeds": G16, G19 and G21 re-measured with confidence intervals.

    python3 -m experiments.g23_remeasure                     # 30 seeds, settings A and B, 4 workers
    python3 -m experiments.g23_remeasure --seeds 2 --quick   # the smoke test's run (tiny budgets)
    python3 -m experiments.g23_remeasure --setting B --claims 1,3 --out /tmp/g23
    python3 -m experiments.g23_remeasure --setting separation --claims 3 --maze-gains 1.5 --tag separation

The result is docs/decisions.md entry G23 (docs/research_plan.md section 5, M0b item 15):
the first table in the repository with a confidence interval on it.

Design
------
Profile: legacy, i.e. ``EngineConfig()`` plus each console scenario's own config
(``ui.scenarios``), which is what every G-entry was measured under. Two stochastic
settings, each run in full, both at sensor noise 0.03:

  A  sensors.noise 0.03 + sensors.odometry_speed_noise 0.05 + sensors.odometry_turn_noise
     0.01 + basal_ganglia.softmax_temperature 0.05: the seed reaches every stochastic
     element the engine has (M0b item 8), so seeds are samples of the whole model;
  B  sensors.noise 0.03 only: the setting the G-entries themselves ran when they wrote
     "noise 0.03", so the comparison with their numbers is like for like.

Three more settings separate A's elements (entry G23 section G): each adds ONE of them to
sensor noise 0.03, so what A changes against B can be laid at one element's door:

  A_speed    sensors.noise 0.03 + sensors.odometry_speed_noise 0.05;
  A_turn     sensors.noise 0.03 + sensors.odometry_turn_noise 0.01;
  A_softmax  sensors.noise 0.03 + basal_ganglia.softmax_temperature 0.05.

``--setting separation`` runs the three together; ``--setting both`` (the default) runs
A and B. ``--tag NAME`` suffixes every output file name (maze_recall_NAME.csv, ...), so a
partial run next to the committed A / B tables does not overwrite them; ``--maze-gains``
restricts claim 3 to a subset of its gains (the paired gain-to-gain effect is reported
only when exactly two are run).

Thirty seeds (1-30) in every arm of every setting. The pseudo-replication guard
``core.seeds.require_seeds_are_samples`` runs on every config (inside the harness's
``run_jobs`` for the harness runs, and directly for the moved-sites control), and
``analysis.stats.pseudo_replication_guard`` runs on every per-seed outcome vector; the
number of distinct outcomes, per vector, is written to guard.csv. Nothing here draws
from the RNG outside ``core.rng`` streams: the engine's own streams, and one named stream
for the moved-sites control.

Claim 1, hidden food (G19 / G21): "memory finds 2.8-4.1x as much food and loses no paired
run". Per seed, the finds over the scenario's 3,000-tick budget with memory on (the
scenario's default value_gain, 1.5) and off (value_gain 0), and the moved-sites control
of tests/experiments/test_hidden_food.py (every site jumps to a random place in the food
band every REGROW ticks, before the engine step; the same jumps for every seed and gain),
also on and off. Reported per setting: the mean of each arm with a BCa 95% CI, the paired
on - off effect with its CI and the fraction of seeds with on > off (and on < off), the
ratio of means with a seed-bootstrap BCa CI, Cliff's delta with its magnitude, the same
for the moved-sites arm, and the fixed-over-moved benefit factor (the test's 1.5x bound).

Claim 2, steering band (G16 / G20): "0.4-3.0 without value-induced resting". The
harness's four G16 scenarios (beacon, foraging, hazard_field, memory_maze) over its
DEFAULT_GAINS at 30 seeds, through ``experiments.steering_sensitivity.run_jobs``. Per
setting and gain: for each open scenario the memory-cost statistic of the steering guard
(score at the gain over score at gain 0, as a ratio of means paired by seed, with a BCa
CI), the paired effect, Cliff's delta and the fraction of seeds whose own ratio is at least
0.8; vrest (the harness's value-induced REST share) with a BCa CI; the maze recall rate
with a CI; and G16's own band statistic, the worst-scenario fraction (min over the four
scenarios of mean / own best mean) with a seed-bootstrap BCa CI. The guard band is the
longest contiguous run of gains above 0 whose CIs stay inside the guard's bounds: the
foraging and hazard_field cost ratios' lower CI ends >= 0.8 (memory costs at most a fifth)
and every scenario's vrest upper CI end <= 0.15. The G16 band is the run of gains whose
worst-fraction lower CI end is >= 0.8. The point-estimate bands (no CI) are reported too.

Claim 3, maze recall (G18 / G21): "16 of 16" headings recall and the recall rate is
">= 0.9 across gains". The memory maze over the harness's full 16-heading set
(``--maze-headings full``) at gains 0.8 and 1.5, 30 seeds. Per seed: recalled hidden
trials / hidden trials pooled over the 16 headings (the harness's recall_rate, pooled),
the number of headings whose run recalls (recall_rate >= RECALL_OK, the harness's
recall_ok), and the mean per-heading rate. Reported: the mean pooled rate with a BCa CI,
the fraction of seeds at >= 0.9, the mean number of headings recalling with a CI, the
fraction of seeds recalling on all 16, the fraction of (seed, heading) runs recalling, the
per-heading fraction of seeds recalling, and the paired 0.8 -> 1.5 effect.

Verdict rules (per setting; the entry's overall verdict is the weaker of A and B):
  claim 1  survives when the ratio-of-means CI overlaps the claimed 2.8-4.1 and no seed
           loses (on < off); weakened when the CI excludes 1 but misses the claimed range,
           or some seed loses; does not survive when the ratio CI includes 1;
  claim 2  survives when both the guard band and the G16 band, read from the CIs, cover
           0.4-3.0; weakened when either band is non-empty but narrower; does not survive
           when no gain satisfies the bounds;
  claim 3  survives when, at every gain run (both by default), the recall-rate CI's lower
           end is >= 0.9 and the headings-recalling CI's lower end is >= 15 of 16 (the
           off-axis guard's own bound); weakened when one of the two holds at every gain;
           does not survive otherwise.

Statistics: ``analysis.stats`` throughout (BCa bootstrap, 10,000 replicates, a fixed
hashed seed per statistic so every interval is reproducible and independent of the order
the others are computed in). Ratios of means and the worst-scenario fraction resample
seeds (the paired unit), so the numerator and denominator of a ratio come from the same
seeds in every replicate. Cliff's delta resamples the two samples independently, as the
module does.

Outputs (``--out``, default docs/data/g23): hidden_food.csv, steering_band.csv and
maze_recall.csv hold every per-seed run in the tidy long format (condition, task, seed,
metric, value; condition is "<setting>/<arm>" or "<setting>/gain=<g>"), with the metrics
the claim is read from: hidden food score and sites_found; steering band score and vrest
for the open scenarios, score and attempted for the maze (its recall rate is the quotient,
and its vrest, like hidden food's, is in summary.csv per cell as vrest_mean and vrest_max);
maze recall per seed recalls, attempted, recall_rate and headings_recalling. A claim that
did not run (``--claims``) writes no tidy table.
maze_recall_by_heading.csv has one row per (setting, gain, seed, heading) run;
summary.csv has one row per statistic (claim, setting, task, condition, statistic, n,
estimate, low, high, method, label, note) including the verdict rows; guard.csv has the
guard results; meta.json records the command, the budgets and the wall-clock runtime (the
one file that is not reproducible byte for byte). With ``--tag NAME`` every file is
written as <stem>_NAME.<ext> instead. Identical arguments give byte-identical CSVs. The
full run writes about 320 KB.

``--quick`` shrinks the budgets for the smoke test (300 ticks, gains 0 and 1.5, 4 maze
headings, 200 bootstrap replicates); its numbers mean nothing.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from analysis.stats import (
    CI,
    TIDY_COLUMNS,
    bootstrap_ci,
    cliffs_delta,
    paired_effect,
    pseudo_replication_guard,
    tidy_table,
)
from core.config import EngineConfig
from core.engine import Engine
from core.rng import RNG
from core.seeds import require_seeds_are_samples
from experiments.steering_sensitivity import (
    DEFAULT_GAINS,
    RECALL_OK,
    TICKS,
    Job,
    is_value_rest,
    maze_heading_set,
    run_jobs,
)
from ui.scenarios import HiddenFood

NOISE = 0.03
Overrides = Tuple[Tuple[str, Any], ...]
SETTINGS: Dict[str, Overrides] = {
    "A": (
        ("sensors.odometry_speed_noise", 0.05),
        ("sensors.odometry_turn_noise", 0.01),
        ("basal_ganglia.softmax_temperature", 0.05),
    ),
    "B": (),
    # One element each on top of sensor noise 0.03 (section G of the entry): A's three, separated.
    "A_speed": (("sensors.odometry_speed_noise", 0.05),),
    "A_turn": (("sensors.odometry_turn_noise", 0.01),),
    "A_softmax": (("basal_ganglia.softmax_temperature", 0.05),),
}
SETTING_ORDER = ("A", "B")  # --setting both, the default
SEPARATION_ORDER = ("A_speed", "A_turn", "A_softmax")  # --setting separation
SETTING_GROUPS: Dict[str, Tuple[str, ...]] = {"both": SETTING_ORDER, "separation": SEPARATION_ORDER}
CLAIM2_SCENARIOS = ("beacon", "foraging", "hazard_field", "memory_maze")
OPEN_SCENARIOS = ("beacon", "foraging", "hazard_field")
COST_SCENARIOS = ("foraging", "hazard_field")  # the guard's "outside the maze" scenarios
CLAIM2_GAINS: Tuple[float, ...] = tuple(DEFAULT_GAINS)
CLAIM3_GAINS: Tuple[float, ...] = (0.8, 1.5)
HIDDEN_FOOD_ARMS: Tuple[Tuple[str, Optional[float]], ...] = (("memory_on", None), ("memory_off", 0.0))
MOVED_ARMS: Tuple[Tuple[str, float], ...] = (("moved_on", 1.5), ("moved_off", 0.0))
MIN_FRACTION = 0.8  # the guard: memory never costs more than a fifth
MAX_VREST = 0.15  # the guard: value-induced REST stays rare
MIN_RECALL = 0.9  # the guard: maze recall rate across gains
HIDDEN_FOOD_CLAIM = (2.8, 4.1)  # G19 / G21: x2.84, x2.85, x4.08
BAND_CLAIM = (0.4, 3.0)  # G16 / G20
N_BOOT = 10_000
ALPHA = 0.05
SITE_JUMP_SEED = 1001  # the hidden-food test's own seed for the moved-sites control
SITE_JUMP_STREAM = "hidden_food_site_jumps"
QUICK_TICKS = 300
QUICK_GAINS: Tuple[float, ...] = (0.0, 1.5)
QUICK_HEADINGS = 4
QUICK_N_BOOT = 200
DEFAULT_OUT = Path("docs/data/g23")
SUMMARY_COLUMNS = ("claim", "setting", "task", "condition", "statistic", "n", "estimate", "low", "high",
                   "method", "label", "note")
GUARD_COLUMNS = ("claim", "setting", "task", "condition", "metric", "n", "distinct_values", "distinct_rows",
                 "stochastic_elements", "note")
BY_HEADING_COLUMNS = ("setting", "gain", "seed", "heading_index", "recalls", "attempted")
VERDICTS = ("survives", "weakened", "does not survive")


@dataclass(frozen=True)
class Budget:
    """Everything ``--quick`` changes, plus the claim-3 gains (``--maze-gains``)."""

    ticks: Dict[str, int]
    gains: Tuple[float, ...]
    headings: List[float]
    n_boot: int
    maze_gains: Tuple[float, ...] = CLAIM3_GAINS

    @classmethod
    def full(cls) -> "Budget":
        return cls(dict(TICKS), CLAIM2_GAINS, maze_heading_set("full"), N_BOOT)

    @classmethod
    def quick(cls) -> "Budget":
        return cls({s: QUICK_TICKS for s in TICKS}, QUICK_GAINS, maze_heading_set(QUICK_HEADINGS), QUICK_N_BOOT)


# --------------------------------------------------------------------------- configs and runs


def apply_overrides(config: EngineConfig, overrides: Overrides) -> None:
    """Set dotted config fields, as the harness does for ``--set`` (unknown fields are an error)."""
    for key, value in overrides:
        obj: Any = config
        parts = key.split(".")
        for part in parts[:-1]:
            obj = getattr(obj, part)
        if not hasattr(obj, parts[-1]):
            raise AttributeError(f"config has no field {key!r}")
        setattr(obj, parts[-1], value)


def setting_config(setting: str, scenario_config: EngineConfig) -> EngineConfig:
    """A scenario's own config at ``NOISE`` with the setting's overrides applied."""
    scenario_config.sensors.noise = NOISE
    apply_overrides(scenario_config, SETTINGS[setting])
    return scenario_config


def band_point(rng: Any) -> Tuple[float, float]:
    """Uniform on the band 2.0-3.0 m in from the walls (the sites sit ~2.5 m in).

    The construction of tests/experiments/test_hidden_food.py, with the harness's
    named stream in place of a bare ``random.Random``."""
    while True:
        x, y = rng.uniform(-8.0, 8.0), rng.uniform(-8.0, 8.0)
        if 2.0 <= 10.0 - max(abs(x), abs(y)) <= 3.0:
            return x, y


@dataclass(frozen=True)
class MovedJob:
    setting: str
    value_gain: float
    seed: int
    ticks: int


def run_moved_sites(job: MovedJob) -> Dict[str, Any]:
    """Hidden food with every site jumping to a random band place every REGROW ticks.

    The jump happens before the tick's engine step, so the engine sees a moved
    site first; the jumps come from one named stream with a fixed seed, so they
    are the same for every seed and gain (as in the test, where they are the
    same for every heading and gain). Row fields match the harness's hidden_food rows.
    """
    scenario = HiddenFood()
    config = setting_config(job.setting, scenario.config())
    config.basal_ganglia.value_gain = job.value_gain
    engine = Engine(seed=job.seed, config=config)
    scenario.setup(engine)
    jumps = RNG(seed=SITE_JUMP_SEED).stream(SITE_JUMP_STREAM)
    value_rest = 0
    for tick in range(job.ticks):
        if tick > 0 and tick % scenario.REGROW == 0:
            for item in scenario.items:
                item.x, item.y = band_point(jumps)
        td = engine.run(1)[0]
        ctx = getattr(engine, "context", None)
        if ctx is not None and is_value_rest(ctx, config.basal_ganglia.value_gain):
            value_rest += 1
        scenario.on_tick(engine, td.tick)
    return {
        "scenario": "hidden_food_moved",
        "value_gain": config.basal_ganglia.value_gain,
        "seed": job.seed,
        "noise": NOISE,
        "heading": None,
        "ticks": job.ticks,
        "score": scenario.collected,
        "sites_found": scenario.sites_found(),
        "blocks": scenario.blocks(job.ticks),
        "vrest": value_rest / job.ticks if job.ticks > 0 else 0.0,
    }


def run_moved_jobs(jobs: Sequence[MovedJob], workers: Optional[int]) -> List[Dict[str, Any]]:
    """The moved-sites runs, after the seeds-are-samples guard on each setting's config."""
    for setting in sorted({j.setting for j in jobs}, key=list(SETTINGS).index):
        seeds = {j.seed for j in jobs if j.setting == setting}
        require_seeds_are_samples(setting_config(setting, HiddenFood().config()), len(seeds))
    if len(jobs) <= 1 or workers == 1:
        return [run_moved_sites(job) for job in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run_moved_sites, jobs, chunksize=1))


# --------------------------------------------------------------------------- statistics helpers


def stat_seed(*key: Any) -> int:
    """A reproducible bootstrap seed from a statistic's name: hashed, so order does not matter."""
    digest = hashlib.sha256(":".join(str(k) for k in key).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def seed_bootstrap(stat: Callable[[np.ndarray], Any], n: int, n_boot: int, seed: int) -> CI:
    """BCa interval of a statistic of the seed set, by resampling seed indices.

    ``stat`` takes an integer index array, (n,) for the estimate and the jackknife
    rows or (k, n) for the replicates, and reduces over its last axis. Resampling
    indices keeps paired quantities paired: a ratio of means over the same seeds,
    or the worst-scenario fraction over every scenario's rows of the same seeds.
    """
    index = np.arange(n, dtype=np.float64)

    def statistic(m: Any, axis: int = -1) -> Any:
        return stat(np.asarray(m).astype(np.int64))

    return bootstrap_ci(index, statistic, n_boot=n_boot, alpha=ALPHA, seed=seed)


def undefined_ci(n: int, note: str) -> CI:
    return CI(math.nan, math.nan, math.nan, "none", int(n), 0, ALPHA, note)


def ratio_of_means_ci(num: Sequence[float], den: Sequence[float], n_boot: int, seed: int) -> CI:
    """mean(num) / mean(den) over the same seeds, with a seed-bootstrap BCa interval."""
    a = np.asarray(num, dtype=np.float64)
    b = np.asarray(den, dtype=np.float64)
    if a.size != b.size:
        raise ValueError(f"paired samples need the same length, got {a.size} and {b.size}")
    if a.size == 0 or float(b.mean()) == 0.0:
        return undefined_ci(a.size, "undefined: the denominator's mean is 0")
    if np.any(b == 0.0) and a.size < 2:
        return undefined_ci(a.size, "undefined: one seed with a zero denominator")

    def stat(ii: np.ndarray) -> Any:
        with np.errstate(divide="ignore", invalid="ignore"):
            return a[ii].mean(axis=-1) / b[ii].mean(axis=-1)

    ci = seed_bootstrap(stat, a.size, n_boot, seed)
    if not (math.isfinite(ci.low) and math.isfinite(ci.high)):
        return CI(ci.estimate, math.nan, math.nan, "none", ci.n, ci.n_boot, ci.alpha,
                  "interval undefined: a replicate had a zero denominator")
    return ci


def benefit_factor_ci(on: Sequence[float], off: Sequence[float], moved_on: Sequence[float],
                      moved_off: Sequence[float], n_boot: int, seed: int) -> CI:
    """(mean on / mean off) / (mean moved_on / mean moved_off) over the same seeds."""
    arrays = [np.asarray(x, dtype=np.float64) for x in (on, off, moved_on, moved_off)]
    n = arrays[0].size
    if any(x.size != n for x in arrays) or n == 0:
        raise ValueError("the four arms need the same number of seeds")
    if float(arrays[1].mean()) == 0.0 or float(arrays[3].mean()) == 0.0 or float(arrays[2].mean()) == 0.0:
        return undefined_ci(n, "undefined: a mean in the denominator is 0")

    def stat(ii: np.ndarray) -> Any:
        with np.errstate(divide="ignore", invalid="ignore"):
            fixed = arrays[0][ii].mean(axis=-1) / arrays[1][ii].mean(axis=-1)
            moved = arrays[2][ii].mean(axis=-1) / arrays[3][ii].mean(axis=-1)
            return fixed / moved

    ci = seed_bootstrap(stat, n, n_boot, seed)
    if not (math.isfinite(ci.low) and math.isfinite(ci.high)):
        return CI(ci.estimate, math.nan, math.nan, "none", ci.n, ci.n_boot, ci.alpha,
                  "interval undefined: a replicate had a zero denominator")
    return ci


def worst_fraction_ci(scores: np.ndarray, gain_index: int, n_boot: int, seed: int) -> CI:
    """G16's band statistic at one gain: min over scenarios of mean[g] / best mean, over seeds.

    ``scores`` is (scenarios, gains, seeds). A scenario whose best mean is 0 in a
    replicate gives fraction 0 there, as the harness's ``gain_fractions`` does.
    """
    scores = np.asarray(scores, dtype=np.float64)
    if scores.ndim != 3:
        raise ValueError(f"scores must be (scenarios, gains, seeds), got shape {scores.shape}")

    def stat(ii: np.ndarray) -> Any:
        means = scores[:, :, ii].mean(axis=-1)  # (S, G) or (S, G, k)
        best = means.max(axis=1)  # (S,) or (S, k)
        with np.errstate(divide="ignore", invalid="ignore"):
            frac = np.where(best > 0.0, means[:, gain_index] / best, 0.0)
        return frac.min(axis=0)

    return seed_bootstrap(stat, scores.shape[-1], n_boot, seed)


def contiguous_band(ok: Mapping[float, bool]) -> List[float]:
    """The longest run of consecutive grid gains flagged True (ties to the lower gains)."""
    runs: List[List[float]] = []
    current: List[float] = []
    for gain in sorted(ok):
        if ok[gain]:
            current.append(gain)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    if not runs:
        return []
    return max(runs, key=len)  # max keeps the first of equal lengths: the lower gains


def band_text(band: Sequence[float]) -> str:
    return f"{band[0]:g}-{band[-1]:g}" if band else "none"


def fraction(values: Sequence[float], predicate: Callable[[float], bool]) -> float:
    values = list(values)
    return sum(1 for v in values if predicate(v)) / len(values) if values else math.nan


# --------------------------------------------------------------------------- verdicts


def verdict_hidden_food(ratio: CI, fraction_losses: float) -> Tuple[str, str]:
    lo, hi = HIDDEN_FOOD_CLAIM
    if not (math.isfinite(ratio.low) and math.isfinite(ratio.high)):
        return "does not survive", "ratio interval undefined"
    if ratio.low <= 1.0:
        return "does not survive", f"ratio CI {ratio.low:.2f}-{ratio.high:.2f} includes 1"
    problems = []
    if not (ratio.low <= hi and ratio.high >= lo):
        problems.append(f"ratio CI {ratio.low:.2f}-{ratio.high:.2f} misses the claimed {lo:g}-{hi:g}x")
    if fraction_losses > 0.0:
        problems.append(f"{fraction_losses:.0%} of seeds lose with memory on")
    if problems:
        return "weakened", "; ".join(problems)
    return "survives", (f"ratio CI {ratio.low:.2f}-{ratio.high:.2f} overlaps the claimed {lo:g}-{hi:g}x "
                        "and no seed loses")


def verdict_band(band_guard: Sequence[float], band_g16: Sequence[float]) -> Tuple[str, str]:
    lo, hi = BAND_CLAIM

    def covers(band: Sequence[float]) -> bool:
        return bool(band) and band[0] <= lo and band[-1] >= hi

    text = f"guard band {band_text(band_guard)}, G16 band {band_text(band_g16)} (claimed {lo:g}-{hi:g})"
    if covers(band_guard) and covers(band_g16):
        return "survives", text
    if band_guard or band_g16:
        return "weakened", text
    return "does not survive", text


def verdict_maze(rate_cis: Mapping[float, CI], headings_cis: Mapping[float, CI], n_headings: int) -> Tuple[str, str]:
    bound = n_headings - 1
    rate_ok = all(c.low >= MIN_RECALL for c in rate_cis.values())
    headings_ok = all(c.low >= bound for c in headings_cis.values())
    rates = ", ".join(f"gain {g:g}: {c.low:.3f}" for g, c in sorted(rate_cis.items()))
    heads = ", ".join(f"gain {g:g}: {c.low:.2f}" for g, c in sorted(headings_cis.items()))
    text = f"recall-rate CI lower ends {rates} (bound {MIN_RECALL:g}); headings-recalling CI lower ends {heads} (bound {bound})"
    if rate_ok and headings_ok:
        return "survives", text
    if rate_ok or headings_ok:
        return "weakened", text
    return "does not survive", text


def weaker(verdicts: Sequence[str]) -> str:
    return max(verdicts, key=VERDICTS.index) if verdicts else "not run"


# --------------------------------------------------------------------------- results


class Results:
    """Collects the tidy rows, the summary rows and the guard rows of one run."""

    def __init__(self, n_boot: int) -> None:
        self.n_boot = n_boot
        self.tidy: Dict[str, List[Dict[str, Any]]] = {"hidden_food": [], "steering_band": [], "maze_recall": []}
        self.by_heading: List[Dict[str, Any]] = []
        self.summary: List[Dict[str, Any]] = []
        self.guard: List[Dict[str, Any]] = []
        self.verdicts: Dict[str, Dict[str, str]] = {}

    def record(self, claim: str, setting: str, task: str, condition: str, statistic: str, n: int,
               estimate: float, low: float = math.nan, high: float = math.nan, method: str = "none",
               label: str = "", note: str = "") -> None:
        self.summary.append({
            "claim": claim, "setting": setting, "task": task, "condition": condition, "statistic": statistic,
            "n": int(n), "estimate": estimate, "low": low, "high": high, "method": method, "label": label,
            "note": note,
        })

    def record_ci(self, claim: str, setting: str, task: str, condition: str, statistic: str, ci: CI,
                  label: str = "") -> None:
        self.record(claim, setting, task, condition, statistic, ci.n, ci.estimate, ci.low, ci.high, ci.method,
                    label, ci.note)

    def record_mean(self, claim: str, setting: str, task: str, condition: str, values: Sequence[float],
                    statistic: str = "mean") -> CI:
        ci = bootstrap_ci(np.asarray(values, dtype=np.float64), np.mean, n_boot=self.n_boot, alpha=ALPHA,
                          seed=stat_seed(claim, setting, task, condition, statistic))
        self.record_ci(claim, setting, task, condition, statistic, ci)
        return ci

    def record_paired(self, claim: str, setting: str, task: str, condition: str, a: Sequence[float],
                      b: Sequence[float], name: str) -> Dict[str, Any]:
        """paired_effect(a, b), Cliff's delta(a, b) and the ratio of means b / a, under ``name``."""
        a = np.asarray(a, dtype=np.float64)
        b = np.asarray(b, dtype=np.float64)
        effect = paired_effect(a, b, n_boot=self.n_boot, alpha=ALPHA, seed=stat_seed(claim, setting, task, condition, name, "paired"))
        self.record(claim, setting, task, condition, f"{name}_paired_diff", effect["n"], effect["mean_diff"],
                    effect["low"], effect["high"], effect["method"], "", effect["note"])
        self.record(claim, setting, task, condition, f"{name}_fraction_b_gt_a", effect["n"], effect["fraction_b_gt_a"])
        self.record(claim, setting, task, condition, f"{name}_fraction_b_lt_a", effect["n"],
                    fraction(b - a, lambda d: d < 0.0))
        self.record(claim, setting, task, condition, f"{name}_fraction_ties", effect["n"], effect["fraction_ties"])
        delta = cliffs_delta(a, b, n_boot=self.n_boot, alpha=ALPHA, seed=stat_seed(claim, setting, task, condition, name, "delta"))
        self.record(claim, setting, task, condition, f"{name}_cliffs_delta", a.size, delta["delta"], delta["low"],
                    delta["high"], delta["method"], delta["magnitude"], delta["note"])
        ratio = ratio_of_means_ci(b, a, self.n_boot, stat_seed(claim, setting, task, condition, name, "ratio"))
        self.record_ci(claim, setting, task, condition, f"{name}_ratio_of_means", ratio)
        return {"effect": effect, "delta": delta, "ratio": ratio}

    def record_guard(self, claim: str, setting: str, task: str, condition: str, metric: str,
                     rows: Sequence[Mapping[str, Any]], elements: Sequence[str]) -> None:
        """Both guards' results for one per-seed outcome vector."""
        values = [row[metric] for row in rows]
        outcome = pseudo_replication_guard(rows, allow=True)
        distinct_rows = outcome if isinstance(outcome, int) else len({json.dumps(dict(r), sort_keys=True) for r in rows})
        self.guard.append({
            "claim": claim, "setting": setting, "task": task, "condition": condition, "metric": metric,
            "n": len(rows), "distinct_values": len(set(values)), "distinct_rows": distinct_rows,
            "stochastic_elements": " ".join(elements), "note": "" if isinstance(outcome, int) else outcome,
        })

    def verdict(self, claim: str, setting: str, text: str, reason: str) -> None:
        self.verdicts.setdefault(claim, {})[setting] = text
        self.record(claim, setting, "", "", "verdict", 0, math.nan, label=text, note=reason)


def by_index(jobs: Sequence[Any], rows: Sequence[Mapping[str, Any]]) -> List[Tuple[Any, Mapping[str, Any]]]:
    if len(jobs) != len(rows):
        raise RuntimeError(f"{len(jobs)} jobs but {len(rows)} rows")
    return list(zip(jobs, rows))


def elements_of(setting: str, scenario_config: EngineConfig) -> List[str]:
    return setting_config(setting, scenario_config).stochastic_elements()


# --------------------------------------------------------------------------- claim 1


def claim_hidden_food(res: Results, settings: Sequence[str], seeds: Sequence[int], budget: Budget,
                      workers: Optional[int]) -> int:
    claim = "1"
    ticks = budget.ticks["hidden_food"]
    jobs = [Job("hidden_food", gain, seed, NOISE, ticks, SETTINGS[s], None)
            for s in settings for _arm, gain in HIDDEN_FOOD_ARMS for seed in seeds]
    rows = run_jobs(jobs, workers)
    moved_jobs = [MovedJob(s, gain, seed, ticks) for s in settings for _arm, gain in MOVED_ARMS for seed in seeds]
    moved_rows = run_moved_jobs(moved_jobs, workers)
    harness = {(j.overrides, j.value_gain, j.seed): r for j, r in by_index(jobs, rows)}
    moved = {(j.setting, j.value_gain, j.seed): r for j, r in by_index(moved_jobs, moved_rows)}
    for setting in settings:
        elements = elements_of(setting, HiddenFood().config())
        arms: Dict[str, List[Mapping[str, Any]]] = {}
        for arm, gain in HIDDEN_FOOD_ARMS:
            arms[arm] = [harness[(SETTINGS[setting], gain, seed)] for seed in seeds]
        for arm, gain in MOVED_ARMS:
            arms[arm] = [moved[(setting, gain, seed)] for seed in seeds]
        scores = {arm: [float(r["score"]) for r in arm_rows] for arm, arm_rows in arms.items()}
        for arm, arm_rows in arms.items():
            condition = f"{setting}/{arm}"
            for seed, row in zip(seeds, arm_rows):
                res.tidy["hidden_food"].append({"condition": condition, "task": "hidden_food", "seed": seed,
                                                "score": row["score"], "sites_found": row["sites_found"]})
            res.record_guard(claim, setting, "hidden_food", condition, "score", arm_rows, elements)
            res.record_mean(claim, setting, "hidden_food", condition, scores[arm])
            res.record_mean(claim, setting, "hidden_food", condition, [float(r["vrest"]) for r in arm_rows], "vrest_mean")
        fixed = res.record_paired(claim, setting, "hidden_food", f"{setting}/fixed_sites", scores["memory_off"],
                                  scores["memory_on"], "on_vs_off")
        res.record_paired(claim, setting, "hidden_food", f"{setting}/moved_sites", scores["moved_off"],
                          scores["moved_on"], "on_vs_off")
        benefit = benefit_factor_ci(scores["memory_on"], scores["memory_off"], scores["moved_on"], scores["moved_off"],
                                    res.n_boot, stat_seed(claim, setting, "benefit"))
        res.record_ci(claim, setting, "hidden_food", f"{setting}/fixed_over_moved", "benefit_factor", benefit)
        losses = fraction(np.asarray(scores["memory_on"]) - np.asarray(scores["memory_off"]), lambda d: d < 0.0)
        res.verdict(claim, setting, *verdict_hidden_food(fixed["ratio"], losses))
    return len(jobs) + len(moved_jobs)


# --------------------------------------------------------------------------- claim 2


def claim_steering_band(res: Results, settings: Sequence[str], seeds: Sequence[int], budget: Budget,
                        workers: Optional[int]) -> int:
    claim = "2"
    gains = budget.gains
    jobs = [Job(scen, gain, seed, NOISE, budget.ticks[scen], SETTINGS[s], None)
            for s in settings for scen in CLAIM2_SCENARIOS for gain in gains for seed in seeds]
    rows = run_jobs(jobs, workers)
    table = {(j.overrides, j.scenario, j.value_gain, j.seed): r for j, r in by_index(jobs, rows)}
    from ui.scenarios import make_scenario

    for setting in settings:
        over = SETTINGS[setting]
        score: Dict[str, Dict[float, np.ndarray]] = {}
        vrest: Dict[str, Dict[float, np.ndarray]] = {}
        rate: Dict[float, np.ndarray] = {}
        for scen in CLAIM2_SCENARIOS:
            elements = elements_of(setting, make_scenario(scen).config())
            score[scen] = {}
            vrest[scen] = {}
            for gain in gains:
                cell = [table[(over, scen, gain, seed)] for seed in seeds]
                condition = f"{setting}/gain={gain:g}"
                for seed, row in zip(seeds, cell):
                    # Open scenarios: the two guard metrics. Maze: score and attempted (its
                    # recall rate is the quotient; its vrest, 0 in every run, is in summary.csv
                    # as vrest_mean and vrest_max per cell).
                    tidy = {"condition": condition, "task": scen, "seed": seed, "score": row["score"]}
                    if scen == "memory_maze":
                        tidy["attempted"] = row["attempted"]
                    else:
                        tidy["vrest"] = row["vrest"]
                    res.tidy["steering_band"].append(tidy)
                res.record_guard(claim, setting, scen, condition, "score", cell, elements)
                score[scen][gain] = np.array([float(r["score"]) for r in cell])
                vrest[scen][gain] = np.array([float(r["vrest"]) for r in cell])
                res.record_mean(claim, setting, scen, condition, score[scen][gain], "score_mean")
                v = res.record_mean(claim, setting, scen, condition, vrest[scen][gain], "vrest_mean")
                res.record(claim, setting, scen, condition, "vrest_max", v.n, float(vrest[scen][gain].max()))
                if scen == "memory_maze":
                    rate[gain] = np.array([float(r["recall_rate"]) for r in cell])
                    res.record_mean(claim, setting, scen, condition, rate[gain], "recall_rate_mean")
                    res.record(claim, setting, scen, condition, "fraction_seeds_recall_ok", len(cell),
                               fraction(rate[gain], lambda x: x >= RECALL_OK))
        cost_ok: Dict[float, bool] = {}
        cost_ok_point: Dict[float, bool] = {}
        g16_ok: Dict[float, bool] = {}
        g16_ok_point: Dict[float, bool] = {}
        cube = np.stack([np.stack([score[scen][g] for g in gains]) for scen in CLAIM2_SCENARIOS])
        for gi, gain in enumerate(gains):
            condition = f"{setting}/gain={gain:g}"
            ratio_low = {}
            ratio_point = {}
            if gain > 0.0 and 0.0 in gains:
                for scen in OPEN_SCENARIOS:
                    paired = res.record_paired(claim, setting, scen, condition, score[scen][0.0], score[scen][gain],
                                               "vs_gain0")
                    own = np.where(score[scen][0.0] > 0.0, score[scen][gain] / np.where(score[scen][0.0] > 0.0, score[scen][0.0], 1.0), np.nan)
                    res.record(claim, setting, scen, condition, "vs_gain0_fraction_seeds_within_a_fifth", own.size,
                               float(np.mean(own[np.isfinite(own)] >= MIN_FRACTION)) if np.isfinite(own).any() else math.nan)
                    ratio_low[scen] = paired["ratio"].low
                    ratio_point[scen] = paired["ratio"].estimate
            worst = worst_fraction_ci(cube, gi, res.n_boot, stat_seed(claim, setting, "worst_fraction", gain))
            limiting = min(CLAIM2_SCENARIOS, key=lambda s: (score[s][gain].mean() / max(score[s][g].mean() for g in gains)
                                                             if max(score[s][g].mean() for g in gains) > 0 else 0.0, s))
            res.record_ci(claim, setting, "four_scenarios", condition, "worst_fraction", worst, limiting)
            vrest_high = {scen: res_vrest_high(res, claim, setting, scen, condition) for scen in CLAIM2_SCENARIOS}
            vrest_point = {scen: float(vrest[scen][gain].mean()) for scen in CLAIM2_SCENARIOS}
            if gain > 0.0:
                cost_ok[gain] = (all(ratio_low.get(s, math.nan) >= MIN_FRACTION for s in COST_SCENARIOS)
                                 and all(vrest_high[s] <= MAX_VREST for s in CLAIM2_SCENARIOS))
                cost_ok_point[gain] = (all(ratio_point.get(s, math.nan) >= MIN_FRACTION for s in COST_SCENARIOS)
                                       and all(vrest_point[s] <= MAX_VREST for s in CLAIM2_SCENARIOS))
                g16_ok[gain] = worst.low >= MIN_FRACTION
                g16_ok_point[gain] = worst.estimate >= MIN_FRACTION
                res.record(claim, setting, "four_scenarios", condition, "in_guard_band_ci", len(seeds), float(cost_ok[gain]))
                res.record(claim, setting, "four_scenarios", condition, "in_g16_band_ci", len(seeds), float(g16_ok[gain]))
        band_guard = contiguous_band(cost_ok)
        band_g16 = contiguous_band(g16_ok)
        res.record(claim, setting, "four_scenarios", f"{setting}/band", "guard_band_ci", len(seeds), math.nan,
                   label=band_text(band_guard))
        res.record(claim, setting, "four_scenarios", f"{setting}/band", "guard_band_point", len(seeds), math.nan,
                   label=band_text(contiguous_band(cost_ok_point)))
        res.record(claim, setting, "four_scenarios", f"{setting}/band", "g16_band_ci", len(seeds), math.nan,
                   label=band_text(band_g16))
        res.record(claim, setting, "four_scenarios", f"{setting}/band", "g16_band_point", len(seeds), math.nan,
                   label=band_text(contiguous_band(g16_ok_point)))
        recall_gains = [g for g in gains if g > 0.0 and rate_low(res, setting, g) >= MIN_RECALL]
        res.record(claim, setting, "memory_maze", f"{setting}/band", "maze_recall_ok_gains_ci", len(seeds), math.nan,
                   label=band_text(contiguous_band({g: g in recall_gains for g in gains if g > 0.0})))
        res.verdict(claim, setting, *verdict_band(band_guard, band_g16))
    return len(jobs)


def res_vrest_high(res: Results, claim: str, setting: str, scen: str, condition: str) -> float:
    for row in res.summary:
        if (row["claim"], row["setting"], row["task"], row["condition"], row["statistic"]) == (claim, setting, scen, condition, "vrest_mean"):
            return float(row["high"])
    raise KeyError((claim, setting, scen, condition, "vrest_mean"))


def rate_low(res: Results, setting: str, gain: float) -> float:
    condition = f"{setting}/gain={gain:g}"
    for row in res.summary:
        if (row["claim"], row["setting"], row["task"], row["condition"], row["statistic"]) == ("2", setting, "memory_maze", condition, "recall_rate_mean"):
            return float(row["low"])
    raise KeyError(("2", setting, "memory_maze", condition, "recall_rate_mean"))


# --------------------------------------------------------------------------- claim 3


def claim_maze_recall(res: Results, settings: Sequence[str], seeds: Sequence[int], budget: Budget,
                      workers: Optional[int]) -> int:
    claim = "3"
    headings = budget.headings
    gains = budget.maze_gains
    ticks = budget.ticks["memory_maze"]
    jobs = [Job("memory_maze", gain, seed, NOISE, ticks, SETTINGS[s], h)
            for s in settings for gain in gains for seed in seeds for h in headings]
    rows = run_jobs(jobs, workers)
    table = {(j.overrides, j.value_gain, j.seed, j.heading): r for j, r in by_index(jobs, rows)}
    from ui.scenarios import make_scenario

    task = "memory_maze_full_circle"
    for setting in settings:
        over = SETTINGS[setting]
        elements = elements_of(setting, make_scenario("memory_maze").config())
        pooled: Dict[float, np.ndarray] = {}
        counts: Dict[float, np.ndarray] = {}
        rate_cis: Dict[float, CI] = {}
        heading_cis: Dict[float, CI] = {}
        for gain in gains:
            condition = f"{setting}/gain={gain:g}"
            per_seed: List[Dict[str, Any]] = []
            per_seed_runs: List[List[Tuple[int, int]]] = []
            run_ok: List[float] = []
            per_heading_ok = np.zeros(len(headings))
            for seed in seeds:
                runs = [table[(over, gain, seed, h)] for h in headings]
                recalls = sum(int(r["score"]) for r in runs)
                attempted = sum(int(r["attempted"]) for r in runs)
                ok = [float(r["recall_rate"]) >= RECALL_OK for r in runs]
                per_heading_ok += np.array(ok, dtype=np.float64)
                run_ok.extend(float(o) for o in ok)
                per_seed.append({
                    "seed": seed,
                    "recalls": recalls,
                    "attempted": attempted,
                    "recall_rate": recalls / attempted if attempted else 0.0,
                    "headings_recalling": sum(ok),
                    "mean_heading_rate": float(np.mean([r["recall_rate"] for r in runs])),
                })
                per_seed_runs.append([(int(r["score"]), int(r["attempted"])) for r in runs])
                for hi, r in enumerate(runs):
                    res.by_heading.append({"setting": setting, "gain": gain, "seed": seed, "heading_index": hi,
                                           "recalls": r["score"], "attempted": r["attempted"]})
            for row in per_seed:
                tidy = {k: v for k, v in row.items() if k != "mean_heading_rate"}  # derivable from the by-heading file
                res.tidy["maze_recall"].append({"condition": condition, "task": task, **tidy})
            res.record_guard(claim, setting, task, condition, "recall_rate",
                             [{"seed": r["seed"], "recall_rate": r["recall_rate"], "runs": runs}
                              for r, runs in zip(per_seed, per_seed_runs)], elements)
            pooled[gain] = np.array([r["recall_rate"] for r in per_seed])
            counts[gain] = np.array([float(r["headings_recalling"]) for r in per_seed])
            rate_cis[gain] = res.record_mean(claim, setting, task, condition, pooled[gain], "recall_rate_mean")
            res.record(claim, setting, task, condition, "fraction_seeds_recall_ok", len(seeds),
                       fraction(pooled[gain], lambda x: x >= MIN_RECALL))
            res.record_mean(claim, setting, task, condition, [r["mean_heading_rate"] for r in per_seed], "mean_heading_rate")
            heading_cis[gain] = res.record_mean(claim, setting, task, condition, counts[gain], "headings_recalling_mean")
            res.record(claim, setting, task, condition, "fraction_seeds_all_headings", len(seeds),
                       fraction(counts[gain], lambda x: x >= len(headings)))
            res.record(claim, setting, task, condition, "fraction_runs_recalling", len(run_ok), float(np.mean(run_ok)))
            res.record(claim, setting, task, condition, "recalls_mean", len(seeds),
                       float(np.mean([r["recalls"] for r in per_seed])))
            for hi, h in enumerate(headings):
                res.record(claim, setting, task, f"{condition}/heading={h:.2f}", "fraction_seeds_recalling_heading",
                           len(seeds), float(per_heading_ok[hi] / len(seeds)))
        if len(gains) == 2:
            lo_gain, hi_gain = gains
            res.record_paired(claim, setting, task, f"{setting}/gain={lo_gain:g}_to_{hi_gain:g}", pooled[lo_gain],
                              pooled[hi_gain], "recall_rate")
        res.verdict(claim, setting, *verdict_maze(rate_cis, heading_cis, len(headings)))
    return len(jobs)


# --------------------------------------------------------------------------- output


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    f = float(value)
    if math.isnan(f):
        return "nan"
    if f.is_integer() and abs(f) < 1e15:
        return str(int(f))
    return f"{f:.6g}"


def write_csv(path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([fmt(row[c]) for c in columns])


def write_tidy(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        write_csv(path, TIDY_COLUMNS, [])
        return
    df = tidy_table(rows)
    write_csv(path, TIDY_COLUMNS, [dict(zip(TIDY_COLUMNS, record)) for record in df.itertuples(index=False)])


def output_name(stem: str, ext: str, tag: Optional[str]) -> str:
    """``<stem>.<ext>``, or ``<stem>_<tag>.<ext>`` under ``--tag``."""
    return f"{stem}_{tag}.{ext}" if tag else f"{stem}.{ext}"


def write_outputs(out: Path, res: Results, meta: Mapping[str, Any], tag: Optional[str] = None) -> List[Path]:
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for name, rows in res.tidy.items():
        if not rows:
            continue  # the claim did not run
        path = out / output_name(name, "csv", tag)
        write_tidy(path, rows)
        files.append(path)
    if res.by_heading:
        path = out / output_name("maze_recall_by_heading", "csv", tag)
        write_csv(path, BY_HEADING_COLUMNS, res.by_heading)
        files.append(path)
    path = out / output_name("summary", "csv", tag)
    write_csv(path, SUMMARY_COLUMNS, res.summary)
    files.append(path)
    path = out / output_name("guard", "csv", tag)
    write_csv(path, GUARD_COLUMNS, res.guard)
    files.append(path)
    path = out / output_name("meta", "json", tag)
    path.write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    files.append(path)
    return files


def print_summary(res: Results) -> None:
    for row in res.summary:
        if row["statistic"] == "verdict":
            continue
        ci = ""
        if math.isfinite(row["low"]) or math.isfinite(row["high"]):
            ci = f"  [{fmt(row['low'])}, {fmt(row['high'])}] {row['method']}"
        label = f"  {row['label']}" if row["label"] else ""
        note = f"  ({row['note']})" if row["note"] else ""
        print(f"claim {row['claim']}  {row['task']:24s} {row['condition']:28s} {row['statistic']:44s} "
              f"n={row['n']:<4d} {fmt(row['estimate'])}{ci}{label}{note}")
    print()
    for claim in sorted(res.verdicts):
        for setting, text in res.verdicts[claim].items():
            reason = next(r["note"] for r in res.summary
                          if r["statistic"] == "verdict" and r["claim"] == claim and r["setting"] == setting)
            print(f"claim {claim}, setting {setting}: {text}  ({reason})")
        print(f"claim {claim}, overall: {weaker(list(res.verdicts[claim].values()))}")


CLAIMS: Dict[str, Callable[..., int]] = {
    "1": claim_hidden_food,
    "2": claim_steering_band,
    "3": claim_maze_recall,
}


def main(argv: Optional[Sequence[str]] = None) -> Results:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", type=int, default=30, help="number of seeds, 1..N (default 30)")
    parser.add_argument("--seed-start", type=int, default=1, help="first seed (default 1)")
    parser.add_argument("--setting", choices=tuple(SETTINGS) + tuple(SETTING_GROUPS), default="both",
                        help="one setting, 'both' (A and B, the default) or 'separation' (A_speed, A_turn, A_softmax)")
    parser.add_argument("--claims", default="1,2,3", help="comma-separated subset of 1,2,3 (default all)")
    parser.add_argument("--maze-gains", default=None,
                        help=f"comma-separated subset of claim 3's gains {','.join(f'{g:g}' for g in CLAIM3_GAINS)} (default all)")
    parser.add_argument("--workers", type=int, default=4, help="worker processes (default 4)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output directory (default {DEFAULT_OUT})")
    parser.add_argument("--tag", default=None, help="suffix for the output file names (summary_TAG.csv, ...)")
    parser.add_argument("--n-boot", type=int, default=None, help=f"bootstrap replicates (default {N_BOOT})")
    parser.add_argument("--quick", action="store_true", help="tiny budgets for the smoke test; the numbers mean nothing")
    args = parser.parse_args(argv)
    if args.seeds < 1:
        parser.error("--seeds must be >= 1")
    if args.workers is not None and args.workers < 1:
        parser.error("--workers must be >= 1")
    claims = [c.strip() for c in args.claims.split(",") if c.strip()]
    unknown = [c for c in claims if c not in CLAIMS]
    if unknown or not claims:
        parser.error(f"--claims must name a subset of {','.join(CLAIMS)}, got {args.claims!r}")
    maze_gains = CLAIM3_GAINS
    if args.maze_gains is not None:
        try:
            chosen = tuple(float(g) for g in args.maze_gains.split(",") if g.strip())
        except ValueError:
            parser.error(f"--maze-gains must be numbers, got {args.maze_gains!r}")
        if not chosen or any(g not in CLAIM3_GAINS for g in chosen) or len(set(chosen)) != len(chosen):
            parser.error(f"--maze-gains must name a subset of {','.join(f'{g:g}' for g in CLAIM3_GAINS)}, got {args.maze_gains!r}")
        maze_gains = tuple(g for g in CLAIM3_GAINS if g in chosen)
    if args.tag is not None and (not args.tag or any(c in args.tag for c in "/\\.")):
        parser.error(f"--tag must be a plain name, got {args.tag!r}")

    settings = list(SETTING_GROUPS.get(args.setting, (args.setting,)))
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    budget = Budget.quick() if args.quick else Budget.full()
    budget = Budget(budget.ticks, budget.gains, budget.headings,
                    budget.n_boot if args.n_boot is None else int(args.n_boot), maze_gains)
    res = Results(budget.n_boot)
    started = time.perf_counter()
    jobs = 0
    for claim in sorted(set(claims), key=list(CLAIMS).index):
        t0 = time.perf_counter()
        jobs += CLAIMS[claim](res, settings, seeds, budget, args.workers)
        print(f"claim {claim}: done in {time.perf_counter() - t0:.0f} s", file=sys.stderr)
    runtime = time.perf_counter() - started
    meta = {
        "command": "python3 -m experiments.g23_remeasure " + " ".join(argv if argv is not None else sys.argv[1:]),
        "settings": {s: [list(kv) for kv in SETTINGS[s]] for s in settings},
        "noise": NOISE,
        "seeds": seeds,
        "claims": claims,
        "ticks": budget.ticks,
        "gains_claim2": list(budget.gains),
        "gains_claim3": list(budget.maze_gains),
        "maze_headings": len(budget.headings),
        "n_boot": budget.n_boot,
        "alpha": ALPHA,
        "workers": args.workers,
        "jobs": jobs,
        "quick": bool(args.quick),
        "tag": args.tag,
        "runtime_s": round(runtime, 1),
        "verdicts": {c: {**v, "overall": weaker(list(v.values()))} for c, v in res.verdicts.items()},
    }
    files = write_outputs(args.out, res, meta, args.tag)
    print_summary(res)
    total = sum(p.stat().st_size for p in files)
    print(f"\n{jobs} runs in {runtime:.0f} s; wrote {len(files)} files ({total / 1024:.0f} KB) to {args.out}")
    return res


if __name__ == "__main__":
    main()
