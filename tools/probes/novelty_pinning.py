"""Working-memory "novelty" is a checksum-changed bit, pinned at 1 under noise.

Claims (sleep-energy, neuromodulation and action-selection audits, 2026-10-03):

* ``WorkingMemory.update`` sets novelty = 1.0 iff sha256(repr(Observation))
  differs from the previous tick's. At sensor noise 0 that means "the agent
  moved": mean novelty 0.613 over 2000 open-field ticks, 0.082 during sleep.
* At the console's noise 0.03 the repr of noisy float ray distances changes
  every tick, so novelty is 1.000 on every tick including sleep; ACh
  (= novelty) is pinned at 1.0 and NE (= 0.5 pain + 0.5 novelty) is floored
  at 0.5, so vision_gain is a constant 0.9 instead of 0.6.
* ``wm_load`` saturates at the 32-entry capacity and is read by nothing.
"""

from __future__ import annotations

from tools.probes._common import Results, budget, frac, mean, noisy_config, probe_main, run_engine


def run(scale: float = 1.0) -> Results:
    ticks = budget(2000, scale, 100)
    out: Results = {"config": f"seed 1, barren world, pacing off, {ticks} ticks, sensors.noise 0 vs 0.03"}
    for noise in (0.0, 0.03):
        trace, _ = run_engine(1, ticks, noisy_config(noise))
        nov = [td.wm_novelty for td in trace]
        asleep = [td.wm_novelty for td in trace if td.microsleep_active]
        moving = [td.wm_novelty for td in trace if td.action_thrust > 0 and not td.microsleep_active]
        out[f"noise_{noise}"] = {
            "novelty_mean": mean(nov),
            "novelty_mean_during_microsleep": mean(asleep),
            "novelty_mean_while_thrusting": mean(moving),
            "frac_ticks_novelty_1": frac(nov, lambda x: x == 1.0),
            "ACh_mean": mean([td.neuromodulators["ACh"] for td in trace]),
            "NE_min": min(td.neuromodulators["NE"] for td in trace),
            "wm_load_max": max(td.wm_load for td in trace),
        }
    return out


main = probe_main(run, "novelty bit pinned by sensor noise")

if __name__ == "__main__":
    main()
