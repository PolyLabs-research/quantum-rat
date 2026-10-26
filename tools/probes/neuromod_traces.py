"""The four modulator traces in the stock headless protocols.

Claims (neuromodulation audit, 2026-10-03, scratch trace_stats.py; 1500
ticks, seeds 1-2):

* open_field and survival_arena_toy at noise 0: DA == 0.5 and 5HT == 0.5 on 100%
  of ticks (no reward ever), ACh == 1 on 63% of ticks, NE mean 0.32.
* At sensors.noise 0.03: novelty == 1 on 100% of ticks in every scenario, so
  ACh is pinned at 1.0 and NE sits at 0.50-0.51; pain > 0 on ~50% of ticks
  purely from clamped uniform noise, giving DA a +/-0.01 jitter around 0.5.
* foraging: DA < 0.5 on 64-68% of ticks (the reward EMA goes positive, so
  every zero-reward step is a "disappointment") and hits exactly 1.0 on
  contact; 5HT ranges 0.33-0.72. beacon: DA saturates at 1.0 on contact.
"""

from __future__ import annotations

from experiments.protocols import BeaconProtocol, ForagingProtocol, OpenFieldProtocol, SurvivalArenaProtocol
from tools.probes._common import Results, budget, frac, mean, noisy_config, probe_main, run_protocol

PROTOCOLS = (OpenFieldProtocol, BeaconProtocol, ForagingProtocol, SurvivalArenaProtocol)
SEEDS = (1, 2)
EPS = 1e-9


def run(scale: float = 1.0) -> Results:
    ticks = budget(1500, scale, 60)
    out: Results = {"config": f"stock protocols, {ticks} ticks max, seeds {SEEDS}, sensors.noise 0 vs 0.03"}
    for proto_cls in PROTOCOLS:
        for noise in (0.0, 0.03):
            for seed in SEEDS:
                rows, eng = run_protocol(proto_cls(), seed, ticks, noisy_config(noise))
                da = [r.neuromodulators["DA"] for r in rows]
                ne = [r.neuromodulators["NE"] for r in rows]
                ach = [r.neuromodulators["ACh"] for r in rows]
                ht = [r.neuromodulators["5HT"] for r in rows]
                out[f"{proto_cls.name}_noise{noise}_seed{seed}"] = {
                    "n": len(rows),
                    "novelty_eq_1": frac([r.wm_novelty for r in rows], lambda x: x == 1.0),
                    "ACh_mean": mean(ach),
                    "DA_eq_0.5": frac(da, lambda x: abs(x - 0.5) < EPS),
                    "DA_lt_0.5": frac(da, lambda x: x < 0.5 - EPS),
                    "DA_min_max": [min(da), max(da)],
                    "DA_eq_1.0": frac(da, lambda x: x >= 1.0),
                    "NE_mean": mean(ne),
                    "pain_gt_0": frac([r.obs_pain for r in rows], lambda x: x > 0),
                    "5HT_min_max": [min(ht), max(ht)],
                    "reward_nonzero": frac([r.reward for r in rows], lambda x: abs(x) > EPS),
                    "expected_reward_final": eng.neuromod_system.expected_reward,
                }
    return out


main = probe_main(run, "neuromodulator traces in the stock protocols")

if __name__ == "__main__":
    main()
