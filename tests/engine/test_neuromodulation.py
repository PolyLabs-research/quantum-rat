"""Dopamine is now a causal reward-prediction-error signal, not a random walk."""

from core.engine import Engine
from core.neuromodulation import NeuromodulatorSystem
from experiments.protocols.beacon import BeaconProtocol


def test_dopamine_rises_on_better_than_expected_reward():
    nm = NeuromodulatorSystem()
    base = nm.update(reward=0.0)["DA"]
    high = nm.update(reward=1.0)["DA"]
    assert base == 0.5  # neutral baseline with no surprise
    assert high > base  # positive prediction error raises dopamine


def test_dopamine_falls_below_baseline_on_disappointment():
    nm = NeuromodulatorSystem()
    nm.update(reward=1.0)
    nm.update(reward=1.0)  # raise the expectation
    low = nm.update(reward=0.0)["DA"]
    assert low < 0.5  # worse-than-expected reward drops dopamine


def test_neuromodulators_are_deterministic_not_random():
    a = NeuromodulatorSystem()
    b = NeuromodulatorSystem()
    for _ in range(5):
        assert a.update(reward=0.2, novelty=0.3, pain=0.1) == b.update(reward=0.2, novelty=0.3, pain=0.1)


def test_engine_dopamine_responds_to_reaching_a_target():
    engine = Engine(seed=1337)
    proto = BeaconProtocol()
    proto.setup(engine)
    das = []
    for i in range(40):
        tick = engine.run(1)[0]
        proto.on_tick(engine, tick, i)
        das.append(tick.neuromodulators["DA"])
        if proto.is_done(engine, tick, i):
            break
    assert max(das) > 0.5  # dopamine rose as the agent approached and reached the beacon
