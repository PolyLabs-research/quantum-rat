"""The fast-schema confirmation (docs/prereg/history_fast_schema.md): fresh seeds, two arms, the bounds as preregistered."""

from __future__ import annotations

from experiments import history_fast_schema as fs
from experiments import m3_part2 as p2


def test_the_registration() -> None:
    from core.config import PRE_G54

    assert fs.CONFIGS["none"] == PRE_G54 and fs.CONFIGS["fast"]["history.schema"] == {"taste": (-1.0, 0.0, 0.0)}
    assert fs.CONFIGS["fast"]["history.reward_context"] == ("taste",) and "motivation.enabled" not in fs.CONFIGS["fast"]
    spent_gate = set(range(1, 245))
    assert not (set(fs.SEEDS["gate_seeds"]) & spent_gate) and not (set(fs.SEEDS["track_seeds"]) & spent_gate)
    assert not (set(fs.SEEDS["food_seeds"]) & set(range(1, 47)))


def test_the_bounds_read_the_tables() -> None:
    seeds = {"gate_seeds": (1, 2, 3), "track_seeds": (1, 2, 3), "food_seeds": (1, 2, 3)}
    food = [{"config": c, "arm": a, "seed": s, "finds": f} for s in (1, 2, 3) for c, a, f in
            (("none", "steer", 40 + s), ("fast", "steer", 45 + s), ("none", "no_steer", 50), ("fast", "no_steer", 50))]
    track = [{"config": c, "arm": "learned", "seed": s, "traversals": t, "rewards": 10} for s in (1, 2, 3) for c, t in (("none", 30), ("fast", 33 + s))]
    gate = [{"config": c, "condition": cond, "source": src, "session": ses, "seed": s, "success": v}
            for s in (1, 2, 3) for (cond, src, ses) in fs.GATE_VALUES.values() for c, v in (("none", 1.0), ("fast", 0.99))]
    v = fs.bounds(gate, track, food, seeds, n_boot=100)
    assert v["K1_finds_steer"]["mean_diff"] == 5.0 and v["K1_finds_steer"]["passes"]
    assert v["K2_passes"] and all(abs(e["mean_diff"] + 0.01) < 1e-9 for e in v["K2_gate_no_loss"].values())
    assert v["K3_track_traversals"]["passes"] and v["K3_track_traversals"]["bound"] == -3.0


def test_quick_run(tmp_path) -> None:
    result = fs.main(["--quick", "--workers", "1", "--out", str(tmp_path)])
    assert set(result["bounds"]) == {"K1_finds_steer", "K2_gate_no_loss", "K2_passes", "K3_track_traversals", "reported"}
    assert len(result["scores"]) == 2 and (tmp_path / "manifest.json").exists() and p2.QUICK["food_seeds"] == (1,)
