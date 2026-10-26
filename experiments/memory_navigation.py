"""Water-maze-style memory navigation, and what replay buys you.

Paradigm (one agent, several trials, the brain's memory persists between them):

1. **Trial 0 — goal visible.** Vision guides the agent to the goal, laying down
   a trajectory and reward at the goal place.
2. **Sleep.** Optionally (``replay=True``) the trajectory is replayed, which
   consolidates the place-value map by propagating value backward from the goal
   along the path (see ``brain/systems/value_memory.py``).
3. **Trials 1+ — goal hidden.** The goal is invisible to vision, so the agent
   can only reach it by following the learned value map.

Two findings:

* **Repeated recall does not erode the map.** The value map is learned by
  TD(0), so following the gradient on zero-reward steps reinforces it (bootstrap
  on the successor) rather than decaying it toward the immediate zero reward.
  An agent doing repeated hidden-recall trials keeps reaching the goal and gets
  faster as it learns from experience. At sensor noise 0 (this config) every
  seed is the same run, so this is one sample; it also held at noise 0.03 on
  the seeds tried (G12). ``run_memory_navigation_seeds`` (and ``--seeds`` on
  the command line) refuses several seeds on such a config unless told
  ``allow_identical_seeds`` (``--allow-identical-seeds``), see ``core.seeds``.
* **Replay is a modest, fragile data-efficiency speed-up, not a precondition.**
  After a single demonstration both agents reach the hidden goal at the default
  settings. With the default split steering, at the default
  goal (6, 3) the margin is small (13 vs 14 ticks), because the replayed
  gradient points along the start heading and both agents take nearly the same
  straight path. Off axis it is larger: over six goals the replay probes total
  138 ticks against 174 online, e.g. 42 vs 65 at (2, 6)
  (tests/experiments/test_replay_geometry.py). The larger margin seen under
  max-norm steering (14 vs 22 at (6, 3)) was mostly the online agent sitting
  in value-induced REST, not replay; under max-norm replay could also hurt
  (goal (3, 7): 76 vs 36 ticks). The six-goal result holds at noise 0 and
  value_gain 1.4-3.0 but fails at gains 0.8-1.3 (one off-axis replay probe
  times out after a one-action divergence) and under sensor noise 0.03; see
  that test's docstring. In the console's memory maze the first hidden recall
  is slightly *slower* with replay (15 vs 13 ticks at noise 0.03), while later
  recalls are faster (median 10 vs 16) so more fit in a session. (An earlier
  version appeared to show replay as *necessary*, but that was an artifact of
  a deficient online rule that decayed values toward immediate reward.)

This runs at the engine's default spatial resolution, forward bias and
``value_gain`` (1.5); the only memory-system change is ``generalization_radius``,
so a single trajectory fills a followable 2-D value field via overlapping place
fields, plus sparse reward (approach_weight 0).
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from brain.systems.spatial import SpatialState
from core.config import (
    BasalGangliaConfig,
    EngineConfig,
    RewardConfig,
    ValueMemoryConfig,
)
from core.engine import Engine
from core.seeds import require_seeds_are_samples
from core.world import WorldObject

DEFAULT_GOAL: Tuple[float, float] = (6.0, 3.0)
DEFAULT_GOAL_RADIUS = 1.5


def memory_nav_config() -> EngineConfig:
    """Config for the memory-navigation assay.

    Spatial resolution (``bin_size``), ``forward_bias`` and ``value_gain`` (1.5,
    set explicitly here; it predates the engine default becoming 1.5 and now
    equals it) are the engine defaults; the value/memory system only gets
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
            engine.value_memory.consolidate(
                passes=consolidation_passes, dwell_extinction=engine.config.value_memory.dwell_extinction
            )
        engine.value_memory.trajectory.clear()
        trial += 1
    for _ in range(n_recall):
        engine.world.objects[0].kind = "hidden"  # invisible: memory only
        ticks = _run_trial(engine, goal, goal_radius, max_ticks)
        results.append(TrialResult(trial, False, ticks, ticks < max_ticks))
        engine.value_memory.trajectory.clear()
        trial += 1
    return results


def run_memory_navigation_seeds(
    replay: bool,
    seeds: Sequence[int],
    *,
    allow_identical_seeds: bool = False,
    **kwargs: Any,
) -> Dict[int, List[TrialResult]]:
    """``run_memory_navigation`` once per seed, after the pseudo-replication guard.

    With more than one distinct seed the config (``kwargs["config"]`` or
    ``memory_nav_config()``) must have a stochastic element on, or
    ``core.seeds.PseudoReplicationError`` is raised; ``allow_identical_seeds``
    prints a warning and runs them anyway. Returns ``{seed: results}`` in the
    order given.
    """
    config = kwargs.get("config") or memory_nav_config()
    require_seeds_are_samples(config, len(set(seeds)), allow_identical_seeds=allow_identical_seeds)
    return {seed: run_memory_navigation(replay, seed=seed, **kwargs) for seed in seeds}


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Memory navigation with and without replay (one seed by default).")
    parser.add_argument("--seeds", type=int, default=1, help="number of seeds (default 1)")
    parser.add_argument("--seed-start", type=int, default=1337, help="first seed (default 1337)")
    parser.add_argument("--allow-identical-seeds", action="store_true",
                        help="run several seeds although no stochastic element is on (one sample, "
                             "not N; prints a warning instead of refusing, see core.seeds)")
    args = parser.parse_args(argv)
    if args.seeds < 1:
        parser.error("--seeds must be >= 1")
    seeds = range(args.seed_start, args.seed_start + args.seeds)
    for replay in (True, False):
        by_seed = run_memory_navigation_seeds(replay, seeds, allow_identical_seeds=args.allow_identical_seeds)
        tag = "replay   " if replay else "no-replay"
        for seed, rows in by_seed.items():
            summary = [(r.trial, "vis" if r.visible else "hid", r.ticks_to_goal) for r in rows]
            if args.seeds == 1:
                print(tag, summary)  # the output as it was before --seeds existed
            else:
                print(tag, f"seed {seed}", summary)


if __name__ == "__main__":
    main()
