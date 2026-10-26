"""The Mattar & Daw rule on the Q learner (brain/systems/replay_mattar_daw.py; docs/prereg/rq1_track_mattar_daw.md).

Pins the gain at the acted-from state, the EVB with its gain floor, the one-step argmax, the forward n-step
extension (its candidate, its target, the chain's growth and reset, how it walks as a transition for the replay
machinery), the ablation, the priority, and the rule's integration with the track (the learner it needs, the
events it records). The track's ``QTrackModel`` is the model under test, not a stub.
"""

from __future__ import annotations

import math

import pytest

from brain.systems.replay_mattar_daw import (
    MATTAR_DAW,
    MATTAR_DAW_1STEP,
    ExtendedBackup,
    MattarDawReplay,
    gain_q,
)
from brain.systems.replay_rules import StoredTransition, TransitionMemory, replay
from core.rng import RNG
from experiments.linear_track_replay import EAST, LinearTrack, QTrackModel, TrackAgent, TrackConfig, _rule_for, run_seed


def _setup(laps_to_store: int = 1):
    """A Q-learner agent that walked straight to the east goal once (cells 0..39 then the consume), with the model."""
    cfg = TrackConfig(laps=4, learner="q", pre_run_pause=True)
    track = LinearTrack(cfg)
    agent = TrackAgent(cfg, track)
    model = QTrackModel(cfg, track, agent)
    state = track.start_state(EAST)
    for lap in range(laps_to_store):
        state = track.start_state(EAST)
        for i in range(cfg.n_bins):
            nxt, _ = track.step(state, "FORWARD")
            if track.at_goal(nxt):
                agent.store_and_learn(state, 0.0, nxt, False, lap, i)
                agent.store_and_learn(nxt, 1.0, nxt, True, lap, i + 1)
                break
            agent.store_and_learn(state, 0.0, nxt, False, lap, i)
            state = nxt
    model.set_acting(track.start_state(-EAST))
    return cfg, track, agent, model


def test_gain_is_the_expected_improvement_of_the_decision_at_the_acted_from_state() -> None:
    cfg, track, agent, model = _setup()
    q0 = {"FORWARD": 0.0, "TURN": 0.0}
    assert gain_q(model, q0, "FORWARD", 0.0) == 0.0  # no move, no gain
    up = gain_q(model, q0, "FORWARD", 0.05)  # FORWARD is already preferred by the prior: raising it helps a little
    assert up > 0.0
    # Raising TURN from a tie with a prior on FORWARD moves probability toward TURN, whose value is now the higher.
    assert gain_q(model, q0, "TURN", 0.05) > 0.0
    # A move that makes no difference to the softmax (both actions saturated) gives a negligible gain.
    saturated = {"FORWARD": 10.0, "TURN": 0.0}
    assert abs(gain_q(model, saturated, "FORWARD", 0.01)) < 1e-9
    assert gain_q(model, q0, "FORWARD", 0.05) == gain_q(model, q0, "FORWARD", 0.05)  # deterministic


