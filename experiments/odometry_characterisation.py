"""Characterise the research profile's odometry noise (docs/research_plan.md section 4, M1; docs/odometry.md).

    python3 -m experiments.odometry_characterisation                       # 30 seeds, every condition, all cores
    python3 -m experiments.odometry_characterisation --conditions named --seeds 4 --distance 400 --out /tmp/odo
    python3 -m experiments.odometry_characterisation --conditions grid --out /tmp/odo

A partial run (fewer seeds, a shorter distance, a subset of the conditions, a
small bootstrap) refuses the committed output directory (docs/data/m1): give it
``--out``.

What is measured
----------------
The research profile (``EngineConfig.research()``) estimates its own motion
with seeded odometry noise (M0b item 8, ``core.sensors._compute_egomotion``):
the raw forward displacement d becomes d (1 + sigma_speed xi) and the raw
heading change gets + N(0, sigma_turn), both before the Observation's clamps
(forward in [-1, 1] units, turn in [-pi, pi]). The spatial system
(``brain.systems.spatial``) dead-reckons from those two numbers. Nothing resets
the estimate until M2b's wall-contact reset, so the error against the body is
pure accumulated odometry error. This script runs the engine in a barren world
large enough that the body never meets a wall (a 5,000-unit box; the run stops
after 2,000 units = 200 m of travel, docs/units.md), 30 seeds per condition,
and records at every 25 units of travel the position-estimate error (the
distance between the estimate and the body), the signed heading-estimate
error and the accumulated signed along-track error (the sum over ticks of the
estimated minus the true forward displacement). Per condition it fits the
log-log slope of the mean error against distance over [50, 2000] units, with a
seed-bootstrap BCa interval (analysis.stats).

Conditions: ``speed_only`` (0.05), ``turn_only`` (0.01 rad), ``both`` (the
research placeholders), and a grid turn in {0.0025, 0.005, 0.01, 0.02} rad x
speed in {0, 0.05, 0.1}, the softmax temperature at the research 0.1
throughout. The walk is what the body does under that profile, and in an open
barren world that walk is a straight line: with nothing in view the channel
scores are constant (FORWARD 1.0, each TURN 0.3, REST 0.0 with the novelty bit
at 1), so at temperature 0.1 a TURN is about a 1-in-500 draw (each of the two
TURN channels about 1 in 1,100) and a 2,000-unit run is about 2,000 FORWARD
ticks with a handful of turns (measured: 99.8% FORWARD). Because the growth
laws below depend on whether the walk turns, the three named conditions are
also run on a ``turning`` walk: ``basal_ganglia.forward_bias`` 0.15 instead of
0.8, which brings FORWARD (0.35) within the temperature of the TURNs (0.3), so
the body walks FORWARD on about 46% of ticks and TURNs 0.3 rad left or right
on about 51% (a persistent random walk; REST 2%). Odometry and everything
else stay the research defaults; the control changes only the walk.

Expectations, written before the runs
-------------------------------------
- Speed noise alone, if the per-tick error were zero-mean: the along-track
  error is a sum of independent terms, so the error grows as sqrt(distance),
  log-log slope 0.5. But the noise is applied before the clamp, and a FORWARD
  step of 1.0 sits at the top of the forward range, so on a full-thrust tick
  only a slowing error survives: the estimated step is min(1 + 0.05 xi, 1),
  whose mean is 1 - 0.05 E[xi+] = 1 - 0.05 / sqrt(2 pi) = 1 - 0.01995. On a
  straight walk that bias accumulates linearly, so the expected slope is 1.0
  (the random part, sd 0.029 sqrt(N), stays under 2 units at N = 2,000 and
  is swamped). On a turning walk the per-tick bias vectors point along
  changing headings and partly cancel: the biased part follows the body's
  net displacement, which grows as sqrt(distance), so the slope returns
  towards 0.5. The 0.3-unit TURN steps are unclamped and unbiased.
- Heading noise alone: the heading error is a random walk, sd sigma sqrt(t)
  over t ticks (every tick draws, moving or not). On a straight walk the
  lateral position error is the running sum of that random walk, which grows
  as t^1.5 (slope 1.5), and the along-track shortfall from 1 - cos(error)
  grows as t^2, so the measured slope over a long straight run is expected
  at or somewhat above 1.5. On a turning walk the lateral error vectors
  decorrelate with the heading, and the error grows about linearly
  (slope about 1.0).
- Both: the sum; the heading term dominates the position error by an order
  of magnitude at 2,000 units, so ``both`` should read like ``turn_only``.
- The plan's acceptance band, 0.5 to 1.5, brackets both single-noise laws
  for a turning walk; on the straight walk the heading-noise law sits at its
  upper edge or above it. This script reports what it measures and
  docs/odometry.md says which walk each number belongs to.

ATP decorrelation (plan section 4, M1: "in the legacy profile with the gate
flag off, |r(error, ATP)| < 0.1"): legacy profile (``EngineConfig()``), the
default 20 x 20 barren box (the walls clamp the body, so the per-tick
statistics matter more than the absolute error), odometry noise at the
research values, 3,000 ticks, seeds 1-4, ``spatial.gate_scales_egomotion``
True (the legacy gate multiplies egomotion before integration) and False.
Four Pearson correlations with ATP are reported per run: the error itself
over all ticks and from tick 200 on (ATP decays from 1.0 to its limit cycle
over the first ~100 ticks while any error grows, a shared trend that
correlates the two whatever the mechanism), the per-tick increment of the
error magnitude, and the relative step error on moving ticks, (|estimated
step| / |true step|) - 1, which is what the odometry gets wrong on a tick
independently of how far the ATP-throttled body moved. The last is the
decorrelation statistic: with the gate flag on it equals gate - 1 plus noise
(-1 when CLOSED, -0.6 when NARROW), so it tracks ATP; with the flag off it is
the speed noise, 0.05 xi, which cannot.

Outputs (``--out``, default docs/data/m1): odometry_curves.csv (the mean
curves per condition), odometry_seeds.csv (one row per run),
odometry_slopes.csv (one row per condition: the fit, its interval, the clamp
bias, the walk statistics), odometry_atp.csv (one row per ATP run) and
odometry_meta.json. Floats are written with six significant digits.

Determinism: every random number comes from the engine's own named streams
(``sensors_odometry``, ``action_softmax``); the bootstrap draws from
``analysis.stats``'s own seeded generator. Sums use ``math.fsum`` (exact), the
bootstrap's column means numpy's pairwise sum; nothing here calls a BLAS
product. Runs are independent, so the worker pool only changes wall-clock.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from brain.systems.spatial import wrap_angle
from core.config import EngineConfig
from core.engine import Engine
from core.seeds import require_seeds_are_samples

TARGET_DISTANCE = 2000.0  # units of travel: 200 m under docs/units.md
CHECKPOINT = 25.0  # units between recorded points
FIT_LOW = 50.0  # the fit runs over [FIT_LOW, target distance]
BOUNDS = (2500.0, 2500.0)  # half-widths: a 5,000-unit box that 2,000 units of travel from the centre cannot leave
TICK_CAP = 20_000  # a run that has not travelled the target distance by then is reported as capped
SEEDS: Tuple[int, ...] = tuple(range(1, 31))
RESEARCH_SPEED = 0.05
RESEARCH_TURN = 0.01
TURNING_FORWARD_BIAS = 0.15  # the turning-walk control: FORWARD 0.35 against TURN 0.3 at temperature 0.1
ATP_TICKS = 3000
ATP_SEEDS: Tuple[int, ...] = (1, 2, 3, 4)
ATP_TRANSIENT = 200  # ticks dropped from the "after transient" error correlation
DEFAULT_OUT = Path("docs/data/m1")
DEFAULT_N_BOOT = 10_000
WALKS = ("straight", "turning")


@dataclass(frozen=True)
class Condition:
    name: str
    speed: float  # sensors.odometry_speed_noise
    turn: float  # sensors.odometry_turn_noise (rad)
    walk: str = "straight"  # "straight": the research walk; "turning": forward_bias TURNING_FORWARD_BIAS

    def config(self) -> EngineConfig:
        """``EngineConfig.research()`` with this condition's odometry noise, the big box and the walk."""
        if self.walk not in WALKS:
            raise ValueError(f"unknown walk {self.walk!r}; one of {WALKS}")
        cfg = EngineConfig.research()
        cfg.sensors.odometry_speed_noise = float(self.speed)
        cfg.sensors.odometry_turn_noise = float(self.turn)
        cfg.world.bounds = BOUNDS
        if self.walk == "turning":
            cfg.basal_ganglia.forward_bias = TURNING_FORWARD_BIAS
        return cfg


