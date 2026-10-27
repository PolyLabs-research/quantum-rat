"""Live simulation sessions for the lab console.

A ``SimSession`` owns one engine running one scenario. It advances the engine
on request and turns engine state into compact, JSON-serialisable views:

* ``step(n)``      -> a per-tick series (for charts and the trail) + new events
* ``frame()``      -> the full display state of the latest tick (``replay_events``:
  the last five finished replay events, ``brain.systems.replay_events``)
* ``value_map()``  -> the learned place-value map in world coordinates
* ``avalanche_histogram()`` -> the avalanche-size distribution (log bins)
* ``params()`` / ``set_param()`` -> whitelisted live parameters
* ``record(dir)``  -> save the session as a run the replay viewer can open
  (with ``replay_events.jsonl`` when any replay event happened)

Everything here is instrumentation: it reads the engine to *show* it, and the
brain still only ever sees its Observation.
"""

from __future__ import annotations

import json
import math
import secrets
import threading
import time
from collections import OrderedDict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

from brain.systems.basal_ganglia import channel_terms, selection_probabilities
from brain.systems.replay_events import REPLAY_EVENTS_FILE, write_replay_events
from metrics.decisions import COUNTERFACTUAL_TERMS, DECISIONS_FILE, counterfactual_probabilities, decision_record, record_line, total_variation
from core.engine import Engine
from metrics.logger import _canonical_json
from metrics.manifest import build_manifest, finish_manifest, write_manifest
from metrics.scene import write_scene
from metrics.schema import SCHEMA_VERSION
from ui.scenarios import START_POSE, Scenario, make_scenario
from ui.scenarios import DEFAULT_PROFILE, PROFILE_IDS, profile_config

Event = Dict[str, Any]

MAX_STEPS_PER_CALL = 200
HISTORY_LIMIT = 50_000
TURNING_WINDOW = 300  # ticks over which the live turning and closure readouts are taken
EVENT_LIMIT = 300
# Finished replay events kept for the frame and the recording, drained from the
# engine's bounded log every tick. At the legacy defaults a microsleep bout
# comes about every 60 ticks, so this covers more ticks than HISTORY_LIMIT; the
# keep is not tied to the history, so ``record`` writes only the kept events
# that end inside the recorded ticks (``n_replay_events`` counts those, and
# ``n_replay_events_total`` every event the session saw).
REPLAY_EVENT_LIMIT = 4096
FRAME_REPLAY_EVENTS = 5  # how many of the latest replay events a frame carries
REGIME_EVENT_GAP = 60  # ticks between criticality-regime announcements
GATE_EVENT_GAP = 30  # ticks between sensory-gate announcements (the gate can flicker)


@dataclass(frozen=True)
class Param:
    key: str
    label: str
    group: str
    min: float
    max: float
    step: float
    help: str
    integer: bool = False


