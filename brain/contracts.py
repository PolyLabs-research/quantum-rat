"""Data contracts for Brain IO."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class VisionRay:
    """Vision ray sample."""

    dist: float  # normalized 0-1 distance
    obj_type: str  # semantic label (may be empty for no hit)
    angle: float  # radians relative to heading

    def validate(self) -> None:
        if not 0.0 <= self.dist <= 1.0:
            raise ValueError(f"dist must be in [0,1], got {self.dist}")
        if not -3.14159266 <= self.angle <= 3.14159266:  # pi rounded up, as heading (pi itself is in range; G45)
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
    # M2b step 1 (docs/prereg/m2b_estimate.md); both None unless the sensor config turns them on, and a None field is
    # left out of the checksum and the determinism record (``observation_fields``), so every earlier observation
    # serialises as before. ``heading``: the declared heading oracle, the allocentric heading with a seeded error
    # (radians, [-pi, pi]). ``wall_contacts``: the egocentric angle of the outward normal of each arena wall the body
    # touches (radians, [-pi, pi]; empty when none).
    heading: Optional[float] = None
    wall_contacts: Optional[Tuple[float, ...]] = None
    # G48: the distal cues in view, (name, egocentric bearing in [-pi, pi], distance in units), each with its seeded
    # error; None unless sensors.landmark_sensing (then left out of the checksum, as the M2b fields).
    landmarks: Optional[Tuple[Tuple[str, float, float], ...]] = None
    # G48: the displacement perpendicular to the heading (units, positive to the left), within the forward range; None
    # unless sensors.lateral_odometry.
    lateral_delta: Optional[float] = None
    # M3 step 2 (draft): the distance to the nearest solid along each of core.sensors.FREE_SPACE_ANGLES; None unless
    # sensors.free_space_sensing.
    free_space: Optional[Tuple[float, ...]] = None
    # G60 (docs/prereg/whole_smell.md): the odour of uneaten food at the (left, right) nostril, each in [0, 1]; None unless
    # sensors.olfaction.
    odour: Optional[Tuple[float, float]] = None

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
        # pi rounded up, as heading and wall_contacts: the egomotion clamp yields exactly +-pi for a one-tick turn of pi
        # or more, which 3.14159 (pi rounded down) rejected; reachable only with the rodent body at a corner (G45).
        if not -3.14159266 <= self.turn_delta <= 3.14159266:
            raise ValueError(f"turn_delta must be in [-pi, pi], got {self.turn_delta}")
        for ray in self.vision_rays:
            ray.validate()
        if self.heading is not None and not -3.14159266 <= self.heading <= 3.14159266:
            raise ValueError(f"heading must be in [-pi, pi], got {self.heading}")
        if self.wall_contacts is not None:
            if len(self.wall_contacts) > 2:
                raise ValueError(f"at most two walls can be touched at once (a corner), got {len(self.wall_contacts)}")
            for angle in self.wall_contacts:
                if not -3.14159266 <= angle <= 3.14159266:
                    raise ValueError(f"wall contact angles must be in [-pi, pi], got {angle}")
        if self.lateral_delta is not None and not -forward_limit <= self.lateral_delta <= forward_limit:
            raise ValueError(f"lateral_delta must be within [-{forward_limit}, {forward_limit}], got {self.lateral_delta}")
        if self.landmarks is not None:
            for name, bearing, distance in self.landmarks:
                if not isinstance(name, str) or not -3.14159266 <= bearing <= 3.14159266 or not distance >= 0.0:
                    raise ValueError(f"a landmark is (name, bearing in [-pi, pi], distance >= 0), got {(name, bearing, distance)}")
        if self.odour is not None:
            if len(self.odour) != 2 or not all(0.0 <= v <= 1.0 for v in self.odour):
                raise ValueError(f"odour must be (left, right), each in [0, 1], got {self.odour}")


# The Observation's optional fields (M2b): omitted from the checksum and the determinism record while None.
OPTIONAL_OBSERVATION_FIELDS: Tuple[str, ...] = ("heading", "wall_contacts", "landmarks", "lateral_delta", "free_space", "odour")


def observation_fields(obs: Observation) -> Dict[str, Any]:
    """``dataclasses.asdict(obs)`` without the optional fields that are None: what ``observation_checksum`` hashes and
    ``core.determinism.observation_record`` writes, so an observation that does not use them reads as before M2b."""
    data = asdict(obs)
    for name in OPTIONAL_OBSERVATION_FIELDS:
        if data.get(name) is None:
            data.pop(name, None)
    return data


@dataclass(frozen=True)
class Action:
    """Minimal action contract."""

    name: str
    thrust: float  # forward magnitude
    turn: float  # turn delta (radians)
