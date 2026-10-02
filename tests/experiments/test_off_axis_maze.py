"""Memory-maze recall from every start heading, including starts facing away from the goal.

Before this guard, the console's memory maze (goal at (6, 3), start (0, 0))
recalled only from start headings within about 0.7 rad of the goal bearing
(0.46 rad): at noise 0, seed 1, 1500 ticks, 4 of 16 headings over the circle
reached the hidden goal on >= 90% of trials. Measured causes:

- The visible trial from a start facing away is a search (34-129 ticks
  instead of 6-9), and TD values fall by the discount 0.9 per step of it, so
  after consolidation the largest value difference the agent can sample at
  the start is 4e-4 to 4e-9 on 11 of the 12 failing headings: below the 1e-3
  at which the map counts as flat, so it gives no direction. Sampling the
  full circle (offsets out to pi) or averaging lookaheads of 1, 2 and 4 m does
  not help (4/16 headings either way): there is no gradient to find.
- During a long search ATP can fall below 0.55. The TRN then narrows the
  sensory gate, and the gate also scales the egomotion fed to path
  integration, so on 7 of the 12 failing headings the agent's internal frame
  had shifted by 1.8-12 m by the time it touched the goal. Whatever it learns
  about the goal's place is then in the wrong place.
- A failed hidden trial runs 300 ticks, so the agent starts the next one
  tired, and recall collapses for the rest of the session.

The fix is two parts, both in ui.scenarios.MemoryMaze.config:
value_memory.goal_vector (sleep replay of the rewarded arrival stores the
goal's place cell; where the map is flat the agent turns toward it) and fatigue
pacing with pace_low 0.6, above the gate's 0.55 threshold. Measured at 1000
ticks (this test), all 16 headings recall on >= 90% of hidden trials (the
tightest is heading 2.75: 14 of 15); with either part removed 7-11 of 16 do.
The recall counts differ a lot between headings (8-128): a long, wandering
demonstration still leaves a slow route where the map is not quite flat
(e.g. heading 5.11: 9 recalls), because the vector only steers where the map
is flat.
"""

from __future__ import annotations

import functools
from typing import Dict, Tuple

import pytest

from experiments.steering_sensitivity import Job, maze_heading_set, run_job

TICKS = 1000
GAIN = 1.5
ABLATIONS = {
    "no goal vector": (("value_memory.goal_vector", False),),
    "pacing below the gate threshold": (("basal_ganglia.pace_low", 0.4),),
    "no pacing": (("basal_ganglia.pace_rest_bonus", 0.0),),
}


@functools.lru_cache(maxsize=None)
def _rows(overrides: Tuple[Tuple[str, object], ...] = ()) -> Tuple[Dict, ...]:
    return tuple(run_job(Job("memory_maze", GAIN, 1, 0.0, TICKS, overrides, h)) for h in maze_heading_set("full"))


def _recalls(row: Dict) -> bool:
    return row["attempted"] >= 3 and row["recall_rate"] >= 0.9


def test_full_circle_heading_set():
    headings = maze_heading_set("full")
    assert len(headings) == 16 and headings[0] == 0.0
    assert max(headings) > 5.8  # covers the circle, including starts facing away from the goal


def test_maze_recalls_from_every_start_heading():
    for row in _rows():
        assert _recalls(row), (round(row["heading"], 2), row["score"], row["attempted"], row["train_ticks"])


@pytest.mark.parametrize("name", sorted(ABLATIONS))
def test_both_parts_of_the_fix_are_needed(name):
    # Measured: 11 / 8 / 7 of 16 headings recall without the goal vector / with
    # pace_low 0.4 / with no pacing.
    failing = sum(not _recalls(row) for row in _rows(ABLATIONS[name]))
    assert failing >= 3, (name, failing)
