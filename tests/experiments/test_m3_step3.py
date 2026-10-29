"""M3 step 3's pilot (docs/prereg/m3_step3.md): the configurations, the selection rule, a quick run."""

from __future__ import annotations

from core.config import EngineConfig
from core.engine import Engine
from experiments import m3_part2 as p2
from experiments import m3_step3 as s3


def test_the_configurations_and_the_base() -> None:
    assert set(s3.CONFIGS) == {"research", "q_none", "q_uniform", "q_reverse", "q_reverse_oracle"}
    assert s3.BASE == {"place.reward_step_cap": True} and "history.enabled" not in s3.BASE  # the profile as G54 left it
    assert s3.LEARNER_CONFIGS == ("q_none", "q_uniform", "q_reverse") and s3.CONFIGS["q_reverse_oracle"]["action_value.oracle_state"]
    for ov in s3.CONFIGS.values():
        cfg = EngineConfig.research()
        for k, v in {**s3.BASE, **ov}.items():
            cfg.set_field(k, v)
        e = Engine(seed=1, config=cfg)
        e.run(2)
        assert e.history is not None and (e.action_learner is not None) == ("action_value.enabled" in ov)


def _score(name, passed, track_ok):
    return {"config": name, "passed": passed, "eligible": track_ok,
            "passes": {b: track_ok for b in s3.TRACK_BOUNDS}}


def test_the_selection_rule() -> None:
    assert s3.select([_score("research", 11, True), _score("q_reverse_oracle", 11, True), _score("q_none", 9, False)]) is None
    assert s3.select([_score("q_uniform", 10, True), _score("q_reverse", 10, True), _score("q_none", 9, True)]) == "q_reverse"
    assert s3.select([_score("q_uniform", 11, True), _score("q_reverse", 10, True)]) == "q_uniform"


def test_quick_run(tmp_path) -> None:
    result = s3.main(["--quick", "--workers", "1", "--out", str(tmp_path)])
    assert len(result["scores"]) == 5 and (tmp_path / "track.csv").exists() and "replay_events" in (tmp_path / "track.csv").read_text().splitlines()[0]
    assert all(b in result["track"]["q_reverse"]["learned"] for b in ("replay_events", "rest_share")) and p2.BOUNDS[0] == "track_learned"
