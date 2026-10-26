"""Realised speed under the declared units: is the calibration (0.2 s per tick, 0.1 m per unit) sane?

docs/research_plan.md section 5, M0b item 6, says to freeze the physical units
(``core.config.UnitsConfig``, docs/units.md) only after measuring, under the
research profile on the open-field protocol, the realised mean moving-tick
speed and the fraction of immobile ticks against rat track-running speeds
(0.2-0.6 m/s while running) and stopping-period durations (stops at reward
wells last a few seconds). M0a's energy freeze removed the ATP throttle on the
step, but the arbiter's REST ticks and the 0.3-unit TURN steps still make the
realised speed differ from the nominal FORWARD 0.5 m/s.

Measured here, per seed (1-4) and pooled over 3000 open-field ticks each, for
``EngineConfig.research()`` and, for contrast, ``EngineConfig.legacy()``:

* the mean speed over moving ticks in m/s, a moving tick being one whose step
  is > 0.05 units (0.5 cm: separates the 0.3 and 1.0 steps from REST and from
  the shortest wall-clamped steps), and the mean speed over all ticks;
* the fraction of immobile ticks and the stop bouts, i.e. runs of consecutive
  immobile ticks (complete runs only: a run still going when the trace ends is
  not counted): their number, median and max in seconds;
* the fraction of ticks with the body at a wall (|x| or |y| at the bound; the
  box clamps it there);
* the realised heading change: the fraction of ticks that turn (|dh| > 1e-9
  rad), their mean |dh| in rad/s, and how many distinct |dh| values occur with
  their min and max, rounded to 6 decimals (the research profile shows one value,
  TURN_STEP 0.3, the heading differences carrying floating-point rounding).

The true heading is read from ``engine.context.heading`` tick by tick (TickData
logs only the estimate); positions are ``TickData.pos``. The step on tick t is
the displacement from the position logged at t-1 to the one at t, so a run of
n ticks gives n-1 steps and heading changes.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

from brain.systems.spatial import wrap_angle
from core.config import EngineConfig, UnitsConfig
from core.engine import Engine
from experiments.protocols import OpenFieldProtocol
from tools.probes._common import Results, budget, frac, mean, median, probe_main

SEEDS = (1, 2, 3, 4)
MOVING_THRESHOLD_UNITS = 0.05
TURN_EPS = 1e-9

Series = Tuple[List[float], List[float], List[bool]]  # steps, heading changes, at-wall flags


def _open_field_series(config: EngineConfig, seed: int, ticks: int) -> Series:
    engine = Engine(seed=seed, config=config)
    proto = OpenFieldProtocol()
    proto.setup(engine)
    poss: List[Tuple[float, float]] = []
    headings: List[float] = []
    for i in range(ticks):
        td = engine.run(1, reset=(i == 0))[0]
        proto.on_tick(engine, td, i)
        poss.append(td.pos)
        headings.append(engine.context.heading)
    bx, by = config.world.bounds
    steps = [math.hypot(poss[t][0] - poss[t - 1][0], poss[t][1] - poss[t - 1][1]) for t in range(1, ticks)]
    turns = [wrap_angle(headings[t] - headings[t - 1]) for t in range(1, ticks)]
    at_wall = [abs(x) >= bx or abs(y) >= by for x, y in poss]
    return steps, turns, at_wall


def _stop_bouts(steps: Sequence[float]) -> List[int]:
    """Lengths (ticks) of the complete runs of consecutive immobile ticks."""
    bouts: List[int] = []
    cur = 0
    for s in steps:
        if s > MOVING_THRESHOLD_UNITS:
            if cur:
                bouts.append(cur)
            cur = 0
        else:
            cur += 1
    return bouts  # a run still going at the end was cut by the run, not the model: left out


def _summarise(runs: Sequence[Series], units: UnitsConfig) -> Dict[str, object]:
    steps = [s for run in runs for s in run[0]]
    turns = [d for run in runs for d in run[1]]
    at_wall = [w for run in runs for w in run[2]]
    bouts = [b for run in runs for b in _stop_bouts(run[0])]
    moving = [s for s in steps if s > MOVING_THRESHOLD_UNITS]
    turning = [abs(d) for d in turns if abs(d) > TURN_EPS]
    distinct = sorted({round(d, 6) for d in turning})
    return {
        "ticks": len(steps) + len(runs),
        "mean_moving_speed_m_s": units.metres_per_second(mean(moving)),
        "mean_speed_all_ticks_m_s": units.metres_per_second(mean(steps)),
        "frac_immobile": frac(steps, lambda s: s <= MOVING_THRESHOLD_UNITS),
        "stop_bouts": len(bouts),
        "stop_bout_median_s": units.seconds(median(bouts)),
        "stop_bout_max_s": units.seconds(max(bouts)) if bouts else float("nan"),
        "frac_at_wall": frac(at_wall, bool),
        "frac_turning": frac(turns, lambda d: abs(d) > TURN_EPS),
        "mean_turn_rad_s": units.radians_per_second(mean(turning)),
        "distinct_abs_turns": len(distinct),
        "abs_turn_min_max_rad": [min(distinct), max(distinct)] if distinct else [float("nan"), float("nan")],
    }


def run(scale: float = 1.0) -> Results:
    ticks = budget(3000, scale, 100)
    units = EngineConfig().units
    out: Results = {
        "config": (
            f"OpenFieldProtocol, seeds {SEEDS}, {ticks} ticks each, EngineConfig.research() and "
            f"EngineConfig.legacy() (pacing off), 20x20 unit box"
        ),
        "units": (
            f"dt_s {units.dt_s}, metres_per_unit {units.metres_per_unit}: nominal FORWARD "
            f"{units.metres_per_second(1.0)} m/s, TURN {units.metres_per_second(0.3)} m/s and "
            f"{units.radians_per_second(0.3)} rad/s; moving tick = step > {MOVING_THRESHOLD_UNITS} units"
        ),
        "reference": (
            "rats: 0.2-0.6 m/s while running a track, stops at reward wells of a few seconds "
            "(docs/research_plan.md section 5 item 6)"
        ),
    }
    for label, config in (("research", EngineConfig.research()), ("legacy", EngineConfig.legacy())):
        runs = [_open_field_series(config, seed, ticks) for seed in SEEDS]
        out[f"{label}_by_seed"] = {seed: _summarise([series], units) for seed, series in zip(SEEDS, runs)}
        out[f"{label}_pooled"] = _summarise(runs, units)
    return out


main = probe_main(run, "realised speed under the declared units")

if __name__ == "__main__":
    main()
