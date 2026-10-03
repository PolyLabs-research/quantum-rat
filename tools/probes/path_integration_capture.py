"""Path integration is either perfect or crippled by the TRN gate, never noisy.

Claims (spatial audit, 2026-10-03, scratch gate_cause.py and drift.py):

* At engine defaults (no pacing) over 3000 open-field ticks the gate was
  CLOSED on 2542 and NARROW on 399 ticks (OPEN 2%), driven entirely by
  ATP < 0.55 (kappa never exceeded 1.1); the integrator captured 71.6 m of a
  264.3 m true path (27%), ending 22.8 m from the true position with a 2.17 rad
  heading error.
* With gate-safe pacing (pace_rest_bonus 5, pace_low 0.6) the error is exactly
  0.000 m: egomotion is noiseless ground truth, so the gate is the only source
  of "drift".
* Seeds 1-4 give identical numbers at noise 0 (see seed_pseudoreplication).
"""

from __future__ import annotations

import math

from core.config import EngineConfig
from tools.probes._common import Results, budget, path_length, probe_main, run_engine, trn_state_counts

SEEDS = (1, 2, 3, 4)


def config(pace_low):
    cfg = EngineConfig()
    if pace_low is not None:
        cfg.basal_ganglia.pace_rest_bonus = 5.0
        cfg.basal_ganglia.pace_low = pace_low
    return cfg


def measure(seed: int, ticks: int, pace_low) -> dict:
    trace, eng = run_engine(seed, ticks, config(pace_low))
    states = trn_state_counts(trace)
    errs = [math.hypot(td.grid_x - td.pos[0], td.grid_y - td.pos[1]) for td in trace]
    true_path = path_length([td.pos for td in trace])
    est_path = path_length([(td.grid_x, td.grid_y) for td in trace])
    hd_err = abs((trace[-1].hd_angle - eng.agent.heading + math.pi) % (2 * math.pi) - math.pi)
    return {
        "states": states,
        "gated_frac": (states["NARROW"] + states["CLOSED"]) / len(trace),
        "ticks_atp_lt_0_55": sum(1 for td in trace if td.atp < 0.55),
        "ticks_kappa_gt_1_1": sum(1 for td in trace if td.kappa > 1.1),
        "true_path_m": true_path,
        "estimated_path_m": est_path,
        "captured_frac": est_path / true_path if true_path else float("nan"),
        "final_error_m": errs[-1],
        "max_error_m": max(errs),
        "final_heading_error_rad": hd_err,
    }


def run(scale: float = 1.0) -> Results:
    ticks = budget(3000, scale, 100)
    out: Results = {"config": f"barren default world, {ticks} ticks, seeds {SEEDS}; pacing off vs pace_low 0.6 (bonus 5)"}
    for pace_low in (None, 0.6):
        tag = "pacing_off" if pace_low is None else f"pace_low_{pace_low}"
        rows = [measure(s, ticks, pace_low) for s in SEEDS]
        out[f"{tag}_seed1"] = rows[0]
        out[f"{tag}_final_error_m_by_seed"] = [r["final_error_m"] for r in rows]
        out[f"{tag}_captured_frac_by_seed"] = [r["captured_frac"] for r in rows]
    return out


main = probe_main(run, "path-integration capture under the TRN gate")

if __name__ == "__main__":
    main()
