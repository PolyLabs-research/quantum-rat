"""The live-console backend: scenarios, sessions, params, events and recording.

These tests pin the legacy profile (EngineConfig() defaults); see docs/decisions.md G22 and docs/profiles.md.
"""

import json
import math

import pytest

from core.config import EngineConfig
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


def test_memory_maze_frame_shows_the_goal_memory():
    session = SimSession("memory_maze")
    assert session.frame()["goal"] is None  # nothing consolidated yet
    while not session.scenario.history:
        session.step(1)
    frame = session.frame()  # training ended: sleep replay stored the goal's place cell
    gx, gy = frame["goal"]
    assert abs(gx - 6.0) < 2.0 and abs(gy - 3.0) < 2.0  # at the goal disk's edge (radius 1.5)
    assert frame["action"]["goal_vector"] in (True, False)
    assert SimSession("foraging").frame()["goal"] is None  # the goal vector is off there


def test_gate_safe_pacing_rests_before_the_trn_narrows():
    """GATE_SAFE_PACE_LOW is tied to TRNConfig.open_at_atp by prose only (it stays a literal so the
    pacing latch compares against exactly 0.6); this keeps the tie honest."""
    from core.config import TRNConfig
    from ui.scenarios import GATE_SAFE_PACE_LOW, MAZE_PACE_LOW

    assert GATE_SAFE_PACE_LOW == MAZE_PACE_LOW == 0.6
    assert GATE_SAFE_PACE_LOW > TRNConfig().open_at_atp


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


# --- the research profile in the console (docs/decisions.md G38) ---------------------------


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_every_scenario_runs_on_the_research_profile_and_reports_the_place_code(scenario_id):
    session = SimSession(scenario_id, seed=7, profile="research")
    session.step(30)
    frame = session.frame()
    info = session.place_info()
    assert frame["profile"] == "research" and session.engine.config.profile == "research"
    assert info["n"] == info["nx"] * info["ny"] == len(info["cx"]) == len(info["cy"]) == 400
    assert len(frame["place"]["rates"]) == len(frame["sr"]["value"]) == len(frame["sr"]["field"]) == 400
    assert len(frame["sr"]["weights"]) == 400 and frame["sr"]["rule"] == "per_feature" and frame["sr"]["updates"] >= 1
    assert frame["place"]["active"] >= 1 and 0.0 < frame["place"]["max"] <= 1.0
    # The decoded position is the estimate (the decoder is exact for noiseless rates).
    dx, dy = frame["place"]["decoded"]
    assert math.hypot(dx - frame["agent"]["est_x"], dy - frame["agent"]["est_y"]) < 0.02
    # The research profile freezes ATP and never sleeps; everything sent is plain JSON.
    assert frame["energy"]["atp"] == 1.0 and frame["trn"]["state"] == "OPEN"
    json.dumps(frame)
    json.dumps(info)


def test_the_legacy_profile_is_the_default_and_has_no_place_code():
    session = SimSession("open_field", seed=7)
    frame = session.frame()
    assert session.profile == "legacy" == frame["profile"]
    assert frame["place"] is None and frame["sr"] is None and session.place_info() is None
    assert frame["replay_trails"] == []
    with pytest.raises(ValueError):
        SimSession("open_field", profile="toy")


def test_profile_overrides_are_the_scenarios_own_settings_and_survive_a_reset():
    session = SimSession("memory_maze", seed=3, profile="research")
    fields = {name: (p, s) for name, p, s in session.profile_overrides}
    assert fields["value_memory.generalization_radius"] == (0, 2)
    assert fields["value_memory.oracle_homing"] == (False, True)
    assert fields["reward.approach_weight"] == (1.0, 0.0)
    cfg = session.engine.config
    assert cfg.profile == "research" and cfg.trn.microsleep_enabled is False and cfg.place.enabled
    assert cfg.value_memory.generalization_radius == 2 and cfg.value_memory.oracle_homing is True
    session.reset(seed=4)
    assert session.profile == "research" and session.engine.config.profile == "research"
    # A scenario with no settings of its own runs the profile as it is.
    plain = SimSession("open_field", seed=3, profile="research")
    assert plain.profile_overrides == [] and plain.engine.config.diff(EngineConfig.research()) == []


