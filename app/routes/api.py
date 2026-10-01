from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from flask import current_app, jsonify, request

from app.routes import bp
from core.engine import Engine
from metrics.hash import RunHash, tick_hash
from core.determinism import BASELINE_PATH, DEFAULT_TICKS, generate_trace


class EngineState:
    """Wrapper to hold engine and history for API responses."""

    def __init__(self, seed: int = 1337) -> None:
        self.engine = Engine(seed=seed)
        self.history: List[Dict[str, Any]] = []
        self.pheromones: List[List[float]] = []
        self.map_size = 10

    def step(self, batch_size: int) -> Dict[str, Any]:
        ticks = self.engine.run(batch_size)
        self.history.extend(ticks)
        last = ticks[-1]
        return serialize_tick(last, pheromones=self.pheromones, map_size=self.map_size)


state: EngineState | None = None


def init_state(seed: int = 1337) -> None:
    global state
    state = EngineState(seed=seed)


def _load_baseline_hashes() -> List[Dict[str, Any]]:
    if not BASELINE_PATH.exists():
        return []
    return json.loads(BASELINE_PATH.read_text())


def serialize_tick(tick, *, pheromones: List[List[float]], map_size: int) -> Dict[str, Any]:
    neuromod = tick.neuromodulators or {}
    return {
        "rat": list(tick.pos),
        "walls": [],
        "targets": [],
        "predator": [0.0, 0.0],
        "brain": {"soma": [], "theta": [], "grid": [], "hd": []},
        "cerebellum": {"predicted_pos": [0.0, 0.0], "correction_vector": [0.0, 0.0]},
        "stats": {
            "frustration": 0.0,
            "score": tick.score,
            "status": "AWAKE",
            "energy": tick.glycogen,
            "atp": tick.atp,
            "deaths": 0,
            "generation": 0,
            "dopamine": neuromod.get("DA", 0.0),
            "dopamine_tonic": neuromod.get("DA", 0.0),
            "dopamine_phasic": 0.0,
            "serotonin": neuromod.get("5HT", 0.0),
            "norepinephrine": neuromod.get("NE", 0.0),
            "ne_phasic": 0.0,
            "ne_uncertainty": 0.0,
            "ne_mode": "BALANCED",
            "lc_mode": "BALANCED",
            "ach_tonic": neuromod.get("ACh", 0.0),
            "ach_mode": "BALANCED",
            "ach_precision_gain": 0.0,
            "boredom": 0.0,
            "panic": 0.0,
            "cortisol": 0.0,
            "mode": "SAFE",
            "place_nav_mag": 0.0,
            "mt_theta_readouts": {},
            "mt_soma_readouts": {},
            "mt_plasticity_mult": 0.0,
            "mt_gate_thr": 0.0,
            "map_size": map_size,
            "trn_modes": [],
            "wm": {
                "slots": 0,
                "write_threshold": 0.0,
                "decay_rate": 0.0,
                "motor_gain": 0.0,
                "bias_vec": [],
                "slot_strengths": [],
            },
            "pp": {"pe_norm": 0.0, "pe_ema": 0.0, "yhat_next": [0.0] * 6},
        },
        "pheromones": pheromones,
        "whiskers": {"angle": 0.0, "hits": [False, False]},
        "vision": [],
        "tournament_status": "",
    }


@bp.route("/", methods=["GET"])
def index() -> Any:
    return jsonify({"status": "ok"})


@bp.route("/step", methods=["POST"])
def step() -> Any:
    assert state is not None, "Engine state not initialized"
    req = request.get_json(silent=True) or {}
    batch_size = int(req.get("batch_size", 1))
    batch_size = max(1, min(batch_size, 100))
    payload = state.step(batch_size)
    return jsonify(payload)


@bp.route("/reset", methods=["POST"])
def reset() -> Any:
    assert state is not None, "Engine state not initialized"
    seed = request.get_json(silent=True) or {}
    new_seed = int(seed.get("seed", 1337))
    init_state(seed=new_seed)
    return jsonify({"status": "reset", "seed": new_seed})


@bp.route("/history", methods=["GET"])
def history() -> Any:
    assert state is not None, "Engine state not initialized"
    return jsonify([serialize_tick(t, pheromones=state.pheromones, map_size=state.map_size) for t in state.history])


@bp.route("/config", methods=["POST"])
def config() -> Any:
    # Config is accepted for parity but stored minimally.
    return jsonify({"status": "ok"})


@bp.route("/tournament/start", methods=["POST"])
def tournament_start() -> Any:
    return jsonify({"status": "started", "tournament_status": "STARTED"})


@bp.route("/lab/start", methods=["POST"])
def lab_start() -> Any:
    return jsonify({"status": "started", "test": "open_field", "walls": []})


@bp.route("/lab/stop", methods=["POST"])
def lab_stop() -> Any:
    return jsonify({"status": "stopped"})


@bp.route("/lab/results", methods=["GET"])
def lab_results() -> Any:
    return jsonify({"active": False, "protocol": None, "data_points": 0, "data": []})


@bp.route("/maps/list", methods=["GET"])
def maps_list() -> Any:
    return jsonify([])


@bp.route("/maps/save", methods=["POST"])
def maps_save() -> Any:
    return jsonify({"status": "saved"})


@bp.route("/maps/load", methods=["POST"])
def maps_load() -> Any:
    return jsonify({"status": "loaded", "walls": []})


@bp.route("/determinism_check", methods=["POST"])
def determinism_check() -> Any:
    baseline = _load_baseline_hashes()
    trace = generate_trace(seed=1337, ticks=DEFAULT_TICKS)
    run_hash = RunHash()
    hashes = []
    for tick in trace:
        digest = run_hash.update(tick)
        hashes.append({"tick": tick.tick, "hash": digest})
    hashes.append({"tick": "run", "hash": run_hash.hexdigest()})

    baseline_hash = baseline[-1]["hash"] if baseline else None
    match = baseline == hashes if baseline else False
    return jsonify(
        {
            "match": match,
            "baseline_hash": baseline_hash,
            "run_hash": run_hash.hexdigest(),
            "ticks": DEFAULT_TICKS,
        }
    )