NAMED_CONDITIONS: Tuple[Condition, ...] = (
    Condition("speed_only", RESEARCH_SPEED, 0.0),
    Condition("turn_only", 0.0, RESEARCH_TURN),
    Condition("both", RESEARCH_SPEED, RESEARCH_TURN),
)
GRID_TURNS = (0.0025, 0.005, 0.01, 0.02)
GRID_SPEEDS = (0.0, 0.05, 0.1)
GRID_CONDITIONS: Tuple[Condition, ...] = tuple(
    Condition(f"grid_turn{turn}_speed{speed}", speed, turn) for turn in GRID_TURNS for speed in GRID_SPEEDS
)
TURNING_CONDITIONS: Tuple[Condition, ...] = tuple(
    Condition(f"{c.name}_turning", c.speed, c.turn, "turning") for c in NAMED_CONDITIONS
)
CONDITION_SETS: Dict[str, Tuple[Condition, ...]] = {
    "named": NAMED_CONDITIONS,
    "grid": GRID_CONDITIONS,
    "turning": TURNING_CONDITIONS,
    "all": NAMED_CONDITIONS + GRID_CONDITIONS + TURNING_CONDITIONS,
}


@dataclass(frozen=True)
class Checkpoint:
    distance: float  # the nominal checkpoint (units travelled)
    tick: int  # the first tick at which the body had travelled that far
    pos_err: float  # |estimate - body| (units)
    hd_err: float  # estimated minus true heading, wrapped to [-pi, pi] (rad)
    along_err: float  # accumulated (estimated - true) forward displacement (units)


