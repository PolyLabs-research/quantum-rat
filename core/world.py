"""Deterministic world stepping."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from brain.contracts import Action
from core.entities import Agent

Bounds = Tuple[float, float]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class WorldObject:
    """A circular feature the agent can perceive and interact with.

    ``kind`` is the semantic label surfaced to vision (e.g. "target", "hazard").
    """

    x: float
    y: float
    radius: float
    kind: str


@dataclass
class World:
    """World applies actions deterministically to agents and holds features."""

    bounds: Bounds = (10.0, 10.0)
    agents: List[Agent] = field(default_factory=list)
    objects: List[WorldObject] = field(default_factory=list)

    def add_agent(self, agent: Agent) -> None:
        self.agents.append(agent)

    def add_object(self, obj: WorldObject) -> None:
        self.objects.append(obj)

    def step(self, action: Action, *, energy_scale: float = 1.0) -> None:
        """Advance the world by one tick applying the provided action."""
        thrust = action.thrust * energy_scale
        turn = action.turn * energy_scale
        for agent in self.agents:
            agent.apply_motion(forward_delta=thrust, turn_delta=turn)
            agent.pos = (
                _clamp(agent.pos[0], -self.bounds[0], self.bounds[0]),
                _clamp(agent.pos[1], -self.bounds[1], self.bounds[1]),
            )


__all__ = ["World", "WorldObject"]
