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
    lookahead: float = 1.0  # distance projected ahead to read neighbouring place values
    generalization_radius: int = 0  # place-field spread in cells (0 = exact, no generalization)
    generalization_falloff: float = 0.5  # per-cell weight decay for generalization
    # Extinction of self-made value peaks: a dwelling (same-cell) transition on a
    # positively valued place is charged this much before the TD backup, so a peak
    # the agent built by standing still fades instead of pinning it there. Moving
    # transitions are never charged, so traversed paths do not become repulsive
    # (a global living cost does that and breaks online maze learning). 0 disables.
    dwell_extinction: float = 0.02
    # Whether approach shaping is written into the value map. False keeps the map
    # to primary outcomes only (contact reward and pain above the sensory-reliability
    # floor max(0.05, sensors.noise), see Engine.map_pain_floor); dopamine and
    # the other neuromodulators still see the full shaped reward either way.
    learn_shaping: bool = False


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
    # Neuromodulator control couplings (0 disables; defaults are no-ops at baseline
    # modulator levels NE=0, ACh=0, 5HT=0.5, so default behaviour is unchanged).
    ach_precision_gain: float = 0.5  # acetylcholine sharpens sensory (vision) precision
    ne_threat_gain: float = 0.5  # norepinephrine raises arousal / threat sensitivity
    fiveht_patience_gain: float = 0.4  # serotonin raises patience (willingness to rest)
    value_gain: float = 1.5  # drive toward higher-value directions from the learned map
    criticality_gain: float = 0.0  # how strongly near-critical cortical gain scales vision (0 = off)
    # Freeze habituation: pain-driven REST habituates while the agent keeps freezing
    # in pain, so a freeze is not an absorbing state. The pain->REST drive is scaled
    # by exp(-F / freeze_tau), where F counts recent pain-freeze ticks (+1 per REST
    # tick with pain > freeze_pain_threshold, otherwise F *= freeze_decay). The
    # threshold sits above the sensor-noise amplitude, so this is an exact no-op
    # unless real pain occurs. freeze_tau <= 0 disables it.
    freeze_tau: float = 15.0
    freeze_pain_threshold: float = 0.2
    freeze_decay: float = 0.9
    # Cue gating: memory steering is muted while a target is in view, by
    # w = max(0, 1 - cue_gate_gain * closeness of the nearest visible target), so
    # the value map cannot override what the agent can see. 0 disables.
    cue_gate_gain: float = 2.0
    # Homeostatic pacing: once ATP falls below pace_low the agent prefers REST
    # (by pace_rest_bonus) until ATP recovers to pace_high. Both thresholds are
    # fractions of astrocyte.atp_baseline (the ATP ceiling), so the release point
    # is always reachable: absolute thresholds latched REST for good whenever
    # atp_baseline < pace_high. 0 disables (default in the core engine; the
    # lab-console scenarios that are energy-limited turn it on).
    pace_rest_bonus: float = 0.0
    pace_low: float = 0.4  # x atp_baseline
    pace_high: float = 0.9  # x atp_baseline
    # Memory-steering geometry: how the value map's advantages (value one
    # lookahead step away along the heading and a fan each side, minus value
    # here) become the FORWARD / TURN_LEFT / TURN_RIGHT value signals.
    #   "split" (default): a decisive turn signal measured relative to ahead
    #   (see brain.systems.basal_ganglia.split_value_signals). Each side reads
    #   sign(d) * clip((|d| / s - value_turn_dead_zone) / value_turn_ramp, 0, 1)
    #   with d = side - ahead and s = max|advantage| (s = 1, i.e. raw value units,
    #   when value_turn_relative is False; value_turn_ramp <= 0 makes it a step).
    #   value_turn_exclusive: when both sides beat ahead only the better one turns
    #   (ties go left). value_ahead_mode sets FORWARD's term: "zero", "maxnorm"
    #   (ahead / s), "positive" (max(0, ahead / s)), "oppose" (minus the
    #   stronger turn) or "oppose_positive" (both). value_common_mode > 0 adds
    #   tanh(min(ahead, left, right) / value_common_mode) to all three when every
    #   direction beats here (0 = off). Only "split" reads these fields.
    #   Because nothing is measured against "here", max(signals) >= 0 always, so
    #   a value-map local maximum cannot push every move below REST.
    #   "maxnorm" (the pre-G15 steering, kept for comparison and for the legacy
    #   digests): each advantage divided by the largest magnitude; at a local
    #   maximum this reads (-1, -1, -1) and REST wins (value-induced REST).
    value_steer: str = "split"
    value_turn_dead_zone: float = 0.1
    value_turn_ramp: float = 0.2
    value_turn_relative: bool = True
    value_turn_exclusive: bool = True
    value_ahead_mode: str = "oppose_positive"
    value_common_mode: float = 0.0


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
