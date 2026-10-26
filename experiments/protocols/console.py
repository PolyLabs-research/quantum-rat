"""The lab console's scenarios as headless protocols.

One adapter per scenario in ``ui.scenarios``, registered with the headless
runner under ``console_<scenario id>``: ``console_open_field``,
``console_beacon``, ``console_foraging``, ``console_hazard_field``,
``console_hidden_food`` and ``console_memory_maze``. The bare names
(``open_field``, ``beacon``, ``foraging``) stay the existing headless
protocols, which are different experiments with their own configurations.

An adapter runs the scenario exactly as the live console does
(``ui.sim_session.SimSession``): the engine is built from the scenario's own
``EngineConfig`` (``engine_config``), ``scenario.setup`` lays out the arena,
and on every tick the engine steps first and ``scenario.on_tick`` runs after
it, with the engine's tick number. So a headless run of ``console_<id>`` at a
seed writes the same ``ticks.jsonl`` the console would record from a live
session of ``<id>`` at that seed (tests/experiments/test_console_protocols.py
checks this). An adapter never ends a run early: the scenario's own rules
(trials, timeouts, regrowth) are what the console shows, and they keep running.

The run directory gets the usual ``ticks.jsonl``, ``scene.json``,
``summary.json`` and ``manifest.json``, plus ``events.jsonl``: the scenario's
event log (the lines the console's event panel would show), one JSON object
per line with ``tick``, ``text``, ``level`` and ``kind``.

``summary.json`` carries the scenario's own counters, read from its state, its
``status()`` readout as the console shows it, and a ``score``, defined per
scenario as its primary counter: distance travelled (open field), beacons
reached, food collected (foraging, hazard field, hidden food) and hidden-goal
recalls (memory maze). These are the scenario's counts, nothing more: a score
here is a definition for ranking runs, not a claim about the agent.

Scenario actions (the console's buttons, such as "sleep & consolidate now")
are not available headless; a run uses each scenario's defaults.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from core.config import EngineConfig
from experiments.protocols.base import Protocol
from metrics.schema import TickData
from ui.scenarios import Beacon, Foraging, HazardField, HiddenFood, MemoryMaze, OpenField, Scenario, make_scenario

Event = Dict[str, Any]

CONSOLE_PREFIX = "console_"


class ConsoleProtocol(Protocol):
    """Run one console scenario headless, in the live session's order of operations."""

    scenario_id: str = ""

    def __init__(self, config: dict | None = None) -> None:
        if config:
            raise ValueError(f"{self.name} takes no protocol config; the scenario fixes its own layout and settings")
        self.scenario: Scenario = make_scenario(self.scenario_id)
        self.events: List[Event] = []
        self.ticks_run = 0

    def engine_config(self) -> Optional[EngineConfig]:
        """The scenario's own configuration; it wins over the runner's base profile."""
        return self.scenario.config()

    def setup(self, engine: Any) -> None:
        self.scenario.setup(engine)

    def on_tick(self, engine: Any, tickdata: TickData, tick_index: int) -> None:
        # The engine has already stepped (the runner calls engine.run(1) first),
        # as in SimSession._advance; the scenario sees the engine's tick number.
        self.ticks_run += 1
        self.events.extend(self.scenario.on_tick(engine, tickdata.tick))

    def is_done(self, engine: Any, tickdata: TickData, tick_index: int) -> bool:
        return False

    def counters(self) -> Dict[str, Any]:
        """The scenario's own counters, read from its state (JSON-ready)."""
        return {}

    def score(self) -> float:
        """The scenario's primary counter (see the module docstring)."""
        return 0.0

    def summarize(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "ticks_run": self.ticks_run,
            "scenario": self.scenario_id,
            "status": self.scenario.status(),
            # The runner moves this list into events.jsonl (experiments.runner.write_events).
            "events": list(self.events),
        }
        summary.update(self.counters())
        summary["score"] = self.score()
        return summary


