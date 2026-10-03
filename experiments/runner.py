"""Headless experiment runner: one protocol, one seed, one run directory.

A run directory holds ``ticks.jsonl`` (one TickData per line), ``scene.json``
(the arena layout for the replay viewer), ``summary.json`` (the protocol's
summary plus the run hash) and ``manifest.json`` (provenance: code, config,
seeds, platform, wall-clock; see ``metrics.manifest``). A protocol whose
summary carries an ``events`` list (the console adapters,
``experiments.protocols.console``) also gets ``events.jsonl``. A run in which
replay happened (microsleep replay, ``brain.systems.replay_events``) also gets
``replay_events.jsonl``, one finished replay event per line, written as the
events close so a long run is not capped by the engine's bounded log; the
summary's ``n_replay_events`` counts them (0, and no file, when none occurred;
a replay still in progress when the run stops is not an event).

The engine's configuration comes from the protocol when it supplies one
(``Protocol.engine_config``), else from the base profile: ``--profile legacy``
(the ``EngineConfig()`` defaults) or ``--profile research``.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, TextIO, Type

from brain.systems.replay_events import REPLAY_EVENTS_FILE
from core.config import EngineConfig
from core.engine import Engine
from experiments.protocols.base import Protocol
from experiments.protocols.beacon import BeaconProtocol
from experiments.protocols.console import CONSOLE_PROTOCOLS
from experiments.protocols.foraging import ForagingProtocol
from experiments.protocols.open_field import OpenFieldProtocol
from experiments.protocols.t_maze_toy import TMazeProtocol
from experiments.protocols.morris_water_maze_toy import MorrisWaterMazeProtocol
from experiments.protocols.survival_arena_toy import SurvivalArenaProtocol
from metrics.hash import RunHash
from metrics.logger import JsonlLogger, _canonical_json
from metrics.manifest import build_manifest, finish_manifest, write_manifest
from metrics.scene import write_scene
from metrics.schema import SCHEMA_VERSION, TickData


PROTOCOLS: Dict[str, Type[Protocol]] = {
    "beacon": BeaconProtocol,
    "foraging": ForagingProtocol,
    "open_field": OpenFieldProtocol,
    "t_maze_toy": TMazeProtocol,
    "morris_water_maze_toy": MorrisWaterMazeProtocol,
    "survival_arena_toy": SurvivalArenaProtocol,
    # The lab console's scenarios, run headless (console_open_field, console_beacon, ...).
    **CONSOLE_PROTOCOLS,
}

PROFILES: Dict[str, Any] = {
    "legacy": EngineConfig.legacy,
    "research": EngineConfig.research,
}
DEFAULT_PROFILE = "legacy"

EVENTS_FILE = "events.jsonl"


def list_protocols() -> str:
    return "\n".join(sorted(PROTOCOLS.keys()))


def base_config(profile: str) -> EngineConfig:
    """A fresh ``EngineConfig`` for a named profile (``legacy`` or ``research``)."""
    try:
        factory = PROFILES[profile]
    except KeyError:
        raise ValueError(f"Unknown profile {profile!r}; choose one of {', '.join(sorted(PROFILES))}") from None
    return factory()


def write_events(outdir: Path, summary: Dict[str, Any]) -> Optional[int]:
    """Move a summary's ``events`` list into ``events.jsonl``.

    A protocol that logs events (the console adapters) returns them from
    ``summarize`` under ``events``; they go to ``events.jsonl`` in ``outdir``,
    one JSON object per line, and the summary keeps only ``n_events`` so
    ``summary.json`` stays small. Returns the number of events written, or
    None when the summary has no ``events`` key (then nothing is written).
    """
    events = summary.pop("events", None)
    if events is None:
        return None
    with open(Path(outdir) / EVENTS_FILE, "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(_canonical_json(event) + "\n")
    summary["n_events"] = len(events)
    return len(events)


class ReplayEventWriter:
    """Writes the engine's finished replay events to ``replay_events.jsonl`` as they close.

    ``drain(engine)`` empties ``engine.replay_log`` into the file (opened on the
    first event, so the file exists only when a replay happened) and ``count``
    is how many were written. Call it every tick: the log is bounded, and
    draining it keeps a long run from losing its oldest events.
    """

    def __init__(self, outdir: Path) -> None:
        self.path = Path(outdir) / REPLAY_EVENTS_FILE
        self.count = 0
        self._fh: Optional[TextIO] = None

    def drain(self, engine: Engine) -> int:
        written = 0
        for event in engine.replay_log.drain():
            if self._fh is None:
                self._fh = open(self.path, "w", encoding="utf-8")
            self._fh.write(_canonical_json(event.to_dict()) + "\n")
            written += 1
        self.count += written
        return written

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Headless experiment runner")
    parser.add_argument("--protocol", choices=sorted(PROTOCOLS.keys()))
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--ticks", type=int, default=1000)
    parser.add_argument("--out", type=str, required=False)
    parser.add_argument("--list", action="store_true", help="List available protocols")
    parser.add_argument("--protocol-config", type=str, help="Path to JSON protocol config")
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES.keys()),
        default=DEFAULT_PROFILE,
        help=(
            "Base engine profile (default: %(default)s) for protocols that do not supply their own "
            "configuration. The console_* protocols supply the scenario's own configuration, which "
            "wins over this option; the manifest records both the profile that ran and the one requested."
        ),
    )
    return parser.parse_args()


def run(
    protocol_name: str,
    seed: int,
    ticks: int,
    outdir: Path,
    protocol_config: dict | None = None,
    *,
    profile: str = DEFAULT_PROFILE,
) -> None:
    proto_cls = PROTOCOLS[protocol_name]
    protocol = proto_cls(protocol_config)
    config = protocol.engine_config()
    if config is None:
        config = base_config(profile)
    engine = Engine(seed=seed, config=config)
    protocol.setup(engine)

    outdir.mkdir(parents=True, exist_ok=True)
    tick_path = outdir / "ticks.jsonl"
    summary_path = outdir / "summary.json"
    write_scene(engine, outdir / "scene.json", {"protocol": protocol_name})
    manifest = build_manifest(
        engine.config,
        protocol=protocol_name,
        seeds=[seed],
        ticks_requested=ticks,
        extra={"profile_requested": profile, "protocol_config": protocol_config or {}},
    )

    logger = JsonlLogger(tick_path)
    rh = RunHash()
    replay_events = ReplayEventWriter(outdir)

    ticks_run_actual = 0
    started = time.perf_counter()
    for i in range(ticks):
        tickdata_list = engine.run(1)
        tick = tickdata_list[0]
        ticks_run_actual += 1
        protocol.on_tick(engine, tick, i)
        replay_events.drain(engine)  # after on_tick, so a protocol may read the log first
        logger.write_tick(tick)
        rh.update(tick)
        if protocol.is_done(engine, tick, i):
            break
    wall_seconds = time.perf_counter() - started
    logger.close()
    replay_events.close()

    summary = protocol.summarize()
    write_events(outdir, summary)
    summary.update(
        {
            "protocol": protocol_name,
            "seed": seed,
            "ticks_requested": ticks,
            "ticks_run": ticks_run_actual,
            "schema_version": SCHEMA_VERSION,
            "run_hash": rh.hexdigest(),
            "protocol_config": protocol_config or {},
            "n_replay_events": replay_events.count,
        }
    )
    summary_path.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    finish_manifest(manifest, ticks_run=ticks_run_actual, wall_seconds=wall_seconds)
    write_manifest(outdir / "manifest.json", manifest)


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
    run(args.protocol, args.seed, args.ticks, outdir, protocol_config=protocol_config, profile=args.profile)


if __name__ == "__main__":
    main()
