"""AgentDNA must actually change behaviour, or tournaments rank nothing.

Before this was wired, ``configure_engine`` was a no-op and every agent ran
the identical brain, so the leaderboard reflected only RNG offset.
"""

import tempfile
from pathlib import Path

from agents.dna import generate_population
from tournaments.manager import TournamentManager


def test_population_is_seed_deterministic_and_seed_sensitive():
    a = [d.params for d in generate_population(1, 4)]
    b = [d.params for d in generate_population(1, 4)]
    c = [d.params for d in generate_population(2, 4)]
    assert a == b  # same seed -> same population
    assert a != c  # different seed -> different population


def test_dna_spreads_the_leaderboard():
    with tempfile.TemporaryDirectory() as d:
        pop = generate_population(seed=1337, n=4)
        mgr = TournamentManager(
            seed=1337,
            agents=pop,
            protocols=[{"name": "open_field", "ticks": 120}, {"name": "beacon", "ticks": 120}],
            outdir=Path(d),
        )
        mgr.run()
        scores = [round(r["total_score"], 4) for r in mgr.leaderboard]
        # Agents differ behaviourally, so the leaderboard is not a flat tie.
        assert len(set(scores)) > 1
