"""Beacon-approach protocol: a visible target the agent must navigate to.

Unlike the other assays, this one places a real, perceivable object in the
World (surfaced to vision as obj_type == "target") and scores on reaching it.
It is the proof that the perception loop is closed: a sighted agent steers to
the beacon, a vision-blind agent does not. The target is placed off the
agent's initial heading so reaching it requires actually sensing it.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from core.world import WorldObject
from experiments.protocols.base import Protocol
from metrics.schema import TickData


class BeaconProtocol(Protocol):
    name = "beacon"

    def __init__(self, config: dict | None = None) -> None:
        cfg = config or {}
        self.target_x = float(cfg.get("target_x", 6.0))
        self.target_y = float(cfg.get("target_y", 3.0))
        self.target_radius = float(cfg.get("target_radius", 1.2))
        self.reached = False
        self.time_to_target = -1
        self.path_length = 0.0
        self.min_distance = math.inf
        self.ticks_run = 0

    def setup(self, engine: Any) -> None:
        engine.agent.pos = (0.0, 0.0)
        engine.agent.heading = 0.0
        engine.world.add_object(
            WorldObject(x=self.target_x, y=self.target_y, radius=self.target_radius, kind="target")
        )

    def _distance(self, tick: TickData) -> float:
        dx = tick.pos[0] - self.target_x
        dy = tick.pos[1] - self.target_y
        return math.sqrt(dx * dx + dy * dy)

    def on_tick(self, engine: Any, tickdata: TickData, tick_index: int) -> None:
        self.ticks_run += 1
        self.path_length += abs(tickdata.obs_forward_delta)
        dist = self._distance(tickdata)
        self.min_distance = min(self.min_distance, dist)
        if not self.reached and dist <= self.target_radius:
            self.reached = True
            self.time_to_target = tick_index

    def is_done(self, engine: Any, tickdata: TickData, tick_index: int) -> bool:
        return self.reached

    def summarize(self) -> Dict[str, float | int | bool]:
        score = max(0.0, 100.0 - self.time_to_target) if self.reached else 0.0
        return {
            "ticks_run": self.ticks_run,
            "reached": self.reached,
            "time_to_target": self.time_to_target,
            "path_length": self.path_length,
            "min_distance": self.min_distance if self.min_distance != math.inf else -1.0,
            "score": score,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "target_radius": self.target_radius,
        }


__all__ = ["BeaconProtocol"]
