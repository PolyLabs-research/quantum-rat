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

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, List, Tuple

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
    # Odometry noise on the agent's self-motion estimate (the egomotion the
    # spatial system integrates; the body moves exactly as before). Drawn from
    # the "sensors_odometry" stream in core.sensors._compute_egomotion, forward
    # first then turn, each only when its sigma is > 0 (0 => no draw).
    # odometry_speed_noise: standard deviation of a multiplicative Gaussian
    # factor on the raw forward displacement, d' = d * (1 + sigma * xi).
    # odometry_turn_noise: standard deviation (radians) of an additive Gaussian
    # term on the raw heading change. Both are counted by
    # EngineConfig.stochastic_elements (core.seeds).
    odometry_speed_noise: float = 0.0
    odometry_turn_noise: float = 0.0


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
    # Whether the ATP throttle scales the body's motion. World.step multiplies
    # thrust and turn by the energy_scale the engine hands it: atp / atp_baseline
    # when this is True (legacy), 1.0 on every tick when it is False (step length
    # independent of ATP; the gate value still scales the FORWARD drive, so ATP
    # reaches action selection by that route unless the gate is held OPEN, see
    # docs/profiles.md; the energy stores still move and are still logged).
    scales_motion: bool = True
    # When True the astrocyte does not tick at all: ATP and glycogen stay at
    # their initial values (``atp``, ``glycogen`` above) for the whole run and
    # the throttle is 1.0 on every tick; ctx.atp / ctx.glycogen are logged as
    # before. At the default initial ATP (1.0, above trn.open_at_atp) the TRN
    # gate therefore stays OPEN unless kappa exceeds trn.narrow_above_kappa, and
    # microsleep (ATP below trn.trigger_atp for trn.trigger_streak ticks) cannot
    # trigger.
    frozen: bool = False


@dataclass
class NeuromodConfig:
    reward_lr: float = 0.1  # EMA rate of the running mean of reward (DA = reward - this mean)
    rpe_scale: float = 1.0  # scale of (reward - running mean) in DA and of the mean in 5HT


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
    # Extinction of self-made value peaks: a dwelling transition on a positively
    # valued place is charged this much before the TD backup, so a peak the agent
    # built by staying put fades instead of pinning it there. "Dwelling" means the
    # transition starts and ends in the same place-cell bin, so REST and turns made
    # in place (a TURN moves 0.3, usually inside one 0.5 bin) are charged alike;
    # transitions that cross into another bin are never charged, so traversed
    # paths do not become repulsive (a global living cost does that and breaks
    # online maze learning). Replay re-applies the charge under the same rule
    # (the cell must still be positive), so it extinguishes but never makes a
    # cell aversive. 0 disables.
    dwell_extinction: float = 0.02
    # Whether approach shaping is written into the value map. False keeps the map
    # to primary outcomes only (contact reward and pain above the sensory-reliability
    # floor max(0.05, sensors.noise), see Engine.map_pain_floor); dopamine and
    # the other neuromodulators still see the full shaped reward either way.
    learn_shaping: bool = False
    # Which transitions microsleep replay backs up. True: at sleep onset the newest
    # trn.replay_window transitions are snapshotted and replayed most recent first
    # (reverse order), cycling if sleep outlasts them (a sleep lasts
    # trn.duration = 25 ticks, so at the defaults it never does), never across
    # an episode boundary; begin_episode ends the replay of a sleep in
    # progress. See Engine._replay for how this relates to rodent replay.
    # False (legacy): the TRN observation-buffer index (0..window-1) is
    # used as a trajectory index from the OLDEST end, which replays transitions
    # ~150-200 ticks old, every second one, in forward order. TickData.replay_index
    # is the TRN index either way.
    replay_recent: bool = True
    # Goal-vector memory: remember the place cell where reward was found and,
    # wherever the value map is locally flat (largest sampled advantage below
    # goal_vector_flat), turn toward it by path integration. The TD map's
    # values fall by ``discount`` per step of the demonstration, so after a long
    # first trial (a start facing away from the goal: 34-129 ticks of search)
    # the start region reads as flat and the map alone gives no direction; the
    # vector does. ``goal_vector_source``: "replay" (default) writes the goal
    # only when a rewarded transition is replayed (sleep consolidation or
    # microsleep replay), so it is a product of consolidation like the
    # replayed gradient; "online" also writes it on target contact. Visits to
    # the goal's own place cell that find no reward erase it (extinction, see
    # goal_extinction_misses).
    # The turn command is sign(b) * clip((|b| - goal_turn_dead_zone) /
    # goal_turn_ramp, 0, 1) for the bearing b to the goal's cell centre, with
    # FORWARD giving way by the same amount, and nothing while the goal lies
    # inside the ~1 m circle a run of turns traces (turning would orbit it; see
    # brain.systems.basal_ganglia.goal_vector_signals). False disables.
    goal_vector: bool = False
    goal_vector_source: str = "replay"
    # The vector steers only where the map's largest sampled advantage is below
    # this (the map's own flatness threshold, Engine.VALUE_FLAT, where split and
    # max-norm steering give no command). A huge value gives the vector
    # precedence whenever a goal is held (measured, not the default).
    goal_vector_flat: float = 1e-3
    goal_turn_dead_zone: float = 0.15  # radians (half a TURN_STEP)
    goal_turn_ramp: float = 0.3  # radians (one TURN_STEP); <= 0 makes it a step
    # Extinction: the goal is erased after this many visits in a row to its
    # place cell that end without target contact (contact on the tick the
    # agent leaves the cell counts); any target contact resets the count.
    # The remembered cell straddles the goal's contact circle, so a single
    # miss can be a pass through the part of the cell outside it. 0 disables
    # extinction. Measured in docs/decisions.md G21.
    goal_extinction_misses: int = 2


