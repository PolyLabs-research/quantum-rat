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

import math
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, ClassVar, Dict, List, Mapping, Optional, Tuple

from brain.systems.criticality import CriticalityConfig


@dataclass
class UnitsConfig:
    """Physical units, declared once (docs/units.md; docs/research_plan.md section 5, M0b item 6).

    This is a declaration, not a mechanism: no engine constant reads it yet.
    The engine moves in world units and ticks; these two numbers say what a
    unit and a tick mean, so that every distance, speed and duration in a
    write-up, and the durations in the replay metrics (plan section 2), are
    expressed in metres and seconds through one place. The declaration is the
    same in both profiles (``EngineConfig.legacy()`` and ``research()``).

    Derived table at the defaults (dt_s 0.2, metres_per_unit 0.1):

    - the 20 x 20 unit arena (``WorldConfig.bounds`` (10, 10)) is a 2 m x 2 m
      open field;
    - FORWARD, 1.0 unit per tick, is 0.5 m/s. Realised only where energy
      scaling is off (the research profile); under the legacy throttle the
      step is ``thrust * energy_scale``;
    - a TURN, ``TURN_STEP`` 0.3 rad per tick, is 1.5 rad/s, and its
      ``TURN_THRUST`` 0.3 unit per tick is 0.15 m/s. Heading is quantised in
      0.3 rad steps: a kinematic constraint to state in every write-up;
    - the memory maze's 300-tick trial timeout is the standard 60 s;
    - for comparison, rats run tracks at 0.2-0.6 m/s (plan section 5, item 6).
      The realised speeds are measured by tools/probes/realised_speed.

    Rates per second multiply by :attr:`ticks_per_second` (1 / dt_s, exactly
    5.0 at the default) rather than divide by ``dt_s``, so that the table
    above holds to the last bit (0.3 / 0.2 reads 1.4999999999999998 in
    binary floating point; 0.3 * 5.0 reads 1.5). :meth:`ticks` rounds to the
    nearest whole tick, halves up (``floor(x + 0.5)``), so 0.1 s is 1 tick.
    """

    dt_s: float = 0.2  # seconds per engine tick
    metres_per_unit: float = 0.1  # metres per world unit

    def __post_init__(self) -> None:
        if not (self.dt_s > 0.0 and self.metres_per_unit > 0.0):
            raise ValueError(f"UnitsConfig needs positive dt_s and metres_per_unit, got {self.dt_s}, {self.metres_per_unit}")

    @property
    def ticks_per_second(self) -> float:
        return 1.0 / self.dt_s

    def seconds(self, ticks: float) -> float:
        """Duration of ``ticks`` ticks in seconds."""
        return ticks * self.dt_s

    def ticks(self, seconds: float) -> int:
        """Whole ticks in ``seconds``: the nearest integer, halves rounded up."""
        return int(math.floor(seconds * self.ticks_per_second + 0.5))

    def metres(self, units: float) -> float:
        return units * self.metres_per_unit

    def units(self, metres: float) -> float:
        return metres / self.metres_per_unit

    def metres_per_second(self, units_per_tick: float) -> float:
        return units_per_tick * self.metres_per_unit * self.ticks_per_second

    def radians_per_second(self, rad_per_tick: float) -> float:
        return rad_per_tick * self.ticks_per_second


HEADING_SOURCES: Tuple[str, ...] = ("integrated", "oracle")


@dataclass
class WorldConfig:
    bounds: Tuple[float, float] = (10.0, 10.0)


BODY_MODELS: Tuple[str, ...] = ("discrete", "rodent")


