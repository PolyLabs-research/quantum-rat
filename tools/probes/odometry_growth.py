"""Path-integration error growth under the research odometry values, and its decorrelation from ATP.

Added for Milestone 1 (docs/research_plan.md section 4, M1; docs/odometry.md;
the full 30-seed characterisation is ``experiments.odometry_characterisation``,
whose current tables live in docs/data/m2a/odometry, the M1 record in
docs/data/m1). Re-recorded at M2a, when the research profile's forward range
became 2.0 and the novelty bit left action selection. Not an audit claim.

Claims (docs/odometry.md, the M2a section):

* In an open barren world the research profile's walk is a straight line (a
  TURN is about an exp(-8) softmax draw per channel when nothing is in view,
  since M2a decoupled the novelty bit), so over 2,000 units of travel: speed
  noise 0.05 alone gives a log-log slope of error against distance near 0.5,
  the law of a zero-mean error, with a wide per-seed spread at 4 seeds (0.73
  here, 0.48 [0.36, 0.61] over 30 seeds) and an along-track bias per unit of
  0 within sampling error; under the legacy forward range of 1.0 (the M1
  record) the same noise read slope 0.97 and a bias of -0.020 per unit,
  because a FORWARD step sat at the top of the range and only slowing errors
  survived the clamp; turn noise 0.01 rad alone gives the integrated heading
  random walk, 1.73 at these 4 seeds (one seed's lateral error is one
  realisation; 1.48 [1.31, 1.63] over 30 seeds); both together read like turn
  noise alone.
* Legacy profile, default barren box, odometry noise at the research values,
  3,000 ticks: with ``spatial.gate_scales_egomotion`` on, the relative step
  error on moving ticks (|estimated step| / |true step| - 1) tracks ATP
  (r 0.87: the gate freezes the estimate when ATP is low); with it off
  |r| < 0.08 (the residual is the wall-sliding under-read of 14 clamped TURN
  ticks, present with zero noise too, docs/odometry.md). The error itself
  correlates with ATP at about -0.23 under both flags over all ticks, a
  shared trend of ATP's initial decay and the growing error, and within
  +-0.08 once the first 200 ticks are dropped. The legacy profile keeps the
  forward range of 1.0, so these numbers are the M1 ones.

``--scale`` multiplies the distance travelled (floor 100 units) and the ATP
tick budget (floor 100 ticks); at a small scale the "after transient"
correlation is NaN (no ticks left after the 200-tick transient) and the fit
runs over the few checkpoints between 50 units and the scaled distance.
"""

from __future__ import annotations

from typing import List

from experiments.odometry_characterisation import (
    ATP_TICKS,
    BOUNDS,
    CHECKPOINT,
    FIT_LOW,
    NAMED_CONDITIONS,
    RESEARCH_SPEED,
    RESEARCH_TURN,
    TARGET_DISTANCE,
    SeedRun,
    atp_decorrelation,
    fit_condition,
    run_seed,
)
from tools.probes._common import Results, budget, probe_main

SEEDS = (1, 2, 3, 4)


def run(scale: float = 1.0) -> Results:
    distance = float(budget(int(TARGET_DISTANCE), scale, 100))
    atp_ticks = budget(ATP_TICKS, scale, 100)
    fit_range = (FIT_LOW, distance)
    out: Results = {
        "config": (
            f"EngineConfig.research() in a {2 * BOUNDS[0]:.0f}-unit barren box (no wall is reached), seeds {SEEDS}, "
            f"each run to {distance:.0f} units of travel, checkpoints every {CHECKPOINT:.0f} units, log-log fit of the "
            f"mean error over [{FIT_LOW:.0f}, {distance:.0f}]; ATP: legacy profile, 20x20 box, odometry "
            f"{RESEARCH_SPEED} / {RESEARCH_TURN} rad, {atp_ticks} ticks, gate_scales_egomotion on and off"
        ),
        "expectation": (
            "zero-mean speed error: slope 0.5 and an along-track bias of 0 (the research forward range of 2.0 "
            "clips nothing; under the legacy range of 1.0 the clamp turned it into a shortfall of 0.02 per unit "
            "and slope 1.0); heading random walk on a straight walk: 1.5 or above"
        ),
    }
    for condition in NAMED_CONDITIONS:
        runs: List[SeedRun] = [run_seed(condition, seed, distance) for seed in SEEDS]
        fit = fit_condition(condition, runs, fit_range)
        name = condition.name
        out[f"{name}_slope"] = fit["slope"]
        out[f"{name}_seed_slope_min_max"] = [fit["seed_slope_min"], fit["seed_slope_max"]]
        out[f"{name}_ticks_by_seed"] = [r.ticks for r in runs]
        out[f"{name}_final_error_by_seed"] = [r.final_pos_err for r in runs]
        out[f"{name}_final_hd_error_by_seed"] = [r.final_hd_err for r in runs]
        out[f"{name}_bias_per_unit_by_seed"] = [r.bias_per_unit for r in runs]
        first = runs[0]
        out[f"{name}_actions_seed1"] = {"FORWARD": first.forward_ticks, "TURN": first.turn_ticks, "REST": first.rest_ticks}
    for flag in (True, False):
        rows = [atp_decorrelation(seed, flag, atp_ticks) for seed in SEEDS]
        tag = "gate_on" if flag else "gate_off"
        out[f"{tag}_r_step_error_by_seed"] = [r["r_step_error"] for r in rows]
        out[f"{tag}_r_error_by_seed"] = [r["r_error"] for r in rows]
        out[f"{tag}_r_error_after_transient_by_seed"] = [r["r_error_after_transient"] for r in rows]
        out[f"{tag}_r_error_increment_by_seed"] = [r["r_error_increment"] for r in rows]
        out[f"{tag}_final_error_by_seed"] = [r["final_error"] for r in rows]
    return out


main = probe_main(run, "odometry error growth and ATP decorrelation")

if __name__ == "__main__":
    main()
