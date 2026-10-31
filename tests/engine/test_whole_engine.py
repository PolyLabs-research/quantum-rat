"""The whole in the engine (G56; docs/prereg/whole_resource.md): every part off by default; on, each does what §2 says."""

from __future__ import annotations

import pytest

from core.config import EngineConfig
from core.engine import Engine
from core.world import WorldObject
from experiments import whole_resource as wr


def _place(eng, x, y):
    """Put the body on (x, y) and hold it there for the next tick (the world step moves it by the last action first)."""
    from brain.contracts import Action

    eng.agent.pos = (x, y)
    eng.last_action = Action(name="REST", thrust=0.0, turn=0.0)


def _engine(overrides, seed=1, food=True, k=0.1):
    cfg = wr.engine_config(overrides, k)
    eng = Engine(seed=seed, config=cfg)
    if food:
        for (x, y) in wr.PATCHES:
            eng.world.add_object(WorldObject(x, y, wr.PATCH_RADIUS, "target"))
    eng.run(1, reset=True)
    return eng


def test_every_part_is_off_on_both_profiles() -> None:
    for cfg in (EngineConfig.legacy(), EngineConfig.research()):
        assert not (cfg.metabolism.enabled or cfg.interoception.enabled or cfg.sleep.enabled or cfg.criticality.dynamic
                    or cfg.replay.sr_replay or cfg.basal_ganglia.criticality_scales_walls)
        assert cfg.neuromod.model == "legacy" and cfg.value_memory.source != "sr_action"
    e = Engine(seed=1, config=EngineConfig.research())
    e.run(3)
    assert e.metabolism is None and e.sleep is None and e.bio_neuromod is None and e.crit_coupling is None and e.sr_replay is None


def test_the_requirements() -> None:
    cfg = EngineConfig.research()
    cfg.interoception.enabled = True
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)  # nothing to sense without metabolism
    cfg = EngineConfig.research()
    cfg.value_memory.source = "sr_action"
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)  # needs the action value
    cfg = EngineConfig.legacy()
    cfg.replay.sr_replay = True
    with pytest.raises(ValueError):
        Engine(seed=1, config=cfg)  # needs the successor features


def test_the_need_blind_body_eats_whatever_it_touches_and_pays_for_moving() -> None:
    eng = _engine({}, k=0.1)
    e0 = eng.metabolism.reserve
    _place(eng, 5.0, 5.0)  # put it on a patch
    eng.run(1)
    ctx = eng.context
    assert ctx.ingested == 0.1 and ctx.meal_value == 1.0 and ctx.map_reward == 1.0  # the contact bonus: it does not sense need
    assert eng.metabolism.gut > 0.0 and eng._consume_remaining > 0
    eng.run(5)
    assert eng.context.consuming or eng.last_action.name == "REST"  # the body rests while it eats
    assert eng.metabolism.spent > 0.0 and eng.metabolism.reserve != e0


def test_interoception_eats_only_when_a_meal_reduces_the_drive() -> None:
    eng = _engine({"interoception.enabled": True}, k=0.1)
    eng.metabolism.reserve = 0.79  # sated: a meal would overshoot the setpoint
    _place(eng, 5.0, 5.0)
    eng.run(1)
    assert eng.context.target_contact and eng.context.ingested == 0.0 and eng.context.incentive == 0.0 and eng.context.target_gain == 0.0
    eng.metabolism.reserve = 0.3  # hungry
    _place(eng, 5.0, 5.0)
    eng.run(1)
    ctx = eng.context
    assert ctx.ingested == 0.1 and 0.0 < ctx.meal_value < 1.0 and ctx.hunger > 0.9 and ctx.incentive > 0.0


def test_sleep_closes_the_gate_and_the_neuromodulators_move() -> None:
    over = wr.merge(wr.PARTS["interoception"], wr.PARTS["sleep"], wr.PARTS["dopamine"], wr.PARTS["acetylcholine"],
                    wr.PARTS["noradrenaline"], wr.PARTS["serotonin"], wr.PARTS["criticality"], {"sleep.wake_time_constant": 20.0})
    eng = _engine(over, food=False, k=0.1)
    eng.metabolism.reserve = 0.79  # sated, so hunger does not keep it awake
    trace = eng.run(200)
    assert eng.sleep.bouts >= 1 and eng.sleep.ticks_asleep > 0
    names = {td.action_name for td in trace if td.microsleep_active}
    assert names == {"REST"}  # asleep, selection gets no input: the body rests
    assert any(td.trn_state == "CLOSED" for td in trace)
    assert eng.bio_neuromod is not None and eng.crit_coupling is not None and eng.context.criticality_m != 1.0


def test_the_whole_runs_and_replays_its_map() -> None:
    eng = _engine(wr.whole(), seed=3, k=0.1)
    eng.metabolism.reserve = 0.45
    meals = 0
    for _ in range(1500):
        eng.run(1)
        if eng.context.ingested_object is not None:
            eng.context.ingested_object.kind = "collected"
            meals += 1
    assert eng.action_learner is not None and eng.sr_replay is not None and len(eng.sr_replay.memory) > 0
    assert meals >= 1 and eng.metabolism.eaten >= 0.1
    assert eng.sr_replay.backups > 0 or len(eng.replay_log) == 0  # replay ran wherever acetylcholine allowed it
    eng.begin_episode()
    assert eng._replay_pending is None and eng._v_prev is None and eng._consume_remaining == 0
