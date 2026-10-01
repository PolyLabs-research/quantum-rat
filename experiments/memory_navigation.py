"""Water-maze-style memory navigation: does replay let the agent return to a
hidden goal from memory?

Paradigm (one agent, several trials, the brain's memory persists between them):

1. **Trial 0 — goal visible.** Vision guides the agent to the goal, laying down
   a trajectory and a reward at the goal place.
2. **Sleep.** Optionally (``replay=True``) the trajectory is replayed, which
   consolidates the place-value map -- propagating value backward from the goal
   along the path (see ``brain/systems/value_memory.py``).
3. **Trials 1+ — goal hidden.** The goal is invisible to vision, so the agent
   can only reach it by following the consolidated value map.

With replay the agent navigates back to the hidden goal; without it (no
consolidation) the thin online map does not generalise and the agent does not.

This runs at the engine's default spatial resolution and forward bias; it only
turns up the value/memory system (higher ``value_gain`` so the map can steer
against the forward drive, and ``generalization_radius`` so a single trajectory
fills a followable 2-D value field via overlapping place fields). Without value
generalization a lone trajectory is a thin one-cell path the agent falls off,
so this is where spatial generalization earns its place.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from brain.systems.spatial import SpatialState
from core.config import (
    BasalGangliaConfig,
    EngineConfig,
    RewardConfig,
    ValueMemoryConfig,
)
from core.engine import Engine
from core.world import WorldObject

DEFAULT_GOAL: Tuple[float, float] = (6.0, 3.0)
DEFAULT_GOAL_RADIUS = 1.5


def memory_nav_config() -> EngineConfig:
    """Config for the memory-navigation assay.

    Spatial resolution (``bin_size``) and ``forward_bias`` are the engine
    defaults; only the value/memory system is turned up: a higher ``value_gain``
    so the learned map can steer against the forward drive, and
    ``generalization_radius`` so a single trajectory fills a followable 2-D value
    field (overlapping place fields) rather than a thin one-cell path. Sparse
    reward (approach_weight 0) isolates replay's contribution: only the goal
    place is valued online, so the backward gradient comes from consolidation.
    """
    return EngineConfig(
        reward=RewardConfig(approach_weight=0.0, contact_bonus=1.0, pain_weight=1.0),
        basal_ganglia=BasalGangliaConfig(value_gain=1.5),
        value_memory=ValueMemoryConfig(generalization_radius=2),
    )


@dataclass
class TrialResult:
    trial: int
    visible: bool
    ticks_to_goal: int
    reached: bool


def _run_trial(engine: Engine, goal: Tuple[float, float], goal_radius: float, max_ticks: int) -> int:
    # Return the agent to the start with a fresh internal frame; keep its memory.
    engine.agent.pos = (0.0, 0.0)
    engine.agent.heading = 0.0
    engine.agent.last_pos = (0.0, 0.0)
    engine.agent.last_heading = 0.0
    engine.spatial.state = SpatialState()
    first = True
    for i in range(max_ticks):
        engine.run(1, reset=first)
        first = False
        if math.hypot(engine.agent.pos[0] - goal[0], engine.agent.pos[1] - goal[1]) <= goal_radius:
            return i + 1
    return max_ticks


def run_memory_navigation(
    replay: bool,
    *,
    seed: int = 1337,
    n_train: int = 1,
    n_recall: int = 1,
    max_ticks: int = 200,
    goal: Tuple[float, float] = DEFAULT_GOAL,
    goal_radius: float = DEFAULT_GOAL_RADIUS,
    consolidation_passes: int = 60,
    config: Optional[EngineConfig] = None,
) -> List[TrialResult]:
    """Run ``n_train`` visible training trials then ``n_recall`` hidden probes.

    Consolidation (replay) happens only after the visible training trials, so the
    probe measures recall of the consolidated demonstration rather than learning
    during the probe itself.
    """
    config = config or memory_nav_config()
    engine = Engine(seed=seed, config=config)
    engine.world.add_object(WorldObject(goal[0], goal[1], goal_radius, "target"))

    results: List[TrialResult] = []
    trial = 0
    for _ in range(n_train):
        engine.world.objects[0].kind = "target"  # visible: vision guides the agent
        ticks = _run_trial(engine, goal, goal_radius, max_ticks)
        results.append(TrialResult(trial, True, ticks, ticks < max_ticks))
        if replay:
            engine.value_memory.consolidate(passes=consolidation_passes)
        engine.value_memory.trajectory.clear()
        trial += 1
    for _ in range(n_recall):
        engine.world.objects[0].kind = "hidden"  # invisible: memory only
        ticks = _run_trial(engine, goal, goal_radius, max_ticks)
        results.append(TrialResult(trial, False, ticks, ticks < max_ticks))
        engine.value_memory.trajectory.clear()
        trial += 1
    return results


def main() -> None:
    for replay in (True, False):
        rows = run_memory_navigation(replay)
        tag = "replay   " if replay else "no-replay"
        summary = [(r.trial, "vis" if r.visible else "hid", r.ticks_to_goal) for r in rows]
        print(tag, summary)


if __name__ == "__main__":
    main()
