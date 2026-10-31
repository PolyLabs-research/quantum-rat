"""The whole, part 1 (docs/prereg/whole_resource.md): the 27 configurations, the spark's scoring, the verdict, a quick run."""

from __future__ import annotations

import math

from core.config import EngineConfig
from core.engine import Engine
from experiments import whole_resource as wr


def test_the_configurations() -> None:
    configs = wr.configurations()
    assert len(wr.PARTS) == 12 and len(configs) == 27
    assert configs["base"] == wr.BASE and configs["whole"] == wr.whole()
    assert configs["whole_nomemory"]["basal_ganglia.value_gain"] == 0.0
    for name in wr.PARTS:  # removing a part leaves none of its own fields set differently from the base's
        minus = configs[f"whole-{name}"]
        assert all(minus.get(k) == configs["whole"].get(k) for k in minus)
    assert not configs["whole-dopamine"]["neuromod.dopamine"] if "neuromod.dopamine" in configs["whole-dopamine"] else True
    assert configs["whole-dopamine"]["neuromod.model"] == "biological"  # the other three modulators keep the model on
    for ov in configs.values():  # every one builds and runs
        e = Engine(seed=1, config=wr.engine_config(ov, 0.1))
        e.run(2)
        assert e.metabolism is not None


def _rows(name, n=12, survived=True, dev=0.1, hungry=(0.3, 0.9), sated=(0.3, 0.2), eff=1.0):
    return [{"config": name, "seed": s, "survived": survived, "mean_dev_late": dev, "hungry_share": hungry[0],
             "moving_hungry": hungry[1], "sated_share": sated[0], "moving_sated": sated[1], "efficiency": eff, "meals": 10,
             "sleep_share": 0.0, "low_share": 0.0, "postprandial_rest": 0.5} for s in range(n)]


def test_the_spark_and_the_verdict() -> None:
    good = wr.score(_rows("w"))
    assert good["spark"] and good["R1a"] and good["R1b"] and good["R2"] and good["activity_contrast"] == 0.7
    assert not wr.score(_rows("w", dev=0.2))["spark"]  # R1(b)
    assert not wr.score(_rows("w", survived=False))["spark"]  # R1(a)
    assert not wr.score(_rows("w", sated=(0.01, 0.2)))["R2"]  # too few seeds in both states
    bad = wr.score(_rows("b", dev=0.3, sated=(0.3, 0.9)))
    scores = {"base": bad, "whole": good, "whole_nomemory": wr.score(_rows("n", eff=0.5))}
    for p in wr.PARTS:
        scores[f"base+{p}"] = bad
        scores[f"whole-{p}"] = bad if p in ("interoception", "motivation") else good
    v = wr.verdict(scores)
    assert v["1_whole_shows_the_spark"] and v["2_no_single_addition_shows_it"] and not v["3_most_removals_break_it"]
    assert v["removals_that_break_it"] == ["interoception", "motivation"] and v["R3_memory_margin"]
    assert math.isclose(v["synergy"]["whole_gain"], 0.2) and v["synergy"]["sum_of_single_gains"] == 0.0


def test_quick_run(tmp_path) -> None:
    summary = wr.main(["--phase", "pilot", "--quick", "--workers", "1", "--out", str(tmp_path)])
    assert len(summary["scores"]) == 27 and (tmp_path / "runs.csv").exists() and (tmp_path / "energy_trace.csv").exists()
    cal = wr.main(["--phase", "calibrate", "--quick", "--workers", "1", "--out", str(tmp_path / "cal")])
    assert cal["calibration"]["meals"] >= 0 and EngineConfig.research().metabolism.enabled is False
