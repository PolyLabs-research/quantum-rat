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
from core.config import BasalGangliaConfig, EngineConfig, SensorConfig, ValueMemoryConfig
from core.engine import Engine
from core.world import WorldObject
from experiments.memory_navigation import memory_nav_config
from experiments.protocols.foraging import DEFAULT_TARGETS as FORAGING_TARGETS

Event = Dict[str, Any]

START_POSE: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # x, y, heading (all scenarios)

# Homeostatic pacing for the energy-limited task scenarios (beacon, foraging,
# hazard_field): once ATP drops below pace_low the agent rests until it has
# recovered to pace_high, instead of running itself into microsleep. It stays
# off in the core engine and in open_field (the microsleep/replay demo).
# memory_maze and hidden_food pace with a higher threshold (GATE_SAFE_PACE_LOW).
PACE_REST_BONUS = 5.0
# Gate-safe pacing (memory_maze, hidden_food): rest before ATP reaches the
# level (0.55, `TRNConfig.open_at_atp`) below which the TRN narrows the
# sensory gate. The gate also scales the egomotion fed to path integration, so
# a fatigued agent's internal frame drifts: in the maze a long search on the
# visible trial (a start facing away from the goal) shifts it by up to 12 m and
# the goal it learns is in the wrong place; in hidden_food, where nothing resets
# the frame, it reaches 16-37 m after 3000 ticks. The default pace_low (0.4)
# lies below that level and does not prevent the drift.
# Kept a literal (0.55 + 0.05 is 0.6000000000000001 in floating point, which
# would move the pacing latch); tests/ui/test_sim_session.py checks it stays
# above TRNConfig().open_at_atp.
GATE_SAFE_PACE_LOW = 0.6
MAZE_PACE_LOW = GATE_SAFE_PACE_LOW


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
        "Exploration driven by a forward bias, the novelty bit (1 on any tick whose observation "
        "changed, which here means the agent moved) and wall avoidance at 12 m range; the agent "
        "keeps to the middle (85% of ticks in the central 10 x 10 m, under 3% within 1 m of a wall)",
        "Effort drains ATP; sustained running triggers microsleep and replay",
        "Avalanches spreading on the criticality lattice. It is bond percolation: subcritical at "
        "the default coupling 0.25 (κ settles near 0.91 with the exponent-1.5 estimator), spanning "
        "avalanches from 0.35, critical at 0.5, just above the slider's 0.45",
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
        "Dopamine (reward minus its running mean) hits 1.0 on arrival; between beacons it tracks "
        "the approach reward against that mean",
        "The value map remembers where the beacon was, but memory is muted while the beacon is "
        "in view (cue gating). Set cue gating of memory to 0 and old spots can pull the agent "
        "away from the beacon it is looking at",
        "When ATP runs low the agent stops to recover (fatigue pacing) instead of collapsing into microsleep",
        "Memory does not help this chase: the beacon has moved on from every remembered spot, so "
        "memory steering at 0 scores about the same or slightly better",
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
        "Each collection is a reward: dopamine (reward minus its running mean) hits 1.0 on contact "
        "and sits below 0.5 on most other ticks once the mean is up; the value map builds up",
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
        "Pain near a hazard raises norepinephrine (half pain plus half the novelty bit) and a brief freeze; the freeze "
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
    summary = "Hidden-goal recall: find a visible goal once, then return to it after it is hidden."
    watch = (
        "Trial 1: vision guides the agent to the goal, laying down a trajectory",
        "Sleep: replay propagates value backward along the path (watch the value map light up)",
        "Later trials: the goal is invisible; the agent navigates from its value map",
        "Turn replay off and restart to compare: online learning alone still recalls, but early "
        "recalls take longer (median 16 vs 10 ticks over the first 1,500 ticks; by 3,000 ticks both "
        "medians are 10), so fewer fit in a session (about 240 vs 300 in 3,000 ticks at seed 1337). "
        "The very first hidden trial is not faster with replay (15 vs 13 ticks at the default goal)",
        "Turn the inter-trial rest off: the agent now has to stop and recover mid-trial "
        "(fatigue pacing), so recalls take longer and fewer fit in a session. Set fatigue "
        "pacing to 0 as well: the agent tires, its sensory gate narrows, path integration "
        "drifts (the hollow ghost) and recall starts to fail",
        "Started facing away from the goal, the visible trial is a long search, so the replayed "
        "gradient has faded to nothing at the start. Sleep also stores the goal's place, and where "
        "the map is flat the agent turns toward it (goal vector). Fatigue pacing keeps the "
        "sensory gate open during the search so that place is stored where it really is. The stored "
        "place is forgotten after two visits in a row that find no goal there, so the stored place of "
        "a goal that moved stops pulling the agent (the value map can still lead it back there for a "
        "while, until that gradient fades)",
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
        config = memory_nav_config()
        config.value_memory.goal_vector = True
        config.basal_ganglia.pace_rest_bonus = PACE_REST_BONUS
        config.basal_ganglia.pace_low = MAZE_PACE_LOW
        return config

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


class HiddenFood(Scenario):
    """Invisible, renewable food at fixed sites: an open task where place memory pays.

    Six food sites sit about 2.5 m in from the walls, just inside the loop the
    agent runs when nothing pulls it elsewhere (with an open sensory gate the
    default agent heads for a wall and follows it round). The food is kind
    "hidden": contact rewards it (``Engine._nearest_target`` includes "hidden"),
    but vision does not treat it as food, so neither the vision drive nor the
    cue gate ever sees it. An eaten site regrows ``REGROW`` ticks later, in
    place, and can be eaten again from the following tick (an engine step has
    to see it as food first, so every find comes with the contact reward).
    Without memory the agent finds food only when its loop happens to brush a
    site; with memory, the value map learns the contact reward at the site
    (primary reward only) and steers the agent back toward it on later passes.

    Config (scenario-only, the engine defaults are untouched):
    - pacing with ``pace_low`` 0.6: the agent rests before ATP reaches 0.55,
      the level below which the TRN gate narrows to 0.4 and path integration
      under-counts turns and motion. Nothing here resets the path-integration
      frame (unlike the maze's teleport to the start), so errors accumulate.
      With the console's usual pace_low 0.4 the gate is narrowed on about a
      third of ticks, and after 3000 ticks the estimated position is on
      average 16 m (memory off) to 39 m (memory on) from the truth (seeds 1-8,
      noise 0.03); the map is then useless and memory costs ~41% (14.5 vs 24.4
      finds, 0 wins of 8). With pace_low 0.6 the gate stays open and the drift
      is at most 1.2 m (wall contact while turning). Caveat: the narrowed gate
      also weakens FORWARD, so the fatigued agent wanders the interior and
      finds far more food without memory (24.4) than the rested agent does
      with it (6.75);
    - ``generalization_radius`` 2, as in the memory maze, so one contact values
      a followable patch rather than a single 0.5 m cell (with 0 the benefit
      drops from x2.84 to x1.58 at noise 0.03).

    What the benefit is (seeds 1-8 at noise 0.03, gain 1.5, unless noted; see
    docs/decisions.md G21): memory-driven area-restricted search near recent
    finds, not accurate site memory and not route planning. Positive value
    lies within a few metres of a site (90th percentile 2.6-4.3 m), so memory
    pulls only an agent that passes close by, and the memory agent then
    circles a site it knows (~70% of its finds at its favourite site). It
    needs a real map but not precise sites: a map read rotated by 22 degrees
    (every phantom peak >= 2.8 m from a real site) keeps about half to nearly
    all of the extra finds (x2.74 against x2.84 on seeds 1-8; x1.91 / x2.67
    against x2.85 / x4.08 on the other blocks), a map read at 2x
    scale gives none (x1.00), and wiping the map every 150 or 500 ticks leaves
    x1.24-2.17. Part of it survives without fixed sites: with every site
    jumping to a random place in the food band every 150 ticks memory still
    gives x1.08-1.47. If the sites lie on the default loop (2 m from the walls
    instead of 2.5 m) the agent finds them anyway and memory costs ~half
    (x0.55), and an agent that explores the interior (forward_bias 0.5) also
    does better without memory (37.2 vs 19.1 finds).
    """

    id = "hidden_food"
    title = "Hidden food"
    summary = "Invisible food at fixed sites regrows after it is eaten. The agent has to find it, then remember where it was."
    watch = (
        "The food is invisible to the agent: vision never reports it as food, so only a chance "
        "brush finds a site the first time. The dashed rings show where it is",
        "Turn Memory steering to 0 and restart: the agent runs a loop along the walls and finds "
        "food only by luck (about 2-4 items in 3000 ticks)",
        "With memory on, each find writes a value peak near the site (watch the value map). On later "
        "passes the agent swerves into it, and it often keeps circling a site it knows, eating "
        "each time the food regrows. Over many runs it finds about 3x as much food as with memory "
        "off (2.8-4x), but one run can be unlucky: until the loop brushes a site, memory has nothing to use",
        "This is searching near recent finds rather than exact site memory: the map only has to be "
        "right to within about 3 m, and memory still helps a little when the food moves",
        "The memory agent tends to settle on one or two sites rather than touring all six: the value "
        "map only pulls from a few metres away, so a site it has not visited for a while is out of reach",
        "The agent rests when ATP falls to 60%, before the sensory gate narrows; a narrowed gate "
        "under-counts motion, path integration drifts (the hollow ghost) and the map becomes useless. "
        "Nothing resets the drift here, so it only grows",
        "Lower Forward drive to 0.5 and restart: the agent wanders the interior and finds far more "
        "food without memory, and memory steering then costs food, because circling one site beats "
        "touring only when the tour is slow",
    )
    RADIUS = 1.25
    SITES: Tuple[Tuple[float, float], ...] = (
        (7.5, -2.0),
        (7.5, 4.5),
        (2.5, 7.5),
        (-5.0, 7.5),
        (-7.5, -1.0),
        (-1.5, -7.5),
    )
    REGROW = 150  # ticks from being eaten until the site has food again
    PACE_LOW = GATE_SAFE_PACE_LOW  # x atp_baseline: rest before the TRN gate narrows (ATP < 0.55)
    GENERALIZATION_RADIUS = 2

    def __init__(self) -> None:
        self.collected = 0
        self.collect_ticks: List[int] = []
        self.items: List[WorldObject] = []
        self.eaten_at: List[Optional[int]] = []
        self.site_counts: List[int] = []
        self.last_site: Optional[int] = None

    def config(self) -> EngineConfig:
        return EngineConfig(
            basal_ganglia=BasalGangliaConfig(pace_rest_bonus=PACE_REST_BONUS, pace_low=self.PACE_LOW),
            value_memory=ValueMemoryConfig(generalization_radius=self.GENERALIZATION_RADIUS),
        )

    def setup(self, engine: Engine) -> None:
        super().setup(engine)
        self.items = [WorldObject(x, y, self.RADIUS, "hidden") for (x, y) in self.SITES]
        self.eaten_at = [None] * len(self.items)
        self.site_counts = [0] * len(self.items)
        for item in self.items:
            engine.world.add_object(item)

    def on_tick(self, engine: Engine, tick: int) -> List[Event]:
        events: List[Event] = []
        for i, item in enumerate(self.items):
            eaten = self.eaten_at[i]
            if item.kind == "collected" and eaten is not None and tick - eaten >= self.REGROW:
                # Regrown, but not collectable until an engine step has seen it as
                # food: a site that regrows under the agent is eaten on the next
                # tick, with the contact reward (and the map write) that goes with
                # it, never in this on_tick without one.
                item.kind = "hidden"
                self.eaten_at[i] = None
                continue
            if item.kind == "hidden" and _dist(engine, item) <= self.RADIUS:
                item.kind = "collected"
                self.eaten_at[i] = tick
                self.collected += 1
                self.site_counts[i] += 1
                self.collect_ticks.append(tick)
                first = self.site_counts[i] == 1
                again = "" if first else f", visit {self.site_counts[i]}"
                where = "new site" if first else "known site"
                events.append(_event(tick, f"Found hidden food at site {i + 1} ({where}{again}); {self.collected} total", "good"))
                self.last_site = i
        return events

    def sites_found(self) -> int:
        return sum(1 for n in self.site_counts if n > 0)

    BAND = (2.0, 3.0)  # the moved-sites control's band, in from the walls (the sites sit ~2.5 in)

    @classmethod
    def band_point(cls, rng: Any) -> Tuple[float, float]:
        """A point uniform on the band ``BAND`` in from the walls of the 20-unit box.

        Two ``rng.uniform(-8.0, 8.0)`` draws per candidate, rejected until the
        candidate is in the band; ``rng`` is any object with ``uniform``
        (``random.Random`` or a ``core.rng`` stream). The construction of the
        moved-sites control, shared by tests/experiments/test_hidden_food.py and
        experiments/g23_remeasure.py so it is defined once.
        """
        low, high = cls.BAND
        while True:
            x, y = rng.uniform(-8.0, 8.0), rng.uniform(-8.0, 8.0)
            if low <= 10.0 - max(abs(x), abs(y)) <= high:
                return x, y

    def jump_sites(self, rng: Any) -> None:
        """Move every site to a fresh :meth:`band_point` (the moved-sites control), in site order."""
        for item in self.items:
            item.x, item.y = self.band_point(rng)

    BLOCK = 500  # ticks per block of the learning curve

    def blocks(self, ticks: int) -> List[int]:
        """Collections per ``BLOCK``-tick block over the first ``ticks`` ticks (the learning curve)."""
        out = [0] * (ticks // self.BLOCK)
        for t in self.collect_ticks:
            if t // self.BLOCK < len(out):
                out[t // self.BLOCK] += 1
        return out

    def status(self) -> Dict[str, Any]:
        ready = sum(1 for i in self.items if i.kind == "hidden")
        return {
            "Food found": self.collected,
            "Sites discovered": f"{self.sites_found()}/{len(self.SITES)}",
            "Sites with food now": f"{ready}/{len(self.items)}",
            "Finds per site": " ".join(str(n) for n in self.site_counts) if self.site_counts else "—",
        }

    def actions(self) -> List[Dict[str, str]]:
        return [
            {"id": "forget", "label": "Forget the map", "help": "Erase the value map: the agent must rediscover every site."},
        ]

    def do_action(self, engine: Engine, action_id: str, tick: int) -> List[Event]:
        if action_id == "forget":
            engine.value_memory.values.clear()
            return [_event(tick, "Value map erased: the agent no longer remembers any site", "warning")]
        return super().do_action(engine, action_id, tick)

SCENARIOS = {cls.id: cls for cls in (OpenField, Beacon, Foraging, HazardField, HiddenFood, MemoryMaze)}


def make_scenario(scenario_id: str) -> Scenario:
    try:
        return SCENARIOS[scenario_id]()
    except KeyError:
        raise ValueError(f"Unknown scenario: {scenario_id!r}") from None


def list_scenarios() -> List[Dict[str, Any]]:
    return [cls().describe() for cls in SCENARIOS.values()]


__all__ = ["Scenario", "SCENARIOS", "START_POSE", "make_scenario", "list_scenarios", "teleport_to_start"]
