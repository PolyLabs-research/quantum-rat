"""Replay's data-efficiency advantage over several goal geometries.

tests/experiments/test_memory_navigation.py checks one geometry, goal (6, 3),
where the replayed gradient points almost along the start heading: the replay
agent and the one-demonstration online agent take nearly the same straight
path, so under split steering the margin there is 1 tick (13 vs 14). Under
max-norm steering that test used to pass by 8 ticks, but the margin was the
online agent sitting in value-induced REST at its weak peak, not replay
helping; and with max-norm replay sometimes hurt (goal (3, 7): 76 ticks, 34 of
them REST, vs 36 online).

This test asks the question over six goals, on axis and off it, at the
default memory_nav_config (start heading 0, seed 1337): one visible
demonstration, then one hidden probe, with or without 60 consolidation passes
in between. Measured probe ticks (replay / online):

    (6, 3)  13 / 14      (6, -3) 11 / 14      (4, 5)  30 / 36
    (2, 6)  42 / 65      (7, 0)   9 /  9      (3, 7)  33 / 36
    total  138 / 174

so at these settings replay is no slower on any of the six goals (one tie)
and faster on five, most clearly off axis.

This is a single deterministic sample, and it is fragile; the assertions are
the ones asked for, not tuned to pass. Measured on the same goals
(replay / online totals, probes that time out at 200 counted as 200):
- value_gain: every gain from 0.8 to 1.3 fails the same way. The replay
  probe to (6, -3) takes one different action at tick 3 (FORWARD instead of
  TURN_LEFT), passes about 0.3 outside the goal disk, leaves the valued field
  and times out (326 / 174). Gains 1.4-1.6 give 138 / 174 and 1.7-3.0 give
  145-147 / 174. The default 1.5 sits only about 0.1 above that edge;
- split dead zone 0.12 instead of 0.1: (6, -3) times out again (334 / 174);
- max-norm steering: 192 / 166, replay <= online on 3 of 6;
- sensor noise 0.03: the visible demonstration to the off-axis goals wanders
  (104-123 ticks instead of 29-30) and both arms then time out on (4, 5),
  (2, 6) and (3, 7); on (6, -3) replay times out while online takes 10.

These tests pin the legacy profile (EngineConfig() defaults); see docs/decisions.md G22 and docs/profiles.md.
"""

from experiments.memory_navigation import run_memory_navigation

GOALS = [(6.0, 3.0), (6.0, -3.0), (4.0, 5.0), (2.0, 6.0), (7.0, 0.0), (3.0, 7.0)]


def _probe(goal, replay):
    results = run_memory_navigation(replay=replay, n_recall=1, goal=goal)
    train = next(r for r in results if r.visible)
    probe = next(r for r in results if not r.visible)
    assert train.reached, (goal, replay, train)
    return probe


def test_replay_beats_online_learning_across_goal_geometries():
    ticks = {}
    for goal in GOALS:
        with_replay, online = _probe(goal, True), _probe(goal, False)
        assert with_replay.reached and online.reached, (goal, with_replay, online)
        ticks[goal] = (with_replay.ticks_to_goal, online.ticks_to_goal)
    total_replay = sum(r for r, _ in ticks.values())
    total_online = sum(o for _, o in ticks.values())
    assert total_replay < total_online, ticks
    assert sum(r <= o for r, o in ticks.values()) >= 4, ticks
