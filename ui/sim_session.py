"""Live simulation sessions for the lab console.

A ``SimSession`` owns one engine running one scenario. It advances the engine
on request and turns engine state into compact, JSON-serialisable views:

* ``step(n)``      -> a per-tick series (for charts and the trail) + new events
* ``frame()``      -> the full display state of the latest tick
* ``value_map()``  -> the learned place-value map in world coordinates
* ``avalanche_histogram()`` -> the avalanche-size distribution (log bins)
* ``params()`` / ``set_param()`` -> whitelisted live parameters
* ``record(dir)``  -> save the session as a run the replay viewer can open

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

from core.engine import Engine
from metrics.logger import _canonical_json
from metrics.scene import write_scene
from metrics.schema import SCHEMA_VERSION
from ui.scenarios import START_POSE, Scenario, make_scenario

Event = Dict[str, Any]

MAX_STEPS_PER_CALL = 200
HISTORY_LIMIT = 50_000
EVENT_LIMIT = 300
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
    def __init__(self, scenario_id: str, seed: int = 1337, params: Optional[Dict[str, float]] = None) -> None:
        self.id = secrets.token_hex(8)
        self.scenario_id = scenario_id
        self.seed = int(seed)
        self.lock = threading.RLock()
        self.last_access = time.monotonic()
        self.overrides: Dict[str, float] = {}
        self._build(dict(params or {}))

    # ---------------------------------------------------------------- lifecycle

    def _build(self, params: Dict[str, float]) -> None:
        self.scenario: Scenario = make_scenario(self.scenario_id)
        self.engine = Engine(seed=self.seed, config=self.scenario.config())
        self.scenario.setup(self.engine)
        self.overrides = {}
        for key, value in params.items():
            self._apply_param(key, value)
        self.history: Deque[Dict[str, Any]] = deque(maxlen=HISTORY_LIMIT)
        self.events: Deque[Event] = deque(maxlen=EVENT_LIMIT)
        self._seq = 0
        self._prev_microsleep = False
        self._regime: Optional[str] = None
        self._regime_tick = -REGIME_EVENT_GAP
        self._gate = "OPEN"
        self._gate_tick = -GATE_EVENT_GAP
        self.tick = -1
        self._emit({"tick": 0, "text": f"{self.scenario.title} started (seed {self.seed})", "level": "info", "kind": "session"})
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
        for event in self.scenario.on_tick(self.engine, td.tick) + self._generic_events(td.tick):
            self._emit(event)
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
        goal_cell = None  # the goal-vector memory, in world coordinates (only when that memory is on)
        goal = eng.goal_point() if eng.config.value_memory.goal_vector else None
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
            "status": self.scenario.status(),
        }

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

    def _target(self, key: str) -> Tuple[Any, str]:
        obj: Any = self.engine.config
        parts = key.split(".")
        for part in parts[:-1]:
            obj = getattr(obj, part)
        return obj, parts[-1]

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
        obj, attr = self._target(key)
        setattr(obj, attr, applied)
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
        out = []
        for p in PARAMS:
            obj, attr = self._target(p.key)
            out.append({**asdict(p), "value": getattr(obj, attr)})
        return out

    # --------------------------------------------------------------- actions

    def do_action(self, action_id: str) -> None:
        for event in self.scenario.do_action(self.engine, action_id, self.tick):
            self._emit(event)

    # ---------------------------------------------------------------- record

    def record(self, runs_dir: Path) -> str:
        runs_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = f"live_{self.scenario_id}_s{self.seed}_{stamp}"
        run_id, n = base, 1
        while (runs_dir / run_id).exists():
            n += 1
            run_id = f"{base}-{n}"
        run_dir = runs_dir / run_id
        run_dir.mkdir()
        with open(run_dir / "ticks.jsonl", "w", encoding="utf-8") as fh:
            for row in self.history:
                fh.write(_canonical_json(row) + "\n")
        summary = {
            "protocol": self.scenario_id,
            "source": "live console",
            "seed": self.seed,
            "ticks_run": len(self.history),
            "schema_version": SCHEMA_VERSION,
            "params": dict(self.overrides),
            "status": self.scenario.status(),
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
        # Objects as they stand now (a beacon shows its latest spot); the start
        # pose is the origin of the agent's path-integration frame.
        write_scene(self.engine, run_dir / "scene.json", {
            "start_pose": list(START_POSE),
            "scenario": self.scenario.describe(),
            "snapshot_tick": self.tick,
        })
        self._emit({"tick": self.tick, "text": f"Recorded {len(self.history)} ticks as run '{run_id}'", "level": "good", "kind": "session"})
        return run_id


class SessionStore:
    """A small LRU of live sessions (the console is a single-user local tool)."""

    def __init__(self, limit: int = 6) -> None:
        self.limit = limit
        self._sessions: "OrderedDict[str, SimSession]" = OrderedDict()
        self._lock = threading.Lock()

    def create(self, scenario_id: str, seed: int, params: Optional[Dict[str, float]] = None) -> SimSession:
        session = SimSession(scenario_id, seed=seed, params=params)
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