@dataclass(frozen=True)
class SeedRun:
    condition: str
    seed: int
    ticks: int
    distance: float
    capped: bool
    checkpoints: Tuple[Checkpoint, ...]
    along_err: float
    forward_ticks: int
    turn_ticks: int
    rest_ticks: int
    net_displacement: float
    final_pos_err: float
    final_hd_err: float

    @property
    def bias_per_unit(self) -> float:
        """The clamp bias: the signed along-track error per unit travelled."""
        return self.along_err / self.distance if self.distance > 0 else float("nan")


def run_seed(
    condition: Condition,
    seed: int,
    target_distance: float = TARGET_DISTANCE,
    checkpoint: float = CHECKPOINT,
    tick_cap: int = TICK_CAP,
) -> SeedRun:
    """One run of ``condition`` at ``seed`` until the body has travelled ``target_distance`` (or ``tick_cap``)."""
    engine = Engine(seed=seed, config=condition.config())
    distance = 0.0
    along = 0.0
    next_cp = checkpoint
    points: List[Checkpoint] = []
    forward = turns = rests = 0
    ticks = 0
    agent = engine.agent
    heading = 0.0
    td = None
    for n in range(1, tick_cap + 1):
        td = engine.run(1, reset=(n == 1))[0]
        ticks = n
        heading = engine.context.heading  # the body's heading after this tick (TickData logs only the estimate)
        # The true forward displacement, computed as the odometry computes its raw value
        # before adding noise: the displacement projected on the new heading.
        dx = agent.pos[0] - agent.last_pos[0]
        dy = agent.pos[1] - agent.last_pos[1]
        step = dx * math.cos(heading) + dy * math.sin(heading)
        distance += abs(step)
        along += td.obs_forward_delta - step
        if td.action_name == "FORWARD":
            forward += 1
        elif td.action_name == "REST":
            rests += 1
        else:
            turns += 1
        while next_cp <= distance and next_cp <= target_distance:
            points.append(
                Checkpoint(
                    distance=next_cp,
                    tick=n,
                    pos_err=math.hypot(td.grid_x - agent.pos[0], td.grid_y - agent.pos[1]),
                    hd_err=wrap_angle(td.hd_angle - heading),
                    along_err=along,
                )
            )
            next_cp += checkpoint
        if distance >= target_distance:
            break
    assert td is not None
    return SeedRun(
        condition=condition.name,
        seed=seed,
        ticks=ticks,
        distance=distance,
        capped=distance < target_distance,
        checkpoints=tuple(points),
        along_err=along,
        forward_ticks=forward,
        turn_ticks=turns,
        rest_ticks=rests,
        net_displacement=math.hypot(agent.pos[0], agent.pos[1]),
        final_pos_err=math.hypot(td.grid_x - agent.pos[0], td.grid_y - agent.pos[1]),
        final_hd_err=wrap_angle(td.hd_angle - heading),
    )


