import json
import tempfile
from pathlib import Path

from experiments.runner import run


def load_summary(protocol: str, ticks: int = 200):
    with tempfile.TemporaryDirectory() as d:
        outdir = Path(d)
        run(protocol, seed=123, ticks=ticks, outdir=outdir)
        return json.loads(Path(outdir, "summary.json").read_text())


def test_morris_water_maze_toy_summary_keys():
    summary = load_summary("morris_water_maze_toy", ticks=200)
    for key in ["platform_reached", "time_to_platform", "path_length", "score"]:
        assert key in summary


def test_survival_arena_toy_summary_keys():
    summary = load_summary("survival_arena_toy", ticks=200)
    for key in ["dead", "ticks_run", "hazard_ticks", "damage", "score"]:
        assert key in summary