def test_the_one_step_argmax_restarts_the_chain_and_the_extension_grows_it() -> None:
    cfg, track, agent, model = _setup()
    rule = MattarDawReplay(model)
    assert rule.name == MATTAR_DAW and rule.value_scaled is True and rule.extension
    memory, learner = agent.memory, agent.learner
    rule.begin(memory, 0)
    assert rule.chain == [] and rule.span(memory) == 40  # 39 forward steps and the consume, all distinct
    stream = RNG(seed=1).stream("replay")
    first = rule.choose(memory, learner, stream, 0)
    assert isinstance(first, StoredTransition) and rule.chain == [first] and rule.last_choice == "one_step"
    # Build a chain by hand from the lap's start: its extension is the transition from its successor state.
    start = memory.episode(0)[0]
    rule.chain = [start]
    exts = rule._extensions(rule._distinct(memory), learner)
    assert len(exts) == 1
    evb, ext = exts[0]
    assert isinstance(ext, ExtendedBackup) and ext.first is start and (ext.appended.x, ext.appended.y) == (start.x_next, start.y_next)
    assert ext.length == 2 and ext.action == "FORWARD"
    # The 2-step target: r1 + g r2 + g^2 max_a Q(s3) (rewards 0 here).
    expected = cfg.discount ** 2 * learner.value(ext.appended.x_next, ext.appended.y_next)
    assert ext.target == pytest.approx(expected)
    # It walks like a transition of the appended state for the replay record, and its backup moves the chain's first Q.
    assert (ext.x, ext.y, ext.cell, ext.episode) == (ext.appended.x, ext.appended.y, ext.appended.cell, ext.appended.episode)
    before = learner.q(start.x, start.y)["FORWARD"]
    delta = ext.backup(learner)
    assert delta == pytest.approx(expected - before) and learner.q(start.x, start.y)["FORWARD"] == pytest.approx(before + cfg.learning_rate * delta)
    assert ext.td_error(learner) == pytest.approx(expected - learner.q(start.x, start.y)["FORWARD"])
    # Choosing the extension grows the chain; a chain ending in the consume has no extension.
    rule.chain = [start]
    rule._ranked = lambda m, l: [(0.0, 1, 0, ext)]  # type: ignore[method-assign]
    chosen = rule.choose(memory, learner, stream, 1)
    assert chosen is ext and rule.chain == [start, ext.appended] and rule.last_choice == "extension"
    rule.chain = [memory.episode(0)[-1]]  # the consume
    assert rule._extensions(rule._distinct(memory), learner) == []


def test_the_ablation_has_no_extensions_and_ties_prefer_the_extension_then_recency() -> None:
    cfg, track, agent, model = _setup()
    one = MattarDawReplay(model, extension=False)
    assert one.name == MATTAR_DAW_1STEP and not one.extension and one.value_scaled is True
    one.begin(agent.memory, 0)
    one.chain = [agent.memory.episode(0)[0]]
    assert one._extensions(one._distinct(agent.memory), agent.learner) == []
    full = MattarDawReplay(model)
    full.begin(agent.memory, 0)
    full.chain = [agent.memory.episode(0)[0]]
    ranked = full._ranked(agent.memory, agent.learner)
    assert len(ranked) == 41 and ranked == sorted(ranked, key=lambda item: (item[0], item[1], item[2]))
    # The priority is the largest EVB, at least the floor times the need of some candidate.
    assert full.priority(agent.memory, agent.learner, 0) == ranked[-1][0] >= 0.0
    with pytest.raises(ValueError):
        MattarDawReplay(model, gain_floor=-1.0)
    empty = TransitionMemory(10)
    with pytest.raises(ValueError):
        full.begin(empty, 0)


def test_the_rule_runs_through_the_replay_machinery_and_the_track() -> None:
    cfg, track, agent, model = _setup()
    rule = MattarDawReplay(model)
    outcome = replay(rule, agent.memory, agent.learner, 8, 0, RNG(seed=3).stream("replay"), tick=0, travel_sign=1)
    assert outcome.n_backups == 8 and len(outcome.event.cells) == 8 and len(outcome.deltas) == 8
    # Integration: both rules run on the track under the q learner, record events at both pauses, and need it.
    for condition in (MATTAR_DAW, MATTAR_DAW_1STEP):
        run = run_seed(condition, 1, TrackConfig(laps=4, learner="q", pre_run_pause=True))
        assert all(lap.replay_backups == 20 for lap in run.laps if lap.rewarded)
        assert {e["trigger"] for e in run.events} == {"reward", "pre_run"} and all(e["rule"] == condition for e in run.events)
        assert all(len(e["cells"]) == 20 for e in run.events)
    with pytest.raises(ValueError):
        run_seed(MATTAR_DAW, 1, TrackConfig(laps=2))  # the v learner
    with pytest.raises(ValueError):
        run_seed("gain_need", 1, TrackConfig(laps=2, learner="q"))
    with pytest.raises(ValueError):
        _rule_for(MATTAR_DAW, TrackConfig(laps=2, learner="q"), model=None)
    with pytest.raises(ValueError):
        QTrackModel(TrackConfig(laps=2), track, agent)
    # The floors run on the q learner and the first lap is identical across conditions (Q = 0 and V = 0 agree).
    first = {c: run_seed(c, 2, TrackConfig(laps=2, learner="q")).first_lap_actions for c in ("none", "prioritised_td", MATTAR_DAW)}
    assert len(set(first.values())) == 1 and first["none"] == run_seed("none", 2, TrackConfig(laps=2)).first_lap_actions


