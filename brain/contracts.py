"""Data contracts for Brain IO."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class VisionRay:
    """Vision ray sample."""

    dist: float  # normalized 0-1 distance
    obj_type: str  # semantic label (may be empty for no hit)
    angle: float  # radians relative to heading

    def validate(self) -> None:
        if not 0.0 <= self.dist <= 1.0:
            raise ValueError(f"dist must be in [0,1], got {self.dist}")
        if not -3.14159 <= self.angle <= 3.14159:
            raise ValueError(f"angle must be in [-pi, pi], got {self.angle}")


@dataclass(frozen=True)
class Observation:
    """Immutable snapshot provided to the Brain."""

    vision_rays: Tuple[VisionRay, ...]
    whisker_hits: Tuple[bool, bool]
    pain_signal: float  # 0.0 - 1.0
    # Egomotion: the agent's own estimate of the signed distance travelled this
    # tick, in world units. Its range is the sensor contract's
    # ``forward_delta_limit`` (core.config.SensorConfig): 1.0 in the legacy
    # profile, where a full-thrust step of 1.0 sits at the top of the range and
    # a positive odometry error is clamped away; 2.0 in the research profile, so
    # that the research odometry error is signed and zero-mean (docs/odometry.md).
    forward_delta: float
    turn_delta: float  # egomotion: heading change this tick (radians)

    def validate(self, forward_limit: float = 1.0) -> None:
        """Check the ranges; ``forward_limit`` is the egomotion range in force (``SensorConfig.forward_delta_limit``).
        The default, 1.0, is the legacy contract, so every existing call reads as before.
        """
        if len(self.whisker_hits) != 2 or not all(isinstance(v, bool) for v in self.whisker_hits):
            raise ValueError("whisker_hits must be a tuple of two booleans")
        if not 0.0 <= self.pain_signal <= 1.0:
            raise ValueError(f"pain_signal must be in [0,1], got {self.pain_signal}")
        if not forward_limit > 0.0:
            raise ValueError(f"forward_limit must be positive, got {forward_limit}")
        if not -forward_limit <= self.forward_delta <= forward_limit:
            raise ValueError(
                f"forward_delta must be within [-{forward_limit}, {forward_limit}], got {self.forward_delta}"
            )
        if not -3.14159 <= self.turn_delta <= 3.14159:
            raise ValueError(f"turn_delta must be in [-pi, pi], got {self.turn_delta}")
        for ray in self.vision_rays:
            ray.validate()


@dataclass(frozen=True)
class Action:
    """Minimal action contract."""

    name: str
    thrust: float  # forward magnitude
    turn: float  # turn delta (radians)
