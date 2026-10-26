"""At sensors.noise 0, N seeds are N copies of one behavioural run.

Claims (spatial, sensors and infrastructure audits, 2026-10-03):

* With ``sensors.noise = 0`` (the engine default) no behavioural path draws
  from the RNG: the seed reaches only the criticality lattice, whose kappa
  never crosses a behavioural threshold at defaults, so seeds 1-4 give
  trajectories identical to the last bit. Claims phrased "seeds 1-8 at noise
  0" are one sample, not eight.
* At noise 0.03 the seeds diverge (sensor noise is drawn per tick).
* The kappa series does differ across seeds (it is the only thing that does).
"""

from __future__ import annotations

import math

from tools.probes._common import Results, budget, noisy_config, probe_main, run_engine

SEEDS = (1, 2, 3, 4)


def run(scale: float = 1.0) -> Results:
    ticks = budget(1000, scale, 50)
    out: Results = {"config": f"barren default world, pacing off, {ticks} ticks, seeds {SEEDS}, noise 0 vs 0.03"}
    for noise in (0.0, 0.03):
        traces = [run_engine(s, ticks, noisy_config(noise))[0] for s in SEEDS]
        ref = traces[0]
        max_dev = max(
            math.hypot(t[i].pos[0] - ref[i].pos[0], t[i].pos[1] - ref[i].pos[1])
            for t in traces[1:]
            for i in range(ticks)
        )
        out[f"noise_{noise}"] = {
            "max_position_deviation_from_seed1_m": max_dev,
            "action_sequences_identical": all([td.action_name for td in t] == [td.action_name for td in ref] for t in traces[1:]),
            "final_positions": [t[-1].pos for t in traces],
            "kappa_series_identical": all([td.kappa for td in t] == [td.kappa for td in ref] for t in traces[1:]),
        }
    return out


main = probe_main(run, "seed pseudo-replication at sensors.noise 0")

if __name__ == "__main__":
    main()
