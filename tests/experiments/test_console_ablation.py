"""The matched-seed memory-steering ablation (experiments.console_ablation), on a quick run (G40)."""

import csv
import json

import pytest

from experiments import console_ablation as ca


def test_arms_differ_in_the_value_gain_only_and_overrides_apply_to_both():
    _, steer = ca.arm_config("hidden_food", "research", "steer", {"sensors.noise": 0.03})
    _, none = ca.arm_config("hidden_food", "research", "no_steer", {"sensors.noise": 0.03})
    assert [d[0] for d in steer.diff(none)] == ["basal_ganglia.value_gain"] and none.basal_ganglia.value_gain == 0.0
    assert steer.sensors.noise == none.sensors.noise == 0.03 and steer.profile == "research" and steer.place.enabled
    assert ca.parse_seeds("1-3,7") == (1, 2, 3, 7) and ca.parse_set(["a.b=0.5", "c.d=abc"]) == {"a.b": 0.5, "c.d": "abc"}


@pytest.fixture(scope="module")
def quick(tmp_path_factory):
    out = tmp_path_factory.mktemp("ablation")
    return out, ca.main(["--quick", "--scenario", "hidden_food", "--profile", "research", "--workers", "1", "--n-boot", "200",
                         "--keep-records", "--out", str(out)])


def test_quick_run_writes_its_files_and_pairs_the_arms(quick):
    out, summary = quick
    assert set(ca.OUTPUT_FILES) <= {p.name for p in out.iterdir()}
    assert summary["seeds"] == [1, 2] and summary["ticks"] == ca.QUICK_TICKS and summary["profile"] == "research"
    assert set(summary["effects"]) == set(ca.METRICS) and set(summary["per_arm_means"]) == set(ca.ARMS)
    rows = list(csv.DictReader(open(out / "ablation_per_seed.csv", newline="", encoding="utf-8")))
    assert {r["condition"] for r in rows} == set(ca.ARMS) and len(rows) == 2 * 2 * len(ca.METRICS)
    assert list(csv.DictReader(open(out / "ablation_bouts.csv", newline="", encoding="utf-8")).fieldnames) == list(ca.BOUT_COLUMNS)
    assert (out / "decisions_steer_s1.jsonl").exists() and (out / "decisions_no_steer_s2.jsonl").exists()
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["config"]["profile"] == "research" and manifest["arms"] == ca.ARMS and manifest["ticks_run"] == 2 * 2 * ca.QUICK_TICKS
    finds = summary["effects"]["finds"]
    assert "mean_diff" in finds and finds["n"] == 2
    assert summary["guard"] == 2  # two distinct trajectories on the steer arm


def test_the_guard_refuses_identical_seeds_on_legacy_without_noise(tmp_path):
    with pytest.raises(SystemExit):
        ca.main(["--quick", "--scenario", "open_field", "--profile", "legacy", "--workers", "1", "--n-boot", "100", "--out", str(tmp_path)])
    summary = ca.main(["--quick", "--scenario", "open_field", "--profile", "legacy", "--workers", "1", "--n-boot", "100",
                       "--allow-identical-seeds", "--out", str(tmp_path)])
    assert isinstance(summary["guard"], str) and "identical" in summary["guard"]