# --- statistics (pure Python, exact sums) ------------------------------------


def log_log_slope(points: Sequence[Tuple[float, float]]) -> Tuple[float, float, float]:
    """OLS of log(error) on log(distance) over the points with distance and error > 0: (slope, intercept, r2).

    NaN throughout with fewer than two usable points or no spread in distance.
    """
    xs: List[float] = []
    ys: List[float] = []
    for d, e in points:
        if d > 0.0 and e > 0.0:
            xs.append(math.log(d))
            ys.append(math.log(e))
    n = len(xs)
    nan = float("nan")
    if n < 2:
        return nan, nan, nan
    mx = math.fsum(xs) / n
    my = math.fsum(ys) / n
    sxx = math.fsum((x - mx) * (x - mx) for x in xs)
    syy = math.fsum((y - my) * (y - my) for y in ys)
    sxy = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 0.0:
        return nan, nan, nan
    slope = sxy / sxx
    intercept = my - slope * mx
    r2 = (sxy * sxy) / (sxx * syy) if syy > 0.0 else nan
    return slope, intercept, r2


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Pearson's r; NaN with fewer than two pairs or a constant series."""
    n = min(len(xs), len(ys))
    if n < 2:
        return float("nan")
    xs = list(xs[:n])
    ys = list(ys[:n])
    mx = math.fsum(xs) / n
    my = math.fsum(ys) / n
    sxy = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = math.fsum((x - mx) * (x - mx) for x in xs)
    syy = math.fsum((y - my) * (y - my) for y in ys)
    if sxx <= 0.0 or syy <= 0.0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def _mean(xs: Sequence[float]) -> float:
    return math.fsum(xs) / len(xs) if xs else float("nan")