@dataclass
class BodyConfig:
    """How an action moves the body (M3 step 1, ``docs/prereg/m3_body.md``; decisions G44).

    ``model = "discrete"`` (the default, both profiles) is the body every result up to G43 ran: a FORWARD step of 1.0
    unit, a TURN of 0.3 rad that also moves 0.3 units, REST still (``core.world.World.step``). ``"rodent"`` is
    ``core.body.RodentBody``: speed and angular velocity as Ornstein-Uhlenbeck processes drifted toward the chosen
    action's targets, turns in place, and wall following, after RatInABox (George et al. 2024), whose noise defaults
    are fitted to Sargolini et al. (2006). Speeds in m/s, rates in rad/s, times in s, distances in m; the engine
    converts with ``UnitsConfig``. The other fields are read only by the rodent model.
    """

    model: str = "discrete"
    run_speed: float = 0.5  # m/s, FORWARD's target: 1 unit per tick, today's FORWARD step
    turn_speed: float = 0.0  # m/s while turning: 0 turns in place (no turning circle)
    turn_rate: float = 1.5  # rad/s, a TURN's target: 0.3 rad per tick, today's TURN step
    speed_coherence_time: float = 0.7  # s (RatInABox)
    speed_noise: float = 0.0  # m/s, the speed process's sd (RatInABox: 0.08)
    rotational_coherence_time: float = 0.08  # s (RatInABox)
    rotational_noise: float = 0.0  # rad/s, the angular velocity process's sd (RatInABox: 120 deg/s = 2.094)
    wall_align_distance: float = 0.1  # m, within which a heading into a wall turns toward it (RatInABox's repel distance)

    def __post_init__(self) -> None:
        if self.model not in BODY_MODELS:
            raise ValueError(f"body.model must be one of {BODY_MODELS}, got {self.model!r}")
        for name in ("run_speed", "turn_rate", "speed_coherence_time", "rotational_coherence_time", "wall_align_distance"):
            value = getattr(self, name)
            if not (math.isfinite(value) and value > 0.0):
                raise ValueError(f"body.{name} must be a positive finite number, got {value!r}")
        for name in ("turn_speed", "speed_noise", "rotational_noise"):
            value = getattr(self, name)
            if not (math.isfinite(value) and value >= 0.0):
                raise ValueError(f"body.{name} must be a finite number >= 0, got {value!r}")


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
    # The Observation's egomotion range: forward_delta is clamped to
    # [-forward_delta_limit, +forward_delta_limit] after the odometry noise is
    # applied (core.sensors._compute_egomotion; Observation.validate checks it).
    # 1.0 (legacy) puts a full-thrust FORWARD step of 1.0 at the top of the
    # range, so a positive speed error is clamped away and a full-speed step
    # averages 1 - sigma / sqrt(2 pi) (0.980 at sigma 0.05: the clamp bias,
    # docs/odometry.md). The research profile sets 2.0, so the estimate carries
    # the signed, zero-mean error it draws (a clip at 2.0 needs xi > 20 at sigma
    # 0.05 and never occurs). The body's motion is unchanged by this field.
    forward_delta_limit: float = 1.0
    # --- M2b step 1 (docs/prereg/m2b_estimate.md): the declared heading oracle and wall-contact sensing ---
    # heading_oracle: the Observation carries ``heading``, the body's allocentric heading plus a Gaussian error of sd
    # heading_oracle_noise (radians), drawn per tick from the "sensors_heading" stream (no draw at 0). Off, the
    # field is None and nothing is drawn. Plan section 2 item 1: heading is given, not inferred from landmarks; a
    # declared limitation of every result that uses it.
    heading_oracle: bool = False
    heading_oracle_noise: float = 0.0
    # wall_contact_sensing: the Observation carries ``wall_contacts``, the egocentric angle (radians, relative to the
    # body's heading) of the outward normal of each arena wall the body touches, x walls before y walls; empty when
    # it touches none. Off, the field is None. Touch is exact: it says which side of the body is against a wall.
    wall_contact_sensing: bool = False
    # unseen_block_rays (decisions G46): whether a "hidden" or "collected" object stops a vision ray or a whisker as an
    # obstacle would. True (the legacy value, every result before G46): the ray stops at the object and reports its
    # kind, and the action selection's side openness reads it as an obstacle, so the agent senses every hidden food
    # site and turns away from it (the audit of 2026-10-27). False (the research profile from G46): such an object is
    # not seen at all, and a ray passes through it to whatever lies behind.
    unseen_block_rays: bool = True
    # --- decisions G48: the agent sees distal cues (``core.world.Cue``) ---
    # landmark_sensing: the Observation carries ``landmarks``, one (name, bearing, distance) per cue within the field
    # of view: the cue's egocentric bearing (radians, [-pi, pi]) with a Gaussian error of sd landmark_bearing_noise and
    # its distance (units) times (1 + landmark_distance_noise * xi), drawn from the "sensors_landmarks" stream (no draw
    # at 0). The field of view is landmark_fov radians centred on the heading (300 degrees: a rat's visual field is
    # nearly panoramic). What it sees is how a cue looks and where it appears; never where it is.
    landmark_sensing: bool = False
    # lateral_odometry (decisions G48): the Observation carries ``lateral_delta``, the body's displacement this tick
    # perpendicular to its heading (units, positive to the left), with the forward odometry's multiplicative error
    # (its own draw, after the turn draw, from "sensors_odometry"). Off, the egomotion is the displacement projected on
    # the heading only, so a body sliding along a wall it pushes into feels only the part of the slide along its
    # heading. A rat feels the rest (vestibular, optic flow); G48's pilot found the unsensed slide biasing a learned
    # cue map in the L arena.
    lateral_odometry: bool = False
    # free_space_sensing (M3 step 2, draft): the Observation carries ``free_space``, the distance (units, capped at
    # vision_range) to the nearest solid (an arena wall or a barrier) along each of ``core.sensors.FREE_SPACE_ANGLES``
    # (relative to the heading): how far the agent can see it could move in each direction of the value fan. Exact
    # (the wall reflex's rangefinder is too). Off: None.
    free_space_sensing: bool = False
    landmark_fov: float = 5.235987755982989
    landmark_bearing_noise: float = 0.05
    landmark_distance_noise: float = 0.10

    def __post_init__(self) -> None:
        if not (math.isfinite(self.heading_oracle_noise) and self.heading_oracle_noise >= 0.0):
            raise ValueError("heading_oracle_noise must be a finite non-negative number")
        if self.heading_oracle_noise > 0.0 and not self.heading_oracle:
            raise ValueError("heading_oracle_noise > 0 needs heading_oracle = True (nothing would be drawn)")



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
    approach_weight: float = 1.0  # reward per unit distance closed toward the nearest visible target
    # shape_hidden (decisions G46): whether approach shaping also counts a "hidden" goal. True (the legacy value, every
    # result before G46): the shaped reward tells the agent, tick by tick, whether it is closing on food it cannot
    # see (a hot/cold signal that reaches action selection through DA and 5HT on the legacy profile). False (the
    # research profile from G46): shaping reads the nearest *visible* target only; a hidden goal still rewards on
    # contact.
    shape_hidden: bool = True
    contact_bonus: float = 1.0  # reward for touching a target
    pain_weight: float = 1.0  # penalty per unit pain signal


