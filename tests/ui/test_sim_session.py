"""The live-console backend: scenarios, sessions, params, events and recording."""

import json
import math

import pytest

from ui.scenarios import SCENARIOS, list_scenarios
from ui.sim_session import MAX_STEPS_PER_CALL, PARAMS, SessionStore, SimSession

FRAME_KEYS = {
    "tick", "agent", "action", "vision", "energy", "trn", "microsleep", "replay",
    "mod", "reward", "crit", "wm", "place_id", "world", "status",
}


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_every_scenario_runs_and_serialises(scenario_id):
    session = SimSession(scenario_id, seed=7)
    series = session.step(50)
    assert len(series) == 50
    assert series[-1]["t"] == session.tick
    frame = session.frame()
    assert FRAME_KEYS <= set(frame)
    # Everything the browser receives must be plain JSON.
    json.dumps(frame)
    json.dumps(session.value_map())
    json.dumps(session.avalanche_histogram())
    json.dumps(series)


def test_scenario_listing_describes_each_scenario():
    listed = {s["id"]: s for s in list_scenarios()}
    assert set(listed) == set(SCENARIOS)
    for item in listed.values():
        assert item["title"] and item["summary"] and item["watch"]


def test_step_is_capped():
    session = SimSession("open_field")
    assert len(session.step(10_000)) == MAX_STEPS_PER_CALL


def test_same_seed_gives_identical_series():
    a = SimSession("foraging", seed=11).step(120)
    b = SimSession("foraging", seed=11).step(120)
    assert a == b


def test_params_are_whitelisted_clamped_and_live():
    session = SimSession("beacon")
    assert session.set_param("basal_ganglia.vision_gain", 99) == 1.5  # clamped to max
    assert session.engine.config.basal_ganglia.vision_gain == 1.5
    assert session.set_param("sensors.vision_rays", 4.6) == 5  # integer param rounds
    with pytest.raises(ValueError):
        session.set_param("astrocyte.atp", 1.0)  # not whitelisted
    with pytest.raises(ValueError):
        session.set_param("basal_ganglia.vision_gain", "lots")
    with pytest.raises(ValueError):
        session.set_param("basal_ganglia.vision_gain", math.nan)
    keys = {p["key"] for p in session.params()}
    assert keys == {p.key for p in PARAMS}


def test_steering_robustness_params_are_live():
    by_key = {p.key: p for p in PARAMS}
    expected = {
        "basal_ganglia.value_gain": ("Action selection", 0.0, 3.0, 0.1),
        "basal_ganglia.cue_gate_gain": ("Action selection", 0.0, 4.0, 0.1),
        "basal_ganglia.wall_gate_gain": ("Action selection", 0.0, 4.0, 0.1),
        "value_memory.dwell_extinction": ("Memory", 0.0, 0.1, 0.005),
        "basal_ganglia.pace_rest_bonus": ("Energy", 0.0, 8.0, 0.5),
    }
    for key, (group, lo, hi, step) in expected.items():
        p = by_key[key]
        assert (p.group, p.min, p.max, p.step) == (group, lo, hi, step)
    session = SimSession("foraging")
    values = {p["key"]: p["value"] for p in session.params()}
    assert values["basal_ganglia.pace_rest_bonus"] == 5.0  # scenario default: pacing on
    assert values["basal_ganglia.cue_gate_gain"] == 2.0
    assert values["basal_ganglia.wall_gate_gain"] == 1.0
    assert values["value_memory.dwell_extinction"] == 0.02
    assert session.set_param("basal_ganglia.pace_rest_bonus", 20) == 8.0
    assert session.set_param("value_memory.dwell_extinction", 0.0) == 0.0
    # The engine passes the config's extinction to the value map on every call,
    # so the param applies from the next tick on.
    seen = []
    record = session.engine.value_memory.record
    session.engine.value_memory.record = lambda cell, reward, dwell_extinction=None: (
        seen.append(dwell_extinction), record(cell, reward, dwell_extinction))[1]
    session.step(1)
    assert seen == [0.0]
    assert SimSession("open_field").params()[[p.key for p in PARAMS].index("basal_ganglia.pace_rest_bonus")]["value"] == 0.0


