"""Multi-landmark foraging: collect several scattered targets.

Unlike the single-target beacon, the arena holds several targets. The agent
forages by sensing and navigating to them one after another; each is removed
(becomes invisible and stops rewarding) once collected. Score is how many are
collected, with a small time penalty. A sighted agent collects them all; a
vision-blind agent collects almost none.

Foraging benefits from a wide field of view (the agent must notice targets off
to the side), so demonstrations use a wider ``SensorConfig`` than the default.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from core.world import WorldObject
from experiments.protocols.base import Protocol
from metrics.schema import TickData

DEFAULT_TARGETS: Tuple[Tuple[float, float], ...] = (
    (4.0, 0.0),
    (0.0, 4.0),
    (-4.0, 2.0),
    (3.0, -4.0),
    (5.0, 3.0),
)


class ForagingProtocol(Protocol):
    name = "foraging"

    def __init__(self, config: dict | None = None) -> None:
        cfg = config or {}
        self.targets: List[Tuple[float, float]] = [tuple(p) for p in cfg.get("targets", DEFAULT_TARGETS)]
        self.radius = float(cfg.get("target_radius", 1.0))
        self.collected = 0
        self.collect_ticks: List[int] = []
        self.ticks_run = 0
        self._objs: List[WorldObject] = []

    def setup(self, engine: Any) -> None:
        engine.agent.pos = (0.0, 0.0)
        engine.agent.heading = 0.0
        self._objs = []
        for (x, y) in self.targets:
            obj = WorldObject(x, y, self.radius, "target")
            engine.world.add_object(obj)
            self._objs.append(obj)

    def on_tick(self, engine: Any, tickdata: TickData, tick_index: int) -> None:
        self.ticks_run += 1
        ax, ay = tickdata.pos
        for obj in self._objs:
            if obj.kind == "target" and math.hypot(ax - obj.x, ay - obj.y) <= self.radius:
                obj.kind = "collected"  # invisible to vision and no longer rewarding
                self.collected += 1
                self.collect_ticks.append(tick_index)

    def is_done(self, engine: Any, tickdata: TickData, tick_index: int) -> bool:
        return self.collected >= len(self.targets)

    def summarize(self) -> Dict[str, Any]:
        n = len(self.targets)
        score = self.collected - 0.005 * self.ticks_run
        return {
            "ticks_run": self.ticks_run,
            "collected": self.collected,
            "n_targets": n,
            "all_collected": self.collected >= n,
            "last_collect_tick": self.collect_ticks[-1] if self.collect_ticks else -1,
            "score": score,
            "target_radius": self.radius,
        }


__all__ = ["ForagingProtocol", "DEFAULT_TARGETS"]
