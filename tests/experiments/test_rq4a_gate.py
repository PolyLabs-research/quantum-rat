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
    # Since M2b's exit (decisions G37) the research profile is the gate's instrument: the SR source with the
    # per-feature rule differs from it in nothing, and the other cells differ only in the source and the reward rule.
    assert EngineConfig.research().diff(rg.gate_config("sr", "per_feature")) == []
    for src in rg.SOURCES:
        diff = {d[0] for d in EngineConfig.research().diff(rg.gate_config(src))}
        assert diff <= {"place.reward_rule", "value_memory.source"}
        assert "place.reward_rule" in diff  # the default argument is the preregistered NLMS rule
        assert ("value_memory.source" in diff) == (src != "sr")
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
    assert set(rg.PREREGS) == {"docs/prereg/m2b_gate.md", "docs/prereg/m2b_gate_confirmatory.md", "docs/prereg/m3_body.md",
                               "docs/prereg/m3_corridor.md"}
    assert rg.committed_dir("docs/prereg/m3_corridor.md", "discrete").as_posix() == "docs/data/m3/corridor/gate/discrete"
    corridor = rg.gate_config("sr", "per_feature", None, "discrete", True)
    assert corridor.basal_ganglia.turn_commitment == 0.3 and abs(corridor.basal_ganglia.wall_avoid_range - 1 / 6) < 1e-15
    assert rg.PREREGS["docs/prereg/m2b_gate_confirmatory.md"]["seeds"] == tuple(range(31, 61))
    # M3 step 1 (G44): the rodent bodies on fresh seeds, one committed directory per body.
    assert rg.PREREGS["docs/prereg/m3_body.md"]["seeds"] == tuple(range(61, 91))
    assert rg.committed_dir("docs/prereg/m3_body.md", "rodent").as_posix() == "docs/data/m3/body/gate/rodent"
    assert rg.committed_dir("docs/prereg/m2b_gate.md", "discrete").as_posix() == "docs/data/m2b/gate"
    with pytest.raises(SystemExit):  # the confirmatory directory refuses a run away from its preregistration
        rg.main(["--quick", "--seeds", "1", "--prereg", "docs/prereg/m2b_gate_confirmatory.md", "--out", "docs/data/m2b/gate_confirmatory"])
    with pytest.raises(SystemExit):
        rg.main(["--prereg", "docs/prereg/other.md", "--out", str(tmp_path / "z")])
    assert {r["source"] for r in _read(explor / "gate_trials.csv")} == {"sr"}
    assert not (tmp_path / "docs").exists()


# --- the audit of 2026-10-27 (decisions G46) ----------------------------------------------------------------------


def test_every_registration_before_g46_pins_the_old_sensing() -> None:
    assert all(spec.get("pre_g46") for spec in rg.PREREGS.values())
    old = rg.gate_config("sr", "per_feature", pre_g46=True)
    new = rg.gate_config("sr", "per_feature", pre_g50=True)  # after G46, before G50's adoptions
    assert old.sensors.unseen_block_rays and old.reward.shape_hidden
    assert not new.sensors.unseen_block_rays and not new.reward.shape_hidden
    assert [d[0] for d in new.diff(old)] == ["sensors.unseen_block_rays", "reward.shape_hidden"]
    from core.config import RESEARCH_G50

    now = rg.gate_config("sr", "per_feature")
    assert sorted(d[0] for d in now.diff(new)) == sorted(RESEARCH_G50)  # G50's adoptions, and nothing else


def test_the_estimate_conditions() -> None:
    cfg = rg.gate_config("sr", "per_feature", estimate="integrated")
    assert cfg.spatial.heading_source == "integrated" and not cfg.spatial.wall_reset
    with pytest.raises(ValueError):
        rg.run_session("sr", "hidden", 1, trials=1, start_estimate="nowhere")


def _estimates_at_trial_starts(start_estimate: str, monkeypatch) -> list:
    """The estimate (x, y) the first tick of each of three trials sees, read before that tick runs."""
    seen = []
    real_run = rg.Engine.run

    def run(self, ticks, *, reset=False):
        if self._ctx_tick_seen is not None and self.value_episode != self._ctx_tick_seen:
            seen.append((self.spatial.state.grid_x, self.spatial.state.grid_y, self.last_action.name))
        self._ctx_tick_seen = None
        return real_run(self, ticks, reset=reset)

    real_reset = rg.Engine.reset_value_episode

    def reset_value_episode(self):
        real_reset(self)
        self._ctx_tick_seen = -1  # the next run call is a trial's first tick

    monkeypatch.setattr(rg.Engine, "_ctx_tick_seen", None, raising=False)
    monkeypatch.setattr(rg.Engine, "run", run)
    monkeypatch.setattr(rg.Engine, "reset_value_episode", reset_value_episode)
    rg.run_session("sr", "visible", 3, trials=3, reward_rule="per_feature", start_estimate=start_estimate, still_start=True)
    return seen


def test_what_the_estimate_is_told_at_a_trial_start(monkeypatch) -> None:
    starts = [rg.STARTS[i][:2] for i in rg.start_order(3, 3)]
    anchor = _estimates_at_trial_starts("anchor", monkeypatch)
    assert [(x, y) for x, y, _ in anchor] == [tuple(s) for s in starts]
    centre = _estimates_at_trial_starts("centre", monkeypatch)
    assert [(x, y) for x, y, _ in centre] == [(0.0, 0.0)] * 3
    carry = _estimates_at_trial_starts("carry", monkeypatch)
    assert all((x, y) != tuple(s) for (x, y, _), s in zip(carry[1:], starts[1:]))  # told nothing
    assert all(a == "REST" for _, _, a in anchor + centre + carry)  # still_start: nothing carried over


# --- barriers (decisions G47) -------------------------------------------------------------------------------------


def test_the_l_layout_blocks_the_west_and_south_starts_only() -> None:
    assert rg.blocked_starts("open") == ()
    assert rg.blocked_starts("L") == (0, 2)
    for b in rg.LAYOUTS["L"]:
        assert not b.contains(*rg.GOAL) and not any(b.contains(x, y) for x, y, _ in rg.STARTS)


def test_a_session_in_the_l_layout_never_enters_a_barrier() -> None:
    real_run = rg.Engine.run
    seen = []

    def run(self, ticks, *, reset=False):
        out = real_run(self, ticks, reset=reset)
        seen.extend(td.pos for td in out)
        return out

    rg.Engine.run = run
    try:
        rg.run_session("none", "visible", 7, trials=4, reward_rule="per_feature", layout="L", still_start=True)
    finally:
        rg.Engine.run = real_run
    assert seen and not any(b.contains(x, y) for x, y in seen for b in rg.LAYOUTS["L"])