def test_frame_reports_pacing_freeze_and_cue_gate():
    session = SimSession("hazard_field")
    frame = session.frame()
    assert isinstance(frame["energy"]["pacing"], bool)
    assert 0.0 <= frame["action"]["freeze"] <= 1.0
    assert 0.0 <= frame["action"]["cue_gate"] <= 1.0
    assert 0.0 <= frame["action"]["wall_gate"] <= 1.0
    assert frame["action"]["steer"] == "split"
    seen = {"pacing": False, "freeze": False, "cue": False, "wall": False}
    for _ in range(1500):
        session.step(1)
        f = session.frame()
        seen["pacing"] |= f["energy"]["pacing"]
        seen["freeze"] |= f["action"]["freeze"] < 1.0
        seen["cue"] |= f["action"]["cue_gate"] < 1.0
        seen["wall"] |= f["action"]["wall_gate"] < 1.0
    assert seen == {"pacing": True, "freeze": True, "cue": True, "wall": True}


def test_changing_coupling_restarts_kappa_measurement():
    session = SimSession("open_field")
    session.step(200)
    assert len(session.engine.criticality.avalanche_sizes) > 0
    session.set_param("criticality.coupling", 0.4)
    assert session.engine.criticality.avalanche_sizes == ()
    assert session.frame()["crit"]["regime"] == "measuring"


def test_foraging_collects_food_and_emits_events():
    session = SimSession("foraging")
    session.step(200)
    session.step(200)
    status = session.frame()["status"]
    left = int(status["Food left in patch"].split("/")[0])
    assert left < 5 or status["Patches cleared"] >= 1
    assert any(e["kind"] == "scenario" and "Collected" in e["text"] for e in session.events)


def test_memory_maze_recalls_hidden_goal_repeatedly_with_rest():
    session = SimSession("memory_maze")
    while session.tick < 900 and session.scenario.trial <= 8:
        session.step(50)
    hidden = [t for t in session.scenario.history if not t["visible"]]
    assert len(hidden) >= 5
    assert all(t["reached"] for t in hidden)


def test_memory_maze_actions():
    session = SimSession("memory_maze")
    session.do_action("toggle_replay")
    assert session.scenario.replay_enabled is False
    session.do_action("toggle_goal")
    assert session.frame()["status"]["Goal"] == "hidden"
    with pytest.raises(ValueError):
        session.do_action("launch_rockets")


def test_events_since_returns_only_new_events():
    session = SimSession("beacon")
    seq = session.events[-1]["seq"]
    session.set_param("basal_ganglia.vision_gain", 0.5)
    new = session.events_since(seq)
    assert len(new) == 1 and "Vision drive" in new[0]["text"]


def test_record_writes_a_replayable_run(tmp_path):
    session = SimSession("hazard_field")
    session.step(80)
    run_id = session.record(tmp_path)
    run_dir = tmp_path / run_id
    lines = (run_dir / "ticks.jsonl").read_text().splitlines()
    assert len(lines) == len(session.history)
    assert json.loads(lines[0])["tick"] == 0
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["protocol"] == "hazard_field" and summary["ticks_run"] == len(lines)
    scene = json.loads((run_dir / "scene.json").read_text())
    assert any(o["kind"] == "hazard" for o in scene["objects"])


def test_session_store_evicts_least_recently_used():
    store = SessionStore(limit=2)
    a = store.create("open_field", 1)
    b = store.create("open_field", 2)
    store.get(a.id)  # touch a, so b is now the oldest
    c = store.create("open_field", 3)
    assert store.get(a.id) is a and store.get(c.id) is c
    assert store.get(b.id) is None
    assert store.delete(a.id) and not store.delete(a.id)