@dataclass
class ValueMemoryConfig:
    # What the steering reads (M2b step 4, docs/prereg/m2b_gate.md): "tabular", this map over the estimate's bins (every
    # profile so far); "sr", the successor representation's value V = M R over the place code (needs place.enabled;
    # brain.systems.successor_features, PlaceConfig.sr_*); "none", no value steering. This map learns in all three.
    source: str = "tabular"
    learning_rate: float = 0.2
    discount: float = 0.9
    capacity: int = 200  # trajectory length retained for replay
    lookahead: float = 1.0  # distance projected ahead to read neighbouring place values
    # reachable_probes (M3 step 2, draft): each direction's value is read only as far as the agent can see it could go
    # (the Observation's free_space, needs sensors.free_space_sensing): the probe point is pulled back to just short of
    # the nearest solid in that direction, so a place behind a wall is not read as one step away. False: every run so far.
    reachable_probes: bool = False
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
    # Oracle homing: the goal-vector slot, an explicit oracle control condition
    # (docs/research_plan.md section 6; relabelled from ``goal_vector`` in M1).
    # Remember the place cell where reward was found and, wherever the sampled
    # value map is locally flat (largest sampled advantage below
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
    # ``goal_vector`` stays as a read/write alias of this field (the property
    # below), so existing call sites and ``--set value_memory.goal_vector=...``
    # keep working; to_dict writes ``oracle_homing`` and from_dict accepts
    # either name. The goal_vector_* fields below name the mechanism and keep
    # their names.
    oracle_homing: bool = False
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

    # Former field names accepted by ``EngineConfig.from_dict`` (not fields: not
    # in ``fields()``, ``to_dict`` or ``diff``).
    FIELD_ALIASES: ClassVar[Mapping[str, str]] = {"goal_vector": "oracle_homing"}

    @property
    def goal_vector(self) -> bool:
        """Alias of :attr:`oracle_homing` (the field's name before M1); reads and writes it."""
        return self.oracle_homing

    @goal_vector.setter
    def goal_vector(self, value: bool) -> None:
        self.oracle_homing = value

    def __post_init__(self) -> None:
        if self.source not in VALUE_SOURCES:
            raise ValueError(f"value_memory.source must be one of {VALUE_SOURCES}, got {self.source!r}")


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
    # --- M2b step 1 (docs/prereg/m2b_estimate.md) ---
    # heading_source: "integrated" sums the egomotion turn into the heading estimate (every profile so far);
    # "oracle" takes the Observation's ``heading`` (needs sensors.heading_oracle).
    heading_source: str = "integrated"
    # wall_reset: on every tick the body touches a wall, the estimate's coordinate along that wall's normal is set to
    # the wall's (Hardcastle, Ganguli & Giocomo 2015, for the reset only); the wall is identified by snapping the
    # allocentric contact normal (heading estimate + the touch's egocentric angle) to the nearest arena axis; the
    # along-wall coordinate is untouched. Needs sensors.wall_contact_sensing. reset_bounds is the arena's half-extent
    # the agent knows, in its estimate frame (which starts at the body's start pose); None means the world's bounds.
    wall_reset: bool = False
    reset_bounds: Optional[Tuple[float, float]] = None
    # --- decisions G48: the estimate learns where the cues are and corrects itself from them ---
    # landmark_gain (0: off, every run before G48): each tick, the estimate moves this fraction of the way toward the
    # position the cues it sees imply, from where it has learned they are (the mean over the seen cues it has seen at
    # least landmark_min_sightings times). landmark_learning_rate: each sighting moves a cue's learned position this
    # fraction toward where the (corrected) estimate puts it (the plain mean of its sightings until 1/n falls below
    # the rate). The map is learned slowly and the self corrected fast, because the cues stay put and the estimate
    # drifts; set from that reason before any run, not tuned. Needs sensors.landmark_sensing.
    landmark_gain: float = 0.0
    landmark_learning_rate: float = 0.01
    landmark_min_sightings: int = 20

    def __post_init__(self) -> None:
        if not (0.0 <= self.landmark_gain <= 1.0 and 0.0 < self.landmark_learning_rate <= 1.0 and self.landmark_min_sightings >= 1):
            raise ValueError("landmark_gain must be in [0, 1], landmark_learning_rate in (0, 1], landmark_min_sightings >= 1")
        if self.heading_source not in HEADING_SOURCES:
            raise ValueError(f"heading_source must be one of {HEADING_SOURCES}, got {self.heading_source!r}")
        if self.reset_bounds is not None:
            bounds = tuple(float(b) for b in self.reset_bounds)
            if len(bounds) != 2 or not all(math.isfinite(b) and b > 0.0 for b in bounds):
                raise ValueError("reset_bounds must be two positive finite half-extents, or None")
            object.__setattr__(self, "reset_bounds", bounds)


