"""Couplings that exist in code but do nothing at the defaults.

Claims (criticality, neuromodulation and sleep-energy audits, 2026-10-03):

* ``BasalGangliaConfig.criticality_gain`` defaults to 0.0, so the field has no
  causal effect; with it at 1.0 the default field is a near-constant ~0.91-0.93
  multiplier on ``vision_gain`` (near_critical_gain of a kappa near 0.9), not a
  state-dependent gain. ``vision_gain`` multiplies target closeness, so in the
  barren default world even that multiplier changes nothing; in the beacon
  protocol contact (tick 9) precedes the first kappa computation (~tick 88),
  so the gain is exactly the 1.0 placeholder; and over the 324-tick foraging
  run the ~0.93 multiplier flips no decision at seed 1.
* ``TRNGate.trn_state``'s ``kappa > 1.1 -> NARROW`` branch never fires at the
  default coupling. The audit put the first coupling at which it fires at
  ~0.40 (converged kappa); the within-episode transient crosses 1.1 already at
  0.35. Either way, with pacing off the agent is almost never at ATP >= 0.55
  after warm-up, so the branch cannot change the gate state; it only matters
  with pacing on (ATP held high), where it narrows the gate for the whole run.
* The ``neuromod`` RNG stream is allocated in ``Engine.__init__`` but never
  drawn from.
"""

from __future__ import annotations

from brain.systems.criticality import CriticalityConfig, near_critical_gain
from core.config import BasalGangliaConfig, EngineConfig
from core.engine import Engine
from experiments.protocols import BeaconProtocol, ForagingProtocol
from tools.probes._common import Results, budget, probe_main, run_engine, run_protocol

COUPLINGS = (0.25, 0.30, 0.35, 0.40, 0.45)


def _paced(cfg: EngineConfig) -> EngineConfig:
    cfg.basal_ganglia.pace_rest_bonus = 5.0
    cfg.basal_ganglia.pace_low = 0.6
    return cfg


def run(scale: float = 1.0) -> Results:
    ticks = budget(3000, scale, 100)
    out: Results = {"config": f"seed 1, default barren world unless stated, {ticks} ticks", "ticks": ticks}

    # (1) criticality gain at defaults vs switched on.
    base, _ = run_engine(1, ticks)
    gains = [near_critical_gain(td.kappa) for td in base]
    warm = next((i for i, td in enumerate(base) if td.kappa != 1.0), len(base))
    out["criticality_gain_default"] = EngineConfig().basal_ganglia.criticality_gain
    out["crit_gain_multiplier_min_max_after_warmup"] = (
        [min(gains[warm:]), max(gains[warm:])] if warm < len(gains) else None
    )
    on_cfg = EngineConfig(basal_ganglia=BasalGangliaConfig(criticality_gain=1.0))
    on, _ = run_engine(1, ticks, on_cfg)
    out["criticality_gain_1_changes_positions_barren_world"] = [t.pos for t in base] != [t.pos for t in on]
    task_ticks = budget(1500, scale, 30)
    for name, proto in (("beacon", BeaconProtocol), ("foraging", ForagingProtocol)):
        rows0, _ = run_protocol(proto(), 1, task_ticks)
        rows1, _ = run_protocol(proto(), 1, task_ticks, on_cfg)
        out[f"{name}_ticks_gain0_vs_gain1"] = [len(rows0), len(rows1)]
        out[f"{name}_kappa_at_last_tick"] = rows0[-1].kappa
        out[f"criticality_gain_1_changes_positions_{name}"] = [t.pos for t in rows0] != [t.pos for t in rows1]

    # (2) kappa > 1.1 TRN branch vs coupling, pacing off and on.
    for paced in (False, True):
        sweep = {}
        for c in COUPLINGS:
            cfg = EngineConfig(criticality=CriticalityConfig(coupling=c))
            if paced:
                cfg = _paced(cfg)
            trace, _ = run_engine(1, ticks, cfg)
            sweep[f"c{c:.2f}"] = {
                "kappa_final": trace[-1].kappa,
                "ticks_kappa_gt_1_1": sum(1 for t in trace if t.kappa > 1.1),
                "ticks_gate_narrowed_by_kappa": sum(
                    1 for t in trace if t.trn_state == "NARROW" and t.atp >= 0.55 and t.kappa > 1.1
                ),
            }
        tag = "paced_0.6" if paced else "pacing_off"
        out[f"trn_kappa_branch_by_coupling_{tag}"] = sweep
        out[f"smallest_coupling_with_kappa_gt_1_1_{tag}"] = next(
            (c for c in COUPLINGS if sweep[f"c{c:.2f}"]["ticks_kappa_gt_1_1"] > 0), None
        )
        out[f"smallest_coupling_where_kappa_narrows_gate_{tag}"] = next(
            (c for c in COUPLINGS if sweep[f"c{c:.2f}"]["ticks_gate_narrowed_by_kappa"] > 0), None
        )

    # (3) the neuromod RNG stream is never drawn.
    engine = Engine(seed=1)
    before = engine.streams["neuromod"]._random.getstate()
    engine.run(ticks, reset=True)
    out["neuromod_stream_state_unchanged_after_run"] = engine.streams["neuromod"]._random.getstate() == before
    return out


main = probe_main(run, "couplings that are dormant at engine defaults")

if __name__ == "__main__":
    main()
