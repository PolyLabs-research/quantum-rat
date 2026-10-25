"""The RQ4(a) gate experiment (experiments/rq4a_gate.py; docs/prereg/m2b_gate.md).

Quick runs only (8 trials, two seeds): the protocol's start order, the ratio statistic, the files and columns, the
preregistered test rows, identical tables across worker counts, and the refusal of the committed directory. The
numbers of a quick run mean nothing; the evaluation is in G36.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
import pytest

from core.config import EngineConfig
from experiments import rq4a_gate as rg


def _read(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_the_protocol() -> None:
    order = rg.start_order(1, 40)
    assert len(order) == 40 and all(sorted(order[i:i + 4]) == [0, 1, 2, 3] for i in range(0, 40, 4))
    assert order == rg.start_order(1, 40) and order != rg.start_order(2, 40)
    assert rg.GOAL == (5.0, 5.0) and rg.GOAL_RADIUS == 1.0 and rg.TRIALS == 40 and rg.TIMEOUT == 300
    for src in rg.SOURCES:
        diff = {d[0] for d in EngineConfig.research().diff(rg.gate_config(src))}
        assert {"place.enabled", "spatial.wall_reset", "spatial.heading_source"} <= diff
        assert ("value_memory.source" in diff) == (src != "tabular")
    with pytest.raises(ValueError):
        rg.gate_config("model")
    with pytest.raises(ValueError):
        rg.run_session("sr", "dark", 1, 1)


def test_the_ratio_is_the_ratio_of_paired_means() -> None:
    hidden = np.array([0.2, 0.4, 0.6, 0.5])
    visible = np.array([0.5, 0.8, 0.6, 0.7])
    ci = rg.ratio_ci(hidden, visible, 2000, 7)
    assert ci.estimate == pytest.approx(hidden.mean() / visible.mean()) and ci.low <= ci.estimate <= ci.high
    zero = rg.ratio_ci(np.array([0.1, 0.2]), np.zeros(2), 200, 1)
    assert math.isnan(zero.estimate)


@pytest.fixture(scope="module")
def quick(tmp_path_factory):
    out = tmp_path_factory.mktemp("gate")
    return out, rg.main(["--quick", "--seeds", "2", "--workers", "2", "--out", str(out)])


def test_quick_run_writes_its_tables(quick) -> None:
    out, res = quick
    assert {p.name for p in out.iterdir()} == set(rg.OUTPUT_FILES)
    trials = _read(out / "gate_trials.csv")
    assert list(trials[0]) == list(rg.TRIAL_COLUMNS) and len(trials) == 3 * 2 * 2 * 8
    assert all(r["guided"] == "False" for r in trials if r["session"] == "visible")
    assert all((r["reached"] == "True") == (r["latency"] != "") for r in trials)
    assert all(int(r["ticks"]) <= rg.TIMEOUT + rg.GUIDE for r in trials)
    assert all(r["arrival_error"] != "nan" for r in trials if r["reached"] == "True")
    # The same start order in every source and session of a seed.
    for seed in ("1", "2"):
        orders = {(r["source"], r["session"]): [] for r in trials if r["seed"] == seed}
        for r in trials:
            if r["seed"] == seed:
                orders[(r["source"], r["session"])].append(r["start"])
        assert len({tuple(v) for v in orders.values()}) == 1
    per_seed = _read(out / "gate_per_seed.csv")
    assert list(per_seed[0]) == list(rg.PER_SEED_COLUMNS) and len(per_seed) == 3 * 2 * 2
    assert len(_read(out / "gate_curve.csv")) == 3 * 2 * 2
    effects = _read(out / "gate_effects.csv")
    assert [e["test"] for e in effects[:1]] == ["g1_relative_success"] and "g2_arrival_error" in {e["test"] for e in effects}
    assert {e["verdict"] for e in effects if e["test"].startswith("g")} <= {"passes", "fails", "undefined (no arrival)"}
    m = json.loads((out / "gate_manifest.json").read_text())
    assert m["protocol"] == "rq4a_gate" and m["prereg"] == "docs/prereg/m2b_gate.md" and m["quick"] is True and m["trials"] == 8
    assert m["ticks_run"] == sum(int(r["ticks"]) for r in trials) and m["timing"]["ticks_per_second"] > 0


def test_quick_run_is_identical_across_workers_and_refuses_the_committed_directory(quick, tmp_path, monkeypatch) -> None:
    out, _ = quick
    again = tmp_path / "again"
    rg.main(["--quick", "--seeds", "2", "--workers", "1", "--out", str(again)])
    for name in rg.OUTPUT_FILES:
        if not name.endswith(".json"):
            assert (out / name).read_bytes() == (again / name).read_bytes(), name
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        rg.main(["--quick", "--seeds", "2"])
    with pytest.raises(SystemExit):
        rg.main(["--sources", "sr", "--reward-rule", "per_feature", "--seeds", "1"])  # partial: refuses the default directory
    explor = tmp_path / "explor"
    rg.main(["--quick", "--seeds", "1", "--workers", "1", "--sources", "sr", "--reward-rule", "per_feature", "--out", str(explor)])
    m = json.loads((explor / "gate_manifest.json").read_text())
    assert m["reward_rule"] == "per_feature" and m["exploratory"] is True and m["sources"] == ["sr"] and m["full_evaluation"] is False
    assert {r["source"] for r in _read(explor / "gate_trials.csv")} == {"sr"}
    assert not (tmp_path / "docs").exists()
