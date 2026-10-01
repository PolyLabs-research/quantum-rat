"""Deterministic engine scaffold that executes the tick pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import math

from brain.contracts import Action, Observation
from brain.systems.basal_ganglia import TURN_STEP, select_action
from brain.systems.criticality import CriticalityField
from brain.systems.spatial import SpatialSystem
from brain.systems.trn_microsleep_replay import TRNGate
from brain.systems.value_memory import ValueMemory
from brain.systems.working_memory import WorkingMemory
from core.config import EngineConfig
from core.entities import Agent
from core.neuromodulation import NeuromodulatorSystem
from core.physiology import Astrocyte
from core.pipeline import PIPELINE_ORDER, Pipeline
from core.rng import RNG, RNGStream
from core.sensors import gather_observation, observation_checksum
from core.world import World
from metrics.schema import TickData


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
    tick_data: TickData | None = None


class Engine:
    """No-op engine scaffold; emits TickData each tick."""

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
        }
        self.world = World(bounds=c.world.bounds)
        self.agent = Agent(id=agent_offset, pos=(0.0, 0.0))
        self.world.add_agent(self.agent)
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
        )
        self._prev_target_dist: float | None = None
        self.criticality = CriticalityField(stream=self.streams["criticality"], config=c.criticality)
        self.trn_gate = TRNGate(
            trigger_atp=c.trn.trigger_atp,
            trigger_streak=c.trn.trigger_streak,
            duration=c.trn.duration,
            recovery_atp=c.trn.recovery_atp,
            recovery_streak_needed=c.trn.recovery_streak_needed,
            replay_window=c.trn.replay_window,
        )
        self.spatial = SpatialSystem(
            turn_gain=c.spatial.turn_gain, decay=c.spatial.decay, bin_size=c.spatial.bin_size
        )
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
        # Demand scales with the agent's current effort so rest is cheap.
        a = self.config.astrocyte
        demand = a.rest_demand + a.motion_demand * min(1.0, abs(self.last_action.thrust))
        ctx.energy_scale = self.astrocyte.tick(demand=demand)
        ctx.atp = self.astrocyte.atp
        ctx.glycogen = self.astrocyte.glycogen

    def _world_step(self, ctx: EngineContext) -> None:
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
        )
        ctx.observation = obs
        ctx.observation_checksum = observation_checksum(obs)

    def _trn_step(self, ctx: EngineContext) -> None:
        # Update criticality metrics before gating
        crit = self.criticality.step()
        ctx.kappa = crit.kappa
        ctx.avalanche_size = crit.avalanche_size
        ctx.criticality_active = crit.active

        # Update microsleep state based on energy
        self.trn_gate.update_microsleep(ctx.atp)
        ctx.microsleep_active = self.trn_gate.microsleep.active
        ctx.microsleep_ticks_remaining = self.trn_gate.microsleep.ticks_remaining

        # TRN gating based on atp/kappa/microsleep
        state, gate_val = self.trn_gate.trn_state(ctx.atp, ctx.kappa)
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
        if replay_active:
            self.value_memory.replay_transition(replay_index)

    def _spatial_step(self, ctx: EngineContext) -> None:
        if ctx.observation is None:
            raise RuntimeError("Observation missing before spatial step")
        # Apply TRN gate as sensory gain
        state = self.spatial.step(ctx.observation, sensory_gain=ctx.trn_gate_value)
        ctx.hd_angle = state.hd_angle
        ctx.grid_x = state.grid_x
        ctx.grid_y = state.grid_y
        ctx.place_id = state.place_id

    def _wm_step(self, ctx: EngineContext) -> None:
        if ctx.observation is None:
            raise RuntimeError("Observation missing before WM step")
        wm_state = self.working_memory.update(ctx.observation, ctx.place_id, ctx.observation_checksum)
        ctx.wm_load = wm_state.load
        ctx.wm_novelty = wm_state.novelty

    def _nearest_target_distance(self, pos: Tuple[float, float]) -> float | None:
        # A "hidden" goal still rewards on contact (it is physically present),
        # but it is invisible to vision (see brain.systems.basal_ganglia).
        targets = [o for o in self.world.objects if o.kind in ("target", "hidden")]
        if not targets:
            return None
        return min(
            ((pos[0] - o.x) ** 2 + (pos[1] - o.y) ** 2) ** 0.5 - o.radius for o in targets
        )

    def _compute_reward(self, ctx: EngineContext) -> float:
        r = self.config.reward
        pain = ctx.observation.pain_signal if ctx.observation else 0.0
        reward = -r.pain_weight * pain
        dist = self._nearest_target_distance(ctx.pos)
        if dist is not None:
            if self._prev_target_dist is not None:
                reward += r.approach_weight * (self._prev_target_dist - dist)
            if dist <= 0.0:
                reward += r.contact_bonus
            self._prev_target_dist = dist
        return reward

    def _value_signals(self, ctx: EngineContext) -> Tuple[float, float, float]:
        """Normalized steer toward higher-value directions (memory-guided navigation).

        Reads the learned place value a step ahead / left / right of the current
        estimate, takes the advantage over the current place, and normalizes by
        the largest-magnitude advantage so the steer is decisive whenever a real
        gradient exists and silent when the map is locally flat. Magnitude-robust,
        so it does not need to be re-tuned to the reward scale.
        """
        look = self.config.value_memory.lookahead
        here = self.value_memory.value_of(self.spatial.bins_at(ctx.grid_x, ctx.grid_y))

        def advantage(theta: float) -> float:
            gx = ctx.grid_x + look * math.cos(theta)
            gy = ctx.grid_y + look * math.sin(theta)
            return self.value_memory.value_of(self.spatial.bins_at(gx, gy)) - here

        hd = ctx.hd_angle
        raw = (advantage(hd), advantage(hd + TURN_STEP), advantage(hd - TURN_STEP))
        scale = max(abs(x) for x in raw)
        if scale < 1e-3:  # locally flat map -> no steer
            return 0.0, 0.0, 0.0
        return raw[0] / scale, raw[1] / scale, raw[2] / scale

    def _brain_step(self, ctx: EngineContext) -> None:
        if ctx.observation is None:
            raise RuntimeError("Observation missing before brain step")

        ctx.reward = self._compute_reward(ctx)
        ctx.neuromodulators = self.neuromod_system.update(
            reward=ctx.reward, novelty=ctx.wm_novelty, pain=ctx.observation.pain_signal
        )
        # Plasticity: value of the current place moves toward reward received there.
        self.value_memory.record(self.spatial.bins_at(ctx.grid_x, ctx.grid_y), ctx.reward)

        # Memory-guided steer from the consolidated value map.
        value_ahead, value_left, value_right = self._value_signals(ctx)

        # Deterministic action selection; dopamine modulates exploration.
        action = select_action(
            observation=ctx.observation,
            wm_novelty=ctx.wm_novelty,
            trn_gain=ctx.trn_gate_value,
            microsleep_active=ctx.microsleep_active,
            config=self.config.basal_ganglia,
            modulators=ctx.neuromodulators,
            value_ahead=value_ahead,
            value_left=value_left,
            value_right=value_right,
        )
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

    def run(self, ticks: int, *, reset: bool = False) -> List[TickData]:
        """Execute the pipeline for N ticks and return TickData stream."""
        if reset or not hasattr(self, "_ctx"):
            self._ctx = EngineContext(tick=-1)
            self.last_action = Action(name="REST", thrust=0.0, turn=0.0)
            self._prev_target_dist = None
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
