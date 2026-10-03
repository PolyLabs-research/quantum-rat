
import subprocess
import tempfile
import json
from pathlib import Path

def run_tournament(seed: int, n_agents: int, ticks: int, protocols: str, out_dir: Path) -> None:
    """Helper to run the tournament CLI."""
    cmd = [
        "python3",
        "-m",
        "tournaments.runner",
        "--seed", str(seed),
        "--n-agents", str(n_agents),
        "--ticks", str(ticks),
        "--protocols", protocols,
        "--out", str(out_dir),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def test_tournament_determinism():
    """
    Runs a tournament twice with the same config and asserts that the outputs are identical.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir1 = Path(tmpdir) / "run1"
        out_dir2 = Path(tmpdir) / "run2"

        seed = 42
        n_agents = 4
        ticks = 200
        protocols = "open_field,beacon,foraging"

        run_tournament(seed, n_agents, ticks, protocols, out_dir1)
        run_tournament(seed, n_agents, ticks, protocols, out_dir2)

        # Compare leaderboards
        leaderboard1 = (out_dir1 / "leaderboard.json").read_text()
        leaderboard2 = (out_dir2 / "leaderboard.json").read_text()
        assert leaderboard1 == leaderboard2

        # Compare agents.json
        agents1 = (out_dir1 / "agents.json").read_text()
        agents2 = (out_dir2 / "agents.json").read_text()
        assert agents1 == agents2

        # Check top 3 results
        lb1_data = json.loads(leaderboard1)
        lb2_data = json.loads(leaderboard2)

        assert len(lb1_data) >= 3
        assert len(lb2_data) >= 3

        for i in range(3):
            assert lb1_data[i]["agent_id"] == lb2_data[i]["agent_id"]
            assert lb1_data[i]["total_score"] == lb2_data[i]["total_score"]
