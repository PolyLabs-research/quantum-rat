"""Engine configuration: one place to tune every subsystem.

The Engine previously hardcoded every system with no injection path, which
blocked AgentDNA, protocol variation, and experiments from changing any
cognitive parameter without editing source. ``EngineConfig`` is that seam:
pass one to ``Engine(config=...)`` to override any subsystem, or have AgentDNA
write to ``engine.config.basal_ganglia`` at runtime (it is read every tick).

Defaults for subsystems that were not otherwise changed reproduce the previous
hardcoded values exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from brain.systems.criticality import CriticalityConfig


@dataclass
class WorldConfig:
    bounds: Tuple[float, float] = (10.0, 10.0)


@dataclass
class SensorConfig:
    """Vision/whisker/pain sensing of real world geometry."""

    vision_rays: int = 3
    fov: float = 1.2  # total angular spread of the ray fan (radians)
    vision_range: float = 12.0  # distance that normalizes to dist == 1.0
    whisker_angle: float = 0.8  # radians off-centre for the two whiskers
    whisker_range: float = 1.0  # contact distance for a whisker hit
    pain_zone: float = 1.5  # distance from a hazard surface at which pain begins
    noise: float = 0.0  # additive sensor noise (0 => fully deterministic, no RNG draw)


@dataclass
class AstrocyteConfig:
    """Energy model. Demand is scaled by action so rest is cheap and a resting
    agent recovers to a sustainable steady state instead of draining to zero."""

    atp: float = 1.0
    glycogen: float = 3.0
    glycogen_max: float = 3.0
    atp_baseline: float = 1.0
    atp_cost: float = 0.04  # ATP cost per unit demand
    glycogen_to_atp_yield: float = 0.5
    glycogen_recharge: float = 0.05  # glycogen drawn to refill ATP when below baseline
    glycogen_regen: float = 0.03  # passive glycogen regeneration per tick (baseline feeding)
    atp_floor: float = 0.0
    rest_demand: float = 0.2  # metabolic demand at rest (thrust == 0)
    motion_demand: float = 0.8  # additional demand scaled by |thrust|


@dataclass
class NeuromodConfig:
    reward_lr: float = 0.1  # EMA rate for expected reward (dopamine RPE baseline)
    rpe_scale: float = 1.0  # reward-prediction-error scale for dopamine


@dataclass
class RewardConfig:
    approach_weight: float = 1.0  # reward per unit distance closed toward the nearest target
    contact_bonus: float = 1.0  # reward for touching a target
    pain_weight: float = 1.0  # penalty per unit pain signal


@dataclass
class ValueMemoryConfig:
    learning_rate: float = 0.2
    discount: float = 0.9
    capacity: int = 200  # trajectory length retained for replay


@dataclass
class SpatialConfig:
    turn_gain: float = 1.0
    decay: float = 1.0
    bin_size: float = 0.5


@dataclass
class TRNConfig:
    trigger_atp: float = 0.30
    trigger_streak: int = 10
    duration: int = 25
    recovery_atp: float = 0.45
    recovery_streak_needed: int = 5
    replay_window: int = 50


@dataclass
class WorkingMemoryConfig:
    capacity: int = 32


@dataclass
class BasalGangliaConfig:
    """Action-selection weights. AgentDNA writes here to differentiate agents."""

    forward_bias: float = 0.8  # base FORWARD drive (multiplied by trn_gain)
    pain_avoidance: float = 0.5  # weight pulling FORWARD down under pain
    rest_pain_gain: float = 0.8  # weight pushing REST up under pain
    novelty_gain: float = 0.2  # exploration drive from working-memory novelty
    turn_bias: float = 0.0  # constant bias: >0 favours TURN_LEFT, <0 favours TURN_RIGHT
    vision_gain: float = 0.6  # drive toward a visible target (0 => blind to vision)
    wall_avoid_gain: float = 0.6  # drive to turn away from a close wall ahead
    dopamine_explore_gain: float = 0.6  # how strongly low dopamine boosts exploration


@dataclass
class EngineConfig:
    """Aggregate of every subsystem's configuration."""

    world: WorldConfig = field(default_factory=WorldConfig)
    sensors: SensorConfig = field(default_factory=SensorConfig)
    astrocyte: AstrocyteConfig = field(default_factory=AstrocyteConfig)
    neuromod: NeuromodConfig = field(default_factory=NeuromodConfig)
    reward: RewardConfig = field(default_factory=RewardConfig)
    value_memory: ValueMemoryConfig = field(default_factory=ValueMemoryConfig)
    criticality: CriticalityConfig = field(default_factory=CriticalityConfig)
    spatial: SpatialConfig = field(default_factory=SpatialConfig)
    trn: TRNConfig = field(default_factory=TRNConfig)
    working_memory: WorkingMemoryConfig = field(default_factory=WorkingMemoryConfig)
    basal_ganglia: BasalGangliaConfig = field(default_factory=BasalGangliaConfig)


__all__ = [
    "WorldConfig",
    "SensorConfig",
    "AstrocyteConfig",
    "NeuromodConfig",
    "RewardConfig",
    "ValueMemoryConfig",
    "SpatialConfig",
    "TRNConfig",
    "WorkingMemoryConfig",
    "BasalGangliaConfig",
    "EngineConfig",
]
