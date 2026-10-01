"""Canonical metrics schema definitions."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Dict, Tuple

SCHEMA_VERSION = "2.1.6"


@dataclass
class TickData:
    """Single source of truth for analysis and UI."""

    schema_version: str = SCHEMA_VERSION
    tick: int = 0
    agent_id: int = 0
    pos: Tuple[float, float] = (0.0, 0.0)
    score: int = 0
    # Brain vitals
    kappa: float = 0.0
    avalanche_size: int = 0
    criticality_active: int = 0
    atp: float = 0.0
    glycogen: float = 0.0
    reward: float = 0.0
    neuromodulators: Dict[str, float] = field(default_factory=dict)
    # Observation summary
    obs_forward_delta: float = 0.0
    obs_turn_delta: float = 0.0
    obs_pain: float = 0.0
    obs_checksum: str = ""
    # TRN / microsleep / replay
    trn_state: str = "OPEN"
    microsleep_active: bool = False
    microsleep_ticks_remaining: int = 0
    replay_active: bool = False
    replay_index: int = -1
    # Spatial
    hd_angle: float = 0.0
    grid_x: float = 0.0
    grid_y: float = 0.0
    place_id: int = 0
    # Working memory / action
    wm_load: int = 0
    wm_novelty: float = 0.0
    action_name: str = "REST"
    action_thrust: float = 0.0
    action_turn: float = 0.0
    # Assay info
    protocol_name: str = ""
    trial_number: int = 0

    def to_ordered_dict(self) -> Dict[str, Any]:
        """Return a plain dict in schema order for deterministic serialization."""
        return {f.name: getattr(self, f.name) for f in fields(self)}