@dataclass
class PlaceConfig:
    """M2b step 2 (docs/prereg/m2b_place_population.md): a Gaussian place-cell population over the position estimate.

    Off by default in both profiles. On, the engine computes every tick the rates r_j = max_rate * exp(-|e - c_j|^2
    / (2 width^2)) of cells centred on a regular grid of pitch ``spacing`` over the arena (``extent`` is the
    half-extent the grid covers; None means the world's bounds), at the spatial system's estimate e
    (``brain.systems.place_population``). The rates feed nothing yet: no action, no learner, no TickData field.
    """

    enabled: bool = False
    spacing: float = 1.0  # units between neighbouring centres (0.1 m): 400 cells in the 2 m box
    width: float = 1.0  # the Gaussian's sd, units (0.1 m; full width at half maximum 0.24 m)
    max_rate: float = 1.0
    extent: Optional[Tuple[float, float]] = None
    # M2b step 4: the SR over the population, learned online when value_memory.source is "sr" (successor features from
    # the identity by TD(0) on the normalised rates; the reward weights R by normalised least mean squares on the map
    # reward at arrival, R += reward_learning_rate * (r - phi.R) phi / |phi|^2). V(p) = phi(p) . (M^T R).
    sr_learning_rate: float = 0.1
    sr_discount: float = 0.95
    reward_learning_rate: float = 0.5
    # How R learns: "nlms" (the preregistered rule above; a regression of the point reward on overlapping fields, which
    # rings the goal with negative weights: decisions G36) or "per_feature", exploratory (each weight tracks the reward
    # seen while its cell is active, R += reward_learning_rate * phi * (r - R), so R >= 0 when rewards are >= 0).
    reward_rule: str = "nlms"
    # G41 (docs/prereg/sr_unlearning_rate.md): with the per-feature rule, the rate at which R falls toward 0 at the
    # active cells on a tick that sees no reward (r == 0). None, the default and the research profile's, uses
    # reward_learning_rate: the rule exactly as G36 preregistered it. A separate, higher rate is the unlearning the
    # circling measurement (G40) pointed to: the value at a just-emptied place outlasting the reward. Read by the
    # per-feature rule only.
    reward_unlearning_rate: Optional[float] = None
    # reward_step_cap (G52): each cell's per-feature step is min(1, rate * phi_i), so a weight moves at most all the way
    # to its target and never past it. Off, every registered run: with the unlearning rate 4 a step overshoots wherever
    # one cell carries more than a quarter of phi (near walls in the open arena, a third of hidden food's ticks, |R|
    # staying below 0.1) and diverges where one carries more than half (the 0.1 m track, where a cell reaches 0.92: G51's
    # track runs with memory steering were made with weights that blew up).
    reward_step_cap: bool = False

    def __post_init__(self) -> None:
        for name in ("spacing", "width", "max_rate", "sr_learning_rate", "reward_learning_rate"):
            value = getattr(self, name)
            if not (math.isfinite(value) and value > 0.0):
                raise ValueError(f"place.{name} must be a positive finite number, got {value!r}")
        if self.reward_unlearning_rate is not None:
            if not (math.isfinite(self.reward_unlearning_rate) and self.reward_unlearning_rate > 0.0):
                raise ValueError(f"place.reward_unlearning_rate must be a positive finite number or None, got {self.reward_unlearning_rate!r}")
        if self.extent is not None:
            extent = tuple(float(e) for e in self.extent)
            if len(extent) != 2 or not all(math.isfinite(e) and e > 0.0 for e in extent):
                raise ValueError("place.extent must be two positive finite half-extents, or None")
            object.__setattr__(self, "extent", extent)
        if not (math.isfinite(self.sr_discount) and 0.0 <= self.sr_discount < 1.0):
            raise ValueError("place.sr_discount must be in [0, 1)")
        if self.reward_rule not in REWARD_RULES:
            raise ValueError(f"place.reward_rule must be one of {REWARD_RULES}, got {self.reward_rule!r}")


REWARD_RULES: Tuple[str, ...] = ("nlms", "per_feature")


