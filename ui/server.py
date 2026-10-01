"""The Quantum Rat lab console: a local web app for the live simulator and the replay viewer.

``create_app()`` builds the Flask app. It serves:

* the single-page console from ``ui/static`` (no CDN, no build step);
* the **live API** under ``/api/sim``: start a scenario, step it, change
  parameters while it runs, trigger scenario actions, and record a session as a
  run;
* the **replay API** under ``/api/runs``: browse recorded runs, page through
  their ticks, and fetch a run's whole series for charts.

It is a single-user tool meant for ``localhost``. By default it refuses requests
whose ``Host`` is not a loopback name (blocking DNS-rebinding), and every POST
must be JSON (so another website cannot drive it with a plain form post).
Start it with ``python -m ui``.
"""

from __future__ import annotations

import json
import math
import mimetypes
from collections import OrderedDict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, Flask, abort, current_app, jsonify, request, send_from_directory

from metrics.schema import SCHEMA_VERSION
from ui.replay_index import get_run_root, get_safe_path, read_jsonl_paged
from ui.scenarios import SCENARIOS, list_scenarios
from ui.sim_session import MAX_STEPS_PER_CALL, PARAMS, SessionStore, SimSession

# Some platforms map .js to text/plain, which browsers refuse for ES modules.
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

STATIC_DIR = Path(__file__).resolve().parent / "static"
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
MAX_SEED = 2**31 - 1
MAX_TICKS_PAGE = 5000
MAX_SERIES_POINTS = 20000
SERIES_CACHE_LIMIT = 8

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'none'; form-action 'none'"
)


class BadRequest(ValueError):
    """Client error that becomes a JSON 400."""


# --------------------------------------------------------------------- helpers


def _host_name(host: str) -> str:
    """Strip the port (and IPv6 brackets) from a Host header value."""
    host = host.strip().lower()
    if host.startswith("["):
        return host[1:].split("]", 1)[0]
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def _json_body() -> Dict[str, Any]:
    if not request.is_json:
        raise BadRequest("Send a JSON body (Content-Type: application/json)")
    body = request.get_json(silent=True)
    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise BadRequest("The JSON body must be an object")
    return body


def _int_field(body: Dict[str, Any], key: str, default: int, lo: int, hi: int) -> int:
    value = body.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BadRequest(f"'{key}' must be a number")
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value) or value != int(value)):
        raise BadRequest(f"'{key}' must be a whole number")
    value = int(value)
    if not lo <= value <= hi:
        raise BadRequest(f"'{key}' must be between {lo} and {hi}")
    return value


def _runs_root() -> Path:
    configured = current_app.config.get("RUNS_DIR")
    return Path(configured).resolve() if configured else get_run_root()


def _safe(run_id: str, *parts: str) -> Path:
    try:
        return get_safe_path(run_id, *parts, root=_runs_root())
    except ValueError as exc:
        raise BadRequest(str(exc)) from None


def _episode_file(run_id: str, agent_id: str, protocol_id: str, name: str) -> Path:
    if agent_id == "default":
        return _safe(run_id, name)
    return _safe(run_id, "agents", agent_id, protocol_id, name)


def _sessions() -> SessionStore:
    return current_app.extensions["quantum_rat_sessions"]


def _session(session_id: str) -> SimSession:
    session = _sessions().get(session_id)
    if session is None:
        abort(404, description="No such simulation (it may have expired); start a new one")
    return session


def _session_payload(session: SimSession) -> Dict[str, Any]:
    """Everything the console needs to (re)draw a session from scratch."""
    return {
        "id": session.id,
        "seed": session.seed,
        "scenario": session.scenario.describe(),
        "params": session.params(),
        "frame": session.frame(),
        "value_map": session.value_map(),
        "histogram": session.avalanche_histogram(),
        "events": list(session.events),
        "series": [],
    }


# ------------------------------------------------------------------- live API

live = Blueprint("live", __name__)


@live.get("/api/meta")
def meta():
    return jsonify(
        {
            "scenarios": list_scenarios(),
            "params": [asdict(p) for p in PARAMS],
            "max_steps": MAX_STEPS_PER_CALL,
            "schema_version": SCHEMA_VERSION,
            "default_seed": 1337,
        }
    )


