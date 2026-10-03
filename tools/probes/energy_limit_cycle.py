"""The default (pacing-off) agent lives on the energy limit cycle.

Claims (sleep-energy audit, 2026-10-03):

* Once glycogen is exhausted the store is one linear tank, atp += 0.015 -
  0.04 * demand per tick (demand 0.2 + 0.8 |thrust|), balanced at demand
  0.375 (mean thrust ~0.22); FORWARD costs 0.040/tick, TURN 0.0176, REST
  0.008. From full at full thrust ATP crosses 0.30 after 47 ticks; at rest it
  sits at 1.0 (glycogen pinned at 0.03).
* In the core engine (pacing off) over 3000 open-field ticks at seed 1: gate
  CLOSED 2542 / NARROW 399 / OPEN 59; 51 microsleeps (1270 ticks asleep) and
  1272 awake ticks with the gate CLOSED (ATP < 0.35); mean ATP 0.353; sleeps
  recur every ~57 ticks (awake gap median 32, min 24). Headless open-field,
  t-maze and survival assays mostly measure this cycle.
"""

from __future__ import annotations

from core.config import AstrocyteConfig
from core.physiology import Astrocyte
from tools.probes._common import (
    Results,
    budget,
    mean,
    median,
    microsleep_bouts,
    microsleep_onsets,
    probe_main,
    run_engine,
    trn_state_counts,
)


def run(scale: float = 1.0) -> Results:
    ticks = budget(3000, scale, 100)
    c = AstrocyteConfig()
    out: Results = {"config": f"AstrocyteConfig defaults; seed 1 barren world, pacing off, {ticks} ticks"}
    # Analytic constants of the exhausted-glycogen regime.
    recharge = c.glycogen_regen * c.glycogen_to_atp_yield
    out["atp_gain_per_tick_when_glycogen_exhausted"] = recharge
    out["demand_balancing_recharge"] = recharge / c.atp_cost
    out["cost_per_tick_FORWARD_TURN_REST"] = [
        c.atp_cost * (c.rest_demand + c.motion_demand * t) - recharge for t in (1.0, 0.3, 0.0)
    ]

    a = Astrocyte()
    for _ in range(budget(2000, scale, 200)):
        a.tick(demand=c.rest_demand)
    out["rest_steady_state_atp_glycogen"] = [a.atp, a.glycogen]
    a = Astrocyte()
    n = 0
    while a.atp >= 0.30 and n < 10000:
        a.tick(demand=c.rest_demand + c.motion_demand)
        n += 1
    out["ticks_to_atp_below_0_30_at_full_thrust_from_fresh"] = n

    trace, _ = run_engine(1, ticks)
    states = trn_state_counts(trace)
    bouts, gaps = microsleep_bouts(trace)
    atps = [td.atp for td in trace]
    out["trn_states"] = states
    out["microsleep_ticks"] = sum(1 for td in trace if td.microsleep_active)
    out["microsleep_onsets"] = microsleep_onsets(trace)
    out["complete_microsleep_bouts"] = len(bouts)
    out["awake_ticks_gate_CLOSED"] = sum(1 for td in trace if not td.microsleep_active and td.trn_state == "CLOSED")
    out["gate_CLOSED_frac"] = states["CLOSED"] / len(trace)
    out["atp_mean_min_max"] = [mean(atps), min(atps), max(atps)]
    out["awake_gap_between_sleeps_median_min"] = [median(gaps), min(gaps)] if gaps else None
    out["actions"] = {
        name: sum(1 for td in trace if td.action_name == name) for name in ("FORWARD", "TURN_LEFT", "TURN_RIGHT", "REST")
    }
    out["mean_logged_thrust"] = mean([td.action_thrust for td in trace])
    return out


main = probe_main(run, "energy limit cycle of the default agent")

if __name__ == "__main__":
    main()
