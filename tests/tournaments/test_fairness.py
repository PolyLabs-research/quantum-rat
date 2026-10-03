
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

def test_seeding_fairness():
    """
    Tests that the same protocol seed is used across agents, and only agent_offset differs.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "run"

        seed = 1337
        n_agents = 4
        ticks = 10
        protocols = "open_field,beacon,foraging"

        run_tournament(seed, n_agents, ticks, protocols, out_dir)

        # Collect all summaries
        summaries = []
        for agent_dir in (out_dir / "agents").iterdir():
            if not agent_dir.is_dir():
                continue
            for protocol_dir in agent_dir.iterdir():
                if not protocol_dir.is_dir():
                    continue
                summary_path = protocol_dir / "summary.json"
                if summary_path.exists():
                    summaries.append(json.loads(summary_path.read_text()))

        assert len(summaries) == n_agents * len(protocols.split(","))

        # Check seeds per protocol
        seeds_per_protocol = {}
        offsets_per_protocol = {}

        for summary in summaries:
            proto = summary["protocol"]
            if proto not in seeds_per_protocol:
                seeds_per_protocol[proto] = []
                offsets_per_protocol[proto] = []
            
            seeds_per_protocol[proto].append(summary["seed"])
            offsets_per_protocol[proto].append(summary["agent_offset"])

        for proto in seeds_per_protocol:
            # All seeds for a given protocol should be the same
            assert len(set(seeds_per_protocol[proto])) == 1
            
            # All offsets for a given protocol should be unique and cover the range of agents
            assert len(set(offsets_per_protocol[proto])) == n_agents
            assert set(offsets_per_protocol[proto]) == set(range(n_agents))