@live.post("/api/sim")
def create_sim():
    body = _json_body()
    scenario_id = body.get("scenario", "open_field")
    if scenario_id not in SCENARIOS:
        raise BadRequest(f"Unknown scenario: {scenario_id!r}")
    seed = _int_field(body, "seed", 1337, 0, MAX_SEED)
    params = body.get("params") or {}
    if not isinstance(params, dict):
        raise BadRequest("'params' must be an object")
    try:
        session = _sessions().create(scenario_id, seed, params)
    except ValueError as exc:
        raise BadRequest(str(exc)) from None
    with session.lock:
        return jsonify(_session_payload(session)), 201


@live.post("/api/sim/<session_id>/step")
def step_sim(session_id: str):
    session = _session(session_id)
    body = _json_body()
    n = _int_field(body, "n", 1, 1, MAX_STEPS_PER_CALL)
    since = _int_field(body, "since", 0, 0, 2**53)
    with session.lock:
        series = session.step(n)
        payload: Dict[str, Any] = {
            "series": series,
            "frame": session.frame(),
            "events": session.events_since(since),
        }
        if body.get("value_map"):
            payload["value_map"] = session.value_map()
        if body.get("histogram"):
            payload["histogram"] = session.avalanche_histogram()
    return jsonify(payload)


@live.post("/api/sim/<session_id>/reset")
def reset_sim(session_id: str):
    session = _session(session_id)
    body = _json_body()
    with session.lock:
        seed = _int_field(body, "seed", session.seed, 0, MAX_SEED)
        session.reset(seed)
        return jsonify(_session_payload(session))


@live.post("/api/sim/<session_id>/param")
def set_param(session_id: str):
    session = _session(session_id)
    body = _json_body()
    key = body.get("key")
    if not isinstance(key, str):
        raise BadRequest("'key' must be a parameter name")
    since = _int_field(body, "since", 0, 0, 2**53)
    with session.lock:
        try:
            applied = session.set_param(key, body.get("value"))
        except ValueError as exc:
            raise BadRequest(str(exc)) from None
        return jsonify(
            {
                "key": key,
                "value": applied,
                "params": session.params(),
                "frame": session.frame(),
                "events": session.events_since(since),
            }
        )


@live.post("/api/sim/<session_id>/action")
def scenario_action(session_id: str):
    session = _session(session_id)
    body = _json_body()
    action_id = body.get("action")
    if not isinstance(action_id, str):
        raise BadRequest("'action' must be an action id")
    since = _int_field(body, "since", 0, 0, 2**53)
    with session.lock:
        try:
            session.do_action(action_id)
        except ValueError as exc:
            raise BadRequest(str(exc)) from None
        return jsonify(
            {
                "frame": session.frame(),
                "value_map": session.value_map(),
                "events": session.events_since(since),
            }
        )


@live.post("/api/sim/<session_id>/record")
def record_sim(session_id: str):
    session = _session(session_id)
    body = _json_body()
    since = _int_field(body, "since", 0, 0, 2**53)
    with session.lock:
        run_id = session.record(_runs_root())
        return jsonify({"run_id": run_id, "events": session.events_since(since)})


@live.delete("/api/sim/<session_id>")
def delete_sim(session_id: str):
    _sessions().delete(session_id)
    return ("", 204)


# ----------------------------------------------------------------- replay API

replay = Blueprint("replay", __name__)


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


@replay.get("/api/runs")
def list_runs():
    """Recorded runs, newest first: experiment runs and tournament runs."""
    run_root = _runs_root()
    if not run_root.exists():
        return jsonify({"runs": [], "root": str(run_root), "error": f"Run directory not found: {run_root}"})

    runs: List[Dict[str, Any]] = []
    for run_dir in run_root.iterdir():
        if not run_dir.is_dir():
            continue
        if (run_dir / "ticks.jsonl").exists():
            entry: Dict[str, Any] = {"id": run_dir.name, "type": "experiment"}
            summary = _read_json(run_dir / "summary.json") or {}
            for key in ("protocol", "seed", "ticks_run", "source"):
                if key in summary:
                    entry[key] = summary[key]
        elif (run_dir / "agents").exists():
            entry = {"id": run_dir.name, "type": "tournament"}
        else:
            continue
        entry["modified"] = run_dir.stat().st_mtime
        runs.append(entry)
    runs.sort(key=lambda r: (-r["modified"], r["id"]))
    return jsonify({"runs": runs, "root": str(run_root)})


