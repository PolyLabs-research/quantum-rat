"""M3 step 2, Part 2's pilot (docs/prereg/m3_step2.md): eight configurations, the draft's bounds and selection rule."""

from __future__ import annotations

import pytest

from experiments import m3_part2 as p


def test_the_configurations() -> None:
    assert len(p.CONFIGS) == 8 and p.CONFIGS["o0_n_L"] == {}  # the research profile as G50 left it
    assert p.CONFIGS["o1_w_S"] == {"basal_ganglia.orient_gain": 1.0, "sensors.fov": 5.235987755982989, "sensors.vision_rays": 11,
                                   "basal_ganglia.wall_avoid_range": 1 / 6, "basal_ganglia.turn_commitment": 0.3}
    assert [p.changes(c) for c in ("o0_n_L", "o1_n_L", "o1_w_S")] == [0, 1, 3]


def _score(name, passed, eligible):
    return {"config": name, "passed": passed, "eligible": eligible, "changes": p.changes(name)}


def test_the_selection_rule() -> None:
    # a reflex lap runner is never chosen, however many bounds it passes
    assert p.select([_score("o1_w_S", 11, False), _score("o0_n_L", 6, True)]) == "o0_n_L"
    # the most bounds, then the fewest changes
    assert p.select([_score("o1_w_L", 9, True), _score("o1_n_L", 9, True), _score("o0_n_L", 8, True)]) == "o1_n_L"
    assert p.select([_score("o1_w_S", 11, False)]) is None


def test_the_scoring_statistics() -> None:
    # G53: traversals per run on the track (the reflex arms at most half the learned arm's) and the control as a margin
    track = [{"config": "c", "arm": a, "traversals": n} for a, n in (("learned", 50), ("no_reward", 20), ("no_steer", 30))]
    gate = [{"config": "c", "condition": cond, "source": src, "session": ses, "success": s}
            for cond in p.GATE for src, ses, s in (("sr", "hidden", 0.9), ("none", "hidden", 0.3), ("sr", "visible", 1.0))]
    s = p.score("c", gate, track, [{"config": "c", "arm": "steer", "finds": 40}])
    assert s["values"]["track_learned"] == 50 and s["passes"]["track_learned"]
    assert s["passes"]["track_reflex_no_reward"] and not s["passes"]["track_reflex_no_steer"] and not s["eligible"]
    assert s["values"]["controls"] == pytest.approx(0.6) and s["passes"]["controls"] and s["passes"]["hidden_food"]


def test_quick_run(tmp_path) -> None:
    summary = p.main(["--quick", "--workers", "1", "--out", str(tmp_path)])
    assert len(summary["scores"]) == 8 and (tmp_path / "track.csv").exists()
