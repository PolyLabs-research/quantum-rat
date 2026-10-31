"""The whole, part 1 (docs/prereg/whole_resource.md): the 27 configurations, the spark's scoring, the verdict, a quick run."""

from __future__ import annotations

import math

from core.config import EngineConfig
from core.engine import Engine
from experiments import whole_resource as wr


def test_the_reward_scale_amendment_a2() -> None:
    scaled = wr.configurations(wr.scaled_parts(7.0))
    assert scaled["whole"]["interoception.reward_scale"] == 7.0 and scaled["base+interoception"]["interoception.reward_scale"] == 7.0
    assert "interoception.reward_scale" not in wr.configurations()["whole"]  # the pilot's and the confirmatory run's, unchanged
    assert "interoception.reward_scale" not in scaled["whole-interoception"] and "interoception.reward_scale" not in scaled["base"]
    from core.engine import Engine
    from core.world import WorldObject

    def meal(scale):
        cfg = wr.engine_config({"interoception.enabled": True, "interoception.reward_scale": scale}, 0.1)
        e = Engine(seed=1, config=cfg)
        e.world.add_object(WorldObject(5.0, 5.0, 0.75, "target"))
        e.run(1, reset=True)
        e.metabolism.reserve = 0.5
        from brain.contracts import Action

        e.agent.pos, e.last_action = (5.0, 5.0), Action(name="REST", thrust=0.0, turn=0.0)
        e.run(1)
        return e.context
    one, seven = meal(1.0), meal(7.0)
    assert one.ingested == seven.ingested == 0.1 and abs(seven.meal_value - 7.0 * one.meal_value) < 1e-12
    assert seven.map_reward == seven.meal_value and seven.incentive == one.incentive  # the incentive is not scaled


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


def _confirm_rows(n=30, survived=True, sd=0.02, level=(0.67, 0.62), moving=(0.3, 0.5), contrast=0.2, eff=6.0):
    full = [{"seed": s, "survived": survived, "energy_sd_late": sd, "energy_mean_late": level[0], "moving_awake": moving[0] + 0.001 * s,
             "hunger_contrast": contrast, "efficiency": eff, "postprandial_rest": 0.8, "sleep_share": 0.2, "meals": 19} for s in range(n)]
    half = [{"seed": s, "survived": survived, "energy_sd_late": sd, "energy_mean_late": level[1], "moving_awake": moving[1] + 0.002 * s,
             "hunger_contrast": contrast, "efficiency": eff, "postprandial_rest": 0.8, "sleep_share": 0.2, "meals": 12} for s in range(n)]
    return full, half


def test_amendment_a1_scoring() -> None:
    assert wr.ENVIRONMENTS["half"] == ((0.0, 6.0), (0.0, -6.0)) and wr.PHASES["confirm"]["seeds"] == tuple(range(13, 43))
    s = wr.score_confirm(*_confirm_rows(), base_spread=0.05, n_boot=200)
    assert s["spark"] and s["R1a"] and s["R1b"] and s["R1c"] and s["R2"] and abs(s["level_drop"] - 0.05) < 1e-9
    assert not wr.score_confirm(*_confirm_rows(sd=0.04), base_spread=0.05, n_boot=200)["R1b"]  # 0.04 > 0.75 x 0.05
    assert not wr.score_confirm(*_confirm_rows(level=(0.67, 0.5)), base_spread=0.05, n_boot=200)["R1c"]  # the level fell 0.17
    assert not wr.score_confirm(*_confirm_rows(moving=(0.5, 0.3)), base_spread=0.05, n_boot=200)["R1c"]  # held it without trying
    assert not wr.score_confirm(*_confirm_rows(contrast=0.1), base_spread=0.05, n_boot=200)["R2"]
    assert not wr.score_confirm(*_confirm_rows(survived=False), base_spread=0.05, n_boot=200)["R1a"]
    assert wr.tercile_contrast([0.1] * 30 + [0.9] * 30 + [0.5] * 30, [False] * 30 + [True] * 30 + [True] * 30, [False] * 90) == 1.0


def test_quick_run(tmp_path) -> None:
    summary = wr.main(["--phase", "pilot", "--quick", "--workers", "1", "--out", str(tmp_path)])
    assert len(summary["scores"]) == 27 and (tmp_path / "runs.csv").exists() and (tmp_path / "energy_trace.csv").exists()
    cal = wr.main(["--phase", "calibrate", "--quick", "--workers", "1", "--out", str(tmp_path / "cal")])
    assert cal["calibration"]["meals"] >= 0 and EngineConfig.research().metabolism.enabled is False
    scale = wr.main(["--phase", "scale", "--quick", "--workers", "1", "--out", str(tmp_path / "scale")])
    assert list(scale["configs"]) == ["whole"] and "reward_scale" in scale["scale"]
    rep = wr.main(["--phase", "repilot", "--quick", "--workers", "1", "--out", str(tmp_path / "rep")])
    assert len(rep["scores"]) == 27 and rep["configs"]["whole"]["interoception.reward_scale"] > 0
    conf = wr.main(["--phase", "confirm", "--quick", "--workers", "1", "--out", str(tmp_path / "conf")])
    assert len(conf["scores"]) == 27 and conf["envs"] == ["full", "half"]
    header = (tmp_path / "conf" / "runs.csv").read_text().splitlines()[0]
    assert header.startswith("config,env,seed") and "hunger_contrast" in header
    pilot_header = (tmp_path / "runs.csv").read_text().splitlines()[0]
    assert pilot_header == ",".join(wr.RUN_COLUMNS)  # the pilot's table keeps its columns