VALUE_SOURCES: Tuple[str, ...] = ("tabular", "sr", "none")


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
    # The checksum-changed "novelty" bit (brain.systems.working_memory) in
    # action selection: novelty_gain adds novelty_gain * novelty (scaled by
    # dopamine through dopamine_explore_gain) to FORWARD, novelty_turn_gain adds
    # novelty_turn_gain * novelty to each TURN channel (the 0.3 that was a
    # literal in _channel_scores until M2a). The research profile sets both to
    # 0: the bit is still computed, logged (TickData.wm_novelty) and fed to the
    # ACh and NE traces, but no longer moves the decision (docs/profiles.md).
    novelty_gain: float = 0.2  # exploration drive from working-memory novelty
    novelty_turn_gain: float = 0.3  # the same bit on the two TURN channels
    turn_bias: float = 0.0  # constant bias: >0 favours TURN_LEFT, <0 favours TURN_RIGHT
    vision_gain: float = 0.6  # drive toward a visible target (0 => blind to vision)
    wall_avoid_gain: float = 0.6  # drive to turn away from a close wall ahead
    # M3 step 1b (docs/prereg/m3_corridor.md, G45). wall_avoid_range: the fraction of sensors.vision_range within which
    # a wall on the centre ray counts as ahead (closeness max(0, 1 - dist / range)); 1.0, every result to date, reads
    # a wall up to 1.2 m away, so in a 0.1 m corridor a heading ~5 degrees off the axis already has a "wall ahead".
    # turn_commitment: added to the previous tick's turn channel while a wall is ahead, so a wall dead ahead does not
    # leave the two turns tied tick after tick (the agent dithered at a track's ends, G44). 0 is off.
    wall_avoid_range: float = 1.0
    turn_commitment: float = 0.0
    # orient_gain (M3 step 2, Part 2; docs/prereg/m3_step2.md): a target seen off to one side and not ahead adds this
    # to the turn toward it, so the agent turns to face a reward it sees before it approaches (a rat orients to a seen
    # reward). 1.0 outweighs FORWARD's bias of 0.8, set from that reason before any pilot; the approach's own drive
    # (vision_gain x closeness) alone was too weak to turn the agent (the visible approach had rested on wall turning).
    # 0 is off, every run so far.
    orient_gain: float = 0.0
    # unmotivated_rest (G52): REST's drive when the agent has no reason to move (motivation.enabled; the "idle" term is
    # this times 1 - the drive). 1.0 outweighs FORWARD's bias (0.8) and a wall's pull to turn (at most 0.9), set from
    # that reason: an agent with nothing to move for stops. Inert at a drive of 1 (motivation off: every run so far).
    unmotivated_rest: float = 1.0
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
class HistoryConfig:
    """What the agent has sensed and done, and where (``brain.systems.history``; G52). Off by default.

    ``channels``: the senses that write history (registered in ``brain.systems.history.CHANNELS``: "taste", "visit",
    "sight"; more are added there). ``*_timescales``: each channel's trace timescales, in ticks (0.2 s): 2 s, 20 s and
    200 s, a log-spaced basis spanning a lap, a trial and a regrowth, set before any run. ``visit_familiarisation``:
    ticks spent at a place for it to become familiar (about ten seconds); ``visit_forgetting``: ticks for that to fade
    (an hour: not within a session). ``reward_context``: the channels whose traces condition the SR's expected reward,
    through weights learned from its prediction errors (what history means is learned). ``schema`` (G53): those
    weights fixed instead, per reward-context channel, one per timescale; then R learns from its own error alone and
    the history term is read on top (None: learned, as G52 built it). Needs place.enabled."""

    enabled: bool = False
    channels: Tuple[str, ...] = ("taste", "visit")
    taste_timescales: Tuple[float, ...] = (10.0, 100.0, 1000.0)
    sight_timescales: Tuple[float, ...] = (10.0, 100.0, 1000.0)
    visit_familiarisation: float = 50.0
    visit_forgetting: float = 18000.0
    reward_context: Tuple[str, ...] = ("taste",)
    schema: Optional[Dict[str, Tuple[float, ...]]] = None


@dataclass
class MotivationConfig:
    """Loops that give the agent a reason to move (``brain.systems.motivation``; G52). Off by default (a drive of 1).

    Each value set from a stated reason before any run, in ticks (0.2 s): curiosity rises within 2 s of novelty and
    fades over 30 s after it; a meal registers after 30 s (``satiety_delay``) and is digested over 2 h; a rat sates on
    about 150 pellets (``satiety_per_meal``); it starts food-restricted, as rats in such experiments are
    (``hunger_initial`` 1); a reward lifts its expectation at once and the expectation fades over 2 min of none.
    ``reasons``: the motives the drive composes (``brain.systems.motivation.REASONS``): ``forage`` is hunger itself
    (G53: a food-restricted rat runs for food it has not found; G52 had it hunger × the reward trace, which left a
    hungry agent resting), and the reward trace sets *vigour*, ``vigour_floor`` + (1 − floor) × trace, which scales
    the forward bias (Niv, Daw, Joel & Dayan 2007: the reward rate sets how hard it works, not whether). Needs
    history's visit channel (novelty)."""

    enabled: bool = False
    curiosity_rise: float = 10.0
    curiosity_fall: float = 150.0
    satiety_per_meal: float = 1.0 / 150.0
    satiety_delay: int = 150
    satiety_digestion: float = 36000.0
    hunger_initial: float = 1.0
    reward_trace_rise: float = 1.0
    reward_trace_fall: float = 600.0
    vigour_floor: float = 0.5
    reasons: Tuple[str, ...] = ("explore", "forage")