# Every parameter here is read by the engine each tick, so changes apply live.
PARAMS: Tuple[Param, ...] = (
    Param("basal_ganglia.vision_gain", "Vision drive", "Action selection", 0.0, 1.5, 0.05,
          "How strongly a visible target pulls the agent. 0 makes it blind to targets."),
    Param("basal_ganglia.forward_bias", "Forward drive", "Action selection", 0.0, 1.5, 0.05,
          "Baseline urge to keep moving forward."),
    Param("basal_ganglia.value_gain", "Memory steering", "Action selection", 0.0, 3.0, 0.1,
          "How strongly the learned value map steers the agent toward places that led to reward."),
    Param("basal_ganglia.cue_gate_gain", "Cue gating of memory", "Action selection", 0.0, 4.0, 0.1,
          "How strongly a visible target mutes memory steering, so what the agent sees beats what it "
          "remembers. The gate reads the raw vision rays, independent of Vision drive: with Vision "
          "drive at 0 a target in view still mutes memory although vision no longer steers toward it. "
          "0 lets memory steer even with a target in view."),
    Param("basal_ganglia.wall_gate_gain", "Wall gating of memory", "Action selection", 0.0, 4.0, 0.1,
          "How strongly a wall close ahead mutes memory's push to keep going straight, so a remembered "
          "place behind a wall cannot pin the agent against it (turns toward a better side are kept). "
          "Reads the raw centre vision ray. 0 turns it off."),
    Param("basal_ganglia.wall_avoid_gain", "Wall avoidance", "Action selection", 0.0, 1.5, 0.05,
          "How hard the agent turns away from a wall close ahead."),
    Param("value_memory.dwell_extinction", "Peak extinction", "Memory", 0.0, 0.1, 0.005,
          "Cost charged when the agent stays in one place cell (resting or turning on the spot) "
          "while that place is positively valued, so value peaks it built by staying put fade "
          "instead of trapping it there. Sleep replay applies the same rule, so a peak fades to "
          "about zero (never below one step's charge) instead of turning aversive. 0 turns extinction off."),
    Param("basal_ganglia.dopamine_explore_gain", "Dopamine → exploration", "Neuromodulation", 0.0, 1.5, 0.05,
          "Dopamine below 0.5 (reward under its running mean) scales up the novelty term in the "
          "FORWARD drive."),
    Param("basal_ganglia.ach_precision_gain", "Acetylcholine → precision", "Neuromodulation", 0.0, 1.5, 0.05,
          "Scales the vision drive by (1 + gain × ACh), where ACh is the novelty bit: 1 whenever the "
          "observation checksum changed, which is every tick at sensor noise 0.03, so there this is a "
          "constant ×(1 + gain)."),
    Param("basal_ganglia.ne_threat_gain", "Norepinephrine → threat", "Neuromodulation", 0.0, 1.5, 0.05,
          "Scales pain avoidance and the pain → REST (freezing) drive by (1 + gain × NE), "
          "NE = ½ pain + ½ the novelty bit."),
    Param("basal_ganglia.fiveht_patience_gain", "Serotonin → patience", "Neuromodulation", 0.0, 1.5, 0.05,
          "Adds a REST drive of gain × (5HT − 0.5); 5HT is 0.5 plus half the running mean of reward, "
          "so 0.5 with no reward."),
    Param("criticality.coupling", "E/I coupling", "Criticality", 0.10, 0.45, 0.01,
          "Per-neighbour activation probability on the 16 × 16 torus (bond percolation). The lattice is "
          "critical at coupling 0.5, above this slider's 0.45; at the default 0.25 it is subcritical "
          "and κ settles near 0.91."),
    Param("basal_ganglia.criticality_gain", "Criticality → sensory gain", "Criticality", 0.0, 1.0, 0.05,
          "How strongly a gain computed from κ scales vision. 0 at defaults, so the panel is a readout. "
          "With the default coupling the gain is a 0.93–1.0 multiplier after warm-up (0.92 at the "
          "long-run κ of 0.91) that changes no decision in the probed worlds (barren, beacon, foraging; "
          "tools/probes/dormant_couplings)."),
    Param("sensors.fov", "Field of view", "Senses", 0.4, 3.0, 0.1,
          "Angular spread of the vision rays, in radians."),
    Param("sensors.vision_rays", "Vision rays", "Senses", 1, 9, 1,
          "Number of rays in the vision fan.", integer=True),
    Param("sensors.vision_range", "Vision range", "Senses", 2.0, 20.0, 0.5,
          "Distance the agent can see."),
    Param("sensors.noise", "Sensor noise", "Senses", 0.0, 0.2, 0.01,
          "Random jitter on vision and pain. With noise on, each seed gives a different run; "
          "with it off, the seed only changes the criticality lattice."),
    Param("basal_ganglia.pace_rest_bonus", "Fatigue pacing", "Energy", 0.0, 8.0, 0.5,
          "Drive to rest once ATP runs low, held until it has recovered. 0 lets the agent run "
          "until it collapses into microsleep."),
    # The research profile's seeded elements and its place code (docs/profiles.md). Every one is read
    # by the engine each tick, so it is live in both profiles where it applies.
    Param("sensors.odometry_speed_noise", "Odometry speed noise", "Estimate & sampling", 0.0, 0.2, 0.01,
          "Seeded error on the self-motion estimate's forward step, as a fraction of the step (research 0.05, "
          "legacy 0). Moves the estimate (the hollow ghost), never the body."),
    Param("sensors.odometry_turn_noise", "Odometry turn noise", "Estimate & sampling", 0.0, 0.05, 0.0025,
          "Seeded error on the estimated heading change, radians per tick (research 0.01, legacy 0). With "
          "the heading oracle on (research) the heading estimate reads the oracle instead, so this moves "
          "nothing there."),
    Param("sensors.heading_oracle_noise", "Heading oracle noise", "Estimate & sampling", 0.0, 0.2, 0.01,
          "The declared heading oracle's error, radians per tick (research 0.05). The legacy profile has no "
          "oracle, so this cannot be raised there."),
    Param("basal_ganglia.softmax_temperature", "Action softmax temperature", "Estimate & sampling", 0.0, 0.5, 0.01,
          "Seeded softmax over the four channel scores (research 0.1); 0 is the deterministic argmax with its "
          "tie order (legacy)."),
    Param("place.reward_learning_rate", "SR reward learning rate", "Estimate & sampling", 0.05, 1.0, 0.05,
          "How fast the successor representation's reward weights track the reward seen at the cells active on "
          "arrival (research 0.5). Nothing without the place population (research profile)."),
    Param("place.reward_unlearning_rate", "SR reward unlearning rate", "Estimate & sampling", 0.05, 8.0, 0.05,
          "How fast those weights fall toward 0 at the active cells on a tick that sees no reward (decisions G41: at "
          "the research default this equals the learning rate, 0.5, and the agent circles a just-emptied site; at 4 "
          "the circling goes and the finds come back). Per-feature rule only; nothing without the place population."),
)
PARAM_INDEX = {p.key: p for p in PARAMS}


