"""Gain x need replay and its ablations (brain/systems/replay_gain_need.py), with the track as the model
(experiments.linear_track_replay.TrackModel; docs/prereg/rq1_track_gain_need.md).

Each test is named for what it proves: the model's structure and policy, that gain is the expected policy
improvement at the predecessors and is non-negative, that the argmax picks the consume first after a reward and
then walks the lap backward, the tie rule, that no draw is taken from the replay stream, and the three modes.
"""

from __future__ import annotations

import math

import pytest

from brain.systems.basal_ganglia import softmax_sample
from brain.systems.replay_gain_need import MODES, GainNeedReplay, gain_of
from brain.systems.replay_rules import StoredTransition, TransitionMemory, replay, replay_thresholded
from core.rng import RNG
from experiments import linear_track_replay as lt

CFG = lt.TrackConfig(n_bins=8, laps=4, lap_cap=200, backups_per_trigger=6, memory_capacity=100, pre_run_pause=True)


def _setup():
    track = lt.LinearTrack(CFG)
    agent = lt.TrackAgent(CFG, track)
    model = lt.TrackModel(CFG, track, agent)
    return track, agent, model


def _store_lap(track, agent, cells, goal, lap=0):
    """Store a straight lap through ``cells`` toward ``goal`` (the last cell), with its consume, learning online."""
    heading = goal
    states = [lt.State(c, heading, goal) for c in cells]
    for k in range(len(states) - 1):
        agent.store_and_learn(states[k], 0.0, states[k + 1], False, lap, k)
    agent.store_and_learn(states[-1], track.reward(goal), states[-1], True, lap, len(states) - 1)
    return states


def test_the_track_model_has_the_lap_structure_and_the_agents_policy() -> None:
    track, agent, model = _setup()
    assert track.n_states == 32
    for s in track.states():
        i = track.index(s)
        succ = model.successors(i)
        assert set(succ) == {"FORWARD", "TURN"}
        assert all((i, a) in model.predecessors(succ[a]) for a in succ)  # every successor lists this state as a predecessor
    # A state in the middle of the track has three predecessors: FORWARD from behind, TURN from the same cell facing away,
    # and nothing else; a state against its wall adds itself (FORWARD blocked).
    mid = track.index(lt.State(4, lt.EAST, lt.EAST))
    assert sorted(model.predecessors(mid)) == sorted([(track.index(lt.State(3, lt.EAST, lt.EAST)), "FORWARD"), (track.index(lt.State(4, lt.WEST, lt.EAST)), "TURN")])
    wall = track.index(lt.State(7, lt.EAST, lt.EAST))
    assert (wall, "FORWARD") in model.predecessors(wall)
    # The policy is the softmax softmax_sample draws from: probabilities sum to 1 and match its frequencies.
    values = {i: 0.0 for i in range(track.n_states)}
    values[track.index(lt.State(5, lt.EAST, lt.EAST))] = 0.05
    p = track.index(lt.State(4, lt.EAST, lt.EAST))
    scores = model.action_scores(p, values)
    assert scores == {"FORWARD": pytest.approx(CFG.forward_prior + 0.5), "TURN": 0.0}
    pi = model.policy(scores)
    assert sum(pi.values()) == pytest.approx(1.0) and pi["FORWARD"] > 0.99
    stream = RNG(3).stream("x")
    draws = [softmax_sample(scores, CFG.temperature, stream, order=lt.ACTIONS) for _ in range(5000)]
    assert abs(draws.count("FORWARD") / 5000 - pi["FORWARD"]) < 0.01
    assert model.learning_rate == CFG.learning_rate
    # Need comes from the SR, initialised from the cyclic structure: positive everywhere, self-occupancy at least 1.
    start = track.index(track.start_state(lt.WEST))
    assert model.need(start, start) >= 1.0
    # Every state of the lap structure has positive need from the start, except the two a lap can never enter: a
    # goal state facing away from its goal (the goal state's only successor is the next lap's start).
    unreachable = {track.index(lt.State(7, lt.WEST, lt.EAST)), track.index(lt.State(0, lt.EAST, lt.WEST))}
    zero = {i for i in range(track.n_states) if model.need(start, i) == 0.0}
    assert zero == unreachable
    assert model.need(start, track.index(lt.State(3, lt.WEST, lt.WEST))) > model.need(start, track.index(lt.State(3, lt.EAST, lt.EAST)))
    # The cyclic structure: a goal state's only successor is the next lap's start; probabilities sum to 1 everywhere.
    cyc = track.cyclic_transitions()
    assert cyc[track.index(lt.State(7, lt.EAST, lt.EAST))] == {track.index(track.start_state(lt.WEST)): 1.0}
    assert all(abs(sum(v.values()) - 1.0) < 1e-12 for v in cyc.values())


