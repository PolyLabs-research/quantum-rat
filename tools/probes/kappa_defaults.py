"""What kappa does at engine defaults, and the reconciliation of two audit numbers.

Claims (criticality audit and sleep-energy audit, 2026-10-03):

* The criticality audit said kappa at defaults (coupling 0.25, 16x16, exponent
  1.5) "converges to 0.905-0.914 and stays there" and that over 3000 engine
  ticks "max kappa is the 1.0 placeholder". The sleep-energy audit said kappa
  was "in [0.917, 1.056] over 3000 ticks at seed 1". Both are right about their
  own run: the first number is the long-run (20,000-tick, 4000-avalanche
  history) value of the standalone field at seed 1337; the second is the
  within-episode transient at seed 1, where the first few hundred avalanches
  carry kappa above 1 before the buffer fills. This probe runs both.
* kappa is pinned at exactly 1.0 until 20 avalanches have completed (62 ticks
  at seed 1337), then drops to ~0.9.
* kappa never exceeds 1.1 at defaults, so ``TRNGate.trn_state``'s kappa branch
  never fires (see also dormant_couplings).
* The kappa series is a function of (seed, tick) only: two engines with the
  same seed and different behavioural configs give bit-identical kappa series
  while their trajectories diverge.
"""

from __future__ import annotations

from brain.systems.criticality import CriticalityField, near_critical_gain
from core.config import BasalGangliaConfig, EngineConfig
from core.rng import spawn_streams
from tools.probes._common import Results, budget, probe_main, run_engine

SEEDS = (1, 2, 3, 4)


def run(scale: float = 1.0) -> Results:
    ticks = budget(3000, scale, 100)
    out: Results = {
        "config": "EngineConfig() defaults: coupling 0.25, 16x16 torus, reference exponent 1.5, "
        "kappa after >= 20 avalanches, 4000-avalanche history; default barren world, sensors.noise 0",
        "engine_ticks": ticks,
    }
    per_seed = {}
    for seed in SEEDS:
        trace, _ = run_engine(seed, ticks)
        ks = [td.kappa for td in trace]
        first = next((i for i, k in enumerate(ks) if k != 1.0), None)
        computed = ks[first:] if first is not None else []
        per_seed[seed] = {
            "first_tick_kappa_computed": first,
            "min": min(ks),
            "max_including_placeholder": max(ks),
            "max_after_warmup": max(computed) if computed else None,
            "final": ks[-1],
            "ticks_kappa_gt_1_1": sum(1 for k in ks if k > 1.1),
            "avalanches": sum(1 for td in trace if td.avalanche_size > 0),
        }
    out["engine_kappa_by_seed"] = per_seed
    mins = [v["min"] for v in per_seed.values()]
    maxs = [v["max_after_warmup"] for v in per_seed.values() if v["max_after_warmup"] is not None]
    out["engine_kappa_range_over_seeds_after_warmup"] = [min(mins), max(maxs)] if maxs else None
    out["engine_ticks_kappa_gt_1_1_total"] = sum(v["ticks_kappa_gt_1_1"] for v in per_seed.values())

    # Standalone field, long run (the criticality audit's convergence number).
    long_ticks = budget(20000, scale, 300)
    field = CriticalityField(spawn_streams(seed=1337, names=["criticality"])["criticality"])
    warm = 0
    while field.kappa == 1.0 and warm < long_ticks:
        field.step()
        warm += 1
    out["standalone_seed1337_ticks_until_kappa_first_computed"] = warm
    samples = []
    every = max(1, long_ticks // 10)
    for i in range(long_ticks):
        field.step()
        if (i + 1) % every == 0:
            samples.append(round(field.kappa, 4))
    out["standalone_seed1337_long_run_ticks"] = long_ticks
    out["standalone_seed1337_kappa_samples"] = samples
    out["standalone_seed1337_kappa_final"] = field.kappa
    out["standalone_seed1337_avalanches_in_history"] = len(field.avalanche_sizes)
    out["near_critical_gain_at_final_kappa"] = near_critical_gain(field.kappa)

    # Behaviour independence: same seed, different behavioural config.
    a, _ = run_engine(7, ticks)
    b, _ = run_engine(
        7, ticks, EngineConfig(basal_ganglia=BasalGangliaConfig(forward_bias=0.1, value_gain=3.0, criticality_gain=1.0))
    )
    out["seed7_kappa_series_identical_across_behavioural_configs"] = [t.kappa for t in a] == [t.kappa for t in b]
    out["seed7_positions_identical_across_behavioural_configs"] = [t.pos for t in a] == [t.pos for t in b]

    lo, hi = out["engine_kappa_range_over_seeds_after_warmup"] or (float("nan"), float("nan"))
    out["reconciled"] = (
        f"At defaults kappa is 1.0 (placeholder) for the first ~60 ticks, then a seed-dependent transient "
        f"within [{lo:.3f}, {hi:.3f}] over {ticks} engine ticks (seeds {SEEDS}), settling toward "
        f"{out['standalone_seed1337_kappa_final']:.3f} once the 4000-avalanche history fills (~16,000 ticks); "
        f"it never exceeds 1.1, so the TRN kappa branch is dead at defaults."
    )
    return out


main = probe_main(run, "kappa at engine defaults (criticality vs sleep-energy audit reconciliation)")

if __name__ == "__main__":
    main()