def _r(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def criticality_regime(kappa: float, n_avalanches: int, needed: int) -> str:
    if n_avalanches < needed:
        return "measuring"
    if kappa < 0.85:
        return "subcritical"
    if kappa > 1.05:
        return "supercritical"
    return "near-critical"


def _to_world(gx: float, gy: float, hd: float) -> Tuple[float, float, float]:
    """Map the agent's internal (path-integration) frame into world coordinates."""
    sx, sy, sh = START_POSE
    c, s = math.cos(sh), math.sin(sh)
    return sx + c * gx - s * gy, sy + s * gx + c * gy, sh + hd


class SimSession:
    def __init__(self, scenario_id: str, seed: int = 1337, params: Optional[Dict[str, float]] = None,
                 profile: str = DEFAULT_PROFILE) -> None:
        if profile not in PROFILE_IDS:
            raise ValueError(f"Unknown profile: {profile!r}; one of {PROFILE_IDS}")
        self.id = secrets.token_hex(8)
        self.scenario_id = scenario_id
        self.profile = profile
        self.profile_overrides: List[Tuple[str, Any, Any]] = []
        self.seed = int(seed)
        self.lock = threading.RLock()
        self.last_access = time.monotonic()
        self.overrides: Dict[str, float] = {}
        self._build(dict(params or {}))

    # ---------------------------------------------------------------- lifecycle

    def _build(self, params: Dict[str, float]) -> None:
        self.scenario: Scenario = make_scenario(self.scenario_id)
        config, self.profile_overrides = profile_config(self.scenario, self.profile)
        self.engine = Engine(seed=self.seed, config=config)
        self._phi_centres = None  # the population's normalised rates at its own centres (lazily; SR value field)
        self.scenario.setup(self.engine)
        self.overrides = {}
        for key, value in params.items():
            self._apply_param(key, value)
        # Behaviour readouts (decisions G39): distance walked, wall-contact ticks, finds (ticks that touched a
        # target: the primary contact reward) and reward, so that cycling can be told from useful behaviour.
        self._distance = 0.0
        self._last_pos: Optional[Tuple[float, float]] = None
        self._wall_ticks = 0
        self._ticks = 0
        self._finds = 0
        self._last_find_tick: Optional[int] = None
        self._reward_total = 0.0
        self._recent: Deque[Tuple[float, float, float]] = deque(maxlen=TURNING_WINDOW + 1)  # (x, y, heading)
        # The decision log (metrics.decisions): one canonical line per tick, kept beside the tick history and
        # written into a recording as decisions.jsonl.
        self.decisions: Deque[Tuple[int, str]] = deque(maxlen=HISTORY_LIMIT)
        self.history: Deque[Dict[str, Any]] = deque(maxlen=HISTORY_LIMIT)
        self.events: Deque[Event] = deque(maxlen=EVENT_LIMIT)
        self.replay_events: Deque[Dict[str, Any]] = deque(maxlen=REPLAY_EVENT_LIMIT)
        self.n_replay_events = 0  # every finished replay event since the session was built or reset
        self._seq = 0
        self._prev_microsleep = False
        self._regime: Optional[str] = None
        self._regime_tick = -REGIME_EVENT_GAP
        self._gate = "OPEN"
        self._gate_tick = -GATE_EVENT_GAP
        self._built_at = time.monotonic()  # for the recording's manifest (wall-clock, pauses included)
        self.tick = -1
        self._emit({"tick": 0, "text": f"{self.scenario.title} started (seed {self.seed}, {self.profile} profile)",
                    "level": "info", "kind": "session"})
        self._advance()  # one tick so there is always a sensory snapshot to show

    def reset(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            self.seed = int(seed)
        self._build(dict(self.overrides))

    def touch(self) -> None:
        self.last_access = time.monotonic()

    # ------------------------------------------------------------------ events

    def _emit(self, event: Event) -> None:
        self._seq += 1
        self.events.append({"seq": self._seq, **event})

    def events_since(self, seq: int) -> List[Event]:
        return [e for e in self.events if e["seq"] > seq]

    def _generic_events(self, tick: int) -> List[Event]:
        events: List[Event] = []
        ctx = self.engine.context
        if ctx is None:
            return events
        if ctx.microsleep_active and not self._prev_microsleep:
            events.append({"tick": tick, "text": "Microsleep: ATP ran low, sensory gate closed, replay begins", "level": "warning", "kind": "sleep"})
        elif self._prev_microsleep and not ctx.microsleep_active:
            events.append({"tick": tick, "text": "Woke up: ATP recovered", "level": "info", "kind": "sleep"})
        self._prev_microsleep = ctx.microsleep_active

        gate = ctx.trn_state
        if gate != self._gate and tick - self._gate_tick >= GATE_EVENT_GAP:
            if gate == "NARROW":
                events.append({"tick": tick, "text": "Sensory gate narrowed (tired): path integration now under-counts motion", "level": "warning", "kind": "gate"})
            elif gate == "CLOSED" and not ctx.microsleep_active:  # microsleep has its own event
                events.append({"tick": tick, "text": "Sensory gate closed: senses and path integration are off", "level": "warning", "kind": "gate"})
            elif gate == "OPEN":
                events.append({"tick": tick, "text": "Sensory gate open again", "level": "info", "kind": "gate"})
            self._gate = gate
            self._gate_tick = tick

        field = self.engine.criticality
        regime = criticality_regime(field.kappa, len(field.avalanche_sizes), field.config.kappa_min_avalanches)
        if regime != "measuring" and regime != self._regime and tick - self._regime_tick >= REGIME_EVENT_GAP:
            events.append({
                "tick": tick,
                "text": (
                    f"κ = {field.kappa:.2f}, in the {regime} band of the exponent-1.5 estimator "
                    "(0.85–1.05 is called 'near-critical'); this is not the lattice's critical point, "
                    "which is at coupling 0.5"
                ),
                "level": "info",
                "kind": "criticality",
            })
            self._regime = regime
            self._regime_tick = tick
        return events

    # --------------------------------------------------------------- stepping

    def _advance(self) -> Dict[str, Any]:
        td = self.engine.run(1)[0]
        self.tick = td.tick
        self.history.append(td.to_ordered_dict())
        self.decisions.append((td.tick, record_line(decision_record(self.engine))))  # before the scenario acts
        self._count_behaviour(td)
        for event in self.scenario.on_tick(self.engine, td.tick) + self._generic_events(td.tick):
            self._emit(event)
        for replay_event in self.engine.replay_log.drain():
            self.replay_events.append(replay_event.to_dict())
            self.n_replay_events += 1
        m = td.neuromodulators
        return {
            "t": td.tick,
            "x": _r(td.pos[0], 3),
            "y": _r(td.pos[1], 3),
            "r": _r(td.reward),
            "da": _r(m.get("DA", 0.5)),
            "ne": _r(m.get("NE", 0.0)),
            "ach": _r(m.get("ACh", 0.0)),
            "ht": _r(m.get("5HT", 0.5)),
            "k": _r(td.kappa),
            "av": td.avalanche_size,
            "act": td.criticality_active,
            "atp": _r(td.atp),
            "gly": _r(td.glycogen),
            "ms": int(td.microsleep_active),
            "rp": int(td.replay_active),
            "a": td.action_name,
            "pain": _r(td.obs_pain),
        }

    def step(self, n: int = 1) -> List[Dict[str, Any]]:
        n = max(1, min(int(n), MAX_STEPS_PER_CALL))
        return [self._advance() for _ in range(n)]

    # --------------------------------------------------------------- behaviour

    TELEPORT = 1.5  # units per tick; a bigger jump is a scenario's teleport, not walking

    def _count_behaviour(self, td: Any) -> None:
        x, y = td.pos
        if self._last_pos is not None:
            step = math.hypot(x - self._last_pos[0], y - self._last_pos[1])
            if step <= self.TELEPORT:
                self._distance += step
        self._last_pos = (x, y)
        bx, by = self.engine.world.bounds
        if abs(x) >= bx - 1e-9 or abs(y) >= by - 1e-9:
            self._wall_ticks += 1
        self._ticks += 1
        ctx = self.engine.context
        if ctx is not None and ctx.target_contact:
            self._finds += 1
            self._last_find_tick = td.tick
        self._reward_total += float(td.reward)
        self._recent.append((x, y, self.engine.agent.heading))

    def _turning(self) -> Tuple[float, float]:
        """Signed turning (revolutions) and closure (net displacement / distance) over the last TURNING_WINDOW ticks."""
        pts = list(self._recent)
        if len(pts) < 2:
            return 0.0, 0.0
        turning = 0.0
        dist = 0.0
        for (x0, y0, h0), (x1, y1, h1) in zip(pts, pts[1:]):
            step = math.hypot(x1 - x0, y1 - y0)
            if step > self.TELEPORT:
                continue
            turning += (h1 - h0 + math.pi) % (2 * math.pi) - math.pi
            dist += step
        net = math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
        return turning / (2 * math.pi), (net / dist) if dist > 0 else 0.0

    def behaviour(self) -> Dict[str, Any]:
        """Generic readouts of what the body did since the session was built or reset."""
        return {
            "distance": _r(self._distance, 1),
            "wall_fraction": _r(self._wall_ticks / self._ticks, 3) if self._ticks else 0.0,
            "finds": self._finds,
            "ticks_since_find": (self.tick - self._last_find_tick) if self._last_find_tick is not None else None,
            "distance_per_find": _r(self._distance / self._finds, 1) if self._finds else None,
            "reward_total": _r(self._reward_total, 2),
            # Circling, live: signed turning over the last TURNING_WINDOW ticks in revolutions (left positive) and the
            # closure of that stretch (net displacement over distance: 0 for a closed loop, 1 for a straight line).
            "turning_window": TURNING_WINDOW,
            "turning_revolutions": _r(self._turning()[0], 2),
            "closure": _r(self._turning()[1], 2),
        }

    # -------------------------------------------------------------- mechanisms

    def mechanisms(self) -> List[Dict[str, str]]:
        """What is in force, from the effective configuration (decisions G39).

        One entry per mechanism the panels describe, with ``status`` ``"active"``
        (it reaches behaviour), ``"readout"`` (computed and shown, but with a gain
        of 0 it moves nothing) or ``"off"`` (not running), and a one-line
        ``detail``. Recomputed after a parameter change, so a slider that turns a
        gain up turns its chip on.
        """
        cfg = self.engine.config
        a, bg, vm, se, sp, pl, trn = cfg.astrocyte, cfg.basal_ganglia, cfg.value_memory, cfg.sensors, cfg.spatial, cfg.place, cfg.trn
        overridden = {name for name, _, _ in self.profile_overrides}
        own = " (this scenario's own setting)"
        out: List[Dict[str, str]] = []

        def add(mid: str, name: str, status: str, detail: str) -> None:
            out.append({"id": mid, "name": name, "status": status, "detail": detail})

        if a.frozen:
            add("energy", "Energy & fatigue", "off", "ATP is held at 1.0: no fatigue, no pacing, no energy throttle on motion")
        else:
            pacing = f"pacing rest {bg.pace_rest_bonus:g} below ATP {bg.pace_low:g}" if bg.pace_rest_bonus > 0 else "no pacing"
            add("energy", "Energy & fatigue", "active",
                f"effort drains ATP; {pacing}; motion {'scaled by ATP' if a.scales_motion else 'not scaled by ATP'}")
        if trn.microsleep_enabled and not a.frozen:
            add("microsleep", "Microsleep & engine replay", "active", "low ATP triggers a microsleep bout that replays the recent path into the value map")
        else:
            add("microsleep", "Microsleep & engine replay", "off",
                "ATP never falls, so no bout can start" if a.frozen and trn.microsleep_enabled else "microsleep disabled")
        if vm.source == "none" or bg.value_gain <= 0:
            add("steer", "Memory steering", "off", "no value signal reaches the scores" if vm.source == "none" else "Memory steering gain is 0")
        elif vm.source == "sr":
            add("steer", "Memory steering", "active", f"reads the SR value V = φ·MᵀR (the blue field) × gain {bg.value_gain:g}; cue and wall gating apply")
        else:
            add("steer", "Memory steering", "active", f"reads the tabular value map × gain {bg.value_gain:g}; cue and wall gating apply")
        radius = f"; place-field radius {vm.generalization_radius}" + (own if "value_memory.generalization_radius" in overridden else "") if vm.generalization_radius else ""
        if vm.source == "tabular":
            add("map", "Tabular value map", "active", f"learns every tick and is what steers{radius}")
        else:
            add("map", "Tabular value map", "readout", f"learns every tick; a diagnostic here, nothing reads it{radius}")
        if pl.enabled and self.engine.place is not None:
            unlearn = "the learning rate" if pl.reward_unlearning_rate is None else f"{pl.reward_unlearning_rate:g}"
            unlearn += own if "place.reward_unlearning_rate" in overridden else ""
            sr = (f"; SR reward rule {pl.reward_rule} (learning {pl.reward_learning_rate:g}, unlearning {unlearn}), γ {pl.sr_discount:g}"
                  if self.engine.sr is not None else "; no SR learner")
            add("place", "Place population & SR", "active", f"{self.engine.place.size} Gaussian place cells over the estimate{sr}")
        else:
            add("place", "Place population & SR", "off", "no population on this profile")
        if vm.oracle_homing:
            add("goal", "Goal memory (oracle homing)", "active",
                "turns toward the remembered goal where the value read is flat: an oracle control, not learned navigation"
                + (own if "value_memory.oracle_homing" in overridden else ""))
        else:
            add("goal", "Goal memory (oracle homing)", "off", "no remembered goal")
        add("vision", "Vision drive", "active" if bg.vision_gain > 0 else "off",
            f"gain {bg.vision_gain:g}; {se.vision_rays} rays over {se.fov:g} rad, range {se.vision_range:g}; a visible target mutes memory (cue gate {bg.cue_gate_gain:g})"
            + (f"; a target seen to one side turns the agent toward it (orient {bg.orient_gain:g})" if bg.orient_gain > 0 else ""))
        reach = "the whole vision range" if bg.wall_avoid_range == 1.0 else f"{bg.wall_avoid_range * se.vision_range * cfg.units.metres_per_unit:.2g} m"
        commit = f"; turn commitment {bg.turn_commitment:g}" if bg.turn_commitment > 0 else ""
        add("wall", "Wall avoidance", "active" if bg.wall_avoid_gain > 0 else "off",
            f"gain {bg.wall_avoid_gain:g} for a wall ahead within {reach}{commit}; a wall ahead also dims memory's push to go straight (gate {bg.wall_gate_gain:g})")
        add("pain", "Pain", "active", f"avoidance {bg.pain_avoidance:g} on FORWARD; freeze (pain → REST) {bg.rest_pain_gain:g}, habituating")
        if bg.softmax_temperature > 0:
            add("select", "Action selection", "active", f"one seeded softmax draw per tick at τ {bg.softmax_temperature:g}: the highest score need not win")
        else:
            add("select", "Action selection", "active", "the highest score wins (argmax, deterministic tie order)")
        gains = {"DA → exploration": bg.dopamine_explore_gain, "ACh → vision": bg.ach_precision_gain,
                 "NE → threat": bg.ne_threat_gain, "5HT → patience": bg.fiveht_patience_gain}
        on = [f"{k} {v:g}" for k, v in gains.items() if v > 0]
        add("neuromod", "Neuromodulators", "active" if on else "readout",
            ("reach the scores through " + ", ".join(on)) if on else "the four traces are computed and logged; every gain is 0, so none reaches the scores")
        if bg.novelty_gain > 0 or bg.novelty_turn_gain > 0:
            add("novelty", "Novelty bit", "active", f"adds {bg.novelty_gain:g} to FORWARD and {bg.novelty_turn_gain:g} to each TURN when the observation changed")
        else:
            add("novelty", "Novelty bit", "readout", "computed and logged (it feeds ACh and NE); gains 0, so it moves no score")
        add("crit", "Criticality → vision", "active" if bg.criticality_gain > 0 else "readout",
            f"gain from κ scales vision × {bg.criticality_gain:g}" if bg.criticality_gain > 0 else "κ and avalanches are measured; the gain weight is 0, so vision is not scaled")
        if se.odometry_speed_noise > 0 or se.odometry_turn_noise > 0:
            add("odometry", "Odometry noise", "active", f"speed sd {se.odometry_speed_noise:g} (fraction), turn sd {se.odometry_turn_noise:g} rad per tick; moves the estimate, not the body")
        else:
            add("odometry", "Odometry noise", "off", "the self-motion estimate is exact")
        if sp.heading_source == "oracle":
            add("heading", "Heading estimate", "active", f"the declared heading oracle, sd {se.heading_oracle_noise:g} rad per tick (a declared limitation)")
        else:
            add("heading", "Heading estimate", "active", "integrated from the egomotion turns (a random walk under turn noise)")
        add("reset", "Wall-contact reset", "active" if sp.wall_reset else "off",
            "a touched wall resets the estimate's coordinate along its normal" if sp.wall_reset else "wall contacts offset the estimate and nothing corrects it")
        add("sensor_noise", "Sensor noise", "active" if se.noise > 0 else "off",
            f"sd {se.noise:g} on vision and pain" if se.noise > 0 else "vision and pain are exact")
        return out

    # ------------------------------------------------------------------ views

    def frame(self) -> Dict[str, Any]:
        eng = self.engine
        ctx = eng.context
        obs = ctx.observation if ctx else None
        sensors = eng.config.sensors
        sp = eng.spatial.state
        est_x, est_y, est_h = _to_world(sp.grid_x, sp.grid_y, sp.hd_angle)
        field = eng.criticality
        n_av = len(field.avalanche_sizes)
        rays = []
        if obs is not None:
            for ray in obs.vision_rays:
                rays.append([_r(ray.angle), _r(ray.dist * sensors.vision_range, 3), ray.obj_type or "none"])
        # The place whose value replay actually backed up this tick (the engine
        # records it: the TRN replay index is not a trajectory position).
        replay_cell = None
        if ctx and ctx.replay_active and ctx.replay_cell is not None:
            replay_cell = self._cell_center(*ctx.replay_cell)
        scores = ctx.action_scores if ctx else {}
        # The decision as its terms and the selection probabilities (decisions G39): the same arithmetic as
        # the engine's scores, recomputed from what it stored, so the panel can say what drove each score.
        bg = eng.config.basal_ganglia
        terms: Dict[str, Dict[str, float]] = {}
        probs: Dict[str, float] = {}
        probs_without_memory: Dict[str, float] = {}
        influence: Dict[str, float] = {}
        if ctx is not None and obs is not None and scores:
            pacing_rest = bg.pace_rest_bonus if ctx.pacing_active else 0.0
            raw = channel_terms(obs, ctx.wm_novelty, ctx.trn_gate_value, ctx.microsleep_active, bg, ctx.neuromodulators,
                                *ctx.value_signals, ctx.criticality_gain, ctx.freeze_habituation, pacing_rest,
                         ctx.previous_action, getattr(ctx, "motivation", 1.0))
            terms = {ch: {k: _r(v) for k, v in t.items()} for ch, t in raw.items()}
            exact = selection_probabilities(scores, bg.softmax_temperature)
            probs = {k: _r(v) for k, v in exact.items()}
            without_memory = counterfactual_probabilities(scores, raw, bg.softmax_temperature, ("memory",))
            probs_without_memory = {k: _r(v) for k, v in without_memory.items()}
            influence = {name: _r(total_variation(exact, counterfactual_probabilities(scores, raw, bg.softmax_temperature, (name,))))
                         for name in COUNTERFACTUAL_TERMS}
        goal_cell = None  # the goal-vector memory, in world coordinates (only with oracle homing on)
        goal = eng.goal_point() if eng.config.value_memory.oracle_homing else None
        if goal is not None:
            gx, gy, _ = _to_world(goal[0], goal[1], 0.0)
            goal_cell = [_r(gx, 3), _r(gy, 3)]
        return {
            "tick": self.tick,
            "agent": {
                "x": _r(eng.agent.pos[0], 3),
                "y": _r(eng.agent.pos[1], 3),
                "heading": _r(eng.agent.heading),
                "est_x": _r(est_x, 3),
                "est_y": _r(est_y, 3),
                "est_heading": _r(est_h),
            },
            "action": {
                "name": ctx.action_name if ctx else "REST",
                "scores": {k: _r(v) for k, v in scores.items()},
                "terms": terms,
                "probs": probs,
                # Counterfactuals (metrics.decisions): the selection without the memory term, and each term
                # family's immediate influence as the total-variation shift it makes to the probabilities.
                "probs_without_memory": probs_without_memory,
                "influence": influence,
                "temperature": _r(bg.softmax_temperature),
                "source": eng.config.value_memory.source,
                "value_gain": _r(bg.value_gain),
                "value": [_r(v) for v in (ctx.value_signals if ctx else (0.0, 0.0, 0.0))],
                "crit_gain": _r(ctx.criticality_gain if ctx else 1.0),
                "freeze": _r(ctx.freeze_habituation if ctx else 1.0),
                "cue_gate": _r(ctx.cue_gate if ctx else 1.0),
                "wall_gate": _r(ctx.wall_gate if ctx else 1.0),
                "steer": eng.config.basal_ganglia.value_steer,
                "goal_vector": bool(ctx and ctx.goal_vector_active),
            },
            "goal": goal_cell,
            "vision": {
                "rays": rays,
                "range": _r(sensors.vision_range, 3),
                "fov": _r(sensors.fov),
                "whiskers": list(obs.whisker_hits) if obs else [False, False],
                "pain": _r(obs.pain_signal if obs else 0.0),
            },
            "energy": {
                "atp": _r(ctx.atp if ctx else 0.0),
                "glycogen": _r(ctx.glycogen if ctx else 0.0),
                "glycogen_max": _r(eng.config.astrocyte.glycogen_max),
                "scale": _r(ctx.energy_scale if ctx else 1.0),
                "pacing": bool(ctx and ctx.pacing_active),
            },
            "trn": {"state": ctx.trn_state if ctx else "OPEN", "gate": _r(ctx.trn_gate_value if ctx else 1.0)},
            "microsleep": {"active": bool(ctx and ctx.microsleep_active), "remaining": ctx.microsleep_ticks_remaining if ctx else 0},
            "replay": {
                "active": bool(ctx and ctx.replay_active),
                "index": ctx.replay_index if ctx else -1,
                "cell": replay_cell,
                "back": ctx.replay_back if ctx else 0,
                "span": ctx.replay_span if ctx else 0,
            },
            # The latest finished replay events (brain.systems.replay_events.ReplayEvent.to_dict),
            # oldest first; a replay in progress is in "replay" above, not here.
            "replay_events": list(self.replay_events)[-FRAME_REPLAY_EVENTS:],
            "mod": {k: _r(v) for k, v in (ctx.neuromodulators if ctx else {}).items()},
            "reward": _r(ctx.reward if ctx else 0.0),
            "crit": {
                "kappa": _r(field.kappa),
                "active": len(field.active_cells),
                "avalanche": ctx.avalanche_size if ctx else 0,
                "gain": _r(ctx.criticality_gain if ctx else 1.0),
                "coupling": _r(field.config.coupling),
                "sigma": _r(4 * field.config.coupling),
                "regime": criticality_regime(field.kappa, n_av, field.config.kappa_min_avalanches),
                "n": n_av,
                "size": field.config.field_size,
                "cells": [list(c) for c in field.avalanche_cells],
                "front": [list(c) for c in field.active_cells],
            },
            "wm": {"load": ctx.wm_load if ctx else 0, "novelty": _r(ctx.wm_novelty if ctx else 0.0)},
            "place_id": ctx.place_id if ctx else 0,
            "world": {
                "bounds": [_r(b, 3) for b in eng.world.bounds],
                "objects": [{"x": _r(o.x, 3), "y": _r(o.y, 3), "r": _r(o.radius, 3), "kind": o.kind} for o in eng.world.objects],
                "pain_zone": _r(sensors.pain_zone, 3),
            },
            "profile": self.profile,
            "behaviour": self.behaviour(),
            # The place code (research profile; None without a population): the population's rates
            # at the estimate and the successor representation's value over the arena (docs/profiles.md).
            "place": self._place_frame(),
            "sr": self._sr_frame(),
            # The latest finished replay events as trails of the cells they backed up, in backup order.
            "replay_trails": self._replay_trails(),
            "status": self.scenario.status(),
        }

    # ------------------------------------------------------------ place code

    def place_info(self) -> Optional[Dict[str, Any]]:
        """The place population's grid, once per session: every cell centre in world coordinates; None without one."""
        pop = self.engine.place
        if pop is None:
            return None
        xs: List[float] = []
        ys: List[float] = []
        for cx, cy in zip(pop.cx.tolist(), pop.cy.tolist()):
            x, y, _ = _to_world(cx, cy, 0.0)
            xs.append(_r(x, 3))
            ys.append(_r(y, 3))
        return {"n": int(pop.size), "nx": int(pop.nx), "ny": int(pop.ny), "spacing": _r(pop.spacing, 3),
                "width": _r(pop.width, 3), "extent": [_r(e, 3) for e in pop.extent], "cx": xs, "cy": ys}

    def _place_frame(self) -> Optional[Dict[str, Any]]:
        eng = self.engine
        pop, rates = eng.place, eng.place_rates
        if pop is None or rates is None:
            return None
        dx, dy = pop.decode(rates)
        decoded = None
        if not (math.isnan(dx) or math.isnan(dy)):
            wx, wy, _ = _to_world(dx, dy, 0.0)
            decoded = [_r(wx, 3), _r(wy, 3)]
        peak = float(rates.max()) if rates.size else 0.0
        return {
            "rates": [_r(float(v), 3) for v in rates.tolist()],
            "max": _r(peak, 3),
            "active": int((rates > 0.5 * pop.max_rate).sum()),
            "decoded": decoded,  # the position the rates encode (world coordinates); None when undefined
        }

    def _sr_frame(self) -> Optional[Dict[str, Any]]:
        eng = self.engine
        if eng.sr is None or eng.place is None or eng.place_rates is None:
            return None
        import numpy as np
        from brain.systems.successor_features import normalised

        pop = eng.place
        if self._phi_centres is None:
            self._phi_centres = np.stack([normalised(pop.rates(float(cx), float(cy))) for cx, cy in zip(pop.cx, pop.cy)])
        u = (eng.sr.M * eng.sr_weights[:, None]).sum(axis=0)  # M^T R, element-wise as the engine computes it
        value = (self._phi_centres * u[None, :]).sum(axis=1)  # V = phi . M^T R at every cell centre
        phi = normalised(eng.place_rates)
        field = eng.sr.psi(phi)  # M phi: the successor features from here
        weights = eng.sr_weights
        return {
            "value": [_r(float(v), 4) for v in value.tolist()],
            "value_max": _r(float(np.abs(value).max()) if value.size else 0.0, 4),
            "field": [_r(float(v), 4) for v in field.tolist()],
            "field_max": _r(float(field.max()) if field.size else 0.0, 4),
            "weights": [_r(float(v), 4) for v in weights.tolist()],
            "weights_max": _r(float(np.abs(weights).max()) if weights.size else 0.0, 4),
            "here": _r(float((phi * u).sum()), 4),
            "updates": int(eng.sr.updates),
            "rule": eng.config.place.reward_rule,
            "discount": _r(eng.sr.gamma, 3),
        }

    def _replay_trails(self) -> List[Dict[str, Any]]:
        trails: List[Dict[str, Any]] = []
        for e in list(self.replay_events)[-FRAME_REPLAY_EVENTS:]:
            cells = e.get("cells") or []
            trails.append({
                "tick_start": e.get("tick_start"),
                "tick_end": e.get("tick_end"),
                "rule": e.get("rule"),
                "direction": e.get("direction"),
                "n": int(e.get("n_backups", len(cells))),
                "points": [self._cell_center(int(c[0]), int(c[1])) for c in cells],
            })
        return trails

    def _cell_center(self, bx: int, by: int) -> List[float]:
        size = self.engine.spatial.bin_size
        x, y, _ = _to_world((bx + 0.5) * size, (by + 0.5) * size, 0.0)
        return [_r(x, 3), _r(y, 3)]

    def value_map(self) -> Dict[str, Any]:
        size = self.engine.spatial.bin_size
        cells = []
        vmax = 0.0
        for (bx, by), v in self.engine.value_memory.values.items():
            if abs(v) < 1e-4:
                continue
            cx, cy = self._cell_center(bx, by)
            cells.append([cx, cy, _r(v)])
            vmax = max(vmax, abs(v))
        return {"cell": _r(size, 3), "cells": cells, "max": _r(vmax)}

    def avalanche_histogram(self) -> Dict[str, Any]:
        sizes = self.engine.criticality.avalanche_sizes
        n_cells = self.engine.criticality.config.field_size ** 2
        edges = [1]
        while edges[-1] <= n_cells:
            edges.append(edges[-1] * 2)
        counts = [0] * (len(edges) - 1)
        for s in sizes:
            for i in range(len(edges) - 1):
                if edges[i] <= s < edges[i + 1]:
                    counts[i] += 1
                    break
        total = len(sizes)
        density = [
            (c / ((edges[i + 1] - edges[i]) * total)) if total and c else 0.0 for i, c in enumerate(counts)
        ]
        return {"edges": edges, "counts": counts, "density": [_r(d, 6) for d in density], "n": total, "exponent": 1.5}

    # ---------------------------------------------------------------- params

    def _apply_param(self, key: str, value: Any) -> float:
        param = PARAM_INDEX.get(key)
        if param is None:
            raise ValueError(f"Unknown parameter: {key!r}")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Parameter {key!r} needs a number") from None
        if math.isnan(number) or math.isinf(number):
            raise ValueError(f"Parameter {key!r} needs a finite number")
        number = min(param.max, max(param.min, number))
        applied: float = int(round(number)) if param.integer else number
        if key == "sensors.heading_oracle_noise" and applied > 0.0 and not self.engine.config.sensors.heading_oracle:
            raise ValueError("Heading oracle noise needs the heading oracle, which the legacy profile has not: "
                             "switch the profile to Research")
        self.engine.config.set_field(key, applied)
        if key == "criticality.coupling":
            self.engine.criticality.reset_statistics()
        self.overrides[key] = applied
        return applied

    def set_param(self, key: str, value: Any) -> float:
        applied = self._apply_param(key, value)
        label = PARAM_INDEX[key].label
        note = " — κ re-measuring" if key == "criticality.coupling" else ""
        self._emit({"tick": self.tick, "text": f"Set {label} = {applied:g}{note}", "level": "info", "kind": "param"})
        return applied

    def params(self) -> List[Dict[str, Any]]:
        config = self.engine.config
        out = []
        for p in PARAMS:
            value = config.get_field(p.key)
            if p.key == "place.reward_unlearning_rate" and value is None:
                value = config.place.reward_learning_rate  # None means "the learning rate" (core.config.PlaceConfig)
            out.append({**asdict(p), "value": value})
        return out

    # --------------------------------------------------------------- actions

    def do_action(self, action_id: str) -> None:
        for event in self.scenario.do_action(self.engine, action_id, self.tick):
            self._emit(event)

    # ---------------------------------------------------------------- record

    def record(self, runs_dir: Path) -> str:
        """Save the session as a run directory the replay viewer can open; returns the run id.

        ``ticks.jsonl`` holds the history deque (the newest ``HISTORY_LIMIT``
        ticks). ``replay_events.jsonl`` holds the kept replay events
        (``REPLAY_EVENT_LIMIT``, the newest) that end inside those ticks, so
        the file never begins before the ticks it sits beside; the summary's
        ``n_replay_events`` counts the lines written and
        ``n_replay_events_total`` every event the session saw. No events file
        when there is nothing to write.
        """
        runs_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        tag = "" if self.profile == DEFAULT_PROFILE else f"_{self.profile}"
        base = f"live_{self.scenario_id}{tag}_s{self.seed}_{stamp}"
        run_id, n = base, 1
        while (runs_dir / run_id).exists():
            n += 1
            run_id = f"{base}-{n}"
        run_dir = runs_dir / run_id
        run_dir.mkdir()
        with open(run_dir / "ticks.jsonl", "w", encoding="utf-8") as fh:
            for row in self.history:
                fh.write(_canonical_json(row) + "\n")
        # The kept replay events that end inside the recorded ticks, as the
        # headless runner writes them; no file when there are none.
        first_tick = self.history[0]["tick"] if self.history else 0
        recorded_events = [e for e in self.replay_events if e["tick_end"] >= first_tick]
        n_written = 0
        if recorded_events:
            with open(run_dir / REPLAY_EVENTS_FILE, "w", encoding="utf-8") as fh:
                n_written = write_replay_events(fh, recorded_events)
        decision_lines = [line for tick, line in self.decisions if tick >= first_tick]
        with open(run_dir / DECISIONS_FILE, "w", encoding="utf-8") as fh:
            for line in decision_lines:
                fh.write(line + "\n")
        summary = {
            "protocol": self.scenario_id,
            "source": "live console",
            "seed": self.seed,
            "ticks_run": len(self.history),
            "schema_version": SCHEMA_VERSION,
            "params": dict(self.overrides),
            "profile": self.profile,
            "profile_overrides": [list(o) for o in self.profile_overrides],
            "status": self.scenario.status(),
            "n_replay_events": n_written,
            "n_replay_events_total": self.n_replay_events,
            "n_decision_records": len(decision_lines),
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
        # Objects as they stand now (a beacon shows its latest spot); the start
        # pose is the origin of the agent's path-integration frame.
        write_scene(self.engine, run_dir / "scene.json", {
            "start_pose": list(START_POSE),
            "scenario": self.scenario.describe(),
            "snapshot_tick": self.tick,
        })
        # Provenance (metrics.manifest): the config as it stands now, parameter
        # overrides included, since those are what ran. The replay viewer
        # ignores this file. A live session has no tick budget, so
        # ticks_requested is how far the session advanced; the history deque
        # may hold fewer rows than that (ticks_run is what was written).
        manifest = build_manifest(
            self.engine.config,
            protocol=self.scenario_id,
            seeds=[self.seed],
            ticks_requested=self.tick + 1,
            extra={
                "source": "live console",
                "params": dict(self.overrides),
                "profile_requested": self.profile,
                "profile_overrides": [list(o) for o in self.profile_overrides],
                "scenario": self.scenario.describe(),
                "timing_note": "wall_seconds is the time since the session was built, pauses included",
            },
        )
        finish_manifest(manifest, ticks_run=len(self.history), wall_seconds=time.monotonic() - self._built_at)
        write_manifest(run_dir / "manifest.json", manifest)
        self._emit({"tick": self.tick, "text": f"Recorded {len(self.history)} ticks as run '{run_id}'", "level": "good", "kind": "session"})
        return run_id


class SessionStore:
    """A small LRU of live sessions (the console is a single-user local tool)."""

    def __init__(self, limit: int = 6) -> None:
        self.limit = limit
        self._sessions: "OrderedDict[str, SimSession]" = OrderedDict()
        self._lock = threading.Lock()

    def create(self, scenario_id: str, seed: int, params: Optional[Dict[str, float]] = None,
               profile: str = DEFAULT_PROFILE) -> SimSession:
        session = SimSession(scenario_id, seed=seed, params=params, profile=profile)
        with self._lock:
            self._sessions[session.id] = session
            while len(self._sessions) > self.limit:
                self._sessions.popitem(last=False)
        return session

    def get(self, session_id: str) -> Optional[SimSession]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                self._sessions.move_to_end(session_id)
                session.touch()
            return session

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)


__all__ = ["SimSession", "SessionStore", "PARAMS", "PARAM_INDEX", "MAX_STEPS_PER_CALL", "criticality_regime"]