def test_gain_is_the_expected_improvement_at_the_predecessors_and_never_negative() -> None:
    track, agent, model = _setup()
    goal = track.index(lt.State(7, lt.EAST, lt.EAST))
    # A fresh table: moving V(goal) up by lr * 1 makes FORWARD at cell 6 more attractive: positive gain.
    g = gain_of(model, goal, 1.0)
    assert g > 0.0
    # By hand at the predecessor (6, east): old scores (prior, 0) -> new (prior + 10 * 0.2, 0).
    p6 = track.index(lt.State(6, lt.EAST, lt.EAST))
    old = model.policy(model.action_scores(p6, {i: 0.0 for i in range(track.n_states)}))
    values = {i: 0.0 for i in range(track.n_states)}
    values[goal] = 0.2
    new = model.policy(model.action_scores(p6, values))
    by_hand_p6 = (new["FORWARD"] - old["FORWARD"]) * 0.2 + (new["TURN"] - old["TURN"]) * 0.0
    # The other predecessors (the goal facing west via TURN, the goal itself via the blocked FORWARD) add their own.
    assert g >= by_hand_p6 - 1e-12 and by_hand_p6 > 0.0
    # A zero TD error moves nothing: zero gain; a negative error gives a non-negative gain too.
    assert gain_of(model, goal, 0.0) == pytest.approx(0.0)
    agent.learner.values[agent.learner.cell(*track.position(lt.State(7, lt.EAST, lt.EAST)))] = 1.0
    assert gain_of(model, goal, -0.75) >= 0.0


def test_argmax_takes_the_consume_first_after_a_reward_then_walks_the_lap_backward_without_a_draw() -> None:
    track, agent, model = _setup()
    _store_lap(track, agent, list(range(8)), lt.EAST)  # an eastward lap from cell 0 to the goal at 7
    model.set_acting(track.start_state(lt.WEST))
    stream = RNG(1).stream("replay")
    before = stream.getstate()
    rule = GainNeedReplay(model, "gain_need")
    outcome = replay(rule, agent.memory, agent.learner, 6, 0, stream, tick=0, travel_sign=1)
    assert stream.getstate() == before  # no draw
    cells = [t.cell[0] for t in outcome.transitions]
    # The first pick is at the goal end (the consume's online backup has already decided the goal's neighbour, so
    # the largest gain is one transition back), and the walk runs backward along the straight lap.
    assert cells[0] in (6, 7)
    assert outcome.event.direction == "reverse" and outcome.sequence_r < 0.0
    assert all(b <= a for a, b in zip(cells, cells[1:])), cells
    assert rule.name == "gain_need" and outcome.event.rule == "gain_need"
    # Thresholded: priority is the largest EVB; it is positive before any backup and the mode runs within the cap.
    track2, agent2, model2 = _setup()
    _store_lap(track2, agent2, list(range(8)), lt.EAST)
    model2.set_acting(track2.start_state(lt.WEST))
    rule2 = GainNeedReplay(model2, "gain_need")
    rule2.begin(agent2.memory, 0)
    p0 = rule2.priority(agent2.memory, agent2.learner, 0)
    assert p0 > 0.0
    out = replay_thresholded(rule2, agent2.memory, agent2.learner, p0 / 10.0, 50, 0, stream, tick=0)
    assert out is not None and 1 <= out.n_backups <= 50
    assert replay_thresholded(rule2, agent2.memory, agent2.learner, 1e9, 50, 0, stream, tick=0) is None


