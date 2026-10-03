"""What open-field motion looks like: step lengths are a physiology artefact.

Claims (sensors-world-tasks audit, 2026-10-03, scratch probe.py):

* Over 3000 open-field ticks (seed 1337, pacing off) 42% of steps are zero
  and the mean step is 0.088 of the nominal 1.0 m FORWARD (max 0.985), because
  the astrocyte's energy_scale multiplies thrust and turn in ``World.step``.
* The agent is anti-thigmotactic: 85% of ticks in the central 10 x 10 m, 2.9%
  within 1 m of a wall (wall avoidance acts at 12 m range), the inverse of
  real rats.
* The open-field protocol score is a large negative number (-2911 at 3000
  ticks) because it subtracts 2 per microsleep tick.
"""

from __future__ import annotations

import math

from experiments.protocols import OpenFieldProtocol
from tools.probes._common import Results, budget, mean, probe_main, run_protocol


def run(scale: float = 1.0) -> Results:
    ticks = budget(3000, scale, 100)
    proto = OpenFieldProtocol()
    rows, _ = run_protocol(proto, 1337, ticks)
    poss = [r.pos for r in rows]
    steps = [math.hypot(poss[i][0] - poss[i - 1][0], poss[i][1] - poss[i - 1][1]) for i in range(1, len(poss))]
    summary = proto.summarize()
    out: Results = {
        "config": f"OpenFieldProtocol, seed 1337, EngineConfig() defaults (pacing off), {ticks} ticks, 20x20 m box",
        "step_mean_max": [mean(steps), max(steps)],
        "frac_zero_steps": sum(1 for s in steps if s == 0.0) / len(steps),
        "frac_steps_ge_0_9": sum(1 for s in steps if s >= 0.9) / len(steps),
        "frac_ticks_within_1m_of_wall": sum(1 for x, y in poss if max(abs(x), abs(y)) >= 9.0) / len(poss),
        "frac_ticks_in_central_10x10": sum(1 for x, y in poss if max(abs(x), abs(y)) <= 5.0) / len(poss),
        "distance_travelled": summary["distance_travelled"],
        "microsleep_ticks": summary["microsleep_count"],
        "protocol_score": summary["score"],
    }
    return out


main = probe_main(run, "open-field motion statistics")

if __name__ == "__main__":
    main()
