from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Type

from experiments.protocols.base import Protocol
from experiments.protocols.beacon import BeaconProtocol
from experiments.protocols.open_field import OpenFieldProtocol
from experiments.protocols.t_maze import TMazeProtocol
from experiments.protocols.morris_water_maze import MorrisWaterMazeProtocol
from experiments.protocols.survival_arena import SurvivalArenaProtocol
from metrics.hash import RunHash
from metrics.logger import JsonlLogger
from metrics.schema import SCHEMA_VERSION, TickData
from core.engine import Engine


PROTOCOLS: Dict[str, Type[Protocol]] = {
    "beacon": BeaconProtocol,
    "open_field": OpenFieldProtocol,
    "t_maze": TMazeProtocol,
    "morris_water_maze": MorrisWaterMazeProtocol,
    "survival_arena": SurvivalArenaProtocol,
}


def list_protocols() -> str:
    return "\n".join(sorted(PROTOCOLS.keys()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Headless experiment runner")
    parser.add_argument("--protocol", choices=sorted(PROTOCOLS.keys()))
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--ticks", type=int, default=1000)
    parser.add_argument("--out", type=str, required=False)
    parser.add_argument("--list", action="store_true", help="List available protocols")
    parser.add_argument("--protocol-config", type=str, help="Path to JSON protocol config")
    return parser.parse_args()


def run(protocol_name: str, seed: int, ticks: int, outdir: Path, protocol_config: dict | None = None) -> None:
    proto_cls = PROTOCOLS[protocol_name]
    protocol = proto_cls(protocol_config)
    engine = Engine(seed=seed)
    protocol.setup(engine)

    outdir.mkdir(parents=True, exist_ok=True)
    tick_path = outdir / "ticks.jsonl"
    summary_path = outdir / "summary.json"

    logger = JsonlLogger(tick_path)
    rh = RunHash()

    ticks_run_actual = 0
    for i in range(ticks):
        tickdata_list = engine.run(1)
        tick = tickdata_list[0]
        ticks_run_actual += 1
        protocol.on_tick(engine, tick, i)
        logger.write_tick(tick)
        rh.update(tick)
        if protocol.is_done(engine, tick, i):
            break
    logger.close()

    summary = protocol.summarize()
    summary.update(
        {
            "protocol": protocol_name,
            "seed": seed,
            "ticks_requested": ticks,
            "ticks_run": ticks_run_actual,
            "schema_version": SCHEMA_VERSION,
            "run_hash": rh.hexdigest(),
            "protocol_config": protocol_config or {},
        }
    )
    summary_path.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")))


def main() -> None:
    args = parse_args()
    if args.list:
        print(list_protocols())
        return
    if not args.protocol:
        raise SystemExit("Protocol required unless --list is used")
    protocol_config = None
    if args.protocol_config:
        protocol_config = json.loads(Path(args.protocol_config).read_text())
    outdir = Path(args.out) if args.out else Path(f"runs/{args.protocol}_{args.seed}")
    run(args.protocol, args.seed, args.ticks, outdir, protocol_config=protocol_config)


if __name__ == "__main__":
    main()
