"""Provenance manifests (metrics/manifest.py): what every run writes beside its data.

The manifest is provenance, not data: nothing in it enters a run hash, and it
is the one file in a run directory with wall-clock time in it. These tests
check its keys and types, the git lookup's graceful failure, the config
round-trip, the timing arithmetic, the sorted output, and that the tournament
and the console recording write one too.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict

import pytest

from agents.dna import generate_population
from core.config import EngineConfig
from metrics.manifest import (
    MANIFEST_VERSION,
    THREAD_ENV_VARS,
    build_manifest,
    config_to_dict,
    finish_manifest,
    git_info,
    write_manifest,
)
from metrics.schema import SCHEMA_VERSION
from tournaments.manager import TournamentManager, stable_hash
from ui.sim_session import SimSession

SHA40 = re.compile(r"^[0-9a-f]{40}$")

TOP_LEVEL_KEYS = {
    "manifest_version", "created_at", "git", "profile", "config", "dt_s", "protocol", "seeds",
    "ticks_requested", "platform", "schema_version",
}
PLATFORM_KEYS = {"system", "release", "machine", "python", "numpy", "blas", "blas_runtime", "blas_threads"}


def _tuples_to_lists(value):
    if isinstance(value, (list, tuple)):
        return [_tuples_to_lists(v) for v in value]
    if isinstance(value, dict):
        return {k: _tuples_to_lists(v) for k, v in value.items()}
    return value


def test_build_manifest_has_the_documented_keys_and_types():
    m = build_manifest(EngineConfig(), protocol="open_field", seeds=[1337], ticks_requested=200)
    assert TOP_LEVEL_KEYS <= set(m)
    assert m["manifest_version"] == MANIFEST_VERSION
    assert m["schema_version"] == SCHEMA_VERSION
    assert m["profile"] == "legacy"
    assert m["protocol"] == "open_field"
    assert m["seeds"] == [1337] and m["ticks_requested"] == 200
    # ISO-8601 UTC: "YYYY-MM-DDTHH:MM:SS+00:00"
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$", m["created_at"])
    assert set(m["platform"]) == PLATFORM_KEYS
    assert set(m["platform"]["blas_threads"]) == set(THREAD_ENV_VARS)
    assert isinstance(m["platform"]["python"], str) and m["platform"]["python"]
    assert m["platform"]["numpy"] is None or isinstance(m["platform"]["numpy"], str)
    assert isinstance(m["platform"]["blas"], str) and m["platform"]["blas"]
    # dt_s comes from a units section when the config has one; otherwise null.
    units = getattr(EngineConfig(), "units", None)
    assert m["dt_s"] == (float(units.dt_s) if units is not None else None)
    json.dumps(m)  # everything is plain JSON


def test_git_sha_is_40_hex_or_unknown_and_dirty_is_a_bool_when_known():
    info = git_info()
    assert set(info) == {"sha", "dirty", "branch"}
    if info["sha"] == "unknown":
        assert info["dirty"] is None and info["branch"] == "unknown"
    else:
        assert SHA40.match(info["sha"])
        assert isinstance(info["dirty"], bool)
        assert isinstance(info["branch"], str) and info["branch"]
    # In this repository the lookup works.
    assert SHA40.match(build_manifest(EngineConfig(), protocol="p", seeds=[1], ticks_requested=1)["git"]["sha"])


def test_git_lookup_fails_gracefully_without_git():
    info = git_info(git="git-command-that-does-not-exist-anywhere")
    assert info == {"sha": "unknown", "dirty": None, "branch": "unknown"}


@pytest.mark.parametrize("make", [EngineConfig.legacy, EngineConfig.research])
def test_config_round_trips_as_asdict_with_tuples_as_lists(make):
    cfg = make()
    m = build_manifest(cfg, protocol="p", seeds=[1], ticks_requested=1)
    assert m["profile"] == cfg.profile
    expected = _tuples_to_lists(asdict(cfg))
    assert m["config"] == expected
    # Through JSON and back: the same dict (the research profile's infinite
    # kappa threshold survives as inf).
    assert json.loads(json.dumps(m["config"])) == expected
    assert isinstance(m["config"]["world"]["bounds"], list)
    assert config_to_dict(cfg) == expected
    assert config_to_dict(expected) == expected  # an already-serialised config is accepted


def test_finish_manifest_computes_ticks_per_second():
    m = build_manifest(EngineConfig(), protocol="p", seeds=[1], ticks_requested=100)
    out = finish_manifest(m, ticks_run=100, wall_seconds=0.25)
    assert out is m
    assert m["ticks_run"] == 100
    assert m["timing"] == {"wall_seconds": 0.25, "ticks_per_second": 400.0}
    assert m["timing"]["ticks_per_second"] > 0
    # No elapsed time: nothing to divide by, and no made-up rate.
    finish_manifest(m, ticks_run=5, wall_seconds=0.0)
    assert m["timing"]["ticks_per_second"] is None


def _key_orders(pairs):
    """Every key list in a parsed-with-order JSON tree, top level first."""
    keys = [k for k, _ in pairs]
    yield keys
    for _, v in pairs:
        if isinstance(v, list) and v and all(isinstance(x, tuple) for x in v):
            yield from _key_orders(v)


def test_write_manifest_writes_sorted_indented_json(tmp_path):
    m = build_manifest(EngineConfig(), protocol="p", seeds=[3, 1, 2], ticks_requested=10, extra={"zeta": 1, "alpha": 2})
    finish_manifest(m, ticks_run=10, wall_seconds=0.5)
    path = tmp_path / "manifest.json"
    write_manifest(path, m)
    text = path.read_text()
    assert text == json.dumps(m, indent=2, sort_keys=True) + "\n"
    assert json.loads(text) == json.loads(json.dumps(m))
    # Keys are sorted at every level of the written file.
    ordered = json.loads(text, object_pairs_hook=lambda pairs: pairs)
    for keys in _key_orders(ordered):
        assert keys == sorted(keys)
    assert m["seeds"] == [3, 1, 2]  # values are not reordered, only keys


def test_extra_keys_go_to_the_top_level_and_may_not_clash():
    m = build_manifest(EngineConfig(), protocol="p", seeds=[1], ticks_requested=1, extra={"source": "x", "pair": (1, 2)})
    assert m["source"] == "x" and m["pair"] == [1, 2]
    with pytest.raises(ValueError):
        build_manifest(EngineConfig(), protocol="p", seeds=[1], ticks_requested=1, extra={"profile": "other"})


def test_tournament_writes_a_manifest_at_its_root(tmp_path):
    agents = generate_population(5, 2)
    protocols = [{"name": "open_field", "ticks": 30}, {"name": "console_beacon", "ticks": 20}]
    manager = TournamentManager(seed=5, agents=agents, protocols=protocols, outdir=tmp_path, manifest_extra={"agents_source": "test"})
    manager.run()
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert m["protocol"] == "tournament" and m["seeds"] == [5]
    assert m["n_agents"] == 2 and m["protocols"] == protocols
    assert m["episode_seeds"] == {"open_field": stable_hash(5, "open_field"), "console_beacon": stable_hash(5, "console_beacon")}
    assert m["ticks_requested"] == 2 * (30 + 20) and m["ticks_run"] == 100
    assert m["timing"]["ticks_per_second"] > 0
    assert m["agents_source"] == "test"
    assert m["config"] == _tuples_to_lists(asdict(EngineConfig()))
    # The existing output files are as before: no manifest inside them, and no
    # manifest in the per-episode directories (one per tournament).
    config = json.loads((tmp_path / "config.json").read_text())
    assert config == {"seed": 5, "protocols": protocols}
    assert not list(tmp_path.glob("agents/**/manifest.json"))
    # The console protocol ran with its scenario's config and logged its events.
    summary = json.loads((tmp_path / "agents" / agents[0].agent_id / "console_beacon" / "summary.json").read_text())
    assert "events" not in summary and summary["n_events"] >= 0
    assert (tmp_path / "agents" / agents[0].agent_id / "console_beacon" / "events.jsonl").exists()


def test_console_recording_writes_a_manifest(tmp_path):
    session = SimSession("foraging", seed=11)
    session.set_param("sensors.fov", 1.0)
    session.step(40)
    run_dir = tmp_path / session.record(tmp_path)
    m = json.loads((run_dir / "manifest.json").read_text())
    assert m["protocol"] == "foraging" and m["seeds"] == [11] and m["source"] == "live console"
    assert m["ticks_run"] == len(session.history) == 41 and m["ticks_requested"] == session.tick + 1 == 41
    assert m["params"] == {"sensors.fov": 1.0}
    assert m["config"]["sensors"]["fov"] == 1.0  # the config as it ran, overrides included
    assert m["profile"] == session.engine.config.profile
    assert m["timing"]["wall_seconds"] >= 0.0
    assert m["scenario"]["id"] == "foraging"
    # The data files are untouched by the manifest.
    assert set(p.name for p in run_dir.iterdir()) == {"ticks.jsonl", "summary.json", "scene.json", "manifest.json"}
    assert "created_at" not in json.loads((run_dir / "summary.json").read_text())
