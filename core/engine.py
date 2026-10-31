"""Deterministic engine scaffold that executes the tick pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import math

from brain.contracts import Action, Observation
from brain.systems.basal_ganglia import (
    TURN_STEP,
    VALUE_STEER_MODES,
    cue_gate_weight,
    goal_vector_signals,
    select_action_with_scores,
    split_value_signals,
    wall_gate_signals,
)
from brain.systems.criticality import CriticalityField, HomeostaticCoupling, near_critical_gain
from brain.systems.interoception import hunger as interoceptive_hunger
from brain.systems.interoception import incentive as meal_incentive
from brain.systems.interoception import meal_reward
from brain.systems.interoception import satiety as interoceptive_satiety
from brain.systems.replay_events import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    RULE_REVERSE_TRAJECTORY,
    RULE_TRN_INDEX,
    TRIGGER_MICROSLEEP,
    OpenReplayEvent,
    ReplayLog,
)
from brain.systems.spatial import SpatialSystem, wrap_angle
from brain.systems.trn_microsleep_replay import TRNGate
from brain.systems.value_memory import Transition, ValueMemory
from brain.systems.working_memory import WorkingMemory
from core.body import RodentBody
from core.config import EngineConfig
from core.entities import Agent
from core.neuromodulation import NeuromodulatorSystem
from core.physiology import Astrocyte
from core.pipeline import PIPELINE_ORDER, Pipeline
from core.rng import RNG, RNGStream
from core.sensors import FREE_SPACE_ANGLES, gather_observation, observation_checksum
from core.world import World, WorldObject
from metrics.schema import TickData

GOAL_VECTOR_SOURCES = ("replay", "online")
# The actions the learned action value is over (M3 step 3; brain.systems.action_value.ACTIONS, not imported here:
# that module needs numpy and importing core.engine must not).
ACTION_VALUE_ACTIONS = ("FORWARD", "TURN_LEFT", "TURN_RIGHT")


@dataclass
class EngineContext:
    """Mutable tick state passed through the pipeline."""

    tick: int
    pos: Tuple[float, float] = (0.0, 0.0)
    heading: float = 0.0
    score: int = 0
    kappa: float = 0.0
    avalanche_size: int = 0
    criticality_active: int = 0
    neuromodulators: Dict[str, float] = field(default_factory=dict)
    observation: Observation | None = None
    observation_checksum: str = ""
    # The place population's rates at this tick's estimate (M2b step 2; None when place.enabled is off). Not in TickData.
    place_rates: Any = None
    trn_state: str = "OPEN"
    trn_gate_value: float = 1.0
    microsleep_active: bool = False
    microsleep_ticks_remaining: int = 0
    replay_active: bool = False
    replay_index: int = -1
    hd_angle: float = 0.0
    grid_x: float = 0.0
    grid_y: float = 0.0
    place_id: int = 0
    wm_load: int = 0
    wm_novelty: float = 0.0
    action_name: str = "REST"
    action_thrust: float = 0.0
    action_turn: float = 0.0
    atp: float = 0.0
    glycogen: float = 0.0
    reward: float = 0.0
    energy_scale: float = 1.0
    protocol_name: str = "no_op"
    trial_number: int = 1
    # Display-only readouts (not logged to TickData, so they never affect the
    # determinism hash): the decision that was made and what drove it.
    action_scores: Dict[str, float] = field(default_factory=dict)
    # The value signals actually fed to action selection (after cue and wall gating).
    value_signals: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    criticality_gain: float = 1.0
    # What the value map learns this tick: primary outcomes only (contact and
    # real pain) unless value_memory.learn_shaping is on. ctx.reward (dopamine's
    # input and the logged reward) is unchanged by this.
    map_reward: float = 0.0
    # G52: the drive to move (1 without motivation), the motivation loops' levels, and the familiarity of where the
    # agent is (history's visit channel; 0 without it).
    motivation: float = 1.0
    motivation_levels: Dict[str, float] = field(default_factory=dict)
    vigour: float = 1.0  # G53: the reward trace's scaling of the forward bias (1 without motivation)
    familiarity: float = 0.0
    # M3 step 3: the action value's advantages (FORWARD, TURN_LEFT, TURN_RIGHT) read this tick, whether the body is in
    # a consumption pause, and the cells of the replay event made this tick, if any.
    action_values: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    consuming: bool = False
    replay_event_cells: Tuple[Tuple[int, int], ...] = ()
    cue_gate: float = 1.0  # weight on memory steering (0 = muted by a visible target)
    wall_gate: float = 1.0  # weight on memory's hold-course push (0 = muted by a wall close ahead)
    freeze_habituation: float = 1.0  # scale on the pain->REST drive (1 = not habituated)
    pacing_active: bool = False  # homeostatic pacing is adding a REST drive this tick
    # The place cell whose value replay backed up this tick (the transition's
    # start), or None; and, with value_memory.replay_recent, how many transitions
    # back from sleep onset it is (1 = the newest) out of how many were snapshotted.
    replay_cell: Tuple[int, int] | None = None
    replay_back: int = 0
    replay_span: int = 0
    target_contact: bool = False  # touching a target this tick (the primary contact reward)
    goal_vector_active: bool = False  # the value signals came from the goal-vector memory
    previous_action: str = "REST"  # the action chosen on the tick before this decision (the turn commitment's input)
    # The whole (G56; docs/prereg/whole_resource.md), readouts: the body's energy (reserve and gut; 0 without
    # metabolism) and whether it has starved; the energy eaten this tick, the object it came from and the meal's
    # reward; interoception's hunger and incentive (0 and 1 without it); the TD error dopamine read; sleep and its
    # pressure; the criticality distance m; the softmax temperature and vision's gain on targets this tick.
    energy: float = 0.0
    gut: float = 0.0
    starved: bool = False
    ingested: float = 0.0
    ingested_object: Any = None
    meal_value: float = 0.0
    hunger: float = 0.0
    incentive: float = 1.0
    td_error: float = 0.0
    asleep: bool = False
    sleep_pressure: float = 0.0
    criticality_m: float = 1.0
    temperature: float = 0.0
    target_gain: float = 1.0
    tick_data: TickData | None = None


class Engine:
    """Runs the fixed tick pipeline (core/pipeline.py) over World, sensors and
    brain systems and emits one TickData per tick."""

    def __init__(self, seed: int, *, agent_offset: int = 0, config: EngineConfig | None = None) -> None:
        self.seed = seed
        self.agent_offset = agent_offset
        self.config = config or EngineConfig()
        c = self.config
        self.rng = RNG(seed=seed, agent_offset=agent_offset)
        self.streams: Dict[str, RNGStream] = {
            "neuromod": self.rng.stream("neuromod"),
            "criticality": self.rng.stream("criticality"),
            "sensors_vision": self.rng.stream("sensors_vision"),
            "sensors_noise": self.rng.stream("sensors_noise"),
            # Seeds-are-samples streams (docs/research_plan.md M0b item 8). Each
            # named stream derives its own child seed, so adding these leaves the
            # four above exactly as they were; at the legacy defaults (noise
            # parameters 0) neither is ever drawn from.
            "sensors_odometry": self.rng.stream("sensors_odometry"),
            "sensors_heading": self.rng.stream("sensors_heading"),  # the heading oracle's error (M2b); drawn only when on
            "action_softmax": self.rng.stream("action_softmax"),
            # The rodent body's speed and rotation noise (M3 step 1, G44); drawn only by that body, only when on.
            "body_motion": self.rng.stream("body_motion"),
            # The distal cues' bearing and distance errors (G48); drawn only when landmark sensing is on.
            "sensors_landmarks": self.rng.stream("sensors_landmarks"),
            # The uniform replay rule's draws (M3 step 3); drawn only by it, only when on.
            "replay": self.rng.stream("replay"),
        }
        self.world = World(bounds=c.world.bounds)
        self.agent = Agent(id=agent_offset, pos=(0.0, 0.0))
        self.world.add_agent(self.agent)
        # The body (M3 step 1, G44): None is the discrete body World.step applies; "rodent" moves this agent instead.
        self.body = RodentBody(c.body, c.units, self.streams["body_motion"]) if c.body.model == "rodent" else None
        self.astrocyte = Astrocyte(
            atp=c.astrocyte.atp,
            glycogen=c.astrocyte.glycogen,
            glycogen_max=c.astrocyte.glycogen_max,
            atp_baseline=c.astrocyte.atp_baseline,
            atp_cost=c.astrocyte.atp_cost,
            glycogen_to_atp_yield=c.astrocyte.glycogen_to_atp_yield,
            glycogen_recharge=c.astrocyte.glycogen_recharge,
            glycogen_regen=c.astrocyte.glycogen_regen,
            atp_floor=c.astrocyte.atp_floor,
        )
        self.neuromod_system = NeuromodulatorSystem(
            reward_lr=c.neuromod.reward_lr, rpe_scale=c.neuromod.rpe_scale
        )
        self.value_memory = ValueMemory(
            learning_rate=c.value_memory.learning_rate,
            discount=c.value_memory.discount,
            capacity=c.value_memory.capacity,
            generalization_radius=c.value_memory.generalization_radius,
            generalization_falloff=c.value_memory.generalization_falloff,
            dwell_extinction=c.value_memory.dwell_extinction,
        )
        # Per-engine action-selection state (never module-global: two engines
        # stepped side by side must not see each other's history).
        self._freeze_level = 0.0  # F: recent pain-freeze ticks (freeze habituation)
        self._recovering = False  # homeostatic pacing latch; persists across episodes like energy does
        self._prev_target_dist: float | None = None
        self._prev_target: Tuple[Any, float, float] | None = None  # (object, x, y) the shaping distance refers to
        # Microsleep replay plan (value_memory.replay_recent): the recent transitions
        # snapshotted at sleep onset, most recent first, and the replay step within it.
        self._replay_plan: List[Transition] | None = None
        self._replay_step = 0
        # Replay as an event object (brain.systems.replay_events, M1): the replay
        # in progress and the bounded log of finished ones. Bookkeeping beside
        # the backups: nothing here feeds TickData or the trace hash.
        self._replay_event: OpenReplayEvent | None = None
        self.replay_log = ReplayLog()
        # Episode counters for the decision log (metrics.decisions, G40): ``episode`` counts calls to
        # ``begin_episode`` (a reset or a scenario's teleport), ``value_episode`` the learners' boundaries
        # (``reset_value_episode``). Readouts; nothing in the pipeline reads them.
        self.episode = 0
        self.value_episode = 0
        # Goal-vector extinction: whether the agent is inside the remembered goal's
        # place cell on this visit, whether it found reward there, and how many
        # visits in a row (to the goal held in _goal_misses_cell) found none.
        self._goal_visit = False
        self._goal_visit_rewarded = False
        self._goal_misses = 0
        self._goal_misses_cell: Tuple[int, int] | None = None
        self.criticality = CriticalityField(stream=self.streams["criticality"], config=c.criticality)
        self.trn_gate = TRNGate(
            trigger_atp=c.trn.trigger_atp,
            trigger_streak=c.trn.trigger_streak,
            duration=c.trn.duration,
            recovery_atp=c.trn.recovery_atp,
            recovery_streak_needed=c.trn.recovery_streak_needed,
            replay_window=c.trn.replay_window,
            closed_below_atp=c.trn.closed_below_atp,
            open_at_atp=c.trn.open_at_atp,
            narrow_above_kappa=c.trn.narrow_above_kappa,
            narrow_gain=c.trn.narrow_gain,
            microsleep_enabled=c.trn.microsleep_enabled,
        )
        if c.spatial.heading_source == "oracle" and not c.sensors.heading_oracle:
            raise ValueError("spatial.heading_source 'oracle' needs sensors.heading_oracle = True")
        if c.spatial.wall_reset and not c.sensors.wall_contact_sensing:
            raise ValueError("spatial.wall_reset needs sensors.wall_contact_sensing = True")
        if c.value_memory.reachable_probes and not c.sensors.free_space_sensing:
            raise ValueError("value_memory.reachable_probes needs sensors.free_space_sensing = True")
        if FREE_SPACE_ANGLES != (0.0, *self.VALUE_FAN_OFFSETS, *(-o for o in self.VALUE_FAN_OFFSETS)):
            raise ValueError("core.sensors.FREE_SPACE_ANGLES must be the value fan (ahead, left, right)")
        if c.spatial.landmark_gain > 0.0 and not c.sensors.landmark_sensing:
            raise ValueError("spatial.landmark_gain > 0 needs sensors.landmark_sensing = True")
        self.spatial = SpatialSystem(
            turn_gain=c.spatial.turn_gain, decay=c.spatial.decay, bin_size=c.spatial.bin_size,
            heading_source=c.spatial.heading_source, wall_reset=c.spatial.wall_reset,
            # The agent knows the arena's half-extent in its estimate frame (declared, docs/prereg/m2b_estimate.md).
            reset_bounds=(c.spatial.reset_bounds or tuple(self.world.bounds)) if c.spatial.wall_reset else None,
            landmark_gain=c.spatial.landmark_gain, landmark_learning_rate=c.spatial.landmark_learning_rate,
            landmark_min_sightings=c.spatial.landmark_min_sightings,
        )
        # The place population (M2b step 2), off by default. Imported here, not at the top: it needs numpy, and
        # importing core.engine must not import numpy (docs/determinism.md, numpy rule 2).
        self.place = None
        self.place_rates = None
        if c.place.enabled:
            from brain.systems.place_population import PlacePopulation

            self.place = PlacePopulation(c.place.extent or tuple(self.world.bounds), spacing=c.place.spacing,
                                         width=c.place.width, max_rate=c.place.max_rate)
        # The SR value source (M2b step 4): successor features over the population and reward weights R, learned online
        # from the agent's own transitions and the map reward; the steering reads V(p) = phi(p) . (M^T R).
        self.sr = None
        self.sr_weights = None
        self._sr_prev = None
        self._sr_u = None
        if c.value_memory.source in ("sr", "action", "sr_action"):  # "action" (M3 step 3) keeps the SR too: need reads its rows
            if self.place is None:
                raise ValueError(f"value_memory.source {c.value_memory.source!r} needs place.enabled = True")
            import numpy as np

            from brain.systems.successor_features import SuccessorFeatures

            self.sr = SuccessorFeatures(self.place.size, c.place.sr_learning_rate, c.place.sr_discount)
            self.sr_weights = np.zeros(self.place.size, dtype=np.float64)
        # History and motivation (G52), off by default: decaying place-tagged traces fed by the senses, whose meaning
        # for the SR's expected reward is learned; and loops that give the agent a reason to move.
        self.history = None
        self.motivation = None
        if c.history.enabled:
            if self.place is None:
                raise ValueError("history.enabled needs place.enabled = True (its traces are over the place features)")
            if c.history.reward_context and self.sr is not None and c.place.reward_rule != "per_feature":
                raise ValueError("history.reward_context conditions the per-feature reward rule only")
            from brain.systems.history import History, HistorySettings

            self.history = History(self.place.size, HistorySettings(
                channels=tuple(c.history.channels), taste_timescales=tuple(c.history.taste_timescales),
                sight_timescales=tuple(c.history.sight_timescales), visit_familiarisation=c.history.visit_familiarisation,
                visit_forgetting=c.history.visit_forgetting, reward_context=tuple(c.history.reward_context),
                schema={k: tuple(v) for k, v in c.history.schema.items()} if c.history.schema else None))
        if c.motivation.enabled:
            if self.history is None or "visit" not in c.history.channels:
                raise ValueError("motivation.enabled needs history.enabled with the 'visit' channel (novelty)")
            from brain.systems.motivation import Motivation, default_loops

            self.motivation = Motivation(default_loops(c.motivation), c.motivation.hunger_initial, tuple(c.motivation.reasons),
                                         c.motivation.vigour_floor)
        # A learned action value over the place code, its transition memory and replay at the consumption pause (M3
        # step 3; docs/prereg/m3_step3.md), off by default.
        self.action_learner = None
        self.transition_memory = None
        self.replay_rule = None
        self._av_prev = None  # (phi, action, x, y, cell) of the last movement tick: the next transition's start
        self._av_phi = None  # phi this tick, for the value read
        self._consume_remaining = 0
        if c.action_value.enabled:
            if self.place is None:
                raise ValueError("action_value.enabled needs place.enabled = True (its features are the place code)")
            from brain.systems.action_value import LinearQ, PlaceActionLearner
            from brain.systems.replay_rules import TransitionMemory

            av = c.action_value
            n_features = self.place.size
            if av.history_features:  # amendment A1: phi and phi times each taste trace
                if self.history is None or "taste" not in c.history.channels:
                    raise ValueError("action_value.history_features needs history.enabled with the 'taste' channel")
                n_features *= 1 + len(self.history.banks["taste"].timescales)
            self.action_learner = PlaceActionLearner(LinearQ(n_features, av.learning_rate, av.discount, av.lam, av.traces),
                                                     self._av_features)
            self.transition_memory = TransitionMemory(c.replay.memory_capacity)
            self.replay_rule = self._make_replay_rule(c.replay.rule)
        elif c.replay.rule != "none":
            raise ValueError("replay.rule needs action_value.enabled = True (the rule backs up the action value)")
        if c.value_memory.source in ("action", "sr_action") and self.action_learner is None:
            raise ValueError(f"value_memory.source {c.value_memory.source!r} needs action_value.enabled = True")
        # The whole (G56; docs/prereg/whole_resource.md §2), every part off by default: the body's metabolism,
        # interoception, the neuromodulators in their roles, homeostatic sleep, criticality as a state variable, and
        # replay of the successor map.
        self.metabolism = None
        if c.metabolism.enabled:
            from core.metabolism import Metabolism

            mc = c.metabolism
            self.metabolism = Metabolism(mc.start, mc.basal_cost, mc.locomotion_factor, mc.sleep_factor, mc.absorption_time)
        if c.interoception.enabled and self.metabolism is None:
            raise ValueError("interoception.enabled needs metabolism.enabled (there is no energy to sense)")
        self.bio_neuromod = None
        if c.neuromod.model == "biological":
            from brain.systems.neuromodulators import BiologicalNeuromodulators

            self.bio_neuromod = BiologicalNeuromodulators(c.neuromod)
        self.sleep = None
        if c.sleep.enabled:
            from brain.systems.sleep import SleepHomeostat

            sc = c.sleep
            self.sleep = SleepHomeostat(sc.wake_time_constant, sc.sleep_time_constant, sc.onset, sc.offset,
                                        sc.hunger_blocks_onset, sc.hunger_wakes)
        self.crit_coupling = None
        if c.criticality.dynamic:
            self.crit_coupling = HomeostaticCoupling(c.criticality.critical_coupling, c.criticality.sleep_coupling,
                                                     c.criticality.homeostasis_time)
        self.sr_replay = None
        if c.replay.sr_replay:
            if self.sr is None:
                raise ValueError("replay.sr_replay needs the successor features (value_memory.source 'sr' or 'sr_action')")
            from brain.systems.sr_replay import SRReplay

            self.sr_replay = SRReplay(c.replay.sr_memory_capacity)
        self._hunger = 0.0  # interoception's hunger at the end of the last brain step (sleep reads it)
        self._v_prev = None  # incentive x SR value at the last tick's estimate (dopamine's TD error)
        self._sr_prev_pos = None  # the estimate at the last online SR step (the map replay's transitions)
        self._sleep_event = None  # the replay event of a sleep in progress
        self._replay_pending: int | None = None  # a meal's replay budget, waiting for acetylcholine to allow it
        self.working_memory = WorkingMemory(capacity=c.working_memory.capacity)
        self.last_action: Action = Action(name="REST", thrust=0.0, turn=0.0)
        self.pipeline = Pipeline(
            handlers={
                "pre_tick": self._pre_tick,
                "physiology": self._physiology_step,
                "sensors": self._sensors_step,
                "trn": self._trn_step,
                "spatial": self._spatial_step,
                "wm": self._wm_step,
                "brain": self._brain_step,
                "world": self._world_step,
                "log": self._log_tick,
            },
            order=PIPELINE_ORDER,
        )

    def _pre_tick(self, ctx: EngineContext) -> None:
        ctx.tick_data = None

    def _physiology_step(self, ctx: EngineContext) -> None:
        a = self.config.astrocyte
        if a.frozen:
            # The astrocyte does not tick: ATP and glycogen keep their initial
            # values and the throttle is 1.0 (see AstrocyteConfig.frozen).
            throttle = 1.0
        else:
            # Demand scales with the agent's current effort so rest is cheap.
            demand = a.rest_demand + a.motion_demand * min(1.0, abs(self.last_action.thrust))
            throttle = self.astrocyte.tick(demand=demand)
        # World.step multiplies thrust and turn by energy_scale; with
        # scales_motion off the body moves the commanded thrust whatever ATP is.
        ctx.energy_scale = throttle if a.scales_motion else 1.0
        ctx.atp = self.astrocyte.atp
        ctx.glycogen = self.astrocyte.glycogen
        if self.metabolism is not None:  # the body's energy balance (G56): last tick's movement is paid for now
            self.metabolism.tick(self.speed_fraction(), asleep=self.sleep is not None and self.sleep.asleep)
            ctx.energy, ctx.gut, ctx.starved = self.metabolism.reserve, self.metabolism.gut, self.metabolism.starved

    def speed_fraction(self) -> float:
        """How fast the body moved on the last tick, as a fraction of full speed: the rodent body's speed over its run
        speed, the discrete body's last thrust (what metabolism charges locomotion by; G56)."""
        if self.body is not None:
            run = self.config.body.run_speed
            return self.body.speed / run if run > 0.0 else 0.0
        return abs(self.last_action.thrust)

    def _world_step(self, ctx: EngineContext) -> None:
        if self.body is not None:
            self.body.step(self.agent, self.last_action.name, self.world.bounds, ctx.energy_scale)
            if self.world.barriers:  # the body's own wall following knows the arena's walls only (G47)
                self.agent.pos = self.world.constrain(self.agent.last_pos, self.agent.pos)
        else:
            self.world.step(action=self.last_action, energy_scale=ctx.energy_scale)
        ctx.pos = self.agent.pos
        ctx.heading = self.agent.heading

    def _sensors_step(self, ctx: EngineContext) -> None:
        obs = gather_observation(
            self.agent,
            self.world,
            config=self.config.sensors,
            vision_stream=self.streams["sensors_vision"],
            noise_stream=self.streams["sensors_noise"],
            odometry_stream=self.streams["sensors_odometry"],
            heading_stream=self.streams["sensors_heading"],
            landmark_stream=self.streams["sensors_landmarks"],
        )
        ctx.observation = obs
        ctx.observation_checksum = observation_checksum(obs)

    def _trn_step(self, ctx: EngineContext) -> None:
        # The dynamic coupling (G56): the lattice's distance from criticality follows the sleep pressure, tuned back
        # homeostatically (last tick's pressure: sleep steps below).
        if self.crit_coupling is not None:
            ctx.criticality_m = self.crit_coupling.step(self.sleep.pressure if self.sleep is not None else 0.0)
            self.criticality.coupling_override = self.crit_coupling.coupling
        # Update criticality metrics before gating
        crit = self.criticality.step()
        ctx.kappa = crit.kappa
        ctx.avalanche_size = crit.avalanche_size
        ctx.criticality_active = crit.active

        # Update microsleep state based on energy
        self.trn_gate.update_microsleep(ctx.atp)
        ctx.microsleep_active = self.trn_gate.microsleep.active
        ctx.microsleep_ticks_remaining = self.trn_gate.microsleep.ticks_remaining
        # Homeostatic sleep (G56): asleep, the thalamic gate is closed, so no sensory input reaches selection (the
        # arbiter's microsleep branch: REST alone). Hunger is the last brain step's.
        if self.sleep is not None:
            pain = ctx.observation.pain_signal if ctx.observation is not None else 0.0
            ctx.asleep = self.sleep.step(self._hunger, pain)
            ctx.sleep_pressure = self.sleep.pressure
            ctx.microsleep_active = ctx.microsleep_active or ctx.asleep

        # TRN gating based on atp/kappa/microsleep
        state, gate_val = self.trn_gate.trn_state(ctx.atp, ctx.kappa)
        if ctx.asleep:
            state, gate_val = "CLOSED", 0.0
        ctx.trn_state = state
        ctx.trn_gate_value = gate_val

        # Replay gating: only allowed during microsleep
        if ctx.observation is None:
            raise RuntimeError("Observation missing before TRN step")
        replay_active, replay_index = self.trn_gate.update_replay(ctx.observation)
        if replay_active and not ctx.microsleep_active:
            raise RuntimeError("Replay active outside microsleep")
        ctx.replay_active = replay_active
        ctx.replay_index = replay_index

        # Offline consolidation: replay propagates value backward along the
        # trajectory (only during microsleep, via the same replay gating).
        self._replay(ctx, replay_active, replay_index)

    def _replay(self, ctx: EngineContext, replay_active: bool, replay_index: int) -> None:
        """Back up one stored transition per microsleep tick.

        With ``value_memory.replay_recent`` the newest ``trn.replay_window``
        transitions are snapshotted when sleep starts, so the trajectory growing
        (and its deque shifting) during sleep does not move the replay, and they
        are replayed most recent first, which carries value from where the path
        ended back along it. The reverse order is borrowed from the awake,
        reward-associated reverse replay of Foster & Wilson 2006 and Diba &
        Buzsaki 2007; replay during sleep (NREM) is mostly forward (Lee &
        Wilson 2002; Ji & Wilson 2007). This replay is neither: it is gated by
        fatigue (TRN microsleep), not time-compressed (one transition per
        tick), and a sleep lasts ``trn.duration`` (25) ticks, so it covers at
        most 25 of the 50 snapshotted transitions. The k-th replay tick backs
        up transition k of the snapshot, cycling if sleep outlasted it (never at
        the defaults). Transitions across an episode boundary are never in it,
        and ``begin_episode`` ends the replay of a sleep in progress.
        TRNGate's replay_index (logged in TickData) is not used for this.
        Without it (legacy), the TRN index is used as a trajectory index.

        Each replay is also recorded as one event (brain.systems.replay_events;
        ``self.replay_log``): opened on the bout's first replay tick (trigger
        ``"microsleep"``; rule ``"reverse_trajectory"``, direction
        ``"reverse"``, span = the snapshot's length under ``replay_recent``;
        rule ``"trn_index"``, direction ``"forward"``, span = the TRN buffer's
        length under the legacy indexing), fed the start cell of every
        transition it backs up, and closed into the log when the sleep ends or
        ``begin_episode`` cuts it. A replay that backs up nothing (an empty
        snapshot; every legacy index on an episode boundary) is no event. Under
        the legacy indexing the backups go on after a reset, so there the cut
        splits the bout's record in two. The event is bookkeeping: the
        backups and the context fields above are exactly as they were.
        """
        vm_cfg = self.config.value_memory
        ctx.replay_cell = None
        ctx.replay_back = 0
        ctx.replay_span = 0
        if not replay_active:
            self._replay_plan = None
            self._close_replay_event()  # the sleep ended: its event is complete
            return
        if not vm_cfg.replay_recent:
            if self._replay_event is None:
                self._replay_event = OpenReplayEvent(
                    ctx.tick, TRIGGER_MICROSLEEP, RULE_TRN_INDEX, DIRECTION_FORWARD, len(self.trn_gate.replay_buffer)
                )
            self._replay_event.tick(ctx.tick)
            transition = self.value_memory.transition(replay_index)
            if transition is not None:
                self.value_memory.replay_backup(transition, dwell_extinction=vm_cfg.dwell_extinction)
                ctx.replay_cell = transition[0]
                self._replay_event.backup(ctx.tick, transition[0])
            return
        if self._replay_plan is None:  # sleep onset: snapshot the recent path
            self._replay_plan = self.value_memory.recent_transitions(self.trn_gate.replay_window)
            self._replay_step = 0
            if self._replay_plan:  # an empty snapshot replays nothing: no event
                self._replay_event = OpenReplayEvent(
                    ctx.tick, TRIGGER_MICROSLEEP, RULE_REVERSE_TRAJECTORY, DIRECTION_REVERSE, len(self._replay_plan)
                )
        plan = self._replay_plan
        if plan:
            position = self._replay_step % len(plan)
            self.value_memory.replay_backup(plan[position], dwell_extinction=vm_cfg.dwell_extinction)
            ctx.replay_cell = plan[position][0]
            ctx.replay_back = position + 1
            ctx.replay_span = len(plan)
            if self._replay_event is not None:
                self._replay_event.backup(ctx.tick, ctx.replay_cell)
        self._replay_step += 1

    def _close_replay_event(self) -> None:
        """Close the replay event in progress, if any, into ``replay_log`` (nothing backed up: no event)."""
        event = self._replay_event
        self._replay_event = None
        if event is not None:
            finished = event.close()
            if finished is not None:
                self.replay_log.append(finished)

    def _spatial_step(self, ctx: EngineContext) -> None:
        if ctx.observation is None:
            raise RuntimeError("Observation missing before spatial step")
        # The TRN gate scales egomotion (legacy) unless spatial.gate_scales_egomotion
        # is off, in which case path integration sees the true egomotion
        # whatever the gate state.
        gain = ctx.trn_gate_value if self.config.spatial.gate_scales_egomotion else 1.0
        state = self.spatial.step(ctx.observation, sensory_gain=gain)
        ctx.hd_angle = state.hd_angle
        ctx.grid_x = state.grid_x
        ctx.grid_y = state.grid_y
        ctx.place_id = state.place_id
        if self.place is not None:
            self.place_rates = ctx.place_rates = self.place.rates(state.grid_x, state.grid_y)

    def _wm_step(self, ctx: EngineContext) -> None:
        if ctx.observation is None:
            raise RuntimeError("Observation missing before WM step")
        wm_state = self.working_memory.update(ctx.observation, ctx.place_id, ctx.observation_checksum)
        ctx.wm_load = wm_state.load
        ctx.wm_novelty = wm_state.novelty

    def _nearest_target(self, pos: Tuple[float, float],
                        kinds: Tuple[str, ...] = ("target", "hidden")) -> Tuple[float, WorldObject] | None:
        """(surface distance, object) of the nearest rewarding object of ``kinds``, if any.

        A "hidden" goal still rewards on contact (it is physically present),
        but it is invisible to vision (``core.sensors.UNSEEN_KINDS``, decisions G46)
        and, unless ``reward.shape_hidden``, to approach shaping.
        """
        best: Tuple[float, WorldObject] | None = None
        for o in self.world.objects:
            if o.kind not in kinds:
                continue
            d = ((pos[0] - o.x) ** 2 + (pos[1] - o.y) ** 2) ** 0.5 - o.radius
            if best is None or d < best[0]:
                best = (d, o)
        return best

    def _nearest_target_distance(self, pos: Tuple[float, float]) -> float | None:
        nearest = self._nearest_target(pos)
        return None if nearest is None else nearest[0]

    # Minimum observed pain the value map will learn from (see map_pain_floor).
    MAP_PAIN_THRESHOLD = 0.05

    def map_pain_floor(self) -> float:
        """Pain must exceed this to enter the value map: max(MAP_PAIN_THRESHOLD, sensors.noise).

        A sensory-reliability floor. Pain noise is uniform in [-noise, +noise]
        (clamped at 0), so an observation at or below ``sensors.noise`` could be
        noise alone, and pure noise must never write aversive memories (at noise
        0.1 it used to paint a hazard-free open field red). Pain at or below the
        floor still reaches ``ctx.reward`` and dopamine, and still drives REST.
        """
        return max(self.MAP_PAIN_THRESHOLD, self.config.sensors.noise)

    def _compute_reward(self, ctx: EngineContext) -> float:
        """Return the full (shaped) reward and set ``ctx.map_reward``.

        ``ctx.map_reward`` is what the value map learns: the contact bonus plus
        reliable pain (> ``map_pain_floor()``), without approach shaping, unless
        ``value_memory.learn_shaping`` is on, in which case it is the full reward.
        """
        r = self.config.reward
        pain = ctx.observation.pain_signal if ctx.observation else 0.0
        reward = -r.pain_weight * pain
        primary = -r.pain_weight * pain if pain > self.map_pain_floor() else 0.0
        learn_shaping = self.config.value_memory.learn_shaping
        # Contact reads every rewarding object, a hidden one included; shaping reads only what the agent can see
        # (decisions G46), unless reward.shape_hidden restores the pre-G46 hot/cold signal toward hidden food.
        nearest = self._nearest_target(ctx.pos)
        shaped = nearest if r.shape_hidden else self._nearest_target(ctx.pos, ("target",))
        ctx.target_contact = nearest is not None and nearest[0] <= 0.0
        if shaped is None:
            self._prev_target_dist = None
            self._prev_target = None
        else:
            dist, obj = shaped
            # Approach shaping rewards closing the distance to the *same* target.
            # When the target set changes under the agent (food eaten, a beacon
            # moved), the distance jumps for reasons that are not the agent's
            # doing; charging that jump would punish every successful collection.
            same = (
                self._prev_target is not None
                and self._prev_target[0] is obj
                and self._prev_target[1:] == (obj.x, obj.y)
            )
            if self._prev_target_dist is not None and same:
                reward += r.approach_weight * (self._prev_target_dist - dist)
            self._prev_target_dist = dist
            self._prev_target = (obj, obj.x, obj.y)
        if self.metabolism is not None:  # G56: touching food is a meal only when the consummatory reflex eats it
            meal = self._ingest(ctx, nearest)
            reward += meal
            primary += meal
        elif ctx.target_contact:
            reward += r.contact_bonus
            primary += r.contact_bonus
        ctx.map_reward = reward if learn_shaping else primary
        return reward

    def _ingest(self, ctx: EngineContext, nearest: Tuple[float, WorldObject] | None) -> float:
        """The consummatory reflex (G56; docs/prereg/whole_resource.md §2): on contact with food, eat it unless a meal is
        under way or the agent has starved; with interoception only when the meal would reduce the drive. Returns the
        meal's reward: interoception's drive reduction, or the contact bonus for an agent that does not sense its need."""
        ctx.ingested, ctx.ingested_object, ctx.meal_value = 0.0, None, 0.0
        if not ctx.target_contact or nearest is None or self._consume_remaining > 0 or self.metabolism.starved:
            return 0.0
        energy = self.config.metabolism.food_energy
        if self.config.interoception.enabled:
            value = meal_reward(self.metabolism.effective, energy, self.config.interoception.setpoint)
            if value <= 0.0:
                return 0.0
        else:
            value = self.config.reward.contact_bonus
        self.metabolism.eat(energy)
        self._consume_remaining = self.config.metabolism.consume_ticks
        ctx.ingested, ctx.ingested_object, ctx.meal_value = energy, nearest[1], value
        return value

    # Directions (relative to heading) the value map is consulted along. The side
    # fans reach ~80 degrees so a value peak off to the side reads as "turn that
    # way" rather than a false local maximum where every sampled step is downhill.
    VALUE_FAN_OFFSETS = (TURN_STEP, 0.8, 1.4)
    # How far short of a sensed solid a reachable probe stops (units; value_memory.reachable_probes).
    PROBE_CLEARANCE = 0.05
    # Largest sampled advantage below which the map counts as locally flat.
    VALUE_FLAT = 1e-3

    def _sr_learn(self, reward: float, lr_scale: float = 1.0, pos: Tuple[float, float] | None = None) -> None:
        """One online step of the SR value source (M2b step 4): the TD backup of the transition from the previous tick's
        features to this tick's, then the reward weights by normalised LMS on the reward received on arrival here.
        ``lr_scale`` multiplies the successor features' learning rate (acetylcholine, G56); with the map replay on, the
        transition is also stored at its positions ``pos`` (the estimate)."""
        from brain.systems.successor_features import normalised

        phi = normalised(self.place_rates)
        if self._sr_prev is not None:
            self.sr.update(self._sr_prev, phi, lr_scale=lr_scale)
            if self.sr_replay is not None and self._sr_prev_pos is not None and pos is not None:
                from brain.systems.sr_replay import MapTransition

                x0, y0 = self._sr_prev_pos
                self.sr_replay.store(MapTransition(x0, y0, pos[0], pos[1], self.episode, self.spatial.bins_at(x0, y0)))
        self._sr_prev_pos = pos
        rate = self.config.place.reward_learning_rate
        if self.config.place.reward_rule == "per_feature":
            # G41: on a tick that sees no reward the weights fall toward 0 at the active cells at the unlearning rate
            # (None: the learning rate, the rule as G36 preregistered it).
            unlearning = self.config.place.reward_unlearning_rate
            if reward == 0.0 and unlearning is not None:
                rate = unlearning
            step = rate * phi
            if self.config.place.reward_step_cap:  # G52: never past the target
                import numpy as np  # local: importing core.engine must not import numpy (docs/determinism.md)

                step = np.minimum(step, 1.0)
            adjustment = self.history.reward_adjustment() if self.history is not None else None
            if adjustment is None or self.history.fixed:
                # G36's rule; with a fixed schema (G53) R learns from its own error and the history term is read on top
                self.sr_weights += step * (reward - self.sr_weights)
            else:  # G52: each feature predicts R + what its history adds; R and the schema learn from the same error
                errors = reward - (self.sr_weights + adjustment)
                self.sr_weights += step * errors
                # The schema learns at the reward learning rate always, not the unlearning rate (which is R's own
                # answer to stale reward); its step is normalised (History.learn_schema).
                self.history.learn_schema(phi, errors, self.config.place.reward_learning_rate)
        else:
            norm = float((phi * phi).sum())
            if norm > 0.0:
                err = reward - float((phi * self.sr_weights).sum())
                self.sr_weights += (rate * err / norm) * phi
        self._sr_prev = phi
        self._sr_u = None  # M^T R changed

    def sr_value(self, x: float, y: float) -> float:
        """The SR value source's V at a position of the estimate frame: phi(p) . (M^T R)."""
        from brain.systems.successor_features import normalised

        if self._sr_u is None:
            weights = self.sr_weights
            if self.history is not None:
                adjustment = self.history.reward_adjustment()
                if adjustment is not None:
                    weights = weights + adjustment  # the expected reward at each place given its history now (G52)
            self._sr_u = (self.sr.M * weights[:, None]).sum(axis=0)  # element-wise, no BLAS (numpy rule 6 kept)
        return float((normalised(self.place.rates(x, y)) * self._sr_u).sum())

    def _history_inputs(self, ctx: EngineContext):
        """What the history channels read this tick, in the agent's own estimate frame (G52)."""
        from brain.systems.history import HistoryInputs, unit_peak

        vr = self.config.sensors.vision_range
        return HistoryInputs(
            here=unit_peak(self.place_rates), primary_reward=ctx.map_reward,
            vision=[(ray.angle, ray.obj_type, ray.dist * vr) for ray in ctx.observation.vision_rays],
            estimate=(ctx.grid_x, ctx.grid_y, ctx.hd_angle),
            rates_at=lambda x, y: unit_peak(self.place.rates(x, y)),
        )

    def reset_value_episode(self) -> None:
        """An episode boundary for every value learner (a protocol's trial start, a teleport): nothing links across it."""
        self.value_memory.reset_episode()
        self._sr_prev = None
        self.value_episode += 1

    def forget_rewards(self) -> None:
        """Erase what the value learners know about reward: the tabular map's values and, with the SR source, its
        reward weights R. The SR's transition structure M is kept (the agent's knowledge of the space, not of
        reward). A console action (decisions G39); nothing in the tick pipeline calls it."""
        self.value_memory.values.clear()
        if self.sr_weights is not None:
            self.sr_weights[:] = 0.0
            self._sr_u = None

    # --- The action value over the place code and replay at the consumption pause (M3 step 3) ---------------------

    def _phi_at(self, x: float, y: float):
        """The place features at a position: the population's rates normalised to sum 1."""
        from brain.systems.successor_features import normalised

        return normalised(self.place.rates(x, y))

    def _make_replay_rule(self, name: str):
        if name == "none":
            return None
        if name == "uniform":
            from brain.systems.replay_rules import UniformReplay

            return UniformReplay()
        if name == "reverse":
            from brain.systems.replay_rules import ReverseTrajectoryReplay

            return ReverseTrajectoryReplay()
        if name == "gain_need":
            from brain.systems.replay_mattar_daw import MattarDawReplay
            from brain.systems.replay_place import PlaceQModel

            return MattarDawReplay(PlaceQModel(self))
        raise ValueError(f"unknown replay rule {name!r}")

    def _av_features(self, x: float, y: float):
        """The action value's features at a position: phi, and with ``history_features`` phi times each taste trace
        at its cell (the place and how recently it was eaten at; amendment A1)."""
        phi = self._phi_at(x, y)
        if not self.config.action_value.history_features:
            return phi
        import numpy as np  # local: importing core.engine must not import numpy (docs/determinism.md)

        traces = self.history.banks["taste"].traces
        return np.concatenate([phi] + [phi * traces[k] for k in range(traces.shape[0])])

    def _av_position(self, ctx: EngineContext) -> Tuple[float, float]:
        """Where the action value reads: the estimate, or the body's true position under ``oracle_state``."""
        if self.config.action_value.oracle_state:
            return float(self.agent.pos[0]), float(self.agent.pos[1])
        return float(ctx.grid_x), float(ctx.grid_y)

    def _action_value_learn(self, ctx: EngineContext) -> None:
        """The last movement's transition into the action value and the transition memory; the consumption pause and
        its replay when the agent has just eaten; the advantages the steering reads this tick."""
        from brain.systems.replay_rules import PlaceTransition

        ctx.replay_event_cells = ()
        x, y = self._av_position(ctx)
        phi = self._av_features(x, y)
        prev = self._av_prev
        if prev is not None:
            phi_prev, action, x0, y0, cell0 = prev
            self.action_learner.learner.update(phi_prev, action, ctx.map_reward, phi, False)
            self.transition_memory.append(PlaceTransition(x0, y0, ctx.map_reward, x, y, False, self.episode, ctx.tick, cell0, action,
                                                          phi=phi_prev, phi_next=phi))
        self._av_prev = None  # set again once this tick's action is chosen, if it is a movement
        self._av_phi = phi
        adv = self.action_learner.learner.advantages(phi)
        ctx.action_values = tuple(adv[a] for a in ACTION_VALUE_ACTIONS)
        if ctx.map_reward > 0.0 and self.config.replay.consume_ticks > 0:
            self._consume_remaining = self.config.replay.consume_ticks
            self._replay_at_pause(ctx)

    def _replay_at_pause(self, ctx: EngineContext) -> None:
        """The rule's backups on the pause's first tick, recorded as one event (nothing of this episode: no event)."""
        from brain.systems.replay_events import TRIGGER_REWARD
        from brain.systems.replay_rules import replay

        rule, memory = self.replay_rule, self.transition_memory
        n = self.config.replay.backups_per_pause
        if rule is None or n < 1 or not memory.episode(self.episode):
            return
        outcome = replay(rule, memory, self.action_learner, n, self.episode, self.streams["replay"], tick=ctx.tick,
                         travel_sign=1, trigger=TRIGGER_REWARD)
        self.replay_log.append(outcome.event)
        ctx.replay_event_cells = outcome.event.cells

    def _pause_action(self, ctx: EngineContext, action: Action) -> Action:
        """The consumption pause: while a meal is under way the body rests."""
        ctx.consuming = False
        if self._consume_remaining > 0:
            self._consume_remaining -= 1
            ctx.consuming = True
            action = Action(name="REST", thrust=0.0, turn=0.0)
        return action

    def _sr_replay_step(self, ctx: EngineContext, delta: float) -> None:
        """Replay of the successor map (G56; docs/prereg/whole_resource.md §2.2): at a meal, the episode's last
        transitions newest first (the budget from dopamine's |TD error|, else the fixed one) when acetylcholine allows,
        recorded as one event; asleep, ``sleep.replay_per_tick`` uniform draws a tick, one event per sleep bout."""
        from brain.systems.replay_events import (
            DIRECTION_NEITHER,
            RULE_REVERSE_TRAJECTORY,
            RULE_UNIFORM,
            TRIGGER_REWARD,
            TRIGGER_SLEEP,
            OpenReplayEvent,
            ReplayEvent,
        )
        from brain.systems.replay_rules import sequence_direction

        bio = self.bio_neuromod
        if ctx.ingested > 0.0:  # the budget is set by the meal's surprise; the sweep waits for the still body
            default = self.config.replay.backups_per_pause
            self._replay_pending = bio.replay_budget(delta, default) if bio is not None else default
        if self._replay_pending is not None and not (bio is None or bio.replay_allowed()):
            if self._consume_remaining == 0 and ctx.ingested == 0.0:
                self._replay_pending = None  # the meal is over and acetylcholine never allowed it
        elif self._replay_pending is not None:
            budget, self._replay_pending = self._replay_pending, None
            sweep = self.sr_replay.reverse_sweep(self.episode, budget)
            if sweep:
                self._replay_map(sweep)
                direction, _ = sequence_direction([t.x for t in sweep], 1)
                cells = tuple(t.cell for t in sweep)
                self.replay_log.append(ReplayEvent(tick_start=ctx.tick, tick_end=ctx.tick, trigger=TRIGGER_REWARD,
                                                   rule=RULE_REVERSE_TRAJECTORY, cells=cells, direction=direction,
                                                   start_cell=cells[0], n_backups=len(cells), span=len(self.sr_replay.memory)))
                ctx.replay_event_cells = cells
        if ctx.asleep and self.config.sleep.replay_per_tick > 0:
            draws = self.sr_replay.draws(self.config.sleep.replay_per_tick, self.streams["replay"])
            if draws:
                if self._sleep_event is None:
                    self._sleep_event = OpenReplayEvent(ctx.tick, TRIGGER_SLEEP, RULE_UNIFORM, DIRECTION_NEITHER, len(self.sr_replay.memory))
                self._sleep_event.tick(ctx.tick)
                self._replay_map(draws)
                for t in draws:
                    self._sleep_event.backup(ctx.tick, t.cell)
        elif not ctx.asleep and self._sleep_event is not None:
            finished = self._sleep_event.close()
            self._sleep_event = None
            if finished is not None:
                self.replay_log.append(finished)

    def _replay_map(self, transitions) -> None:
        """Back the successor features up along stored transitions (positions in the estimate frame)."""
        for t in transitions:
            self.sr.update(self._phi_at(t.x, t.y), self._phi_at(t.x_next, t.y_next))
            self.sr_replay.backups += 1
        self._sr_u = None  # M changed

    def _after_selection(self, ctx: EngineContext, action: Action) -> Action:
        """The consumption pause (the body rests while it eats) and the next transition's start."""
        action = self._pause_action(ctx, action)
        if action.name in ACTION_VALUE_ACTIONS and self._av_phi is not None:
            x, y = self._av_position(ctx)
            self._av_prev = (self._av_phi, action.name, x, y, self.spatial.bins_at(x, y))
        else:
            self._av_prev = None
        return action

    def _value_at(self, x: float, y: float) -> float:
        """The value the steering reads at a position of the estimate frame, from ``value_memory.source``."""
        if self.sr is not None:
            return self.sr_value(x, y)
        return self.value_memory.value_of(self.spatial.bins_at(x, y))

    def _value_signals(self, ctx: EngineContext) -> Tuple[float, float, float]:
        """Steer toward higher-value directions (memory-guided navigation).

        Reads the learned place value one lookahead step away along the heading
        and along a fan on each side and takes the advantage over the current
        place. With ``value_steer == "split"`` (the default) these become the
        FORWARD / TURN_LEFT / TURN_RIGHT commands of ``split_value_signals``: a
        turn toward the side that beats ahead by more than a dead zone relative
        to the local relief, with FORWARD giving way. With ``"maxnorm"`` they are
        (ahead, best-left, best-right) divided by the largest magnitude. Both are
        relative to the local relief, so they are decisive on a real gradient,
        silent on a locally flat map, and need no re-tuning to the reward scale.
        With ``value_memory.oracle_homing`` (the goal-vector slot) on and a
        goal remembered, a map whose largest sampled advantage is below
        ``goal_vector_flat`` hands over to ``goal_vector_signals``: turn toward
        the remembered goal's place.
        """
        source = self.config.value_memory.source
        if source == "none":
            ctx.goal_vector_active = False
            return 0.0, 0.0, 0.0  # no value steering (M2b step 4's control)
        if source == "action":  # M3 step 3: the learned action value, read at the agent's own place
            ctx.goal_vector_active = False
            return self._action_value_read(ctx)
        signals = self._spatial_value_signals(ctx)
        ic = self.config.interoception
        if source in ("sr", "sr_action") and ic.enabled and ic.incentive_memory:
            # G56: the SR's value is revalued at once by the present state (the incentive of a meal now)
            signals = (ctx.incentive * signals[0], ctx.incentive * signals[1], ctx.incentive * signals[2])
        if source == "sr_action":  # G56: the model-free action value read beside it, not revalued
            q = self._action_value_read(ctx)
            g = self.config.action_value.read_gain
            signals = (signals[0] + g * q[0], signals[1] + g * q[1], signals[2] + g * q[2])
        return signals

    def _action_value_read(self, ctx: EngineContext) -> Tuple[float, float, float]:
        """The action value's advantages as steering signals (M3 step 3; the read floor of amendment A1)."""
        ahead, left, right = ctx.action_values
        scale = max(abs(ahead), abs(left), abs(right))
        if scale < self.config.action_value.read_floor:  # amendment A1: a preference below the floor is noise
            return 0.0, 0.0, 0.0
        bg = self.config.basal_ganglia
        if bg.value_steer == "split":
            return split_value_signals(ahead, left, right, scale, bg)
        if bg.value_steer != "maxnorm":
            raise ValueError(f"Unknown value_steer {bg.value_steer!r}; expected one of {VALUE_STEER_MODES}")
        if scale < self.VALUE_FLAT:
            return 0.0, 0.0, 0.0
        return ahead / scale, left / scale, right / scale

    def _spatial_value_signals(self, ctx: EngineContext) -> Tuple[float, float, float]:
        """The place value's signals (tabular or SR), probed along the heading and a fan on each side."""
        look = self.config.value_memory.lookahead
        here = self._value_at(ctx.grid_x, ctx.grid_y)
        # reachable_probes (M3 step 2, draft): each direction is read only as far as the agent sees it could go.
        obs = ctx.observation
        free = obs.free_space if (self.config.value_memory.reachable_probes and obs is not None) else None
        reach = dict(zip(FREE_SPACE_ANGLES, free)) if free is not None else {}

        def advantage(theta: float, off: float) -> float:
            dist = min(look, max(0.0, reach[off] - self.PROBE_CLEARANCE)) if reach else look
            gx = ctx.grid_x + dist * math.cos(theta)
            gy = ctx.grid_y + dist * math.sin(theta)
            return self._value_at(gx, gy) - here

        hd = ctx.hd_angle
        ahead = advantage(hd, 0.0)
        left = [advantage(hd + off, off) for off in self.VALUE_FAN_OFFSETS]
        right = [advantage(hd - off, -off) for off in self.VALUE_FAN_OFFSETS]
        scale = max(abs(x) for x in [ahead, *left, *right])
        vm = self.config.value_memory
        ctx.goal_vector_active = False
        goal = self.goal_point() if vm.oracle_homing else None
        if goal is not None and scale < vm.goal_vector_flat:
            # The map gives no direction here; steer by the remembered goal vector.
            ctx.goal_vector_active = True
            dx, dy = goal[0] - ctx.grid_x, goal[1] - ctx.grid_y
            bearing = wrap_angle(math.atan2(dy, dx) - hd)
            return goal_vector_signals(bearing, math.hypot(dx, dy), vm.goal_turn_dead_zone, vm.goal_turn_ramp)
        bg = self.config.basal_ganglia
        if bg.value_steer == "split":
            return split_value_signals(ahead, max(left), max(right), scale, bg)
        if bg.value_steer != "maxnorm":
            raise ValueError(f"Unknown value_steer {bg.value_steer!r}; expected one of {VALUE_STEER_MODES}")
        if scale < self.VALUE_FLAT:  # locally flat map -> no steer
            return 0.0, 0.0, 0.0
        return ahead / scale, max(left) / scale, max(right) / scale

    def goal_point(self) -> Tuple[float, float] | None:
        """The remembered goal (centre of ``value_memory.goal_cell``) in the path-integration frame."""
        cell = self.value_memory.goal_cell
        if cell is None:
            return None
        b = self.spatial.bin_size
        return (cell[0] + 0.5) * b, (cell[1] + 0.5) * b

    def _update_goal_memory(self, ctx: EngineContext) -> None:
        """Goal-vector bookkeeping: online writing (if configured) and extinction.

        With ``goal_vector_source == "replay"`` (the default) only replaying a
        rewarded transition writes the goal (``ValueMemory.replay_backup``);
        with ``"online"`` target contact also writes the current place cell.

        Extinction: a visit is a stay in the goal's own place cell; it is
        rewarded if target contact happens while inside or on the tick the agent
        leaves (contact reached from the cell next door). The goal is erased
        after ``goal_extinction_misses`` unrewarded visits in a row, so a goal
        that moved, or a place that path-integration drift has displaced, stops
        pulling the agent once it has been checked and found empty more than
        once. Any target contact resets the count: the remembered cell straddles
        the contact circle (it is where the estimate was at first contact), so
        a visit can cross the part of the cell outside the circle and miss a
        goal that never moved; one miss is not evidence that it is gone. The
        count persists across episodes, like the goal, and restarts when a new
        goal is written. 0 disables extinction.
        """
        vm_cfg = self.config.value_memory
        if vm_cfg.goal_vector_source not in GOAL_VECTOR_SOURCES:
            raise ValueError(
                f"Unknown goal_vector_source {vm_cfg.goal_vector_source!r}; expected one of {GOAL_VECTOR_SOURCES}"
            )
        here = self.spatial.bins_at(ctx.grid_x, ctx.grid_y)
        if ctx.target_contact and vm_cfg.goal_vector_source == "online":
            self.value_memory.goal_cell = here
        goal = self.value_memory.goal_cell
        if goal != self._goal_misses_cell:  # a new goal (or none): start counting afresh
            self._goal_visit = self._goal_visit_rewarded = False
            self._goal_misses = 0
            self._goal_misses_cell = goal
        if goal is None:
            return
        if ctx.target_contact:
            self._goal_misses = 0
        if here == goal:
            self._goal_visit = True
            self._goal_visit_rewarded = self._goal_visit_rewarded or ctx.target_contact
        elif self._goal_visit:
            if not (self._goal_visit_rewarded or ctx.target_contact):
                self._goal_misses += 1
                if 0 < vm_cfg.goal_extinction_misses <= self._goal_misses:
                    self.value_memory.goal_cell = None  # checked and found empty, repeatedly
                    self._goal_misses = 0
                    self._goal_misses_cell = None
            self._goal_visit = self._goal_visit_rewarded = False

    def _brain_step(self, ctx: EngineContext) -> None:
        if ctx.observation is None:
            raise RuntimeError("Observation missing before brain step")

        ctx.reward = self._compute_reward(ctx)
        ctx.neuromodulators = self.neuromod_system.update(
            reward=ctx.reward, novelty=ctx.wm_novelty, pain=ctx.observation.pain_signal
        )
        # The whole (G56): interoception reads the state after this tick's meal; dopamine's TD error is taken over the
        # incentive-scaled SR value before this tick's learning; the modulators in their roles replace the traces above.
        ic = self.config.interoception
        if ic.enabled:
            e_eff, energy = self.metabolism.effective, self.config.metabolism.food_energy
            ctx.hunger = interoceptive_hunger(e_eff, ic.setpoint, ic.hunger_floor)
            ctx.incentive = meal_incentive(e_eff, energy, ic.setpoint)
        delta = ctx.map_reward
        if self.bio_neuromod is not None:
            if self.sr is not None and not ctx.asleep:
                v_now = ctx.incentive * self.sr_value(ctx.grid_x, ctx.grid_y)
                v_prev = v_now if self._v_prev is None else self._v_prev
                delta = ctx.map_reward + self.config.place.sr_discount * v_now - v_prev
                self._v_prev = v_now
            sat = interoceptive_satiety(self.metabolism.effective, ic.setpoint, self.config.neuromod.satiety_band) if ic.enabled else 0.0
            ctx.neuromodulators = self.bio_neuromod.update(
                delta=delta, reward=ctx.map_reward, pain=ctx.observation.pain_signal,
                novelty=(1.0 - ctx.familiarity) if self.history is not None else 0.0,
                moving=self.last_action.name != "REST", asleep=ctx.asleep, satiety=sat)
        ctx.td_error = delta
        # Plasticity: TD-learn the map from the map reward (primary outcomes by default).
        # The extinction cost is passed from the config on every call, so it can be
        # tuned live and the config stays the single source of truth.
        self.value_memory.record(
            self.spatial.bins_at(ctx.grid_x, ctx.grid_y),
            ctx.map_reward,
            dwell_extinction=self.config.value_memory.dwell_extinction,
        )
        if self.history is not None:
            self.history.decay()
        if self.sr is not None and not ctx.asleep:  # asleep there is no experience to learn from (G56)
            # With interoception the reward weights learn the outcome (a meal: 1), so the value is revalued by the
            # present state rather than fixed at the state it was learned in (G56).
            outcome = ctx.map_reward - ctx.meal_value + (1.0 if ctx.ingested > 0.0 else 0.0) if ic.enabled else ctx.map_reward
            scale = self.bio_neuromod.sr_learning_scale() if self.bio_neuromod is not None else 1.0
            self._sr_learn(outcome, lr_scale=scale, pos=(ctx.grid_x, ctx.grid_y))
        if self.action_learner is not None:
            self._action_value_learn(ctx)
        if self.sr_replay is not None:
            self._sr_replay_step(ctx, delta)
        drive, vigour = 1.0, 1.0
        if self.history is not None:
            self.history.write(self._history_inputs(ctx))
            self._sr_u = None  # the traces moved: the expected reward with them
            from brain.systems.successor_features import normalised

            ctx.familiarity = self.history.familiarity(normalised(self.place_rates))
            if self.motivation is not None:
                if self.config.motivation.hunger_source == "interoception" and ic.enabled:
                    self.motivation.sensed_hunger = ctx.hunger  # G56: the sensed deficit, not the meal count
                ate = 1.0 if ctx.map_reward > 0.0 else 0.0
                drive = self.motivation.step({"novelty": 1.0 - ctx.familiarity, "meal": ate, "reward": ate})
                vigour = self.motivation.vigour()
                ctx.motivation_levels = dict(self.motivation.levels)
        if self.bio_neuromod is not None and self.config.neuromod.dopamine:
            vigour = self.bio_neuromod.vigour()  # G56: tonic dopamine sets vigour
        ctx.motivation = drive
        ctx.vigour = vigour
        self._hunger = ctx.hunger
        if self.config.value_memory.oracle_homing:
            self._update_goal_memory(ctx)

        bg = self.config.basal_ganglia
        # Memory-guided steer from the consolidated value map, muted while a
        # target is in view (cue gating: what is seen beats what is remembered).
        value_ahead, value_left, value_right = self._value_signals(ctx)
        cue_gate = cue_gate_weight(ctx.observation, bg.cue_gate_gain)
        value_ahead *= cue_gate
        value_left *= cue_gate
        value_right *= cue_gate
        # Wall gating: a wall close ahead mutes memory's push to hold course.
        value_ahead, value_left, value_right, wall_gate = wall_gate_signals(
            value_ahead, value_left, value_right, ctx.observation, bg.wall_gate_gain
        )

        # Gain from kappa (near_critical_gain), logged every tick; it reaches
        # action selection only in proportion to basal_ganglia.criticality_gain,
        # 0 by default.
        # With the dynamic coupling (G56) the gain reads the lattice's distance from criticality, m, not kappa.
        crit_gain = near_critical_gain(ctx.criticality_m if self.crit_coupling is not None else ctx.kappa,
                                       self.config.criticality.gain_width)

        # Freeze habituation: the pain->REST drive fades with recent pain-freezing.
        freeze_h = math.exp(-self._freeze_level / bg.freeze_tau) if bg.freeze_tau > 0.0 else 1.0

        # Homeostatic pacing: hysteretic latch on ATP (recover from pace_low up to
        # pace_high), both as fractions of the ATP ceiling so release is reachable.
        atp_baseline = self.config.astrocyte.atp_baseline
        if ctx.atp < bg.pace_low * atp_baseline:
            self._recovering = True
        elif ctx.atp >= bg.pace_high * atp_baseline:
            self._recovering = False
        pacing = self._recovering and not ctx.microsleep_active and bg.pace_rest_bonus > 0.0
        pacing_rest = bg.pace_rest_bonus if pacing else 0.0

        # Action selection: the deterministic argmax, or at softmax_temperature > 0
        # one seeded softmax draw per tick; dopamine modulates exploration.
        previous_action = self.last_action.name  # the decision before this one (the turn commitment reads it, G45)
        # G56: what food is worth now scales vision's pull to it; noradrenaline raises the temperature after surprise.
        ctx.target_gain = ctx.incentive if (ic.enabled and ic.incentive_vision) else 1.0
        ctx.temperature = bg.softmax_temperature * (self.bio_neuromod.temperature_factor() if self.bio_neuromod is not None else 1.0)
        action, scores = select_action_with_scores(
            observation=ctx.observation,
            wm_novelty=ctx.wm_novelty,
            trn_gain=ctx.trn_gate_value,
            microsleep_active=ctx.microsleep_active,
            config=self.config.basal_ganglia,
            modulators=ctx.neuromodulators,
            value_ahead=value_ahead,
            value_left=value_left,
            value_right=value_right,
            criticality_gain=crit_gain,
            freeze_habituation=freeze_h,
            pacing_rest=pacing_rest,
            action_stream=self.streams["action_softmax"],
            previous_action=previous_action,
            motivation=drive,
            vigour=vigour,
            target_gain=ctx.target_gain,
            temperature=ctx.temperature,
        )
        if self.action_learner is not None:
            action = self._after_selection(ctx, action)
        elif self.metabolism is not None:
            action = self._pause_action(ctx, action)  # G56: the body rests while it eats
        pain = ctx.observation.pain_signal
        if action.name == "REST" and not ctx.microsleep_active and pain > bg.freeze_pain_threshold:
            self._freeze_level += 1.0
        else:
            self._freeze_level *= bg.freeze_decay
        ctx.previous_action = previous_action
        ctx.action_scores = scores
        ctx.value_signals = (value_ahead, value_left, value_right)
        ctx.criticality_gain = crit_gain
        ctx.cue_gate = cue_gate
        ctx.wall_gate = wall_gate
        ctx.freeze_habituation = freeze_h
        ctx.pacing_active = pacing
        self.last_action = action
        ctx.action_name = action.name
        ctx.action_thrust = action.thrust
        ctx.action_turn = action.turn
        ctx.score += int(action.thrust > 0.0)

    def _log_tick(self, ctx: EngineContext) -> None:
        ctx.tick_data = TickData(
            tick=ctx.tick,
            agent_id=self.agent_offset,
            pos=ctx.pos,
            score=ctx.score,
            kappa=ctx.kappa,
            avalanche_size=ctx.avalanche_size,
            criticality_active=ctx.criticality_active,
            neuromodulators=ctx.neuromodulators,
            atp=ctx.atp,
            glycogen=ctx.glycogen,
            reward=ctx.reward,
            obs_forward_delta=ctx.observation.forward_delta if ctx.observation else 0.0,
            obs_turn_delta=ctx.observation.turn_delta if ctx.observation else 0.0,
            obs_pain=ctx.observation.pain_signal if ctx.observation else 0.0,
            obs_checksum=ctx.observation_checksum,
            trn_state=ctx.trn_state,
            microsleep_active=ctx.microsleep_active,
            microsleep_ticks_remaining=ctx.microsleep_ticks_remaining,
            replay_active=ctx.replay_active,
            replay_index=ctx.replay_index,
            hd_angle=ctx.hd_angle,
            grid_x=ctx.grid_x,
            grid_y=ctx.grid_y,
            place_id=ctx.place_id,
            wm_load=ctx.wm_load,
            wm_novelty=ctx.wm_novelty,
            action_name=ctx.action_name,
            action_thrust=ctx.action_thrust,
            action_turn=ctx.action_turn,
            protocol_name=ctx.protocol_name,
            trial_number=ctx.trial_number,
        )

    @property
    def context(self) -> EngineContext | None:
        """The live tick context (read-only use: instrumentation and visualisation)."""
        return getattr(self, "_ctx", None)

    def begin_episode(self) -> None:
        """Start a new episode without resetting the tick counter.

        Clears the pending action, the reward-shaping distance, the freeze
        habituation level, the replay plan of a microsleep in progress and the
        value map's episode boundary, so nothing learned links across a reset
        or a teleport. Memories (value map, goal memory and its extinction
        count, neuromodulator baselines) and the energy-pacing latch (energy
        itself persists) are kept.
        """
        self.last_action = Action(name="REST", thrust=0.0, turn=0.0)
        self._prev_target_dist = None
        self._prev_target = None
        self._freeze_level = 0.0
        self._goal_visit = self._goal_visit_rewarded = False  # the miss count persists, like the goal
        # A microsleep in progress keeps sleeping but replays nothing more: its
        # snapshot is the previous episode's path, and a fresh one would be too
        # (nothing has been recorded since). When awake, the plan is simply
        # unset, so the next sleep -- even one starting on the very next tick --
        # snapshots afresh. The replay event of a sleep in progress closes here
        # (cut by the reset) with the backups it has made so far.
        asleep = bool(getattr(getattr(self, "trn_gate", None), "replay_active", False))
        self._replay_plan = [] if asleep else None
        self._replay_step = 0
        self._close_replay_event()
        self.value_memory.reset_episode()
        self._sr_prev = None  # the SR value source's episode boundary too (M2b step 4)
        if self.action_learner is not None:  # M3 step 3: no transition across a reset; the traces start afresh
            self.action_learner.reset_episode()
            self._av_prev = None
            self._consume_remaining = 0
        if getattr(self, "metabolism", None) is not None:  # G56: a meal does not carry across a reset
            self._consume_remaining = 0
        self._sr_prev_pos = None  # G56: the map replay links no transition across a reset
        self._v_prev = None  # G56: dopamine's TD error starts afresh
        self._replay_pending = None
        if self.body is not None:
            self.body.reset()  # the animal is put down still (G44)
        self.episode += 1

    def run(self, ticks: int, *, reset: bool = False) -> List[TickData]:
        """Execute the pipeline for N ticks and return TickData stream."""
        if reset or not hasattr(self, "_ctx"):
            self._ctx = EngineContext(tick=-1)
            self.begin_episode()
        ctx: EngineContext = self._ctx
        trace: List[TickData] = []
        for _ in range(ticks):
            ctx.tick += 1
            self.pipeline.run(ctx)
            if ctx.tick_data is None:
                raise RuntimeError("Pipeline failed to produce TickData")
            trace.append(ctx.tick_data)
        return trace


__all__ = ["Engine", "EngineContext"]