class ConsoleOpenField(ConsoleProtocol):
    name = CONSOLE_PREFIX + OpenField.id
    scenario_id = OpenField.id

    def counters(self) -> Dict[str, Any]:
        sc: OpenField = self.scenario  # type: ignore[assignment]
        return {"distance_travelled": float(sc.distance)}

    def score(self) -> float:
        return float(self.scenario.distance)  # type: ignore[attr-defined]


class ConsoleBeacon(ConsoleProtocol):
    name = CONSOLE_PREFIX + Beacon.id
    scenario_id = Beacon.id

    def counters(self) -> Dict[str, Any]:
        sc: Beacon = self.scenario  # type: ignore[assignment]
        return {"beacons_reached": int(sc.visits), "last_time_to_reach": sc.last_time}

    def score(self) -> float:
        return float(self.scenario.visits)  # type: ignore[attr-defined]


class ConsoleForaging(ConsoleProtocol):
    name = CONSOLE_PREFIX + Foraging.id
    scenario_id = Foraging.id

    def counters(self) -> Dict[str, Any]:
        sc: Foraging = self.scenario  # type: ignore[assignment]
        return {
            "collected": int(sc.collected),
            "patches_cleared": int(sc.rounds),
            "last_patch_time": sc.last_round_time,
        }

    def score(self) -> float:
        return float(self.scenario.collected)  # type: ignore[attr-defined]


class ConsoleHazardField(ConsoleProtocol):
    name = CONSOLE_PREFIX + HazardField.id
    scenario_id = HazardField.id

    def counters(self) -> Dict[str, Any]:
        sc: HazardField = self.scenario  # type: ignore[assignment]
        return {"collected": int(sc.collected), "hazard_contacts": int(sc.hurts)}

    def score(self) -> float:
        return float(self.scenario.collected)  # type: ignore[attr-defined]


class ConsoleHiddenFood(ConsoleProtocol):
    name = CONSOLE_PREFIX + HiddenFood.id
    scenario_id = HiddenFood.id

    def counters(self) -> Dict[str, Any]:
        sc: HiddenFood = self.scenario  # type: ignore[assignment]
        return {
            "collected": int(sc.collected),
            "sites_found": int(sc.sites_found()),
            "finds_per_site": [int(n) for n in sc.site_counts],
            "collect_ticks": [int(t) for t in sc.collect_ticks],
            # Collections per 500-tick block over the ticks run (the learning curve).
            "blocks": [int(n) for n in sc.blocks(self.ticks_run)],
        }

    def score(self) -> float:
        return float(self.scenario.collected)  # type: ignore[attr-defined]


class ConsoleMemoryMaze(ConsoleProtocol):
    name = CONSOLE_PREFIX + MemoryMaze.id
    scenario_id = MemoryMaze.id

    def counters(self) -> Dict[str, Any]:
        sc: MemoryMaze = self.scenario  # type: ignore[assignment]
        trials = [dict(h) for h in sc.history]
        hidden = [h for h in trials if not h["visible"]]
        recalls = [h for h in hidden if h["reached"]]
        return {
            "trials": trials,
            "trials_completed": len(trials),
            "hidden_trials": len(hidden),
            "recalls": len(recalls),
            "recall_rate": (len(recalls) / len(hidden)) if hidden else None,
            "last_recall_time": recalls[-1]["ticks"] if recalls else None,
            "trial": int(sc.trial),  # the trial in progress when the run ended
            "goal_visible": bool(sc.goal_visible),
        }

    def score(self) -> float:
        return float(self.counters()["recalls"])


CONSOLE_PROTOCOLS: Dict[str, Type[ConsoleProtocol]] = {
    cls.name: cls
    for cls in (
        ConsoleOpenField,
        ConsoleBeacon,
        ConsoleForaging,
        ConsoleHazardField,
        ConsoleHiddenFood,
        ConsoleMemoryMaze,
    )
}


__all__ = [
    "CONSOLE_PREFIX",
    "CONSOLE_PROTOCOLS",
    "ConsoleProtocol",
    "ConsoleOpenField",
    "ConsoleBeacon",
    "ConsoleForaging",
    "ConsoleHazardField",
    "ConsoleHiddenFood",
    "ConsoleMemoryMaze",
]