def test_research_params_are_live_and_the_oracle_noise_needs_the_oracle():
    legacy = SimSession("open_field", seed=1)
    with pytest.raises(ValueError):
        legacy.set_param("sensors.heading_oracle_noise", 0.1)
    assert legacy.set_param("sensors.heading_oracle_noise", 0.0) == 0.0
    assert legacy.set_param("basal_ganglia.softmax_temperature", 0.2) == 0.2
    research = SimSession("open_field", seed=1, profile="research")
    assert research.set_param("sensors.heading_oracle_noise", 0.1) == 0.1
    assert research.engine.config.sensors.heading_oracle_noise == 0.1
    assert research.set_param("place.reward_learning_rate", 0.25) == 0.25
    assert research.engine.config.place.reward_learning_rate == 0.25
    assert "Estimate & sampling" in {p["group"] for p in research.params()}


def test_same_seed_gives_identical_series_on_the_research_profile_and_differs_from_legacy():
    a = SimSession("foraging", seed=11, profile="research").step(80)
    b = SimSession("foraging", seed=11, profile="research").step(80)
    assert a == b
    assert SimSession("foraging", seed=11).step(80) != a


def test_recording_carries_the_profile(tmp_path):
    session = SimSession("hidden_food", seed=2, profile="research")
    session.step(40)
    run_id = session.record(tmp_path)
    assert "_research_" in run_id
    summary = json.loads((tmp_path / run_id / "summary.json").read_text())
    assert summary["profile"] == "research"
    assert ["value_memory.generalization_radius", 0, 2] in summary["profile_overrides"]
    manifest = json.loads((tmp_path / run_id / "manifest.json").read_text())
    assert manifest["profile"] == "research" and manifest["profile_requested"] == "research"
    assert manifest["config"]["place"]["enabled"] is True


# --- the view explains the active mechanisms (docs/decisions.md G39) -----------------------


def test_frame_carries_the_decision_terms_and_the_selection_probabilities():
    for profile in ("legacy", "research"):
        session = SimSession("hazard_field", seed=4, profile=profile)
        session.step(120)
        a = session.frame()["action"]
        assert set(a["terms"]) == set(a["scores"])
        for channel, score in a["scores"].items():
            assert abs(sum(a["terms"][channel].values()) - score) < 2e-3  # the frame rounds to 4 dp
        assert abs(sum(a["probs"].values()) - 1.0) < 2e-3  # the frame rounds each probability to 4 dp
        if profile == "research":
            assert a["source"] == "sr" and a["temperature"] == 0.1
        else:
            assert a["source"] == "tabular" and a["temperature"] == 0.0 and a["probs"][a["name"]] == 1.0


def test_mechanisms_follow_the_effective_configuration():
    legacy = {m["id"]: m for m in SimSession("open_field").mechanisms()}
    assert legacy["energy"]["status"] == legacy["microsleep"]["status"] == legacy["map"]["status"] == "active"
    assert legacy["place"]["status"] == "off" and legacy["neuromod"]["status"] == "active" and legacy["crit"]["status"] == "readout"
    research = SimSession("memory_maze", profile="research")
    m = {x["id"]: x for x in research.mechanisms()}
    assert m["energy"]["status"] == "off" and m["microsleep"]["status"] == "off"
    assert m["steer"]["status"] == "active" and "SR value" in m["steer"]["detail"]
    assert m["map"]["status"] == "readout" and m["place"]["status"] == "active"
    assert m["neuromod"]["status"] == m["novelty"]["status"] == m["crit"]["status"] == "readout"
    assert m["goal"]["status"] == "active" and "own setting" in m["goal"]["detail"]
    assert m["heading"]["detail"].startswith("the declared heading oracle") and m["reset"]["status"] == "active"
    assert {x["status"] for x in research.mechanisms()} <= {"active", "readout", "off"}
    research.set_param("basal_ganglia.ne_threat_gain", 0.5)  # a gain above 0 turns the chip on
    assert {x["id"]: x for x in research.mechanisms()}["neuromod"]["status"] == "active"
    json.dumps(research.mechanisms())


def test_behaviour_readouts_count_what_the_body_did():
    session = SimSession("foraging", seed=11)
    session.step(400)
    b = session.frame()["behaviour"]
    assert b["distance"] > 0 and 0.0 <= b["wall_fraction"] <= 1.0
    assert b["finds"] == session.scenario.collected >= 1  # one contact tick per collection
    assert b["ticks_since_find"] is not None and b["distance_per_find"] > 0 and b["reward_total"] > 0
    fresh = SimSession("open_field", seed=1).frame()["behaviour"]
    assert fresh["finds"] == 0 and fresh["ticks_since_find"] is None and fresh["distance_per_find"] is None
    # The teleport to the start after a maze trial is not walking: the body moves at most 1 unit per tick.
    maze = SimSession("memory_maze", seed=3, profile="research")
    for _ in range(20):
        maze.step(50)
        if maze.scenario.history:
            break
    assert maze.scenario.history and maze.frame()["behaviour"]["distance"] <= maze.tick + 1