@dataclass
class SpatialConfig:
    turn_gain: float = 1.0
    decay: float = 1.0
    bin_size: float = 0.5
    # Whether the TRN gate value (1.0 OPEN, trn.narrow_gain NARROW, 0.0 CLOSED)
    # multiplies the egomotion deltas before path integration (legacy). When
    # False the engine passes sensory_gain = 1.0, so the estimate keeps
    # integrating the true egomotion through NARROW, CLOSED and microsleep. With
    # sensor noise 0 it then equals the true position on every tick; with the
    # gate scaling it, the legacy estimate ends 22.8 units off after 3000
    # barren-world ticks (tools/probes/path_integration_capture).
    gate_scales_egomotion: bool = True


@dataclass
class TRNConfig:
    trigger_atp: float = 0.30
    trigger_streak: int = 10
    duration: int = 25
    recovery_atp: float = 0.45
    recovery_streak_needed: int = 5
    replay_window: int = 50
    # Gate thresholds (previously hard-coded in TRNGate.trn_state; same values,
    # same branch order): CLOSED (gate 0.0) during microsleep or when
    # ATP < closed_below_atp; OPEN (gate 1.0) when ATP >= open_at_atp and
    # kappa <= narrow_above_kappa; otherwise NARROW (gate narrow_gain).
    closed_below_atp: float = 0.35
    open_at_atp: float = 0.55
    narrow_above_kappa: float = 1.1
    narrow_gain: float = 0.4
    # When False no microsleep bout ever starts, so the replay gating that
    # depends on microsleep never fires either (replay_active stays False).
    microsleep_enabled: bool = True


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
    # Weight of the kappa gain (brain.systems.criticality.near_critical_gain) on
    # vision_gain: 0 = off, the default; at 1.0 it flips no decision in the
    # probed worlds (tools/probes/dormant_couplings).
    criticality_gain: float = 0.0
    # Softmax action selection. 0 (default): the deterministic argmax over the
    # channel scores with its fixed tie order (ACTION_ORDER), no RNG draw. tau > 0:
    # the action is sampled with probability proportional to exp((s_i - max_j
    # s_j) / tau) over the channels in that same order, from one random() draw
    # per tick on the "action_softmax" stream (brain.systems.basal_ganglia
    # .softmax_sample); the logged scores stay the scores. Counted by
    # EngineConfig.stochastic_elements (core.seeds).
    softmax_temperature: float = 0.0
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
    # Wall gating: a wall close ahead (centre vision ray) mutes memory's push to
    # hold course, by w = max(0, 1 - wall_gate_gain * wall closeness): FORWARD's
    # positive value signal and negative turn signals are scaled by w, turns
    # toward a better side are kept (see basal_ganglia.wall_gate_signals), so a
    # remembered place behind a wall cannot pin the agent against it. 0 disables.
    wall_gate_gain: float = 1.0
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
    #   Because nothing is measured against "here", max(signals) >= 0 for every
    #   ahead mode except "maxnorm", so a value-map local maximum never lowers
    #   FORWARD. (REST can still win because of value in rare states where
    #   FORWARD is already below REST and the turn signals are negative;
    #   measured value-induced REST is 0 at gains 0.4-3.0.) Unknown mode
    #   strings raise ValueError.
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


# The config fields that make a run depend on its seed, in the order
# EngineConfig.stochastic_elements reports them. Every other RNG stream the
# engine opens is either unused (neuromod) or behaviourally dormant at the
# defaults (criticality, tools/probes/seed_pseudoreplication).
STOCHASTIC_PARAMETERS: Tuple[str, ...] = (
    "sensors.noise",
    "sensors.odometry_speed_noise",
    "sensors.odometry_turn_noise",
    "basal_ganglia.softmax_temperature",
)


