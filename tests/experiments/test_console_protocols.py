"""The lab console's scenarios as headless protocols (experiments/protocols/console.py).

Every console scenario is registered with the headless runner as
``console_<id>``. A run writes ticks.jsonl, scene.json, summary.json,
manifest.json and events.jsonl; the engine takes the scenario's own config;
two runs at one seed are identical; and a headless run of ``console_<id>``
writes the same ticks a live ``SimSession`` of ``<id>`` records at that seed
(the runner steps the engine first and the scenario second, as the session
does), with the same run hash.

These tests pin the legacy profile (the scenarios' configs are built on
EngineConfig()); see docs/decisions.md G22 and docs/profiles.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.protocols.console import CONSOLE_PREFIX, CONSOLE_PROTOCOLS, ConsoleProtocol
from experiments.protocols.open_field import OpenFieldProtocol
from experiments.runner import EVENTS_FILE, PROTOCOLS, run
from metrics.hash import RunHash
from metrics.logger import _canonical_json
from metrics.manifest import config_to_dict
from ui.scenarios import SCENARIOS
from ui.sim_session import MAX_STEPS_PER_CALL, SimSession

RUN_FILES = {"ticks.jsonl", "scene.json", "summary.json", "manifest.json", EVENTS_FILE}
CONSOLE_NAMES = sorted(CONSOLE_PROTOCOLS)


def _read(outdir: Path):
    return {
        "ticks": (outdir / "ticks.jsonl").read_text().splitlines(),
        "events": (outdir / EVENTS_FILE).read_text().splitlines(),
        "summary": json.loads((outdir / "summary.json").read_text()),
        "scene": json.loads((outdir / "scene.json").read_text()),
        "manifest": json.loads((outdir / "manifest.json").read_text()),
    }


def test_every_console_scenario_is_a_headless_protocol_and_the_bare_names_are_unchanged():
    assert set(CONSOLE_PROTOCOLS) == {CONSOLE_PREFIX + sid for sid in SCENARIOS}
    assert CONSOLE_NAMES == [
        "console_beacon", "console_foraging", "console_hazard_field",
        "console_hidden_food", "console_memory_maze", "console_open_field",
    ]
    for name, cls in CONSOLE_PROTOCOLS.items():
        assert PROTOCOLS[name] is cls and issubclass(cls, ConsoleProtocol)
        assert cls.name == name and name == CONSOLE_PREFIX + cls.scenario_id
    assert PROTOCOLS["open_field"] is OpenFieldProtocol  # the bare names stay the old protocols


def test_console_protocols_take_no_protocol_config():
    with pytest.raises(ValueError):
        CONSOLE_PROTOCOLS["console_beacon"]({"targets": []})
    CONSOLE_PROTOCOLS["console_beacon"](None)
    CONSOLE_PROTOCOLS["console_beacon"]({})


@pytest.mark.parametrize("name", CONSOLE_NAMES)
def test_console_protocol_runs_and_writes_the_five_files(name, tmp_path):
    run(name, seed=3, ticks=100, outdir=tmp_path)
    assert {p.name for p in tmp_path.iterdir()} == RUN_FILES
    out = _read(tmp_path)
    assert len(out["ticks"]) == 100  # never ends early
    summary = out["summary"]
    assert summary["protocol"] == name and summary["scenario"] == CONSOLE_PROTOCOLS[name].scenario_id
    assert summary["ticks_run"] == 100 and summary["seed"] == 3
    assert isinstance(summary["score"], float) and summary["score"] >= 0.0
    assert isinstance(summary["status"], dict)
    assert "events" not in summary and summary["n_events"] == len(out["events"])
    for line in out["events"]:
        event = json.loads(line)
        assert {"tick", "text", "level", "kind"} <= set(event)
        assert 0 <= event["tick"] < 100
    # The manifest says what ran: the scenario's own config and profile.
    scenario_config = CONSOLE_PROTOCOLS[name]().engine_config()
    m = out["manifest"]
    assert m["protocol"] == name and m["seeds"] == [3]
    assert m["profile"] == scenario_config.profile == "legacy"
    assert m["config"] == config_to_dict(scenario_config)
    assert m["ticks_requested"] == 100 and m["ticks_run"] == 100
    assert m["timing"]["ticks_per_second"] > 0
    assert out["scene"]["protocol"] == name


def test_summaries_carry_each_scenarios_own_counters(tmp_path):
    expected = {
        "console_open_field": {"distance_travelled"},
        "console_beacon": {"beacons_reached", "last_time_to_reach"},
        "console_foraging": {"collected", "patches_cleared", "last_patch_time"},
        "console_hazard_field": {"collected", "hazard_contacts"},
        "console_hidden_food": {"collected", "sites_found", "finds_per_site", "collect_ticks", "blocks"},
        "console_memory_maze": {"trials", "trials_completed", "hidden_trials", "recalls", "recall_rate", "last_recall_time", "trial", "goal_visible"},
    }
    for name, keys in expected.items():
        outdir = tmp_path / name
        run(name, seed=3, ticks=60, outdir=outdir)
        summary = json.loads((outdir / "summary.json").read_text())
        assert keys <= set(summary), name


@pytest.mark.parametrize("name", CONSOLE_NAMES)
def test_same_seed_gives_identical_data_files(name, tmp_path):
    run(name, seed=5, ticks=100, outdir=tmp_path / "a")
    run(name, seed=5, ticks=100, outdir=tmp_path / "b")
    a, b = _read(tmp_path / "a"), _read(tmp_path / "b")
    assert a["ticks"] == b["ticks"]
    assert a["events"] == b["events"]
    assert a["summary"] == b["summary"]
    assert a["scene"] == b["scene"]
    # The manifest is the one file allowed to differ (wall-clock); its provenance agrees.
    for key in ("config", "profile", "protocol", "seeds", "git", "ticks_run"):
        assert a["manifest"][key] == b["manifest"][key]


def test_profile_option_applies_only_when_the_protocol_has_no_config(tmp_path):
    run("open_field", seed=3, ticks=20, outdir=tmp_path / "research", profile="research")
    m = json.loads((tmp_path / "research" / "manifest.json").read_text())
    assert m["profile"] == "research" and m["profile_requested"] == "research"
    assert m["config"]["trn"]["microsleep_enabled"] is False
    research_summary = json.loads((tmp_path / "research" / "summary.json").read_text())
    run("open_field", seed=3, ticks=20, outdir=tmp_path / "legacy")
    legacy_dir = tmp_path / "legacy"
    assert not (legacy_dir / EVENTS_FILE).exists()  # a bare protocol logs no events
    assert json.loads((legacy_dir / "manifest.json").read_text())["profile"] == "legacy"
    # The two profiles are different runs (the research profile has odometry noise and softmax on).
    legacy_summary = json.loads((legacy_dir / "summary.json").read_text())
    assert legacy_summary["run_hash"] != research_summary["run_hash"]
    assert (legacy_dir / "ticks.jsonl").read_text() != (tmp_path / "research" / "ticks.jsonl").read_text()
    # A console protocol supplies its own config, so the requested profile does not apply.
    run("console_open_field", seed=3, ticks=20, outdir=tmp_path / "console", profile="research")
    c = json.loads((tmp_path / "console" / "manifest.json").read_text())
    assert c["profile"] == "legacy" and c["profile_requested"] == "research"
    assert c["config"]["trn"]["microsleep_enabled"] is True
    with pytest.raises(ValueError):
        run("open_field", seed=3, ticks=1, outdir=tmp_path / "bad", profile="no-such-profile")


def _live_rows(scenario_id: str, seed: int, ticks: int):
    """A live session stepped to ``ticks`` rows, as the console would record them."""
    session = SimSession(scenario_id, seed=seed)  # the build runs tick 0
    remaining = ticks - 1
    while remaining > 0:
        n = min(remaining, MAX_STEPS_PER_CALL)
        session.step(n)
        remaining -= n
    return session, [_canonical_json(row) for row in session.history]


@pytest.mark.parametrize("scenario_id", ["open_field", "hidden_food", "memory_maze"])
def test_headless_console_protocol_matches_the_live_session(scenario_id, tmp_path):
    ticks, seed = 300, 7
    session, rows = _live_rows(scenario_id, seed, ticks)
    assert len(rows) == ticks
    run(CONSOLE_PREFIX + scenario_id, seed=seed, ticks=ticks, outdir=tmp_path)
    out = _read(tmp_path)
    # The same ticks, byte for byte (positions included), and the same run hash.
    assert out["ticks"] == rows
    rh = RunHash()
    for row in session.history:
        rh.update(row)
    assert out["summary"]["run_hash"] == rh.hexdigest()
    # The scenario ended up in the same state in both.
    assert out["summary"]["status"] == session.scenario.status()
    # And the session's own scenario events are the ones in events.jsonl.
    live_events = [e for e in session.events if e["kind"] not in ("session", "sleep", "gate", "criticality", "param")]
    assert [json.loads(line) for line in out["events"]] == [{k: v for k, v in e.items() if k != "seq"} for e in live_events]
