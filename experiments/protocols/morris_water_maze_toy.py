"""Toy water-maze protocol (headless): a platform circle in the open box.

What it is: the agent starts at the origin facing +x, and the protocol scores
the first tick at which its true position comes within ``platform_radius`` of
``(platform_x, platform_y)``, plus the path length and a "thigmotaxis" count of
ticks spent at or beyond 0.85 x ``pool_radius`` from the origin.

What it is not: there is no pool, no wall, no cue and no platform object in
the World, so the agent cannot sense the platform, and there is no probe
trial. With the defaults the platform (5, 0) lies on the start heading and is
reached in 5 ticks by any agent that walks forward; from heading pi it takes
1,804 ticks, and two of five off-axis placements ((5, -5) and (-6, -2)) are
never reached within 2,000 ticks (``python -m tools.probes.assay_triviality``,
recorded in tools/probes/README.md). The thigmotaxis count measures distance
from the origin while the agent lives in a square box.

It is kept as a toy under the legacy profile. The water-maze protocol of the
research programme (a pool, a hidden platform, probe trials) is Milestone 4b
in docs/research_plan.md.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from experiments.protocols.base import Protocol
from metrics.schema import TickData


class MorrisWaterMazeProtocol(Protocol):
    name = "morris_water_maze_toy"

    def __init__(self, config: dict | None = None) -> None:
        cfg = config or {}
        self.pool_r = float(cfg.get("pool_radius", 10.0))
        self.platform_r = float(cfg.get("platform_radius", 1.0))
        # Default platform on east side; callers may override via config.
        self.platform_x = float(cfg.get("platform_x", self.pool_r * 0.5))
        self.platform_y = float(cfg.get("platform_y", 0.0))
        self.path_length = 0.0
        self.time_to_platform = -1
        self.platform_reached = False
        self.thigmotaxis_ticks = 0
        self.ticks_run = 0

    def setup(self, engine: Any) -> None:
        engine.agent.pos = (0.0, 0.0)
        engine.agent.heading = 0.0

    def _distance_to(self, tick: TickData, x: float, y: float) -> float:
        dx = tick.pos[0] - x
        dy = tick.pos[1] - y
        return math.sqrt(dx * dx + dy * dy)

    def on_tick(self, engine: Any, tickdata: TickData, tick_index: int) -> None:
        self.ticks_run += 1
        self.path_length += abs(tickdata.obs_forward_delta)

        # Platform check (a protocol-side circle; nothing in the World).
        if not self.platform_reached:
            if self._distance_to(tickdata, self.platform_x, self.platform_y) <= self.platform_r:
                self.platform_reached = True
                self.time_to_platform = tick_index

        # "Thigmotaxis": distance from the origin, although the box is square.
        dist_center = self._distance_to(tickdata, 0.0, 0.0)
        if dist_center >= 0.85 * self.pool_r:
            self.thigmotaxis_ticks += 1

    def is_done(self, engine: Any, tickdata: TickData, tick_index: int) -> bool:
        return self.platform_reached

    def summarize(self) -> Dict[str, float | int | bool]:
        if self.platform_reached:
            score = 100.0 - 0.05 * self.time_to_platform - 0.1 * self.path_length
        else:
            score = 0.0
        return {
            "ticks_run": self.ticks_run,
            "platform_reached": self.platform_reached,
            "time_to_platform": self.time_to_platform,
            "path_length": self.path_length,
            "thigmotaxis_ticks": self.thigmotaxis_ticks,
            "score": score,
            "pool_radius": self.pool_r,
            "platform_radius": self.platform_r,
            "platform_x": self.platform_x,
            "platform_y": self.platform_y,
        }


__all__ = ["MorrisWaterMazeProtocol"]
