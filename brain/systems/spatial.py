"""Deterministic spatial integrator driven purely by egomotion Observation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from brain.contracts import Observation


def wrap_angle(angle: float) -> float:
    """Wrap angle to [-pi, pi]."""
    wrapped = (angle + math.pi) % (2 * math.pi) - math.pi
    return wrapped


@dataclass
class SpatialState:
    hd_angle: float = 0.0
    grid_x: float = 0.0
    grid_y: float = 0.0
    place_id: int = 0


class SpatialSystem:
    """Simple HD/Grid/Place integration from egomotion only."""

    def __init__(self, turn_gain: float = 1.0, decay: float = 1.0, bin_size: float = 0.5) -> None:
        self.state = SpatialState()
        self.turn_gain = turn_gain
        self.decay = decay
        self.bin_size = bin_size

    def bins_at(self, grid_x: float, grid_y: float) -> Tuple[int, int]:
        """Integer place-cell bin coordinates for a grid coordinate."""
        return math.floor(grid_x / self.bin_size), math.floor(grid_y / self.bin_size)

    def place_id_at(self, grid_x: float, grid_y: float) -> int:
        """Deterministic place id for an arbitrary grid coordinate (same binning)."""
        bx, by = self.bins_at(grid_x, grid_y)
        return (int(bx) << 16) ^ (int(by) & 0xFFFF)

    def step(self, observation: Observation, *, sensory_gain: float = 1.0) -> SpatialState:
        # Gate egomotion by sensory_gain (e.g., TRN): CLOSED -> gain 0 freezes updates.
        fwd = observation.forward_delta * sensory_gain
        turn = observation.turn_delta * sensory_gain

        # Head direction update
        self.state.hd_angle = wrap_angle(self.state.hd_angle + turn * self.turn_gain)

        # Grid integration with optional decay
        dx = fwd * math.cos(self.state.hd_angle)
        dy = fwd * math.sin(self.state.hd_angle)
        self.state.grid_x = (self.state.grid_x * self.decay) + dx
        self.state.grid_y = (self.state.grid_y * self.decay) + dy

        self.state.place_id = self.place_id_at(self.state.grid_x, self.state.grid_y)
        return self.state


__all__ = ["SpatialSystem", "SpatialState", "wrap_angle"]
