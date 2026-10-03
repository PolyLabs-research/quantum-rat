"""Toy T-maze protocol (headless): a reward line in the open box.

What it is: the agent starts at the origin facing +x, and the protocol scores
the first tick at which its true x position reaches ``reward_threshold``
(default 5.0), then stops five ticks later.

What it is not: there is no T, no arms, no choice point and no walls in the
World; nothing is sensed and no memory is involved. With the defaults the
reward line is reached in 6 ticks by any agent that walks forward (84 ticks
from heading pi/2, 40 from heading pi; ``python -m
tools.probes.assay_triviality``, recorded in tools/probes/README.md).

It is kept as a toy under the legacy profile. The research programme's
trial-structured protocols are described in docs/research_plan.md.
"""

from __future__ import annotations

from typing import Any, Dict

from experiments.protocols.base import Protocol
from metrics.schema import TickData


class TMazeProtocol(Protocol):
    name = "t_maze_toy"

    def __init__(self, config: dict | None = None) -> None:
        cfg = config or {}
        self.reward_threshold = float(cfg.get("reward_threshold", 5.0))
        self.reward_reached = False
        self.time_to_reward = -1
        self.ticks_run = 0
        self.score = 0.0

    def setup(self, engine: Any) -> None:
        engine.agent.pos = (0.0, 0.0)
        engine.agent.heading = 0.0

    def on_tick(self, engine: Any, tickdata: TickData, tick_index: int) -> None:
        self.ticks_run += 1
        # Score on true position (tickdata.pos), consistent with the other
        # assays. Previously this used tickdata.grid_x, the agent's drifting
        # internal estimate, so the metric and the other assays disagreed.
        if not self.reward_reached and tickdata.pos[0] >= self.reward_threshold:
            self.reward_reached = True
            self.time_to_reward = tick_index

    def is_done(self, engine: Any, tickdata: TickData, tick_index: int) -> bool:
        # End early once reward is reached (after a brief dwell of 5 ticks).
        if self.reward_reached:
            return tick_index >= self.time_to_reward + 5
        return False

    def summarize(self) -> Dict[str, float | int | bool]:
        if self.reward_reached:
            self.score = 10.0 - 0.01 * self.time_to_reward
        else:
            self.score = 0.0
        return {
            "ticks_run": self.ticks_run,
            "reward_reached": self.reward_reached,
            "time_to_reward": self.time_to_reward,
            "score": self.score,
            "reward_threshold": self.reward_threshold,
        }


__all__ = ["TMazeProtocol"]
