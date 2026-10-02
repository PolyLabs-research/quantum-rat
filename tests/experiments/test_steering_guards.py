"""Behavioural guards for memory steering: the outcome, not the mechanism.

The unit tests in tests/engine pin each steering component; these pin what
the components are for. They run the lab-console scenarios headless through
the sensitivity harness (experiments/steering_sensitivity.py) with short
budgets at sensor noise 0 and two start headings, so the whole file takes a few
seconds:

- foraging and hazard_field, with homeostatic pacing on (the console scenario
  configs) and off (``pace_rest_bonus=0``, the core-engine energy policy):
  the summed score at value_gain 1.5 (the default) and 3.0 is at least 80% of
  the score with memory off (value_gain 0), i.e. memory steering never costs
  more than ~20% outside the maze, whatever its gain;
- value-induced REST (``is_value_rest``) stays at or below 0.15 of ticks in
  every one of those runs;
- memory_maze keeps a hidden-goal recall rate >= 0.9 at gains 0.8, 1.5 and 3.0.

Checked against regressions (each by flipping config defaults):
- ``value_steer="maxnorm"`` with ``dwell_extinction=0`` (stock-like steering,
  with or without wall gating): 5 of 11 fail. vREST is 0.18-0.65 in all four
  foraging / hazard_field cells, and foraging with pacing off scores 26 vs 39
  with memory off (0.67). The maze guard still passes: max-norm with the
  maze's own config recalls at these gains on these two headings.
- ``wall_gate_gain=0`` alone: foraging with pacing off fails (the agent is
  pinned against the wall at heading 0: 29 vs 39).
- ``dwell_extinction=0`` alone, under split steering: all pass. Split steering
  makes value-induced REST impossible by construction, so in these short runs
  extinction is not what holds the outcome.
"""

from __future__ import annotations

import functools
import math
from typing import Dict, Tuple

import pytest

from experiments.steering_sensitivity import Job, run_job

TICKS = 1500
MAZE_TICKS = 800
HEADINGS = (0.0, math.pi / 2)
MAZE_HEADINGS = (-0.2, 0.2)
PACING = {"on": (), "off": (("basal_ganglia.pace_rest_bonus", 0.0),)}
MAX_VREST = 0.15
MIN_FRACTION = 0.8


@functools.lru_cache(maxsize=None)
def _rows(scenario: str, gain: float, pacing: str) -> Tuple[Dict, ...]:
    return tuple(run_job(Job(scenario, gain, 1, 0.0, TICKS, PACING[pacing], h)) for h in HEADINGS)


@pytest.mark.parametrize("pacing", ["on", "off"])
@pytest.mark.parametrize("scenario", ["foraging", "hazard_field"])
def test_memory_never_costs_more_than_a_fifth_outside_the_maze(scenario, pacing):
    memory_off = sum(r["score"] for r in _rows(scenario, 0.0, pacing))
    assert memory_off > 0
    for gain in (1.5, 3.0):
        score = sum(r["score"] for r in _rows(scenario, gain, pacing))
        assert score >= MIN_FRACTION * memory_off, (scenario, pacing, gain, score, memory_off)


@pytest.mark.parametrize("pacing", ["on", "off"])
@pytest.mark.parametrize("scenario", ["foraging", "hazard_field"])
def test_value_induced_rest_stays_rare(scenario, pacing):
    for gain in (1.5, 3.0):
        for row in _rows(scenario, gain, pacing):
            assert row["vrest"] <= MAX_VREST, (scenario, pacing, gain, row["heading"], row["vrest"])


@pytest.mark.parametrize("gain", [0.8, 1.5, 3.0])
def test_maze_recall_holds_across_gains(gain):
    for heading in MAZE_HEADINGS:
        row = run_job(Job("memory_maze", gain, 1, 0.0, MAZE_TICKS, (), heading))
        assert row["attempted"] >= 20, row
        assert row["recall_rate"] >= 0.9, (gain, heading, row)
