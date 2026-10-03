"""Behavioural guards for memory steering: the outcome, not the mechanism.

The unit tests in tests/engine pin each steering component; these pin what
the components are for. They run the lab-console scenarios headless through
the sensitivity harness (experiments/steering_sensitivity.py) with short
budgets at sensor noise 0 and two start headings, so the whole file takes a few
seconds:

- foraging and hazard_field, with homeostatic pacing on (the console scenario
  configs) and off (``pace_rest_bonus=0``, the core-engine energy policy):
  the summed score at value_gain 1.5 (the default) and 3.0 is at least 80% of
  the score with memory off (value_gain 0), i.e. at gains 1.5 and 3.0 memory
  steering costs at most ~20% outside the maze. Tightest measured margin:
  foraging with pacing off at gain 3.0, 35 vs 39 items (0.897; it was 33,
  0.846, before microsleep replayed the recent path, value_memory.replay_recent);
- value-induced REST (``is_value_rest``) stays at or below 0.15 of ticks in
  every one of those runs;
- memory_maze keeps a hidden-goal recall rate >= 0.9 at gains 0.8, 1.5 and 3.0
  (this one does not discriminate: max-norm recalls at these gains too), and
  the number of recalls at gains 0.4 and 0.6 stays >= 80% of that at 1.5
  (measured 0.90 / 0.89; stock-like steering 0.57 / 0.62 fails it).
  The maze runs its console config, which since the off-axis fix includes
  the goal vector and pacing (ui.scenarios.MemoryMaze.config); at these
  near-axis headings that changes nothing at the defaults, but it does raise
  the regressed configurations' low-gain recalls (numbers below).

Checked against regressions (each by flipping config defaults):
- ``value_steer="maxnorm"`` with ``dwell_extinction=0`` (stock-like steering):
  6 of 13 fail with the gates on. vREST is 0.18-0.65 in all four
  foraging / hazard_field cells, and foraging with pacing off scores 25 vs 39
  with memory off (0.64; 26 with the legacy replay indexing). The maze
  recall-rate guard still passes, but the
  low-gain recall-count guard fails: 0.57 / 0.62 at gains 0.4 / 0.6 with the
  cue and wall gates off (both cases fail), and only the gain-0.4 case with
  them on (0.51 / 0.86). ``value_steer="maxnorm"`` alone gives 0.59 / 0.92, so
  its gain-0.4 case fails (measured after goal extinction needed two misses,
  value_memory.goal_extinction_misses; with one they were 0.53 / 0.56,
  0.49 / 0.82 and 0.54 / 0.92). Before the maze gained the goal vector and
  pacing these were 0.53 / 0.38 and 0.25 / 0.65.
- ``wall_gate_gain=0`` alone: foraging with pacing off fails (the agent is
  pinned against the wall at heading 0: 29 vs 39).
- ``dwell_extinction=0`` alone, under split steering: all pass. Under split,
  a value-map local maximum never lowers FORWARD, so REST can win because of
  value only in rare states where FORWARD is already below REST; measured
  value-induced REST is 0 at gains 0.4-3.0, so in these short runs extinction
  is not what holds the outcome.

These tests pin the legacy profile (EngineConfig() defaults); see docs/decisions.md G22 and docs/profiles.md.
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
LOW_GAIN_HEADINGS = (-0.2, 0.0, 0.2)
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


@functools.lru_cache(maxsize=None)
def _maze_recalls(gain: float) -> int:
    return sum(run_job(Job("memory_maze", gain, 1, 0.0, MAZE_TICKS, (), h))["score"] for h in LOW_GAIN_HEADINGS)


@pytest.mark.parametrize("gain", [0.4, 0.6])
def test_maze_recalls_hold_at_low_gain(gain):
    # Recall *rate* stays near 1 even when steering collapses (the agent still
    # reaches the goal, just on far fewer trials), so this guards the number of
    # recalls in the session instead. Summed over three headings, the recalls at
    # a low gain must be at least 80% of those at the default gain. Measured
    # (800 ticks, noise 0): split steering 217 / 215 vs 242 at 1.5 (0.90 /
    # 0.89); stock-like steering (max-norm, no extinction, no gates) 0.57 /
    # 0.62 and max-norm alone 0.59 / 0.92, so both fail (at gain 0.4). These
    # are with the maze's goal vector and pacing; without them (before the
    # off-axis fix) they were 0.53 / 0.38 and 0.25 / 0.65.
    default = _maze_recalls(1.5)
    assert _maze_recalls(gain) >= MIN_FRACTION * default, (gain, _maze_recalls(gain), default)
