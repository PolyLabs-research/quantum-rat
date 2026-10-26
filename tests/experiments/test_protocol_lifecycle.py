import json
import tempfile
from pathlib import Path

from experiments.runner import run


def _run_protocol(name: str):
    with tempfile.TemporaryDirectory() as d:
        outdir = Path(d)
        run(name, seed=42, ticks=200, outdir=outdir)
        tick_lines = Path(outdir, "ticks.jsonl").read_text().splitlines()
        summary = json.loads(Path(outdir, "summary.json").read_text())
        return tick_lines, summary


def test_protocol_lifecycle_open_field():
    tick_lines, summary = _run_protocol("open_field")
    assert 0 < len(tick_lines) <= 200
    assert summary["ticks_run"] == len(tick_lines)
    for key in ["ticks_run", "distance_travelled", "exploration_score", "score"]:
        assert key in summary


def test_protocol_lifecycle_t_maze_toy():
    tick_lines, summary = _run_protocol("t_maze_toy")
    assert 0 < len(tick_lines) <= 200
    assert summary["ticks_run"] == len(tick_lines)
    for key in ["ticks_run", "reward_reached", "time_to_reward", "score"]:
        assert key in summary


def test_protocol_lifecycle_morris_water_maze_toy():
    tick_lines, summary = _run_protocol("morris_water_maze_toy")
    assert 0 < len(tick_lines) <= 200
    assert summary["ticks_run"] == len(tick_lines)
    for key in ["ticks_run", "platform_reached", "time_to_platform", "path_length", "score"]:
        assert key in summary


def test_protocol_lifecycle_survival_arena_toy():
    tick_lines, summary = _run_protocol("survival_arena_toy")
    assert 0 < len(tick_lines) <= 200
    assert summary["ticks_run"] == len(tick_lines)
    for key in ["ticks_run", "dead", "hazard_ticks", "safe_ticks", "damage", "score"]:
        assert key in summary
