"""The lab-console HTTP API: live simulation, replay endpoints and request hardening."""

import json

import pytest

from ui.server import create_app
from ui.sim_session import MAX_STEPS_PER_CALL


@pytest.fixture
def app(tmp_path):
    app = create_app(tmp_path / "runs")
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def post(client, url, body=None, **kw):
    return client.post(url, data=json.dumps(body or {}), content_type="application/json", **kw)


def test_index_and_static_assets_are_served(client):
    for path in ("/", "/replay", "/live"):
        rv = client.get(path)
        assert rv.status_code == 200 and b"<!doctype html>" in rv.data.lower()
    rv = client.get("/static/js/main.js")
    assert rv.status_code == 200
    assert rv.mimetype in ("application/javascript", "text/javascript")
    assert "default-src 'self'" in rv.headers["Content-Security-Policy"]


def test_meta_lists_scenarios_and_params(client):
    data = client.get("/api/meta").get_json()
    ids = {s["id"] for s in data["scenarios"]}
    assert {"open_field", "beacon", "foraging", "hazard_field", "memory_maze"} <= ids
    assert data["max_steps"] == MAX_STEPS_PER_CALL
    assert any(p["key"] == "criticality.coupling" for p in data["params"])


def test_live_session_lifecycle(client, tmp_path):
    rv = post(client, "/api/sim", {"scenario": "foraging", "seed": 5})
    assert rv.status_code == 201
    sim = rv.get_json()
    sid = sim["id"]
    assert sim["scenario"]["id"] == "foraging" and sim["seed"] == 5
    assert sim["frame"]["world"]["objects"]

    last_seq = sim["events"][-1]["seq"]
    step = post(client, f"/api/sim/{sid}/step", {"n": 40, "since": last_seq, "value_map": True, "histogram": True}).get_json()
    assert len(step["series"]) == 40
    assert step["frame"]["tick"] == step["series"][-1]["t"]
    assert "value_map" in step and "histogram" in step
    assert all(e["seq"] > last_seq for e in step["events"])

    param = post(client, f"/api/sim/{sid}/param", {"key": "sensors.fov", "value": 1.0}).get_json()
    assert param["value"] == 1.0
    assert any(p["key"] == "sensors.fov" and p["value"] == 1.0 for p in param["params"])

    reset = post(client, f"/api/sim/{sid}/reset", {"seed": 9}).get_json()
    assert reset["seed"] == 9 and reset["frame"]["tick"] == 0
    # Parameter overrides survive a reset.
    assert any(p["key"] == "sensors.fov" and p["value"] == 1.0 for p in reset["params"])

    post(client, f"/api/sim/{sid}/step", {"n": 25})
    rec = post(client, f"/api/sim/{sid}/record").get_json()
    run_id = rec["run_id"]
    assert (tmp_path / "runs" / run_id / "ticks.jsonl").exists()

    # The recording shows up in the replay API, with its scene and series.
    runs = client.get("/api/runs").get_json()["runs"]
    assert runs[0]["id"] == run_id and runs[0]["source"] == "live console"
    scene = client.get(f"/api/runs/{run_id}/default/{run_id}/scene").get_json()
    assert scene["scenario"]["id"] == "foraging"
    series = client.get(f"/api/runs/{run_id}/default/{run_id}/series").get_json()
    assert series["total"] == 26 and len(series["columns"]["x"]) == 26

    assert client.delete(f"/api/sim/{sid}").status_code == 204
    assert post(client, f"/api/sim/{sid}/step", {"n": 1}).status_code == 404


def test_scenario_actions(client):
    sid = post(client, "/api/sim", {"scenario": "memory_maze"}).get_json()["id"]
    rv = post(client, f"/api/sim/{sid}/action", {"action": "toggle_goal"})
    assert rv.status_code == 200
    assert rv.get_json()["frame"]["status"]["Goal"] == "hidden"
    rv = post(client, f"/api/sim/{sid}/action", {"action": "self_destruct"})
    assert rv.status_code == 400 and "Unknown action" in rv.get_json()["error"]


@pytest.mark.parametrize(
    "body",
    [
        {"scenario": "space_station"},
        {"scenario": "beacon", "seed": -1},
        {"scenario": "beacon", "seed": "lots"},
        {"scenario": "beacon", "seed": 1.5},
        {"scenario": "beacon", "params": {"astrocyte.atp": 1}},
        {"scenario": "beacon", "params": ["nope"]},
    ],
)
def test_create_rejects_bad_input(client, body):
    rv = post(client, "/api/sim", body)
    assert rv.status_code == 400
    assert rv.get_json()["error"]


def test_step_bounds_and_param_validation(client):
    sid = post(client, "/api/sim", {"scenario": "beacon"}).get_json()["id"]
    assert post(client, f"/api/sim/{sid}/step", {"n": MAX_STEPS_PER_CALL + 1}).status_code == 400
    assert post(client, f"/api/sim/{sid}/step", {"n": 0}).status_code == 400
    assert post(client, f"/api/sim/{sid}/param", {"key": "engine.seed", "value": 1}).status_code == 400
    assert post(client, f"/api/sim/{sid}/param", {"key": "sensors.fov", "value": "wide"}).status_code == 400


def test_posts_must_be_json(client):
    # A cross-site <form> can only send form/text bodies; those are refused.
    rv = client.post("/api/sim", data="scenario=beacon", content_type="application/x-www-form-urlencoded")
    assert rv.status_code == 400
    rv = client.post("/api/sim", data='{"scenario": "beacon"}', content_type="text/plain")
    assert rv.status_code == 400


def test_non_loopback_host_is_refused(app):
    client = app.test_client()
    rv = client.get("/api/meta", headers={"Host": "evil.example:8000"})
    assert rv.status_code == 403
    assert client.get("/api/meta", headers={"Host": "127.0.0.1:8000"}).status_code == 200
    assert client.get("/api/meta", headers={"Host": "[::1]:8000"}).status_code == 200


def test_host_check_can_be_disabled_for_lan_use(tmp_path):
    app = create_app(tmp_path, local_only=False)
    rv = app.test_client().get("/api/meta", headers={"Host": "rat-lab.local:8000"})
    assert rv.status_code == 200


def test_ticks_page_is_bounded_and_traversal_is_rejected(client, tmp_path):
    run = tmp_path / "runs" / "exp"
    run.mkdir(parents=True)
    (run / "ticks.jsonl").write_text("\n".join(json.dumps({"tick": i, "pos": [i, 0]}) for i in range(30)))
    rv = client.get("/api/runs/exp/default/exp/ticks?start=-5&limit=999999").get_json()
    assert rv["start"] == 0 and rv["limit"] == 5000 and rv["total"] == 30
    assert client.get("/api/runs/exp/default/exp/scene").status_code == 404
    assert client.get("/api/runs/..%2F..%2Fetc/episodes").status_code in (400, 404)


def test_series_decimates_long_runs(client, tmp_path, monkeypatch):
    import ui.server as server

    monkeypatch.setattr(server, "MAX_SERIES_POINTS", 10)
    run = tmp_path / "runs" / "long"
    run.mkdir(parents=True)
    (run / "ticks.jsonl").write_text("\n".join(json.dumps({"tick": i, "pos": [0, 0]}) for i in range(95)))
    data = client.get("/api/runs/long/default/long/series").get_json()
    assert data["total"] == 95 and data["stride"] == 10
    assert data["columns"]["t"][:3] == [0, 10, 20]
