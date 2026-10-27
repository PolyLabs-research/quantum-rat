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


BARRIER_CLEARANCE = 1e-6  # how far outside a barrier's face a blocked body stops (units)


@dataclass
class Barrier:
    """A solid axis-aligned rectangle inside the arena (decisions G47): it stops the body, which slides along it, and
    every vision ray and whisker, which report it as ``"wall"`` (by sight the agent cannot tell it from the arena's
    walls). It is not sensed by touch (``core.sensors._wall_contacts`` reports the arena's walls only, so the declared
    wall-contact reset never fires on it)."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        if not (self.x0 < self.x1 and self.y0 < self.y1):
            raise ValueError(f"a barrier needs x0 < x1 and y0 < y1, got {self}")

    def contains(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


def _limit_axis(start: float, target: float, other: float, faces: List[Tuple[float, float, float, float]]) -> float:
    """Move along one axis from ``start`` toward ``target`` with the other coordinate at ``other``; stop just short of
    the first face crossed. ``faces`` are (lo, hi, other_lo, other_hi) per barrier: its extent on this axis, then on the
    other."""
    end = target
    for lo, hi, olo, ohi in faces:
        if not (olo <= other <= ohi):
            continue
        if start < lo <= end:
            end = lo - BARRIER_CLEARANCE
        elif start > hi >= end:
            end = hi + BARRIER_CLEARANCE
    return end


@dataclass
class World:
    """World applies actions deterministically to agents and holds features."""

    bounds: Bounds = (10.0, 10.0)
    agents: List[Agent] = field(default_factory=list)
    objects: List[WorldObject] = field(default_factory=list)
    barriers: List[Barrier] = field(default_factory=list)

    def add_agent(self, agent: Agent) -> None:
        self.agents.append(agent)

    def add_object(self, obj: WorldObject) -> None:
        self.objects.append(obj)

    def add_barrier(self, barrier: Barrier) -> None:
        self.barriers.append(barrier)

    def constrain(self, frm: Tuple[float, float], to: Tuple[float, float]) -> Tuple[float, float]:
        """Where a move from ``frm`` toward ``to`` ends without entering a barrier: the x component first, then the y,
        each stopped just short of the first face it would cross, so a move into a barrier at an angle slides along it
        and no step, however long, passes through one. With no barrier it is ``to`` unchanged."""
        if not self.barriers:
            return to
        x = _limit_axis(frm[0], to[0], frm[1], [(b.x0, b.x1, b.y0, b.y1) for b in self.barriers])
        y = _limit_axis(frm[1], to[1], x, [(b.y0, b.y1, b.x0, b.x1) for b in self.barriers])
        return (x, y)

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
            if self.barriers:
                agent.pos = self.constrain(agent.last_pos, agent.pos)


__all__ = ["Barrier", "World", "WorldObject"]
