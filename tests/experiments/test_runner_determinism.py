import json
import tempfile
from pathlib import Path

from experiments.runner import run


def assert_deterministic(protocol: str, seed: int, ticks: int):
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        run(protocol, seed=seed, ticks=ticks, outdir=Path(d1))
        run(protocol, seed=seed, ticks=ticks, outdir=Path(d2))

        summary1 = json.loads(Path(d1, "summary.json").read_text())
        summary2 = json.loads(Path(d2, "summary.json").read_text())
        assert summary1 == summary2

        ticks1 = Path(d1, "ticks.jsonl").read_text().splitlines()[:50]
        ticks2 = Path(d2, "ticks.jsonl").read_text().splitlines()[:50]
        assert ticks1 == ticks2


def test_open_field_runner_deterministic():
    assert_deterministic("open_field", seed=1337, ticks=300)


def test_morris_water_maze_toy_runner_deterministic():
    assert_deterministic("morris_water_maze_toy", seed=1337, ticks=300)


def test_survival_arena_toy_runner_deterministic():
    assert_deterministic("survival_arena_toy", seed=1337, ticks=300)