def test_the_forward_extension_makes_forward_sequences_when_gains_are_flat() -> None:
    """The mechanism the prereg predicts: with every gain at its floor, EVB is need's order, the start state's own
    transition wins, and its extension wins the tie, so the chain advances forward along the stored lap."""
    cfg, track, agent, model = _setup()
    # Flatten the gains: a learner whose Q is already exact along the lap gives zero TD error everywhere.
    for _ in range(400):
        for t in agent.memory.episode(0):
            t.backup(agent.learner)
    assert max(abs(t.td_error(agent.learner)) for t in agent.memory.episode(0)) < 1e-6
    model.set_acting(track.start_state(EAST))  # the pre-run pause of an east-bound lap
    rule = MattarDawReplay(model)
    outcome = replay(rule, agent.memory, agent.learner, 10, 0, RNG(seed=5).stream("replay"), tick=0, travel_sign=1)
    cells = [c[0] for c in outcome.event.cells]
    assert cells == list(range(10)) and outcome.event.direction == "forward"
    one = MattarDawReplay(model, extension=False)
    outcome1 = replay(one, agent.memory, agent.learner, 10, 0, RNG(seed=5).stream("replay"), tick=0, travel_sign=1)
    assert [c[0] for c in outcome1.event.cells] != cells  # without the extension the start state is replayed over and over
    assert math.isfinite(outcome1.sequence_r) or outcome1.event.direction == "neither"


def test_the_seeded_priority_reads_the_would_be_chain_and_leaves_choose_alone() -> None:
    """M2a step 6 (G31 C3): under ``priority_mode="seeded"`` the priority before a pause's first backup also reads the
    extensions of a chain seeded with the acting state's most recent outgoing transition; ``choose`` is unchanged."""
    from brain.systems.replay_mattar_daw import PRIORITY_MODES

    cfg, track, agent, model = _setup()
    assert PRIORITY_MODES == ("one_step", "seeded")
    with pytest.raises(ValueError):
        MattarDawReplay(model, priority_mode="chain")
    plain = MattarDawReplay(model)
    seeded = MattarDawReplay(model, priority_mode="seeded")
    named = MattarDawReplay(model, priority_mode="seeded", name="mattar_daw_pos")
    assert plain.priority_mode == "one_step" and seeded.priority_mode == "seeded" and named.name == "mattar_daw_pos" and seeded.name == MATTAR_DAW
    memory, learner = agent.memory, agent.learner
    plain.begin(memory, 0)
    seeded.begin(memory, 0)
    # The acting state is the west-bound start (no stored transition from it): no seed, the two priorities agree.
    assert seeded._seed(seeded._distinct(memory)) is None
    assert seeded.priority(memory, learner, 0) == plain.priority(memory, learner, 0)
    # Acting from the east-bound start, whose transition is stored: the seed is that transition and the seeded priority
    # is at least the one-step one (it is a max over a superset).
    model.set_acting(track.start_state(EAST))
    seed = seeded._seed(seeded._distinct(memory))
    assert seed is memory.episode(0)[0]
    one_step = plain.priority(memory, learner, 0)
    with_seed = seeded.priority(memory, learner, 0)
    assert with_seed >= one_step
    ext_evbs = [evb for evb, _ in seeded._extensions(seeded._distinct(memory), learner, [seed])]
    assert len(ext_evbs) == 1 and with_seed == max(one_step, ext_evbs[0])
    # choose is the same object under both modes, and once a chain exists the seed is not read.
    stream = RNG(seed=2).stream("replay")
    a = plain.choose(memory, learner, stream, 0)
    b = seeded.choose(memory, learner, stream, 0)
    assert a is b and seeded.chain == [b]
    assert seeded.priority(memory, learner, 1) == plain.priority(memory, learner, 1)
    # Without the extension the setting is inert.
    one = MattarDawReplay(model, extension=False, priority_mode="seeded")
    one.begin(memory, 0)
    assert one.priority(memory, learner, 0) == MattarDawReplay(model, extension=False).priority(memory, learner, 0)
