"""The unlearning-rate experiment (experiments.sr_unlearning), on a quick run (G41, docs/prereg/sr_unlearning_rate.md)."""

import csv
import json

import pytest

from experiments import console_ablation as ca
from experiments import sr_unlearning as su


def test_the_arms_and_the_pilot_rule():
    arms = su.arms_for((1.0, 2.0))
    assert list(arms) == ["no_steer", "u0.5", "u1", "u2"]
    assert arms["u0.5"] == {"place.reward_unlearning_rate": 0.5} and arms["u2"] == {"place.reward_unlearning_rate": 2.0}
    _, baseline = ca.arm_config(su.SCENARIO, su.PROFILE, "u0.5", {}, arms)
    _, fast = ca.arm_config(su.SCENARIO, su.PROFILE, "u2", {}, arms)
    assert [d[0] for d in baseline.diff(fast)] == ["place.reward_unlearning_rate"]
    assert baseline.place.reward_rule == "per_feature" and baseline.value_memory.source == "sr"
    means = {"u1": {"finds": 20.0}, "u2": {"finds": 24.0}, "u4": {"finds": 24.0}}
    assert su.choose_rate(means, (1.0, 2.0, 4.0)) == 2.0  # a tie goes to the smaller U
    assert su.PILOT_SEEDS == tuple(range(1, 9)) and su.CONFIRMATORY_SEEDS == tuple(range(9, 17))
    assert not set(su.PILOT_SEEDS) & set(su.CONFIRMATORY_SEEDS)


@pytest.fixture(scope="module")
def pilot(tmp_path_factory):
    out = tmp_path_factory.mktemp("unlearning")
    return out, su.main(["--phase", "pilot", "--quick", "--rates", "2", "--workers", "1", "--n-boot", "200", "--out", str(out)])


def test_a_quick_pilot_writes_its_files_and_chooses_a_rate(pilot):
    out, summary = pilot
    assert set(su.OUTPUT_FILES) <= {p.name for p in out.iterdir()}
    assert summary["phase"] == "pilot" and summary["seeds"] == [1, 2] and summary["rates"] == [2.0] and summary["chosen_rate"] == 2.0
    assert set(summary["per_arm_means"]) == {"no_steer", "u0.5", "u2"}
    assert set(summary["effects"]["u2"]) == {"vs_baseline", "vs_no_steer"} and "vs_no_steer" in summary["effects"]["u0.5"]
    assert {k for k in summary["bounds"] if k.startswith("K")} == {"K1_finds_vs_baseline", "K2_memory_orbit_ticks", "K3_finds_vs_no_steer"}
    rows = list(csv.DictReader(open(out / "unlearning_per_seed.csv", newline="", encoding="utf-8")))
    assert {r["condition"] for r in rows} == {"no_steer", "u0.5", "u2"}
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["phase"] == "pilot" and manifest["config"]["place"]["reward_unlearning_rate"] == 2.0


def test_the_confirmatory_phase_needs_a_rate_and_records_the_preregistration(tmp_path):
    with pytest.raises(SystemExit):
        su.main(["--phase", "confirmatory", "--quick", "--workers", "1", "--out", str(tmp_path)])
    summary = su.main(["--phase", "confirmatory", "--quick", "--unlearning", "2", "--prereg", "docs/prereg/sr_unlearning_rate.md",
                       "--workers", "1", "--n-boot", "200", "--out", str(tmp_path)])
    assert summary["phase"] == "confirmatory" and summary["prereg"] == "docs/prereg/sr_unlearning_rate.md"
    assert summary["bounds"]["arm"] == "u2" and isinstance(summary["bounds"]["K1_finds_vs_baseline"]["passes"], bool)
    assert json.loads((tmp_path / "manifest.json").read_text())["prereg"] == "docs/prereg/sr_unlearning_rate.md"
