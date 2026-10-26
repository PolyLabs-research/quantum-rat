import json
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.dna import AgentDNA
from agents.agent import Agent
from core.config import EngineConfig
from experiments.runner import PROTOCOLS, write_events
from core.engine import Engine
from metrics.manifest import build_manifest, finish_manifest, write_manifest

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

    # A protocol that supplies its own configuration (the console_* adapters)
    # gets it; otherwise the engine's defaults, as before. The agent's genes
    # are applied on top either way.
    engine = Engine(seed=episode_seed, agent_offset=agent_offset, config=protocol.engine_config())

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
    write_events(outdir, summary)  # only a protocol that logs events (console_*) writes events.jsonl
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
    def __init__(
        self,
        seed: int,
        agents: List[AgentDNA],
        protocols: List[dict],
        outdir: Path,
        include_ticks: bool = False,
        manifest_extra: Optional[Dict[str, Any]] = None,
    ):
        self.seed = seed
        self.agents = sorted(agents, key=lambda a: a.agent_id)
        self.protocols = protocols
        self.outdir = outdir
        self.include_ticks = include_ticks
        # Extra provenance for manifest.json (e.g. where the population came from).
        self.manifest_extra = dict(manifest_extra or {})
        self.leaderboard: list = []

    def _manifest(self) -> Dict[str, Any]:
        """The tournament's provenance manifest, before it runs (metrics.manifest).

        ``config`` is the base ``EngineConfig()`` every episode starts from;
        each agent's genes then modify ``basal_ganglia`` (agents.json), and a
        protocol that supplies its own configuration (console_*) replaces the
        base for its episodes. ``episode_seeds`` are the per-protocol seeds
        every agent shares (fairness: only agent offsets differ).
        """
        ticks_requested = len(self.agents) * sum(int(p["ticks"]) for p in self.protocols)
        extra: Dict[str, Any] = {
            "n_agents": len(self.agents),
            "agents": [{"agent_id": a.agent_id, "agent_fingerprint": a.fingerprint()} for a in self.agents],
            "protocols": [dict(p) for p in self.protocols],
            "episode_seeds": {p["name"]: stable_hash(self.seed, p["name"]) for p in self.protocols},
            "include_ticks": bool(self.include_ticks),
            "config_note": (
                "the base configuration of every episode; each agent's genes modify basal_ganglia "
                "(agents.json), and a protocol that supplies its own configuration (console_*) "
                "replaces the base for its episodes"
            ),
        }
        extra.update(self.manifest_extra)
        return build_manifest(
            EngineConfig(),
            protocol="tournament",
            seeds=[self.seed],
            ticks_requested=ticks_requested,
            extra=extra,
        )

    def run(self):
        self.outdir.mkdir(parents=True, exist_ok=True)
        manifest = self._manifest()
        started = time.perf_counter()
        ticks_run_total = 0

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
                ticks_run_total += int(summary.get("ticks_run", 0))

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

        # Provenance at the tournament root: not read by anything, not compared
        # by the regression harness (it skips manifest.json), the one file here
        # with wall-clock time in it.
        finish_manifest(manifest, ticks_run=ticks_run_total, wall_seconds=time.perf_counter() - started)
        write_manifest(self.outdir / "manifest.json", manifest)
