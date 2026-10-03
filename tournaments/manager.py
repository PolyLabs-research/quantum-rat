
import json
import hashlib
from pathlib import Path
from typing import List

from agents.dna import AgentDNA
from agents.agent import Agent
from experiments.runner import PROTOCOLS
from core.engine import Engine

def stable_hash(*args):
    """
    Creates a stable hash from the given arguments.
    """
    s = "|".join(map(str, args))
    return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8], "big") % 2**31

def run_episode(
    protocol_name: str,
    seed: int,
    ticks: int,
    outdir: Path,
    agent_offset: int,
    agent_dna: AgentDNA,
    include_ticks: bool = False,
) -> dict:
    """
    Runs a single episode for an agent and returns the summary.
    """
    proto_cls = PROTOCOLS[protocol_name]
    protocol = proto_cls()
    
    episode_seed = stable_hash(seed, protocol_name)

    engine = Engine(seed=episode_seed, agent_offset=agent_offset)

    agent = Agent(dna=agent_dna)
    agent.configure_engine(engine)

    protocol.setup(engine)

    from metrics.hash import RunHash
    from metrics.schema import SCHEMA_VERSION
    from metrics.logger import JsonlLogger

    rh = RunHash()
    
    logger = None
    if include_ticks:
        from metrics.scene import write_scene

        write_scene(engine, outdir / "scene.json", {"protocol": protocol_name})
        tick_path = outdir / "ticks.jsonl"
        logger = JsonlLogger(tick_path)

    ticks_run_actual = 0
    for i in range(ticks):
        tickdata_list = engine.run(1)
        if not tickdata_list:
            break
        tick = tickdata_list[0]
        ticks_run_actual += 1
        protocol.on_tick(engine, tick, i)
        rh.update(tick)
        if logger:
            logger.write_tick(tick)
        if protocol.is_done(engine, tick, i):
            break
    
    if logger:
        logger.close()

    summary = protocol.summarize()
    summary.update(
        {
            "protocol": protocol_name,
            "seed": episode_seed,
            "agent_offset": agent_offset,
            "agent_id": agent_dna.agent_id,
            "agent_fingerprint": agent_dna.fingerprint(),
            "ticks_requested": ticks,
            "ticks_run": ticks_run_actual,
            "schema_version": SCHEMA_VERSION,
            "run_hash": rh.hexdigest(),
        }
    )
    return summary


class TournamentManager:
    def __init__(self, seed: int, agents: List[AgentDNA], protocols: List[dict], outdir: Path, include_ticks: bool = False):
        self.seed = seed
        self.agents = sorted(agents, key=lambda a: a.agent_id)
        self.protocols = protocols
        self.outdir = outdir
        self.include_ticks = include_ticks
        self.leaderboard: list = []

    def run(self):
        self.outdir.mkdir(parents=True, exist_ok=True)
        
        # Save config and agents.json
        config_path = self.outdir / "config.json"
        config = {"seed": self.seed, "protocols": self.protocols}
        config_path.write_text(json.dumps(config, sort_keys=True, separators=(",", ":")))
        
        agents_json_path = self.outdir / "agents.json"
        agent_data = [json.loads(dna.to_json()) for dna in self.agents]
        agents_json_path.write_text(json.dumps(agent_data, sort_keys=True, separators=(",", ":")))


        agent_results = {agent.agent_id: {"total_score": 0, "protocols": {}} for agent in self.agents}

        for i, agent_dna in enumerate(self.agents):
            agent_outdir = self.outdir / "agents" / agent_dna.agent_id
            agent_outdir.mkdir(parents=True, exist_ok=True)
            
            for protocol_spec in self.protocols:
                protocol_name = protocol_spec["name"]
                ticks = protocol_spec["ticks"]
                weight = protocol_spec.get("weight", 1.0)

                protocol_outdir = agent_outdir / protocol_name
                protocol_outdir.mkdir(exist_ok=True)

                # The agent_offset is the agent's index in the sorted list
                agent_offset = i
                
                summary = run_episode(protocol_name, self.seed, ticks, protocol_outdir, agent_offset, agent_dna, self.include_ticks)
                
                score = summary.get("score", 0)
                agent_results[agent_dna.agent_id]["total_score"] += score * weight
                agent_results[agent_dna.agent_id]["protocols"][protocol_name] = summary
                
                # Write summary to file
                summary_path = protocol_outdir / "summary.json"
                summary_path.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")))

            # Write aggregated results for the agent
            agent_results_path = agent_outdir / "results.json"
            agent_results_path.write_text(json.dumps(agent_results[agent_dna.agent_id], sort_keys=True, separators=(",", ":")))

        # Build leaderboard
        leaderboard_data = []
        for agent_dna in self.agents:
            fingerprint = agent_dna.fingerprint()
            result = agent_results[agent_dna.agent_id]
            leaderboard_data.append(
                {
                    "agent_id": agent_dna.agent_id,
                    "agent_fingerprint": fingerprint,
                    "total_score": result["total_score"],
                    "protocols": {p["name"]: result["protocols"].get(p["name"], {}) for p in self.protocols}
                }
            )

        # Sort leaderboard by score (desc), then by fingerprint (asc) for tie-breaking
        self.leaderboard = sorted(leaderboard_data, key=lambda x: (-x["total_score"], x["agent_fingerprint"]))
        
        leaderboard_path = self.outdir / "leaderboard.json"
        leaderboard_path.write_text(json.dumps(self.leaderboard, sort_keys=True, separators=(",", ":")))