@dataclass
class EngineConfig:
    """Aggregate of every subsystem's configuration.

    ``profile`` labels the set of flags in force: ``"legacy"`` for the defaults
    (``EngineConfig()`` and :meth:`legacy`) and ``"research"`` for
    :meth:`research`. It is a label only: it is not logged in TickData and never
    enters a trace hash. docs/profiles.md lists what the two profiles differ
    in; :meth:`diff` computes it.
    """

    profile: str = "legacy"
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

    @classmethod
    def legacy(cls) -> "EngineConfig":
        """The defaults, labelled: equal to ``EngineConfig()`` in every field."""
        return cls(profile="legacy")

    @classmethod
    def research(cls) -> "EngineConfig":
        """The research profile (docs/research_plan.md section 6, milestone 0a).

        Differs from :meth:`legacy` in exactly these fields (``diff`` lists them):

        - ``spatial.gate_scales_egomotion = False``: the TRN gate no longer
          scales egomotion, so low ATP does not freeze path integration.
        - ``astrocyte.scales_motion = False`` and ``astrocyte.frozen = True``:
          ATP stays at its initial value and energy_scale is 1.0 on every tick,
          so the body moves the commanded thrust.
        - ``trn.microsleep_enabled = False``: no microsleep bouts, hence no
          microsleep-gated replay (sleep becomes a protocol phase later).
        - ``trn.narrow_above_kappa = inf``: the gate's kappa branch is off. With
          ATP frozen at 1.0 the gate is then OPEN on every tick, so the
          criticality lattice cannot reach the FORWARD drive through the gate
          value (at the legacy 1.1 it did at 2 of 41 seeds scanned, see
          docs/profiles.md).
        - ``value_memory.dwell_extinction = 0.0``: no charge for dwelling.
        - Neuromodulator coupling gains in ``basal_ganglia`` set to 0:
          ``dopamine_explore_gain``, ``ach_precision_gain``, ``ne_threat_gain``
          and ``fiveht_patience_gain``. The modulator traces are still computed
          and logged; they just do not reach action selection.

        - Seeds are samples (milestone 0b, item 8): ``sensors.odometry_speed_noise
          = 0.05``, ``sensors.odometry_turn_noise = 0.01`` (seeded noise on the
          self-motion estimate; the body moves exactly as before) and
          ``basal_ganglia.softmax_temperature = 0.1`` (seeded softmax action
          selection). These three values are placeholders, to be characterised
          in milestone 1 (docs/profiles.md); what they fix now is that two
          seeds under this profile are two different runs, which
          :meth:`stochastic_elements` and ``core.seeds`` can check.

        Also set explicitly, but already the legacy value, so not in the diff:
        ``value_memory.generalization_radius = 0``, ``value_memory.goal_vector =
        False`` and ``basal_ganglia.criticality_gain = 0.0`` (the criticality
        coupling to cognition; kappa is still computed and logged).

        Nothing else differs. Not yet in this profile: a wall-contact reset
        for the odometry, a place population and replay as an event stream
        (later milestones).
        """
        cfg = cls(profile="research")
        cfg.sensors.odometry_speed_noise = 0.05
        cfg.sensors.odometry_turn_noise = 0.01
        cfg.spatial.gate_scales_egomotion = False
        cfg.astrocyte.scales_motion = False
        cfg.astrocyte.frozen = True
        cfg.trn.microsleep_enabled = False
        cfg.trn.narrow_above_kappa = float("inf")
        cfg.value_memory.generalization_radius = 0
        cfg.value_memory.goal_vector = False
        cfg.value_memory.dwell_extinction = 0.0
        bg = cfg.basal_ganglia
        bg.criticality_gain = 0.0
        bg.dopamine_explore_gain = 0.0
        bg.ach_precision_gain = 0.0
        bg.ne_threat_gain = 0.0
        bg.fiveht_patience_gain = 0.0
        bg.softmax_temperature = 0.1
        return cfg

    def stochastic_elements(self) -> List[str]:
        """The stochastic elements this config has on, as ``"dotted.field=value"``.

        One entry per parameter in :data:`STOCHASTIC_PARAMETERS` that is > 0,
        in that order: sensor noise (rangefinder and pain), odometry speed
        noise, odometry turn noise and the softmax temperature. Empty means
        no behavioural path draws from the RNG, so every seed gives the same
        run (the criticality lattice is seeded but dormant at the defaults,
        docs/profiles.md); ``core.seeds.require_seeds_are_samples`` refuses a
        multi-seed claim on such a config.
        """
        out: List[str] = []
        for name in STOCHASTIC_PARAMETERS:
            section, field_name = name.split(".")
            value = getattr(getattr(self, section), field_name)
            if value > 0.0:
                out.append(f"{name}={value!r}")
        return out

    def diff(self, other: "EngineConfig") -> List[Tuple[str, Any, Any]]:
        """Fields where ``self`` and ``other`` differ: (dotted.field, self_value, other_value).

        Every nested config dataclass is walked in field declaration order, so
        the list is deterministic, and it is empty when the two are equal.
        """
        return config_diff(self, other)


def config_diff(a: Any, b: Any, prefix: str = "") -> List[Tuple[str, Any, Any]]:
    """Field-by-field difference of two config dataclasses (see ``EngineConfig.diff``)."""
    out: List[Tuple[str, Any, Any]] = []
    for f in fields(a):
        name = f"{prefix}{f.name}"
        va, vb = getattr(a, f.name), getattr(b, f.name)
        if is_dataclass(va) and is_dataclass(vb):
            out.extend(config_diff(va, vb, f"{name}."))
        elif va != vb:
            out.append((name, va, vb))
    return out


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
    "STOCHASTIC_PARAMETERS",
    "config_diff",
]
