"""Scenarios for the live lab console.

A scenario is a small, self-contained experiment the console can run live: it
supplies an engine configuration, lays out the arena, applies any per-tick
rules (collecting targets, ending a trial), reports a status readout, and
offers a few scenario-specific actions (e.g. "sleep & consolidate").

Scenarios only arrange the *world* and run the experiment protocol. The brain
still sees nothing but its Observation; reading engine state here is the
instrument's job, not the agent's.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from brain.systems.spatial import SpatialState
from core.config import BasalGangliaConfig, EngineConfig, SensorConfig
from core.engine import Engine
from core.world import WorldObject
from experiments.memory_navigation import memory_nav_config
from experiments.protocols.foraging import DEFAULT_TARGETS as FORAGING_TARGETS

Event = Dict[str, Any]

START_POSE: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # x, y, heading (all scenarios)

# Homeostatic pacing for the energy-limited task scenarios (beacon, foraging,
# hazard_field): once ATP drops below pace_low the agent rests until it has
# recovered to pace_high, instead of running itself into microsleep. It stays
# off in the core engine and in open_field (the microsleep/replay demo) and
# memory_maze (the rest-off -> path-integration-drift demo).
PACE_REST_BONUS = 5.0


def paced_basal_ganglia() -> BasalGangliaConfig:
    return BasalGangliaConfig(pace_rest_bonus=PACE_REST_BONUS)


def _event(tick: int, text: str, level: str = "info", kind: str = "scenario") -> Event:
    return {"tick": tick, "text": text, "level": level, "kind": kind}


def _dist(engine: Engine, obj: WorldObject) -> float:
    return math.hypot(engine.agent.pos[0] - obj.x, engine.agent.pos[1] - obj.y)


def teleport_to_start(engine: Engine) -> None:
    """Return the agent to the start pose with a fresh internal frame.

    Keeps the brain's memories (value map, neuromodulator baselines) and the tick
    counter; only the body, its path-integration frame and the episode boundary
    reset, so no learned transition links the goal to the start.
    """
    x, y, heading = START_POSE
    engine.agent.pos = (x, y)
    engine.agent.heading = heading
    engine.agent.last_pos = (x, y)
    engine.agent.last_heading = heading
    engine.spatial.state = SpatialState()
    engine.begin_episode()


class Scenario:
    id = "base"
    title = "Scenario"
    summary = ""
    watch: Tuple[str, ...] = ()

    def config(self) -> EngineConfig:
        return EngineConfig()

    def setup(self, engine: Engine) -> None:
        teleport_to_start(engine)

    def on_tick(self, engine: Engine, tick: int) -> List[Event]:
        return []

    def status(self) -> Dict[str, Any]:
        return {}

    def actions(self) -> List[Dict[str, str]]:
        return []

    def do_action(self, engine: Engine, action_id: str, tick: int) -> List[Event]:
        raise ValueError(f"Unknown action for {self.id}: {action_id}")

    def describe(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "watch": list(self.watch),
            "actions": self.actions(),
        }


class OpenField(Scenario):
    id = "open_field"
    title = "Open field"
    summary = "An empty arena. The agent explores, tires, sleeps and replays."
    watch = (
        "Wall-following exploration driven by novelty and wall avoidance",
        "Effort drains ATP; sustained running triggers microsleep and replay",
        "Avalanches spreading on the criticality lattice; drag the E/I coupling to change regime",
    )

    def __init__(self) -> None:
        self.distance = 0.0
        self._last: Optional[Tuple[float, float]] = None

    def on_tick(self, engine: Engine, tick: int) -> List[Event]:
        pos = engine.agent.pos
        if self._last is not None:
            self.distance += math.hypot(pos[0] - self._last[0], pos[1] - self._last[1])
        self._last = pos
        return []

    def status(self) -> Dict[str, Any]:
        return {"Distance travelled": round(self.distance, 1)}


class Beacon(Scenario):
    id = "beacon"
    title = "Beacon chase"
    summary = "A visible beacon hops to a new spot each time the agent reaches it."
    watch = (
        "Vision rays lock onto the beacon and steer the agent toward it",
        "Dopamine spikes on arrival (better than expected), then dips when the beacon jumps away",
        "The value map remembers where the beacon was, but memory is muted while the beacon is "
        "in view (cue gating). Set cue gating of memory to 0 and old spots can pull the agent "
        "away from the beacon it is looking at",
        "When ATP runs low the agent stops to recover (fatigue pacing) instead of collapsing into microsleep",
        "Turn vision drive down to 0 and the agent can no longer find it",
    )
    SPOTS = ((6.0, 3.0), (-5.0, 5.0), (-6.0, -5.0), (5.0, -6.0), (0.0, 7.5), (-7.5, 0.0))
    RADIUS = 1.2

    def __init__(self) -> None:
        self.visits = 0
        self.spot = 0
        self.last_visit_tick = 0
        self.last_time: Optional[int] = None
        self.target: Optional[WorldObject] = None

    def config(self) -> EngineConfig:
        return EngineConfig(basal_ganglia=paced_basal_ganglia())

    def setup(self, engine: Engine) -> None:
        super().setup(engine)
        x, y = self.SPOTS[0]
        self.target = WorldObject(x, y, self.RADIUS, "target")
        engine.world.add_object(self.target)

    def on_tick(self, engine: Engine, tick: int) -> List[Event]:
        assert self.target is not None
        if _dist(engine, self.target) > self.RADIUS:
            return []
        self.visits += 1
        self.last_time = tick - self.last_visit_tick
        self.last_visit_tick = tick
        self.spot = (self.spot + 1) % len(self.SPOTS)
        self.target.x, self.target.y = self.SPOTS[self.spot]
        return [_event(tick, f"Reached beacon #{self.visits} in {self.last_time} ticks; it hops away", "good")]

    def status(self) -> Dict[str, Any]:
        return {"Beacons reached": self.visits, "Last time to reach": self.last_time if self.last_time is not None else "—"}


class Foraging(Scenario):
    id = "foraging"
    title = "Foraging patch"
    summary = "Five food items to collect; the patch refills once it is cleared."
    watch = (
        "A wide field of view lets the agent notice food off to the side",
        "Each collection is a reward: watch dopamine and the value map build up",
        "Narrow the field of view and foraging slows down",
    )
    RADIUS = 1.0

    def __init__(self) -> None:
        self.collected = 0
        self.rounds = 0
        self.round_start = 0
        self.last_round_time: Optional[int] = None
        self.items: List[WorldObject] = []

    def config(self) -> EngineConfig:
        return EngineConfig(sensors=SensorConfig(vision_rays=5, fov=2.4), basal_ganglia=paced_basal_ganglia())

    def setup(self, engine: Engine) -> None:
        super().setup(engine)
        self.items = [WorldObject(x, y, self.RADIUS, "target") for (x, y) in FORAGING_TARGETS]
        for item in self.items:
            engine.world.add_object(item)

    def on_tick(self, engine: Engine, tick: int) -> List[Event]:
        events: List[Event] = []
        for item in self.items:
            if item.kind == "target" and _dist(engine, item) <= self.RADIUS:
                item.kind = "collected"
                self.collected += 1
                remaining = sum(1 for i in self.items if i.kind == "target")
                events.append(_event(tick, f"Collected food ({len(self.items) - remaining}/{len(self.items)})", "good"))
        if self.items and all(i.kind == "collected" for i in self.items):
            self.rounds += 1
            self.last_round_time = tick - self.round_start
            self.round_start = tick
            for item in self.items:
                item.kind = "target"
            events.append(_event(tick, f"Patch cleared in {self.last_round_time} ticks; it refills", "good"))
        return events

    def status(self) -> Dict[str, Any]:
        left = sum(1 for i in self.items if i.kind == "target")
        return {
            "Food left in patch": f"{left}/{len(self.items)}",
            "Patches cleared": self.rounds,
            "Last patch time": self.last_round_time if self.last_round_time is not None else "—",
        }


class HazardField(Scenario):
    id = "hazard_field"
    title = "Hazard field"
    summary = "Food lies beyond hazards. Contact hurts; the agent learns where not to linger."
    watch = (
        "Pain near a hazard drives norepinephrine (arousal) and a brief freeze; the freeze "
        "habituates, so the agent does not stay stuck in the pain zone",
        "Reward goes negative in the pain zone; the value map turns red there",
        "Raise NE → threat sensitivity for a more cautious agent",
    )
    RADIUS = 1.0
    FOOD = ((7.0, 0.0), (0.0, 7.0), (-7.0, -2.0))
    HAZARDS = ((3.5, 0.4), (0.4, 3.5), (-3.5, -1.0))

    def __init__(self) -> None:
        self.collected = 0
        self.hurts = 0
        self._in_pain = False
        self.items: List[WorldObject] = []

    def config(self) -> EngineConfig:
        return EngineConfig(sensors=SensorConfig(vision_rays=5, fov=2.0), basal_ganglia=paced_basal_ganglia())

    def setup(self, engine: Engine) -> None:
        super().setup(engine)
        self.items = [WorldObject(x, y, self.RADIUS, "target") for (x, y) in self.FOOD]
        for item in self.items:
            engine.world.add_object(item)
        for (x, y) in self.HAZARDS:
            engine.world.add_object(WorldObject(x, y, self.RADIUS, "hazard"))

    def on_tick(self, engine: Engine, tick: int) -> List[Event]:
        events: List[Event] = []
        ctx = engine.context
        pain = ctx.observation.pain_signal if ctx and ctx.observation else 0.0
        if pain > 0.5 and not self._in_pain:
            self.hurts += 1
            events.append(_event(tick, "Ouch — entered a hazard's pain zone", "critical"))
        self._in_pain = pain > 0.5
        for item in self.items:
            if item.kind == "target" and _dist(engine, item) <= self.RADIUS:
                item.kind = "collected"
                self.collected += 1
                events.append(_event(tick, f"Collected food ({self.collected} total)", "good"))
        if self.items and all(i.kind == "collected" for i in self.items):
            for item in self.items:
                item.kind = "target"
            events.append(_event(tick, "All food collected; it regrows", "good"))
        return events

    def status(self) -> Dict[str, Any]:
        return {"Food collected": self.collected, "Hazard contacts": self.hurts}


class MemoryMaze(Scenario):
    id = "memory_maze"
    title = "Memory maze"
    summary = "Water-maze recall: find a visible goal once, then return to it after it is hidden."
    watch = (
        "Trial 1: vision guides the agent to the goal, laying down a trajectory",
        "Sleep: replay propagates value backward along the path (watch the value map light up)",
        "Later trials: the goal is invisible; the agent navigates from its value map",
        "Turn replay off and restart to compare: online learning alone recalls more slowly",
        "Turn the inter-trial rest off: the agent tires, its sensory gate narrows, path "
        "integration drifts (the hollow ghost) and recall starts to fail",
    )
    GOAL = (6.0, 3.0)
    RADIUS = 1.5
    TIMEOUT = 300
    CONSOLIDATION_PASSES = 60
    REST_TICKS = 40  # inter-trial interval in the home cage (resting physiology only)

    def __init__(self) -> None:
        self.replay_enabled = True
        self.rest_between_trials = True
        self.trial = 1
        self.trial_start = 0
        self.history: List[Dict[str, Any]] = []
        self.goal: Optional[WorldObject] = None
        self.goal_visible = True

    def config(self) -> EngineConfig:
        return memory_nav_config()

    def setup(self, engine: Engine) -> None:
        super().setup(engine)
        self.goal = WorldObject(self.GOAL[0], self.GOAL[1], self.RADIUS, "target")
        engine.world.add_object(self.goal)

    def _set_visible(self, visible: bool) -> None:
        assert self.goal is not None
        self.goal_visible = visible
        self.goal.kind = "target" if visible else "hidden"

    def _consolidate(self, engine: Engine, tick: int) -> Event:
        n = len(engine.value_memory.trajectory)
        if n == 0:
            return _event(tick, "Nothing to replay yet: no trajectory since this trial started", "info", "replay")
        engine.value_memory.consolidate(
            passes=self.CONSOLIDATION_PASSES, dwell_extinction=engine.config.value_memory.dwell_extinction
        )
        return _event(tick, f"Sleep: replayed a {n}-step trajectory {self.CONSOLIDATION_PASSES}× — value map consolidated", "info", "replay")

    def _end_trial(self, engine: Engine, tick: int, reached: bool) -> List[Event]:
        duration = tick - self.trial_start
        self.history.append({"trial": self.trial, "visible": self.goal_visible, "ticks": duration, "reached": reached})
        where = "visible" if self.goal_visible else "hidden"
        if reached:
            events = [_event(tick, f"Trial {self.trial}: reached the {where} goal in {duration} ticks", "good")]
        else:
            events = [_event(tick, f"Trial {self.trial}: timed out looking for the {where} goal", "warning")]
        was_training = self.goal_visible
        if was_training and self.replay_enabled:
            events.append(self._consolidate(engine, tick))
        engine.value_memory.trajectory.clear()
        if was_training:
            self._set_visible(False)
            events.append(_event(tick, "Goal hidden — from now on the agent must navigate from memory", "info"))
        teleport_to_start(engine)
        if self.rest_between_trials:
            events.append(self._rest(engine, tick))
        self.trial += 1
        self.trial_start = tick
        return events

    def _rest(self, engine: Engine, tick: int) -> Event:
        """Inter-trial interval: the agent rests in the home cage between trials.

        Runs only the energy model at resting demand (the same physiology the
        engine uses), as real water-maze protocols rest the animal between
        trials. No brain ticks happen, so nothing is learned during the rest.
        """
        before = engine.astrocyte.atp
        for _ in range(self.REST_TICKS):
            engine.astrocyte.tick(demand=engine.config.astrocyte.rest_demand)
        return _event(tick, f"Rested {self.REST_TICKS} ticks in the home cage (ATP {before:.2f} → {engine.astrocyte.atp:.2f})", "info", "rest")

    def on_tick(self, engine: Engine, tick: int) -> List[Event]:
        assert self.goal is not None
        if _dist(engine, self.goal) <= self.RADIUS:
            return self._end_trial(engine, tick, reached=True)
        if tick - self.trial_start >= self.TIMEOUT:
            return self._end_trial(engine, tick, reached=False)
        return []

    TRIALS_SHOWN = 30  # the console charts only the most recent trials

    def status(self) -> Dict[str, Any]:
        hidden = [h for h in self.history if not h["visible"]]
        recall = [h for h in hidden if h["reached"]]
        return {
            "Trial": self.trial,
            "Goal": "visible" if self.goal_visible else "hidden",
            "Hidden-goal recalls": f"{len(recall)}/{len(hidden)}" if hidden else "—",
            "Last recall time": recall[-1]["ticks"] if recall else "—",
            "Replay after training": "on" if self.replay_enabled else "off",
            "Rest between trials": "on" if self.rest_between_trials else "off",
            "trials": self.history[-self.TRIALS_SHOWN:],
        }

    def actions(self) -> List[Dict[str, str]]:
        return [
            {"id": "toggle_replay", "label": "Toggle replay", "help": "Whether the agent sleeps and replays after the visible training trial."},
            {"id": "consolidate", "label": "Sleep & consolidate now", "help": "Replay the current trajectory into the value map immediately."},
            {"id": "toggle_goal", "label": "Show / hide goal", "help": "Make the goal visible again (or hide it)."},
            {"id": "toggle_rest", "label": "Toggle rest between trials", "help": "Without rest the agent tires across trials and its path integration degrades."},
        ]

    def do_action(self, engine: Engine, action_id: str, tick: int) -> List[Event]:
        if action_id == "toggle_replay":
            self.replay_enabled = not self.replay_enabled
            state = "on" if self.replay_enabled else "off"
            return [_event(tick, f"Replay after training turned {state} (applies to the next training trial)", "info")]
        if action_id == "toggle_rest":
            self.rest_between_trials = not self.rest_between_trials
            state = "on" if self.rest_between_trials else "off"
            return [_event(tick, f"Rest between trials turned {state}", "info")]
        if action_id == "consolidate":
            return [self._consolidate(engine, tick)]
        if action_id == "toggle_goal":
            self._set_visible(not self.goal_visible)
            return [_event(tick, f"Goal is now {'visible' if self.goal_visible else 'hidden'}", "info")]
        return super().do_action(engine, action_id, tick)


SCENARIOS = {cls.id: cls for cls in (OpenField, Beacon, Foraging, HazardField, MemoryMaze)}


def make_scenario(scenario_id: str) -> Scenario:
    try:
        return SCENARIOS[scenario_id]()
    except KeyError:
        raise ValueError(f"Unknown scenario: {scenario_id!r}") from None


def list_scenarios() -> List[Dict[str, Any]]:
    return [cls().describe() for cls in SCENARIOS.values()]


__all__ = ["Scenario", "SCENARIOS", "START_POSE", "make_scenario", "list_scenarios", "teleport_to_start"]
