"""The whole's upgraded parts (G56; docs/prereg/whole_resource.md §2), each on its own."""

from __future__ import annotations

import math

import pytest

from brain.systems.criticality import CriticalityConfig, CriticalityField, HomeostaticCoupling, near_critical_gain
from brain.systems.interoception import drive, hunger, incentive, meal_reward, satiety
from brain.systems.neuromodulators import NEUTRAL, BiologicalNeuromodulators
from brain.systems.sleep import SleepHomeostat
from brain.systems.sr_replay import MapTransition, SRReplay
from core.config import NeuromodConfig
from core.metabolism import Metabolism
from core.rng import RNG


def test_metabolism_pays_absorbs_caps_and_starves() -> None:
    m = Metabolism(start=0.5, basal_cost=0.01, locomotion_factor=2.0, sleep_factor=0.5, absorption_time=10.0)
    assert m.tick(0.0) == pytest.approx(0.01) and m.reserve == pytest.approx(0.49)
    assert m.tick(1.0) == pytest.approx(0.03) and m.spent_locomotion == pytest.approx(0.02)  # three times resting at full speed
    assert m.tick(1.0, asleep=True) == pytest.approx(0.005)  # asleep: the sleep factor, no locomotion
    m.eat(0.6)
    assert m.effective == pytest.approx(m.reserve + 0.6) and m.eaten == 0.6
    full = Metabolism(start=0.9, basal_cost=0.0, absorption_time=10.0)
    full.eat(0.6)
    for _ in range(300):
        full.tick(0.0)
    assert full.reserve == 1.0 and full.gut < 1e-6 and full.lost == pytest.approx(0.5, abs=1e-6)  # absorbed, capped, excess lost
    m2 = Metabolism(start=0.02, basal_cost=0.01)
    m2.tick(0.0)
    m2.tick(0.0)
    assert m2.starved and m2.reserve == 0.0 and m2.tick(1.0) == 0.0


def test_interoception_reward_is_drive_reduction() -> None:
    sp, k = 0.8, 0.1
    assert drive(sp, sp) == 0.0 and drive(0.0, sp) == 1.0
    assert meal_reward(0.0, k, sp) == pytest.approx(1.0)  # the hungriest meal brings 1
    assert meal_reward(0.3, k, sp) > meal_reward(0.6, k, sp) > 0.0  # worth more the hungrier the agent
    assert meal_reward(0.8, k, sp) < 0.0 and incentive(0.8, k, sp) == 0.0  # past the setpoint eating is aversive
    assert meal_reward(sp - k / 2, k, sp) == pytest.approx(0.0, abs=1e-12)  # positive exactly below setpoint - k/2
    assert hunger(0.8, sp, 0.4) == 0.0 and hunger(0.6, sp, 0.4) == pytest.approx(0.5) and hunger(0.1, sp, 0.4) == 1.0
    assert satiety(0.8, sp, 0.2) == pytest.approx(1.0) and satiety(0.6, sp, 0.2) == pytest.approx(0.0, abs=1e-12)
    with pytest.raises(ValueError):
        meal_reward(0.5, 2.0, sp)


def test_neuromodulators_each_on_only_with_its_part() -> None:
    off = BiologicalNeuromodulators(NeuromodConfig(model="biological"))
    assert off.update(delta=1.0, reward=1.0, pain=0.5, novelty=1.0, moving=True, asleep=False, satiety=1.0) == NEUTRAL
    assert off.vigour() == 1.0 and off.temperature_factor() == 1.0 and off.sr_learning_scale() == 1.0
    assert off.replay_allowed() and off.replay_budget(0.0, 20) == 20
    c = NeuromodConfig(model="biological", dopamine=True, serotonin=True, noradrenaline=True, acetylcholine=True)
    nm = BiologicalNeuromodulators(c)
    lv = nm.update(delta=0.5, reward=0.8, pain=0.0, novelty=1.0, moving=True, asleep=False, satiety=1.0)
    assert lv["DA"] == pytest.approx(1.0) and lv["5HT"] == pytest.approx(1.0) and lv["NE"] == pytest.approx(1.0) and lv["ACh"] == 1.0
    assert nm.vigour() == pytest.approx(0.5 + 0.5 * 0.8) and nm.temperature_factor() == pytest.approx(3.0)
    assert nm.sr_learning_scale() == pytest.approx(1.5) and not nm.replay_allowed() and nm.replay_budget(0.25, 20) == 10
    for _ in range(600):  # no reward for 2 minutes: the tonic level and the surprise fade
        lv = nm.update(delta=0.0, reward=0.0, pain=0.0, novelty=0.0, moving=False, asleep=True, satiety=0.0)
    assert nm.tonic == pytest.approx(0.8 * math.exp(-1.0), rel=1e-6) and lv["NE"] < 1e-3 and lv["ACh"] == 0.0 and nm.replay_allowed()
    assert lv["DA"] == 0.5 and lv["5HT"] == 0.5
    with pytest.raises(ValueError):
        NeuromodConfig(dopamine=True)  # a part needs the biological model


def test_sleep_pressure_builds_awake_falls_asleep_and_hunger_keeps_awake() -> None:
    s = SleepHomeostat(wake_time_constant=100.0, sleep_time_constant=20.0, onset=0.6, offset=0.2)
    ticks = 0
    while not s.step(hunger=0.0, pain=0.0):
        ticks += 1
    assert 85 <= ticks <= 95 and s.bouts == 1  # -100 ln(0.4) = 91.6 ticks to reach 0.6
    while s.step(hunger=0.0, pain=0.0):
        pass
    assert s.pressure <= 0.2 and not s.asleep
    hungry = SleepHomeostat(wake_time_constant=10.0)
    for _ in range(200):
        assert not hungry.step(hunger=0.3, pain=0.0)  # hunger above the block keeps it awake however tired
    assert hungry.step(hunger=0.1, pain=0.0) and not hungry.step(hunger=0.6, pain=0.0)  # hunger wakes it


def test_criticality_follows_sleep_pressure_and_is_tuned_back() -> None:
    hc = HomeostaticCoupling(critical_coupling=0.5, sleep_coupling=0.3, homeostasis_time=100.0)
    assert hc.step(0.0) == 1.0 and hc.coupling == 0.5
    assert hc.step(1.0) == pytest.approx(1.3)
    for _ in range(2000):
        hc.step(1.0)
    assert hc.m == pytest.approx(1.0, abs=1e-6)  # homeostasis pulls the distance back to criticality
    assert hc.step(0.0) < 1.0  # pressure gone (after sleep): subcritical until tuned back
    assert near_critical_gain(1.0) == 1.0 and near_critical_gain(1.3) == pytest.approx(math.exp(-1.0))
    field = CriticalityField(RNG(1).stream("criticality"), CriticalityConfig())
    field.coupling_override = 0.0
    for _ in range(50):
        assert field.step().active <= 1  # no propagation at coupling 0: every avalanche is its seed


def test_map_replay_sweeps_the_episode_backwards_and_draws_uniformly() -> None:
    r = SRReplay(capacity=5)
    for i in range(7):
        r.store(MapTransition(float(i), 0.0, float(i + 1), 0.0, episode=0 if i < 4 else 1, cell=(i, 0)))
    assert len(r.memory) == 5  # the newest five
    assert [t.x for t in r.reverse_sweep(1, 2)] == [6.0, 5.0] and [t.x for t in r.reverse_sweep(0, 10)] == [3.0, 2.0]
    assert r.reverse_sweep(1, 0) == [] and len(r.draws(4, RNG(3).stream("replay"))) == 4 and SRReplay().draws(3, None) == []