def test_duplicates_are_one_candidate_and_ties_go_to_the_most_recent() -> None:
    track, agent, model = _setup()
    memory = agent.memory
    s = lt.State(2, lt.EAST, lt.EAST)
    nxt = lt.State(3, lt.EAST, lt.EAST)
    x, y = track.position(s)
    x2, y2 = track.position(nxt)
    for k in range(5):  # the same transition stored five times, then a different one
        memory.append(StoredTransition(x, y, 0.0, x2, y2, False, 0, k, agent.learner.cell(x, y)))
    other = lt.State(5, lt.EAST, lt.EAST)
    ox, oy = track.position(other)
    memory.append(StoredTransition(ox, oy, 0.0, *track.position(lt.State(6, lt.EAST, lt.EAST)), False, 0, 5, agent.learner.cell(ox, oy)))
    rule = GainNeedReplay(model, "need_only")
    assert rule.span(memory) == 2  # two distinct candidates
    model.set_acting(lt.State(0, lt.EAST, lt.EAST))
    chosen = rule.choose(memory, agent.learner, RNG(1).stream("replay"), 0)
    assert chosen.cell[0] in (2, 5)
    # All-zero priorities (gain mode with no error anywhere): the most recently stored distinct candidate wins.
    rule = GainNeedReplay(model, "gain_only")
    chosen = rule.choose(memory, agent.learner, RNG(1).stream("replay"), 0)
    assert chosen.cell[0] == 5 and chosen.index == 5
    with pytest.raises(ValueError):
        GainNeedReplay(model, "evb")
    with pytest.raises(ValueError):
        GainNeedReplay(model, "gain_need").begin(TransitionMemory(5), 0)
    assert MODES == ("gain_need", "gain_only", "need_only")


def test_the_three_modes_rank_differently_and_run_as_track_conditions() -> None:
    track, agent, model = _setup()
    _store_lap(track, agent, list(range(8)), lt.EAST)
    model.set_acting(track.start_state(lt.WEST))
    gain_only = GainNeedReplay(model, "gain_only")
    need_only = GainNeedReplay(model, "need_only")
    gain_need = GainNeedReplay(model, "gain_need")
    stream = RNG(1).stream("replay")
    for r in (gain_only, need_only, gain_need):
        r.begin(agent.memory, 0)
    g = gain_only.choose(agent.memory, agent.learner, stream, 0)
    n = need_only.choose(agent.memory, agent.learner, stream, 0)
    # The largest gain sits at the goal end of the lap: with V(goal) already backed up online, the policy at the
    # goal's neighbour is near-deterministic, so the backup that moves a decision most is one transition back.
    assert g.cell[0] >= 6
    acting = model.acting_state()
    # need-only picks the stored start state with the largest occupancy from the acting state, not the consume.
    assert model.need(acting, model.state_index(n.x, n.y)) >= model.need(acting, model.state_index(g.x, g.y))
    assert math.isfinite(gain_need.priority(agent.memory, agent.learner, 0))
    # As experiment conditions: every one runs, learns the SR and replays the budget at every pause after the first.
    for c in lt.GAIN_NEED_CONDITIONS:
        run = lt.run_seed(c, 7, CFG)
        assert all(lap.replay_backups == CFG.backups_per_trigger for lap in run.laps if lap.rewarded)
        assert run.laps[0].pre_run_backups == 0 and all(lap.pre_run_backups == CFG.backups_per_trigger for lap in run.laps[1:])
        assert all(math.isfinite(lap.reward_priority_before) for lap in run.laps if lap.rewarded)
        assert run.summary()["replay_events"] == sum(lap.rewarded for lap in run.laps)
    # The first lap is the same as the floors' (no replay has happened yet) and the SR is learned in every condition.
    none = lt.run_seed(lt.RULE_NONE, 7, CFG)
    assert all(lt.run_seed(c, 7, CFG).first_lap_actions == none.first_lap_actions for c in lt.GAIN_NEED_CONDITIONS)
    track2, agent2, _ = _setup()
    before = agent2.sr.M.copy()
    _store_lap(track2, agent2, list(range(8)), lt.EAST)
    assert agent2.sr.updates == 7 and not (agent2.sr.M == before).all()  # seven moves update the SR, the consume does not


def test_gain_is_in_value_units_and_need_is_not() -> None:
    """``value_scaled`` per mode (M2a step 4): EVB and gain scale with V, an occupancy does not."""
    from brain.systems.replay_gain_need import MODES, GainNeedReplay

    assert set(GainNeedReplay.VALUE_SCALED) == set(MODES)
    for mode in MODES:
        rule = GainNeedReplay(object(), mode)  # the model is not read until a backup
        assert rule.value_scaled is (mode != "need_only") and rule.value_scaled is GainNeedReplay.VALUE_SCALED[mode]
