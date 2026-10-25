"""Deterministic spatial integrator driven purely by egomotion Observation.

M2b step 1 (docs/prereg/m2b_estimate.md) adds two options, both off by default so every earlier run reads as before:
``heading_source="oracle"`` takes the heading estimate from the Observation's declared heading oracle instead of
summing the egomotion turn, and ``wall_reset`` resets the estimate's coordinate along a touched wall's normal to the
wall's (Hardcastle, Ganguli & Giocomo 2015, for the reset only), identifying the wall by snapping the allocentric
contact normal (heading estimate + the touch's egocentric angle) to the nearest arena axis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Tuple

from brain.contracts import Observation

HEADING_SOURCES: Tuple[str, ...] = ("integrated", "oracle")
WALL_LABELS: Tuple[str, ...] = ("+x", "-x", "+y", "-y")


def wrap_angle(angle: float) -> float:
    """Wrap angle to [-pi, pi]."""
    wrapped = (angle + math.pi) % (2 * math.pi) - math.pi
    return wrapped


def wall_of_normal(angle: float) -> str:
    """The arena wall an allocentric outward normal points at: the nearest axis, "+x", "-x", "+y" or "-y" (ties at
    the diagonals go to the x walls)."""
    c, s = math.cos(angle), math.sin(angle)
    if abs(c) >= abs(s):
        return "+x" if c >= 0.0 else "-x"
    return "+y" if s >= 0.0 else "-y"


@dataclass
class SpatialState:
    hd_angle: float = 0.0
    grid_x: float = 0.0
    grid_y: float = 0.0
    place_id: int = 0
    # The walls the reset wrote this tick ("+x", "-x", "+y", "-y"; empty when none); diagnostics (M2b step 1).
    resets: Tuple[str, ...] = field(default_factory=tuple)


class SpatialSystem:
    """Simple HD/Grid/Place integration from egomotion, with an optional heading oracle and wall-contact reset."""

    def __init__(self, turn_gain: float = 1.0, decay: float = 1.0, bin_size: float = 0.5, *,
                 heading_source: str = "integrated", wall_reset: bool = False,
                 reset_bounds: Optional[Tuple[float, float]] = None) -> None:
        if heading_source not in HEADING_SOURCES:
            raise ValueError(f"heading_source must be one of {HEADING_SOURCES}, got {heading_source!r}")
        if wall_reset and reset_bounds is None:
            raise ValueError("wall_reset needs reset_bounds, the arena's half-extent in the estimate frame")
        self.state = SpatialState()
        self.turn_gain = turn_gain
        self.decay = decay
        self.bin_size = bin_size
        self.heading_source = heading_source
        self.wall_reset = bool(wall_reset)
        self.reset_bounds = (float(reset_bounds[0]), float(reset_bounds[1])) if reset_bounds is not None else None

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

        # Head direction: the summed egomotion turn, or the declared heading oracle's reading (not gated: it is a
        # heading, not a motion).
        if self.heading_source == "oracle":
            if observation.heading is None:
                raise ValueError("heading_source 'oracle' needs an Observation with a heading (sensors.heading_oracle)")
            self.state.hd_angle = wrap_angle(observation.heading)
        else:
            self.state.hd_angle = wrap_angle(self.state.hd_angle + turn * self.turn_gain)

        # Grid integration with optional decay
        dx = fwd * math.cos(self.state.hd_angle)
        dy = fwd * math.sin(self.state.hd_angle)
        self.state.grid_x = (self.state.grid_x * self.decay) + dx
        self.state.grid_y = (self.state.grid_y * self.decay) + dy

        resets: Tuple[str, ...] = ()
        if self.wall_reset:
            if observation.wall_contacts is None:
                raise ValueError("wall_reset needs an Observation with wall_contacts (sensors.wall_contact_sensing)")
            resets = self._reset(observation.wall_contacts)
        self.state.resets = resets

        self.state.place_id = self.place_id_at(self.state.grid_x, self.state.grid_y)
        return self.state

    def _reset(self, contacts: Tuple[float, ...]) -> Tuple[str, ...]:
        """Write the wall coordinate of each touched wall into the estimate; returns the walls written, in order."""
        assert self.reset_bounds is not None
        bx, by = self.reset_bounds
        written = []
        for angle in contacts:
            wall = wall_of_normal(self.state.hd_angle + angle)
            if wall == "+x":
                self.state.grid_x = bx
            elif wall == "-x":
                self.state.grid_x = -bx
            elif wall == "+y":
                self.state.grid_y = by
            else:
                self.state.grid_y = -by
            written.append(wall)
        return tuple(written)


__all__ = ["HEADING_SOURCES", "SpatialSystem", "SpatialState", "WALL_LABELS", "wall_of_normal", "wrap_angle"]