# The obstacles work's instrument, adopted by the research profile at the owner's decision (docs/decisions.md G50),
# and the values every experiment registered before it pins so it still means what it said.
RESEARCH_G50: Dict[str, Any] = {
    "sensors.lateral_odometry": True,
    "sensors.landmark_sensing": True,
    "spatial.landmark_gain": 0.1,
    "sensors.free_space_sensing": True,
    "value_memory.reachable_probes": True,
}
# G52's cap on the per-feature reward step, adopted by the research profile at the owner's decision (docs/decisions.md
# G53); every experiment registered before it pins the old value. PRE_G50 carries it too: the profile before G50 had
# no cap either, so a pre-G50 registration still means what it said.
PRE_G53: Dict[str, Any] = {"place.reward_step_cap": False}
PRE_G50: Dict[str, Any] = {
    "sensors.lateral_odometry": False,
    "sensors.landmark_sensing": False,
    "spatial.landmark_gain": 0.0,
    "sensors.free_space_sensing": False,
    "value_memory.reachable_probes": False,
    **PRE_G53,
}


@dataclass
class EngineConfig:
    """Aggregate of every subsystem's configuration.

    ``profile`` labels the set of flags in force: ``"legacy"`` for the defaults
    (``EngineConfig()`` and :meth:`legacy`) and ``"research"`` for
    :meth:`research`. It is a label only: it is not logged in TickData and never
    enters a trace hash. docs/profiles.md lists what the two profiles differ
    in; :meth:`diff` computes it. ``units`` (:class:`UnitsConfig`) declares
    what a tick and a world unit mean in seconds and metres; it is identical
    in both profiles and read by no engine constant. :meth:`to_dict` and
    :meth:`from_dict` serialise the whole config as a nested plain dict.
    """

    profile: str = "legacy"
    units: UnitsConfig = field(default_factory=UnitsConfig)
    world: WorldConfig = field(default_factory=WorldConfig)
    body: BodyConfig = field(default_factory=BodyConfig)
    sensors: SensorConfig = field(default_factory=SensorConfig)
    astrocyte: AstrocyteConfig = field(default_factory=AstrocyteConfig)
    neuromod: NeuromodConfig = field(default_factory=NeuromodConfig)
    reward: RewardConfig = field(default_factory=RewardConfig)
    value_memory: ValueMemoryConfig = field(default_factory=ValueMemoryConfig)
    criticality: CriticalityConfig = field(default_factory=CriticalityConfig)
    spatial: SpatialConfig = field(default_factory=SpatialConfig)
    place: PlaceConfig = field(default_factory=PlaceConfig)
    trn: TRNConfig = field(default_factory=TRNConfig)
    working_memory: WorkingMemoryConfig = field(default_factory=WorkingMemoryConfig)
    basal_ganglia: BasalGangliaConfig = field(default_factory=BasalGangliaConfig)
    history: HistoryConfig = field(default_factory=HistoryConfig)
    motivation: MotivationConfig = field(default_factory=MotivationConfig)

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
          selection). The odometry values were characterised in milestone 1 and
          kept (docs/odometry.md); the temperature is still a placeholder.
          What they fix is that two seeds under this profile are two different
          runs, which :meth:`stochastic_elements` and ``core.seeds`` can check.
        - ``sensors.forward_delta_limit = 2.0`` (milestone 2a): the Observation's
          egomotion range is wide enough that the speed error keeps both signs.
          At the legacy 1.0 a full-thrust step sits at the top of the range, so
          positive errors were clamped away and a full-speed step averaged 0.980
          instead of 1.0 (docs/odometry.md); the body is unchanged.
        - ``basal_ganglia.novelty_gain = 0.0`` and ``novelty_turn_gain = 0.0``
          (milestone 2a): the checksum-changed "novelty" bit no longer enters
          action selection. It is still computed and logged (``wm_novelty``)
          and still feeds the ACh and NE traces, which are logged too.

        Also set explicitly, but already the legacy value, so not in the diff:
        ``value_memory.generalization_radius = 0``, ``value_memory.oracle_homing
        = False`` (the goal-vector slot) and ``basal_ganglia.criticality_gain =
        0.0`` (the criticality coupling to cognition; kappa is still computed
        and logged).

        - Milestone 2b's exit (docs/decisions.md G37): the instrument the
          RQ4(a) gate passed with. ``sensors.heading_oracle = True`` with
          ``heading_oracle_noise = 0.05`` (the declared heading oracle, sd 0.05
          rad per tick on its own stream, ``sensors_heading``: the fourth seeded
          element) and ``spatial.heading_source = "oracle"``;
          ``sensors.wall_contact_sensing = True`` and ``spatial.wall_reset =
          True`` (the wall-contact position reset); ``place.enabled = True``
          (the 400-cell Gaussian population over the estimate) with
          ``place.reward_rule = "per_feature"`` and ``value_memory.source =
          "sr"`` (the successor-feature value V = M R steers where the tabular
          map did; the map still learns). The research baselines were
          regenerated once for it (docs/profiles.md).

        - The obstacles work (docs/decisions.md G48-G50; ``RESEARCH_G50``): ``sensors.lateral_odometry``,
          ``sensors.landmark_sensing`` with ``spatial.landmark_gain = 0.1``, ``sensors.free_space_sensing`` and
          ``value_memory.reachable_probes``. Every experiment registered before G50 pins the old values
          (``PRE_G50``); its recorded runs also reproduce at their recorded commits.
        - The audit of 2026-10-27 (docs/decisions.md G46): ``sensors.unseen_block_rays
          = False`` (a hidden or eaten object is not seen: vision rays and whiskers
          pass through it, where they used to stop at it and report its kind) and
          ``reward.shape_hidden = False`` (approach shaping reads visible targets
          only; a hidden goal still rewards on contact). The research baselines
          contain no hidden object and are unchanged by them.
        - ``place.reward_step_cap = True`` (docs/decisions.md G53): each cell's per-feature reward step is at most
          all the way to its target, min(1, rate × φᵢ). Inert at this profile's rate (0.5 × φ ≤ 1); it binds where a
          scenario sets the renewable-reward unlearning rate. Every experiment registered before it pins the old
          value (``PRE_G53``, carried by ``PRE_G50`` too).

        Nothing else differs. Not yet in this profile: replay as an event
        stream inside the engine (M3; the M2a linear-track experiments run
        their replay rules outside the engine, experiments.linear_track_replay).
        """
        cfg = cls(profile="research")
        cfg.sensors.odometry_speed_noise = 0.05
        cfg.sensors.odometry_turn_noise = 0.01
        cfg.sensors.forward_delta_limit = 2.0
        cfg.spatial.gate_scales_egomotion = False
        cfg.astrocyte.scales_motion = False
        cfg.astrocyte.frozen = True
        cfg.trn.microsleep_enabled = False
        cfg.trn.narrow_above_kappa = float("inf")
        cfg.value_memory.generalization_radius = 0
        cfg.value_memory.oracle_homing = False
        cfg.value_memory.dwell_extinction = 0.0
        bg = cfg.basal_ganglia
        bg.criticality_gain = 0.0
        bg.novelty_gain = 0.0
        bg.novelty_turn_gain = 0.0
        bg.dopamine_explore_gain = 0.0
        bg.ach_precision_gain = 0.0
        bg.ne_threat_gain = 0.0
        bg.fiveht_patience_gain = 0.0
        bg.softmax_temperature = 0.1
        # Milestone 2b's exit (docs/decisions.md G37): the configuration the RQ4(a) gate passed with.
        cfg.sensors.heading_oracle = True
        cfg.sensors.heading_oracle_noise = 0.05
        cfg.sensors.wall_contact_sensing = True
        cfg.spatial.heading_source = "oracle"
        cfg.spatial.wall_reset = True
        cfg.place.enabled = True
        cfg.place.reward_rule = "per_feature"
        cfg.value_memory.source = "sr"
        # The audit of 2026-10-27 (docs/decisions.md G46): nothing hidden is sensed, by vision or by shaping.
        cfg.sensors.unseen_block_rays = False
        cfg.reward.shape_hidden = False
        # The obstacles work's instrument (docs/decisions.md G48-G50): the agent feels its sideways displacement, sees
        # distal cues and corrects its estimate from a map of them it learns (inert where there are no cues), senses
        # the free space along its value fan and reads value only where it could go (inert without a solid near).
        for key, value in RESEARCH_G50.items():
            cfg.set_field(key, value)
        # G52's cap on the per-feature reward step (docs/decisions.md G53): a weight never passes its target.
        cfg.place.reward_step_cap = True
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
        # The heading oracle's error draws only while the oracle is on (M2b step 1), so it is counted only then; it is
        # not in STOCHASTIC_PARAMETERS, whose entries draw whenever they are > 0.
        if self.sensors.heading_oracle and self.sensors.heading_oracle_noise > 0.0:
            out.append(f"sensors.heading_oracle_noise={self.sensors.heading_oracle_noise!r}")
        return out

    def get_field(self, key: str) -> Any:
        """The value of the dotted field ``key`` (``"sensors.noise"``); an unknown field is an ``AttributeError``."""
        obj, attr = _walk_dotted(self, key)
        return getattr(obj, attr)

    def set_field(self, key: str, value: Any) -> None:
        """Set the dotted field ``key`` (``"sensors.noise"``) to ``value``.

        The one dotted setter: the harness's ``--set``, the G23 overrides and
        the console's live parameters all go through it. A former field name
        that a section keeps as a property alias (``value_memory.goal_vector``
        for ``oracle_homing``) works; an unknown field raises
        ``AttributeError`` naming the dotted path, so a typo is never a silent
        new attribute. The value is assigned as given (no coercion and no
        ``__post_init__`` re-validation: that is ``from_dict``'s job).
        """
        obj, attr = _walk_dotted(self, key)
        setattr(obj, attr, value)

    def diff(self, other: "EngineConfig") -> List[Tuple[str, Any, Any]]:
        """Fields where ``self`` and ``other`` differ: (dotted.field, self_value, other_value).

        Every nested config dataclass is walked in field declaration order, so
        the list is deterministic, and it is empty when the two are equal.
        """
        return config_diff(self, other)

    def to_dict(self) -> Dict[str, Any]:
        """Every field as a nested plain dict, ``profile`` first, strict-JSON-serialisable.

        Nested config dataclasses become dicts in field declaration order,
        tuples become lists (``world.bounds``) and a non-finite float becomes
        the string ``"inf"``, ``"-inf"`` or ``"nan"`` (the research profile's
        ``trn.narrow_above_kappa``), so ``json.dumps(..., allow_nan=False)``
        accepts the result and a strict JSON reader can open it (``Infinity``
        is not JSON). Every other value is kept as it is. :meth:`from_dict`
        inverts it: ``diff`` is empty after a round trip, also through
        ``json.dumps`` / ``json.loads``.
        """
        return _dataclass_to_plain(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EngineConfig":
        """The inverse of :meth:`to_dict`.

        Every key must name a field at its level, or a former name of one that
        the section lists in ``FIELD_ALIASES`` (``value_memory.goal_vector``
        for ``oracle_homing``; giving both with different values raises); an
        unknown key raises ``ValueError`` naming the dotted path, so a typo or
        a field from a later version is never dropped silently. A key that is
        missing keeps the field's default. A list is turned back into a tuple where the
        field holds a tuple, and the strings ``"inf"``, ``"-inf"`` and
        ``"nan"`` back into floats where the field holds a float; nothing
        else changes type. Each section's ``__post_init__`` runs after its
        fields are set, so the validation a constructor does (``UnitsConfig``
        rejects a non-positive ``dt_s``) applies to deserialised values too.
        """
        cfg = cls()
        _dataclass_from_plain(cfg, data, "")
        return cfg


def _walk_dotted(config: Any, key: str) -> Tuple[Any, str]:
    """The object and attribute name a dotted ``key`` names, or ``AttributeError`` for an unknown field."""
    obj = config
    parts = key.split(".")
    for part in parts[:-1]:
        if not hasattr(obj, part):
            raise AttributeError(f"config has no field {key!r}")
        obj = getattr(obj, part)
    if not hasattr(obj, parts[-1]):
        raise AttributeError(f"config has no field {key!r}")
    return obj, parts[-1]


_NON_FINITE_TO_STR = {math.inf: "inf", -math.inf: "-inf"}
_STR_TO_NON_FINITE = {"inf": math.inf, "-inf": -math.inf, "nan": math.nan}


def _dataclass_to_plain(obj: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        if is_dataclass(value):
            out[f.name] = _dataclass_to_plain(value)
        elif isinstance(value, tuple):
            out[f.name] = list(value)
        elif isinstance(value, float) and not math.isfinite(value):
            out[f.name] = "nan" if math.isnan(value) else _NON_FINITE_TO_STR[value]
        else:
            out[f.name] = value
    return out


def _resolve_aliases(obj: Any, data: Mapping[str, Any], prefix: str) -> Dict[str, Any]:
    """``data`` with the section's former field names (``FIELD_ALIASES``) replaced by the current ones."""
    aliases: Mapping[str, str] = getattr(type(obj), "FIELD_ALIASES", {})
    out: Dict[str, Any] = {}
    for key, value in data.items():
        name = aliases.get(key, key) if isinstance(key, str) else key
        if name in out and out[name] != value:
            raise ValueError(f"config field {prefix}{name} given twice ({key!r} is an alias of it) with different values")
        out[name] = value
    return out


def _dataclass_from_plain(obj: Any, data: Mapping[str, Any], prefix: str) -> None:
    if not isinstance(data, Mapping):
        raise ValueError(f"config section {prefix or '<root>'}: expected a mapping, got {type(data).__name__}")
    data = _resolve_aliases(obj, data, prefix)
    known = [f.name for f in fields(obj)]
    unknown = sorted(str(k) for k in data if k not in known)
    if unknown:
        raise ValueError("unknown config field(s): " + ", ".join(prefix + k for k in unknown))
    for name in known:
        if name not in data:
            continue
        current = getattr(obj, name)
        value = data[name]
        if is_dataclass(current):
            _dataclass_from_plain(current, value, f"{prefix}{name}.")
        elif isinstance(current, tuple):
            setattr(obj, name, tuple(value))
        elif isinstance(current, float) and isinstance(value, str) and value in _STR_TO_NON_FINITE:
            setattr(obj, name, _STR_TO_NON_FINITE[value])
        else:
            setattr(obj, name, value)
    # The constructor's validation, for values that arrived by assignment.
    post_init = getattr(obj, "__post_init__", None)
    if callable(post_init):
        post_init()


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
    "UnitsConfig",
    "WorldConfig",
    "BodyConfig",
    "BODY_MODELS",
    "SensorConfig",
    "AstrocyteConfig",
    "NeuromodConfig",
    "PlaceConfig",
    "RewardConfig",
    "ValueMemoryConfig",
    "SpatialConfig",
    "TRNConfig",
    "WorkingMemoryConfig",
    "BasalGangliaConfig",
    "EngineConfig",
    "HEADING_SOURCES",
    "VALUE_SOURCES",
    "STOCHASTIC_PARAMETERS",
    "config_diff",
]
