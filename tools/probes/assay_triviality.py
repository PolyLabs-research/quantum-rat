"""The headless water-maze and T-maze protocols are solved by walking forward.

Claims (sensors-world-tasks audit, 2026-10-03, scratch probe.py):

* ``MorrisWaterMazeProtocol`` has no pool, no cues and no platform object in
  the World; the platform is a protocol-side circle at (5, 0) on the start
  heading, reached in 5 ticks by any agent that moves forward. Off-axis
  platforms are reached only by chance: (0, 5) at tick 865, (-5, 5) at 176,
  (5, -5) and (-6, -2) never in 2000 ticks; start heading pi reaches the
  default platform at tick 1804.
* ``TMazeProtocol`` has no T: reward is x >= 5 in the open box, reached in 6
  ticks from the default pose.
* ``thigmotaxis_ticks`` counts distance from the origin >= 8.5 m while the
  agent lives in a square.
"""

from __future__ import annotations

import math

from experiments.protocols import MorrisWaterMazeProtocol, TMazeProtocol
from tools.probes._common import Results, budget, probe_main, run_protocol

PLATFORMS = ((5, 0), (0, 5), (-5, 5), (5, -5), (-6, -2))
HEADINGS = (0.0, math.pi / 2, math.pi)


def run(scale: float = 1.0) -> Results:
    ticks = budget(2000, scale, 50)
    out: Results = {"config": f"seed 1337, EngineConfig() defaults, up to {ticks} ticks per run"}
    for px, py in PLATFORMS:
        proto = MorrisWaterMazeProtocol({"platform_x": px, "platform_y": py})
        run_protocol(proto, 1337, ticks)
        s = proto.summarize()
        out[f"mwm_platform_{px}_{py}"] = {
            "reached": s["platform_reached"],
            "time_to_platform": s["time_to_platform"],
            "thigmotaxis_ticks": s["thigmotaxis_ticks"],
        }
    for h in HEADINGS:
        proto = MorrisWaterMazeProtocol()
        run_protocol(proto, 1337, ticks, heading=h)
        s = proto.summarize()
        out[f"mwm_default_platform_heading_{h:.2f}"] = {
            "reached": s["platform_reached"],
            "time_to_platform": s["time_to_platform"],
        }
    for h in HEADINGS:
        proto = TMazeProtocol()
        run_protocol(proto, 1337, ticks, heading=h)
        s = proto.summarize()
        out[f"tmaze_heading_{h:.2f}"] = {"reached": s["reward_reached"], "time_to_reward": s["time_to_reward"]}
    return out


main = probe_main(run, "triviality of the headless water-maze and T-maze assays")

if __name__ == "__main__":
    main()
