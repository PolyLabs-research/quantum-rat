"""Goal-vector extinction in the memory maze: keep a goal that is still there, forget one that moved.

The goal memory (``value_memory.goal_vector``, on in ui.scenarios.MemoryMaze) is
the place cell the agent's estimate was in at first contact, so it straddles
the 1.5 m contact circle: 0-88% of the 0.5 m cell lies outside it, depending
on the start heading. Two bugs erased goals that never moved:

1. Contact reached from the cell next door, on the tick the agent leaves the
   goal cell, was ignored. Maze heading 1.96 (2*pi*5/16), seed 1, noise 0,
   gain 1.5: 10 recalls before, 89 of 89 with the leaving tick counted.
2. One pass through the part of the cell outside the contact circle, without
   contact, erased the goal. Seed 2, heading 3.93 (2*pi*10/16), noise 0.03:
   2 of 5 hidden trials recalled before; 34 of 34 with extinction off.

The rule now (``value_memory.goal_extinction_misses`` = 2): the goal is erased
after two visits in a row that end without target contact, and any contact
resets the count. Measured over the full circle (16 headings at noise 0 with
gains 0.4 / 0.8 / 1.5 / 3.0, and seeds 1-4 at noise 0.03, gain 1.5; 1500
ticks) it gives exactly the runs that extinction off gives (128 of 128 rows
identical). A single miss (with bug 1 fixed) loses heading 5.50 at gains 0.4
and 0.8 (14 and 8 recalls against 56 and 68) and the bug-2 run; three misses
match two on the full circle but forget a moved goal far more slowly (the
moved-goal set-up below over 16 headings at noise 0 and seeds 1-2 at noise
0.03, 4500 ticks: erased a median 720-759 ticks after the move against
157-187, and in 2 of the 32 noisy runs never).

Moved goal (``test_a_moved_goal_is_forgotten``): seed 1, noise 0, the five
start headings facing away from the goal (pi .. 3pi/2, where the map is flat
at the start and the goal vector does the homing). After three hidden
trials the goal moves to (-4, 6). Measured: the old goal is erased 72-421
ticks after the move, and in post-move trials 3-14 the agent runs straight to
the old place (inside its circle within 60 ticks of the start) in 0 of 60
trials (also 0 with a single miss erasing, 2 with three), and with extinction
off (0) in 30 of 60. Bound: erased in all five runs and at most 6 homing
trials; with extinction off that fails.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

import pytest

import ui.scenarios as scenarios_module
from core.engine import Engine
from experiments.steering_sensitivity import Job, run_job
from ui.scenarios import make_scenario

TICKS = 1500
GAIN = 1.5
SINGLE_MISS = (("value_memory.goal_extinction_misses", 1),)
NO_EXTINCTION = (("value_memory.goal_extinction_misses", 0),)


def _maze(seed: int, noise: float, sixteenth: int, overrides=()) -> Dict:
    return run_job(Job("memory_maze", GAIN, seed, noise, TICKS, tuple(overrides), 2 * math.pi * sixteenth / 16))


def _recalls(row: Dict) -> bool:
    return row["attempted"] >= 20 and row["recall_rate"] >= 0.9


def test_contact_from_the_next_cell_keeps_the_goal():
    # Bug 1 alone: even with a single miss erasing, the leaving tick's contact counts.
    for overrides in ((), SINGLE_MISS):
        row = _maze(1, 0.0, 5, overrides)
        assert _recalls(row), (overrides, row["score"], row["attempted"])  # measured 89/89 both


def test_one_pass_outside_the_contact_circle_does_not_erase_the_goal():
    row = _maze(2, 0.03, 10)
    assert _recalls(row), (row["score"], row["attempted"])  # measured 34/34
    single = _maze(2, 0.03, 10, SINGLE_MISS)
    assert not _recalls(single), (single["score"], single["attempted"])  # measured 2/5


OLD_GOAL = (6.0, 3.0)
NEW_GOAL = (-4.0, 6.0)
AWAY_HEADINGS = (8, 9, 10, 11, 12)  # sixteenths of the circle: pi .. 3pi/2
HOMING_TICKS = 60  # a straight run to the old place (recalls before the move take 10-40)
MAX_HOMING = 6


def _moved_goal_run(sixteenth: int, overrides=()) -> Tuple[int | None, List[bool]]:
    """(ticks from the move until the goal memory is erased, per post-move trial: homed on the old place)."""
    saved = scenarios_module.START_POSE
    scenarios_module.START_POSE = (0.0, 0.0, 2 * math.pi * sixteenth / 16)
    try:
        scenario = make_scenario("memory_maze")
        config = scenario.config()
        config.sensors.noise = 0.0
        for key, value in overrides:
            setattr(config.value_memory, key.split(".")[1], value)
        engine = Engine(seed=1, config=config)
        scenario.setup(engine)
        moved_at = erased = first_old = None
        homed: List[bool] = []
        for _ in range(4500):
            tick = engine.run(1)[0].tick
            if moved_at is not None:
                x, y = engine.agent.pos
                if first_old is None and math.hypot(x - OLD_GOAL[0], y - OLD_GOAL[1]) <= scenario.RADIUS:
                    first_old = tick - scenario.trial_start
                if erased is None and engine.value_memory.goal_cell is None:
                    erased = tick - moved_at
            trial = scenario.trial
            scenario.on_tick(engine, tick)
            if moved_at is not None and scenario.trial != trial:
                homed.append(first_old is not None and first_old <= HOMING_TICKS)
                first_old = None
            if moved_at is None and sum(not t["visible"] for t in scenario.history) >= 3:
                assert engine.value_memory.goal_cell is not None
                assert all(t["reached"] for t in scenario.history)
                scenario.goal.x, scenario.goal.y = NEW_GOAL
                moved_at = tick
    finally:
        scenarios_module.START_POSE = saved
    return erased, homed


def _homing(overrides=()) -> Tuple[List[int | None], int]:
    runs = [_moved_goal_run(h, overrides) for h in AWAY_HEADINGS]
    return [erased for erased, _ in runs], sum(sum(homed[2:14]) for _, homed in runs)


def test_a_moved_goal_is_forgotten():
    erased, homing = _homing()
    assert all(e is not None for e in erased), erased  # measured 72-421 ticks after the move
    assert homing <= MAX_HOMING, homing  # measured 0 of 60 trials


def test_without_extinction_the_agent_keeps_homing_on_the_old_place():
    erased, homing = _homing(NO_EXTINCTION)
    assert all(e is None for e in erased)
    assert homing > MAX_HOMING, homing  # measured 30 of 60
