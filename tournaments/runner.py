import argparse
import json
from pathlib import Path

from agents.dna import AgentDNA, generate_population
from tournaments.manager import TournamentManager, PROTOCOLS

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tournament runner for rat brain simulation")
    parser.add_argument("--seed", type=int, default=1337, help="Main seed for the tournament")
    parser.add_argument("--n-agents", type=int, default=8, help="Number of agents to generate if --agents-json is not provided")
    parser.add_argument("--ticks", type=int, default=500, help="Number of ticks per episode")
    parser.add_argument("--out", type=str, required=True, help="Output directory for tournament results")
    parser.add_argument("--protocols", type=str, required=True, help=f"Comma-separated list of protocols to run. Available: {', '.join(sorted(PROTOCOLS.keys()))}")
    parser.add_argument("--agents-json", type=str, help="Path to a JSON file containing a list of AgentDNA")
    parser.add_argument("--include-ticks", action="store_true", help="Include tick data in the output (can be very large)")
    return parser.parse_args()

def main() -> None:
    args = parse_args()

    outdir = Path(args.out)

    if args.agents_json:
        with open(args.agents_json, "r") as f:
            agents_data = json.load(f)
        agents = [AgentDNA.from_json(json.dumps(data)) for data in agents_data]
        agents_source = f"file: {args.agents_json}"
    else:
        agents = generate_population(args.seed, args.n_agents)
        agents_source = f"generated from seed {args.seed} (n_agents {args.n_agents})"

    protocol_names = [p.strip() for p in args.protocols.split(",")]
    for p_name in protocol_names:
        if p_name not in PROTOCOLS:
            raise ValueError(f"Protocol '{p_name}' not found. Available: {', '.join(sorted(PROTOCOLS.keys()))}")

    protocols = [{"name": p, "ticks": args.ticks} for p in protocol_names]

    manager = TournamentManager(
        seed=args.seed,
        agents=agents,
        protocols=protocols,
        outdir=outdir,
        include_ticks=args.include_ticks,
        manifest_extra={"agents_source": agents_source},  # provenance only (manifest.json)
    )
    manager.run()
    print(f"Tournament finished. Results are in {outdir}")

if __name__ == "__main__":
    main()