def _sd(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    m = _mean(xs)
    return math.sqrt(math.fsum((x - m) * (x - m) for x in xs) / (len(xs) - 1))


def _rms(xs: Sequence[float]) -> float:
    return math.sqrt(math.fsum(x * x for x in xs) / len(xs)) if xs else float("nan")


def _common_points(runs: Sequence[SeedRun]) -> int:
    """How many checkpoints every run reached (a capped run may have fewer)."""
    return min(len(r.checkpoints) for r in runs) if runs else 0


def mean_curve(runs: Sequence[SeedRun]) -> List[Dict[str, Any]]:
    """Per checkpoint, over the runs: the mean and sd of the position error, the heading-error spread, the mean tick."""
    rows: List[Dict[str, Any]] = []
    for k in range(_common_points(runs)):
        pos = [r.checkpoints[k].pos_err for r in runs]
        hd = [r.checkpoints[k].hd_err for r in runs]
        rows.append(
            {
                "distance": runs[0].checkpoints[k].distance,
                "n_seeds": len(runs),
                "mean_tick": _mean([float(r.checkpoints[k].tick) for r in runs]),
                "mean_pos_err": _mean(pos),
                "sd_pos_err": _sd(pos),
                "mean_abs_hd_err": _mean([abs(h) for h in hd]),
                "rms_hd_err": _rms(hd),
                "mean_along_err": _mean([r.checkpoints[k].along_err for r in runs]),
            }
        )
    return rows


def _fit_points(curve: Sequence[Mapping[str, Any]], fit_range: Tuple[float, float]) -> List[Tuple[float, float]]:
    low, high = fit_range
    return [(row["distance"], row["mean_pos_err"]) for row in curve if low <= row["distance"] <= high]


def seed_slope(run: SeedRun, fit_range: Tuple[float, float]) -> float:
    """The log-log slope of one run's own error curve over ``fit_range``."""
    low, high = fit_range
    return log_log_slope([(c.distance, c.pos_err) for c in run.checkpoints if low <= c.distance <= high])[0]


def fit_condition(condition: Condition, runs: Sequence[SeedRun], fit_range: Tuple[float, float]) -> Dict[str, Any]:
    """The condition's headline numbers: the slope of the mean curve, the per-seed slopes, the clamp bias, the walk."""
    curve = mean_curve(runs)
    slope, intercept, r2 = log_log_slope(_fit_points(curve, fit_range))
    per_seed = [seed_slope(r, fit_range) for r in runs]
    finite = [s for s in per_seed if not math.isnan(s)]
    last = curve[-1] if curve else None
    ticks = [float(r.ticks) for r in runs]
    total_ticks = math.fsum(ticks)
    biases = [r.bias_per_unit for r in runs]
    nan = float("nan")
    return {
        "condition": condition.name,
        "walk": condition.walk,
        "speed": condition.speed,
        "turn": condition.turn,
        "n_seeds": len(runs),
        "fit_low": fit_range[0],
        "fit_high": fit_range[1],
        "slope": slope,
        "intercept": intercept,
        "r2": r2,
        "seed_slope_mean": _mean(finite),
        "seed_slope_min": min(finite) if finite else nan,
        "seed_slope_max": max(finite) if finite else nan,
        "final_distance": last["distance"] if last else nan,
        "final_mean_err": last["mean_pos_err"] if last else nan,
        "final_sd_err": last["sd_pos_err"] if last else nan,
        "final_rms_hd_err": last["rms_hd_err"] if last else nan,
        "expected_hd_sd": condition.turn * math.sqrt(_mean(ticks)) if runs else nan,
        "mean_ticks": _mean(ticks),
        "forward_share": math.fsum(r.forward_ticks for r in runs) / total_ticks if total_ticks else nan,
        "turn_share": math.fsum(r.turn_ticks for r in runs) / total_ticks if total_ticks else nan,
        "rest_share": math.fsum(r.rest_ticks for r in runs) / total_ticks if total_ticks else nan,
        "net_displacement_mean": _mean([r.net_displacement for r in runs]),
        "bias_per_unit_mean": _mean(biases),
        "bias_per_unit_min": min(biases) if biases else nan,
        "bias_per_unit_max": max(biases) if biases else nan,
        "capped": sum(1 for r in runs if r.capped),
    }


def slope_ci(runs: Sequence[SeedRun], fit_range: Tuple[float, float], n_boot: int = DEFAULT_N_BOOT, seed: int = 0):
    """Seed-bootstrap BCa interval on the slope of the mean curve (``analysis.stats.bootstrap_ci``).

    Resamples runs, rebuilds the mean curve (numpy's pairwise sums over the
    resampled rows) and refits. Returns the ``CI`` record; imports numpy only
    when called.
    """
    import numpy as np

    from analysis.stats import bootstrap_ci

    low, high = fit_range
    k = _common_points(runs)
    distances = [runs[0].checkpoints[i].distance for i in range(k)]
    keep = [i for i, d in enumerate(distances) if low <= d <= high]
    matrix = np.asarray([[r.checkpoints[i].pos_err for i in keep] for r in runs], dtype=float)
    xs = [distances[i] for i in keep]

    def statistic(idx: np.ndarray) -> float:
        rows = matrix[np.asarray(idx, dtype=int)]
        means = rows.mean(axis=0).tolist()
        return log_log_slope(list(zip(xs, means)))[0]

    return bootstrap_ci(np.arange(len(runs), dtype=float), statistic, n_boot=n_boot, seed=seed)


# --- ATP decorrelation (legacy profile) ---------------------------------------


def atp_decorrelation(
    seed: int,
    gate_scales_egomotion: bool,
    ticks: int = ATP_TICKS,
    transient: int = ATP_TRANSIENT,
    speed: float = RESEARCH_SPEED,
    turn: float = RESEARCH_TURN,
) -> Dict[str, Any]:
    """Legacy profile, default barren box, research odometry noise: how the estimate's error relates to ATP.

    Returns the four correlations the module docstring defines (``r_error``,
    ``r_error_after_transient``, ``r_error_increment``, ``r_step_error``),
    the number of moving ticks the step error is taken over, the error at
    the last tick and the gate's CLOSED fraction.
    """
    cfg = EngineConfig()
    cfg.sensors.odometry_speed_noise = float(speed)
    cfg.sensors.odometry_turn_noise = float(turn)
    cfg.spatial.gate_scales_egomotion = bool(gate_scales_egomotion)
    engine = Engine(seed=seed, config=cfg)
    agent = engine.agent
    atp: List[float] = []
    err: List[float] = []
    inc: List[float] = []
    step_err: List[float] = []
    step_atp: List[float] = []
    closed = 0
    prev_est = (0.0, 0.0)
    prev_pos = (0.0, 0.0)
    prev_err = 0.0
    for i in range(ticks):
        td = engine.run(1, reset=(i == 0))[0]
        e = math.hypot(td.grid_x - agent.pos[0], td.grid_y - agent.pos[1])
        est_step = math.hypot(td.grid_x - prev_est[0], td.grid_y - prev_est[1])
        true_step = math.hypot(agent.pos[0] - prev_pos[0], agent.pos[1] - prev_pos[1])
        atp.append(td.atp)
        err.append(e)
        inc.append(e - prev_err)
        if true_step > 1e-12:
            step_err.append(est_step / true_step - 1.0)
            step_atp.append(td.atp)
        closed += td.trn_state == "CLOSED"
        prev_est = (td.grid_x, td.grid_y)
        prev_pos = agent.pos
        prev_err = e
    return {
        "profile": "legacy",
        "gate_scales_egomotion": bool(gate_scales_egomotion),
        "seed": seed,
        "ticks": ticks,
        "r_error": pearson(err, atp),
        "r_error_after_transient": pearson(err[transient:], atp[transient:]),
        "r_error_increment": pearson(inc, atp),
        "r_step_error": pearson(step_err, step_atp),
        "n_moving": len(step_err),
        "final_error": err[-1] if err else float("nan"),
        "frac_closed": closed / ticks if ticks else float("nan"),
    }


# --- the runner --------------------------------------------------------------


def _run_task(task: Tuple[Condition, int, float, float, int]) -> SeedRun:
    condition, seed, distance, checkpoint, cap = task
    return run_seed(condition, seed, distance, checkpoint, cap)


def run_conditions(
    conditions: Sequence[Condition],
    seeds: Sequence[int] = SEEDS,
    target_distance: float = TARGET_DISTANCE,
    checkpoint: float = CHECKPOINT,
    tick_cap: int = TICK_CAP,
    workers: Optional[int] = None,
) -> Dict[str, List[SeedRun]]:
    """Every (condition, seed) run, grouped by condition in the given order; in-process when ``workers == 1``.

    The pseudo-replication guard (``core.seeds``) runs on each condition's config first.
    """
    for condition in conditions:
        require_seeds_are_samples(condition.config(), len(seeds))
    tasks = [(c, s, target_distance, checkpoint, tick_cap) for c in conditions for s in seeds]
    if workers == 1 or len(tasks) <= 1:
        results = [_run_task(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_run_task, tasks, chunksize=1))
    grouped: Dict[str, List[SeedRun]] = {c.name: [] for c in conditions}
    for run in results:
        grouped[run.condition].append(run)
    return grouped


def _fmt(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if value.is_integer() and abs(value) < 1e15:
            return str(int(value))
        return f"{value:.6g}"
    return value


def write_csv(path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_fmt(row[c]) for c in columns])


CURVE_COLUMNS = (
    "condition", "walk", "speed", "turn", "distance", "n_seeds", "mean_tick", "mean_pos_err", "sd_pos_err",
    "mean_abs_hd_err", "rms_hd_err", "mean_along_err",
)
SEED_COLUMNS = (
    "condition", "walk", "speed", "turn", "seed", "ticks", "distance", "capped", "forward_ticks", "turn_ticks",
    "rest_ticks", "net_displacement", "final_pos_err", "final_hd_err", "along_err", "bias_per_unit", "slope",
)
SLOPE_COLUMNS = (
    "condition", "walk", "speed", "turn", "n_seeds", "fit_low", "fit_high", "slope", "slope_low", "slope_high",
    "intercept", "r2", "seed_slope_mean", "seed_slope_min", "seed_slope_max", "final_distance", "final_mean_err",
    "final_sd_err", "final_rms_hd_err", "expected_hd_sd", "mean_ticks", "forward_share", "turn_share", "rest_share",
    "net_displacement_mean", "bias_per_unit_mean", "bias_per_unit_min", "bias_per_unit_max", "capped",
)
ATP_COLUMNS = (
    "profile", "gate_scales_egomotion", "seed", "ticks", "r_error", "r_error_after_transient", "r_error_increment",
    "r_step_error", "n_moving", "final_error", "frac_closed",
)
OUTPUT_FILES = (
    "odometry_curves.csv", "odometry_seeds.csv", "odometry_slopes.csv", "odometry_atp.csv", "odometry_meta.json",
)


def _commit_sha() -> Optional[str]:
    """The checked-out commit, for the meta file; None when it cannot be read."""
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def characterise(
    conditions: Sequence[Condition],
    seeds: Sequence[int] = SEEDS,
    target_distance: float = TARGET_DISTANCE,
    checkpoint: float = CHECKPOINT,
    fit_low: float = FIT_LOW,
    tick_cap: int = TICK_CAP,
    workers: Optional[int] = None,
    n_boot: int = DEFAULT_N_BOOT,
    atp_seeds: Sequence[int] = ATP_SEEDS,
    atp_ticks: int = ATP_TICKS,
) -> Dict[str, Any]:
    """Run everything and return the tables (lists of dicts) plus the raw runs."""
    fit_range = (fit_low, target_distance)
    runs = run_conditions(conditions, seeds, target_distance, checkpoint, tick_cap, workers)
    curves: List[Dict[str, Any]] = []
    seed_rows: List[Dict[str, Any]] = []
    slopes: List[Dict[str, Any]] = []
    for condition in conditions:
        cond_runs = runs[condition.name]
        base = {"condition": condition.name, "walk": condition.walk, "speed": condition.speed, "turn": condition.turn}
        for row in mean_curve(cond_runs):
            curves.append({**base, **row})
        for run in cond_runs:
            seed_rows.append(
                {
                    **base,
                    "seed": run.seed,
                    "ticks": run.ticks,
                    "distance": run.distance,
                    "capped": run.capped,
                    "forward_ticks": run.forward_ticks,
                    "turn_ticks": run.turn_ticks,
                    "rest_ticks": run.rest_ticks,
                    "net_displacement": run.net_displacement,
                    "final_pos_err": run.final_pos_err,
                    "final_hd_err": run.final_hd_err,
                    "along_err": run.along_err,
                    "bias_per_unit": run.bias_per_unit,
                    "slope": seed_slope(run, fit_range),
                }
            )
        fit = fit_condition(condition, cond_runs, fit_range)
        if n_boot > 0 and len(cond_runs) >= 2:
            ci = slope_ci(cond_runs, fit_range, n_boot)
            fit["slope_low"], fit["slope_high"] = ci.low, ci.high
        else:
            fit["slope_low"] = fit["slope_high"] = float("nan")
        slopes.append(fit)
    atp_rows = [atp_decorrelation(s, flag, atp_ticks) for flag in (True, False) for s in atp_seeds]
    return {"runs": runs, "curves": curves, "seeds": seed_rows, "slopes": slopes, "atp": atp_rows}


def write_outputs(out: Path, result: Mapping[str, Any], meta: Mapping[str, Any]) -> List[Path]:
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "odometry_curves.csv", CURVE_COLUMNS, result["curves"])
    write_csv(out / "odometry_seeds.csv", SEED_COLUMNS, result["seeds"])
    write_csv(out / "odometry_slopes.csv", SLOPE_COLUMNS, result["slopes"])
    write_csv(out / "odometry_atp.csv", ATP_COLUMNS, result["atp"])
    with (out / "odometry_meta.json").open("w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=1, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return [out / name for name in OUTPUT_FILES]


def print_summary(result: Mapping[str, Any]) -> None:
    print(
        "condition                     walk      speed  turn     slope [BCa 95%]        per-seed      "
        "err@end   bias/unit  ticks"
    )
    for s in result["slopes"]:
        print(
            f"{s['condition']:<29} {s['walk']:<9} {s['speed']:<6} {s['turn']:<8} "
            f"{s['slope']:6.3f} [{s['slope_low']:6.3f}, {s['slope_high']:6.3f}]  "
            f"{s['seed_slope_min']:5.2f}-{s['seed_slope_max']:5.2f}  {s['final_mean_err']:9.2f}  "
            f"{s['bias_per_unit_mean']:+8.4f}  {s['mean_ticks']:6.0f}"
        )
    print("ATP (legacy profile): gate  seed  r_error  r_after_transient  r_increment  r_step_error  n_moving  final_error")
    for a in result["atp"]:
        print(
            f"  {'on ' if a['gate_scales_egomotion'] else 'off'}   {a['seed']:>3}  {a['r_error']:+7.3f}  "
            f"{a['r_error_after_transient']:+9.3f}          {a['r_error_increment']:+7.3f}      {a['r_step_error']:+7.3f}"
            f"     {a['n_moving']:>5}   {a['final_error']:8.3f}"
        )


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--conditions", choices=sorted(CONDITION_SETS), default="all")
    parser.add_argument("--seeds", type=int, default=len(SEEDS), help="number of seeds (default 30)")
    parser.add_argument("--seed-start", type=int, default=SEEDS[0])
    parser.add_argument("--distance", type=float, default=TARGET_DISTANCE, help="units of travel per run (default 2000)")
    parser.add_argument("--checkpoint", type=float, default=CHECKPOINT)
    parser.add_argument("--fit-low", type=float, default=FIT_LOW, help="lower end of the fit range (default 50)")
    parser.add_argument("--tick-cap", type=int, default=TICK_CAP)
    parser.add_argument("--workers", type=int, default=None, help="worker processes (default: all cores)")
    parser.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT, help="bootstrap replicates (0 skips the interval)")
    parser.add_argument("--atp-seeds", type=int, default=len(ATP_SEEDS), help="seeds 1..N for the ATP decorrelation")
    parser.add_argument("--atp-ticks", type=int, default=ATP_TICKS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if args.seeds < 1 or args.atp_seeds < 1 or args.distance <= 0 or args.checkpoint <= 0:
        parser.error("--seeds, --atp-seeds, --distance and --checkpoint must be positive")
    full = (
        args.conditions == "all"
        and args.seeds == len(SEEDS)
        and args.seed_start == SEEDS[0]
        and args.distance == TARGET_DISTANCE
        and args.checkpoint == CHECKPOINT
        and args.fit_low == FIT_LOW
        and args.n_boot >= 1000
        and args.atp_seeds == len(ATP_SEEDS)
        and args.atp_ticks == ATP_TICKS
    )
    if args.out.resolve() == DEFAULT_OUT.resolve() and not full:
        parser.error(f"a partial run must not overwrite the committed tables in {DEFAULT_OUT}: give --out")
    conditions = CONDITION_SETS[args.conditions]
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    atp_seeds = list(range(1, args.atp_seeds + 1))
    started = time.time()
    result = characterise(
        conditions, seeds, args.distance, args.checkpoint, args.fit_low, args.tick_cap, args.workers, args.n_boot,
        atp_seeds, args.atp_ticks,
    )
    runtime = time.time() - started
    given = list(argv) if argv is not None else sys.argv[1:]
    meta = {
        "command": "python3 -m experiments.odometry_characterisation " + " ".join(given),
        "commit": _commit_sha(),
        "conditions": [c.__dict__ for c in conditions],
        "seeds": seeds,
        "target_distance": args.distance,
        "checkpoint": args.checkpoint,
        "fit_range": [args.fit_low, args.distance],
        "bounds": list(BOUNDS),
        "tick_cap": args.tick_cap,
        "turning_forward_bias": TURNING_FORWARD_BIAS,
        "n_boot": args.n_boot,
        "atp": {
            "seeds": atp_seeds, "ticks": args.atp_ticks, "transient": ATP_TRANSIENT,
            "speed": RESEARCH_SPEED, "turn": RESEARCH_TURN,
        },
        "full": full,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "runtime_s": round(runtime, 1),
        "workers": args.workers if args.workers is not None else os.cpu_count(),
    }
    paths = write_outputs(args.out, result, meta)
    print_summary(result)
    print(f"wrote {', '.join(p.name for p in paths)} to {args.out} in {runtime:.1f} s")
    return result


if __name__ == "__main__":
    main()