@replay.get("/api/runs/<run_id>/episodes")
def list_episodes(run_id: str):
    """Episodes in a run: one ("default") for an experiment, one per agent/protocol for a tournament."""
    run_path = _safe(run_id)
    if not run_path.exists():
        abort(404, description="Run not found")

    episodes = []
    if (run_path / "ticks.jsonl").exists():
        episodes.append({"episode_id": "default", "agent_id": "default", "protocol": run_id})
    elif (run_path / "agents").exists():
        for agent_dir in sorted((run_path / "agents").iterdir()):
            if not agent_dir.is_dir():
                continue
            for protocol_dir in sorted(agent_dir.iterdir()):
                if protocol_dir.is_dir() and (protocol_dir / "summary.json").exists():
                    episodes.append(
                        {
                            "episode_id": f"{agent_dir.name}/{protocol_dir.name}",
                            "agent_id": agent_dir.name,
                            "protocol": protocol_dir.name,
                            "has_ticks": (protocol_dir / "ticks.jsonl").exists(),
                        }
                    )
    return jsonify({"episodes": episodes})


@replay.get("/api/runs/<run_id>/<agent_id>/<protocol_id>/summary")
def get_summary(run_id: str, agent_id: str, protocol_id: str):
    path = _episode_file(run_id, agent_id, protocol_id, "summary.json")
    if not path.exists():
        abort(404, description="Summary not found")
    data = _read_json(path)
    if data is None:
        abort(422, description="Summary is not a JSON object")
    return jsonify(data)


@replay.get("/api/runs/<run_id>/<agent_id>/<protocol_id>/scene")
def get_scene(run_id: str, agent_id: str, protocol_id: str):
    path = _episode_file(run_id, agent_id, protocol_id, "scene.json")
    if not path.exists():
        abort(404, description="This run has no scene.json (recorded before scenes were saved)")
    data = _read_json(path)
    if data is None:
        abort(422, description="Scene is not a JSON object")
    return jsonify(data)


@replay.get("/api/runs/<run_id>/<agent_id>/<protocol_id>/ticks")
def get_ticks(run_id: str, agent_id: str, protocol_id: str):
    start = max(0, request.args.get("start", 0, type=int))
    limit = min(MAX_TICKS_PAGE, max(1, request.args.get("limit", 500, type=int)))
    path = _episode_file(run_id, agent_id, protocol_id, "ticks.jsonl")
    if not path.exists():
        abort(404, description="Ticks file not found")
    ticks, total = read_jsonl_paged(path, start, limit)
    return jsonify({"start": start, "limit": limit, "total": total, "ticks": ticks})