def test_maze_rest_respects_frozen_physiology_and_the_memory_controls_name_their_learner():
    research = SimSession("memory_maze", seed=3, profile="research")
    for _ in range(20):
        research.step(50)
        if any(e["kind"] == "rest" for e in research.events):
            break
    rest = [e for e in research.events if e["kind"] == "rest"][-1]
    assert "frozen" in rest["text"] and research.engine.astrocyte.glycogen == 3.0 and research.engine.astrocyte.atp == 1.0
    research.do_action("consolidate")
    assert "the tabular map only" in research.events[-1]["text"]
    legacy = SimSession("memory_maze", seed=3)
    for _ in range(20):
        legacy.step(50)
        if any(e["kind"] == "rest" for e in legacy.events):
            break
    rest = [e for e in legacy.events if e["kind"] == "rest"][-1]
    assert "physiology updates" in rest["text"] and "frozen" not in rest["text"]
    legacy.do_action("consolidate")
    assert "the tabular map only" not in legacy.events[-1]["text"]
    hidden = SimSession("hidden_food", seed=2, profile="research")
    hidden.engine.sr_weights[:] = 0.5
    hidden.engine.value_memory.values[(0, 0)] = 1.0
    hidden.do_action("forget")
    assert not hidden.engine.sr_weights.any() and not hidden.engine.value_memory.values
    assert "SR reward weights erased" in hidden.events[-1]["text"]
    assert [a["label"] for a in hidden.scenario.actions()] == ["Forget the rewards"]


def test_recordings_carry_the_decision_log_and_the_frame_its_counterfactuals(tmp_path):
    from metrics.decisions import DECISIONS_FILE, read_decisions

    session = SimSession("beacon", seed=5, profile="research")
    session.step(60)
    a = session.frame()["action"]
    assert set(a["probs_without_memory"]) == set(a["probs"]) and set(a["influence"]) == {"memory", "vision", "wall"}
    assert all(0.0 <= v <= 1.0 for v in a["influence"].values())
    b = session.frame()["behaviour"]
    assert b["turning_window"] == 300 and isinstance(b["turning_revolutions"], float) and 0.0 <= b["closure"] <= 1.0
    run_id = session.record(tmp_path)
    records = read_decisions(tmp_path / run_id)
    assert len(records) == len(session.history) == 61 and [r["tick"] for r in records] == [row["tick"] for row in session.history]
    assert json.loads((tmp_path / run_id / "summary.json").read_text())["n_decision_records"] == 61
    assert (tmp_path / run_id / DECISIONS_FILE).exists()


def test_renewable_reward_scenarios_carry_the_unlearning_rate_and_the_instrument_keeps_one_rate():
    """decisions G43: hidden food and beacon set the SR's unlearning rate to 4 as their own setting; the research
    profile keeps None (one rate: the gate's instrument, G42); on the legacy profile the setting is inert (no SR)."""
    from ui.scenarios import RENEWABLE_REWARD_UNLEARNING_RATE

    assert RENEWABLE_REWARD_UNLEARNING_RATE == 4.0 and EngineConfig.research().place.reward_unlearning_rate is None
    for scenario_id in ("hidden_food", "beacon"):
        research = SimSession(scenario_id, seed=2, profile="research")
        assert research.engine.config.place.reward_unlearning_rate == 4.0
        assert ("place.reward_unlearning_rate", None, 4.0) in research.profile_overrides
        place = {m["id"]: m for m in research.mechanisms()}["place"]
        assert "unlearning 4 (this scenario's own setting)" in place["detail"]
        assert {p["key"]: p["value"] for p in research.params()}["place.reward_unlearning_rate"] == 4.0
        legacy = SimSession(scenario_id, seed=2)
        assert legacy.engine.sr is None and legacy.engine.place is None  # nothing reads the field there
    for scenario_id in ("open_field", "foraging", "hazard_field", "memory_maze"):
        assert SimSession(scenario_id, seed=2, profile="research").engine.config.place.reward_unlearning_rate is None