# Columns of the whole-run series: (column name, tick-row extractor).
SERIES_COLUMNS: Tuple[Tuple[str, Any], ...] = (
    ("t", lambda r: r.get("tick", 0)),
    ("x", lambda r: round(float((r.get("pos") or (0, 0))[0]), 3)),
    ("y", lambda r: round(float((r.get("pos") or (0, 0))[1]), 3)),
    ("hd", lambda r: round(float(r.get("hd_angle", 0.0)), 4)),
    ("gx", lambda r: round(float(r.get("grid_x", 0.0)), 3)),
    ("gy", lambda r: round(float(r.get("grid_y", 0.0)), 3)),
    ("k", lambda r: round(float(r.get("kappa", 0.0)), 4)),
    ("av", lambda r: int(r.get("avalanche_size", 0))),
    ("act", lambda r: int(r.get("criticality_active", 0))),
    ("atp", lambda r: round(float(r.get("atp", 0.0)), 4)),
    ("gly", lambda r: round(float(r.get("glycogen", 0.0)), 4)),
    ("r", lambda r: round(float(r.get("reward", 0.0)), 4)),
    ("da", lambda r: round(float((r.get("neuromodulators") or {}).get("DA", 0.0)), 4)),
    ("ne", lambda r: round(float((r.get("neuromodulators") or {}).get("NE", 0.0)), 4)),
    ("ach", lambda r: round(float((r.get("neuromodulators") or {}).get("ACh", 0.0)), 4)),
    ("ht", lambda r: round(float((r.get("neuromodulators") or {}).get("5HT", 0.0)), 4)),
    ("pain", lambda r: round(float(r.get("obs_pain", 0.0)), 4)),
    ("trn", lambda r: str(r.get("trn_state", "OPEN"))),
    ("ms", lambda r: int(bool(r.get("microsleep_active", False)))),
    ("rp", lambda r: int(bool(r.get("replay_active", False)))),
    ("a", lambda r: str(r.get("action_name", ""))),
    ("score", lambda r: r.get("score", 0)),
)


_SERIES_CACHE: "OrderedDict[Tuple[str, int, int], Dict[str, Any]]" = OrderedDict()


def _load_series(path: Path) -> Dict[str, Any]:
    """The whole run as columns (decimated to at most MAX_SERIES_POINTS rows)."""
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key in _SERIES_CACHE:
        _SERIES_CACHE.move_to_end(key)
        return _SERIES_CACHE[key]

    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    total = len(rows)
    stride = max(1, math.ceil(total / MAX_SERIES_POINTS))
    kept = rows[::stride]
    columns = {}
    for name, get in SERIES_COLUMNS:
        try:
            columns[name] = [get(r) for r in kept]
        except (TypeError, ValueError, IndexError):
            columns[name] = []
    result = {"total": total, "stride": stride, "columns": columns}

    _SERIES_CACHE[key] = result
    while len(_SERIES_CACHE) > SERIES_CACHE_LIMIT:
        _SERIES_CACHE.popitem(last=False)
    return result


@replay.get("/api/runs/<run_id>/<agent_id>/<protocol_id>/series")
def get_series(run_id: str, agent_id: str, protocol_id: str):
    path = _episode_file(run_id, agent_id, protocol_id, "ticks.jsonl")
    if not path.exists():
        abort(404, description="Ticks file not found")
    try:
        return jsonify(_load_series(path))
    except ValueError:
        abort(422, description="The ticks file contains a line that is not JSON")


# ------------------------------------------------------------------- the app


def create_app(runs_dir: Optional[str | Path] = None, *, local_only: bool = True) -> Flask:
    """Build the console app.

    ``runs_dir``: where recorded runs live. If omitted, ``$CRITICAL_RAT_RUNS_DIR``
    (default ``runs``) is read on each request.
    ``local_only``: reject requests whose Host header is not a loopback name.
    """
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    app.config.update(
        RUNS_DIR=str(Path(runs_dir).resolve()) if runs_dir else None,
        LOCAL_ONLY=local_only,
        MAX_CONTENT_LENGTH=64 * 1024,
        SEND_FILE_MAX_AGE_DEFAULT=0,
    )
    app.json.sort_keys = False
    app.extensions["quantum_rat_sessions"] = SessionStore()

    @app.before_request
    def _guard_host():
        if app.config["LOCAL_ONLY"] and _host_name(request.host) not in LOOPBACK_HOSTS:
            abort(403, description="This console only answers on localhost (start it with --host to change that)")

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.errorhandler(BadRequest)
    def _bad_request(exc: BadRequest):
        return jsonify({"error": str(exc)}), 400

    for code in (400, 403, 404, 405, 413, 415, 422):

        @app.errorhandler(code)
        def _http_error(exc, code=code):
            if request.path.startswith("/api/"):
                return jsonify({"error": getattr(exc, "description", str(exc))}), code
            return exc

    @app.get("/")
    @app.get("/replay")
    @app.get("/live")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    app.register_blueprint(live)
    app.register_blueprint(replay)
    return app


__all__ = ["create_app", "STATIC_DIR"]
