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


# --- Neuromodulators as control signals (NE/ACh/5HT now change behaviour) ---

from brain.contracts import Observation, VisionRay  # noqa: E402
from brain.systems.basal_ganglia import _channel_scores  # noqa: E402
from core.config import BasalGangliaConfig  # noqa: E402


def _obs_target_and_pain():
    return Observation(
        vision_rays=(VisionRay(0.3, "target", 0.5), VisionRay(0.9, "wall", 0.0), VisionRay(0.9, "wall", -0.5)),
        whisker_hits=(False, False),
        pain_signal=0.5,
        forward_delta=0.0,
        turn_delta=0.0,
    )


def test_acetylcholine_sharpens_vision_precision():
    cfg, obs = BasalGangliaConfig(), _obs_target_and_pain()
    base = _channel_scores(obs, 0.0, 1.0, False, cfg, {})
    ach = _channel_scores(obs, 0.0, 1.0, False, cfg, {"ACh": 1.0})
    assert ach["TURN_LEFT"] > base["TURN_LEFT"]  # the target-driven turn is strengthened


def test_norepinephrine_raises_threat_response():
    cfg, obs = BasalGangliaConfig(), _obs_target_and_pain()
    base = _channel_scores(obs, 0.0, 1.0, False, cfg, {})
    ne = _channel_scores(obs, 0.0, 1.0, False, cfg, {"NE": 1.0})
    assert ne["REST"] > base["REST"]


def test_serotonin_raises_patience():
    cfg, obs = BasalGangliaConfig(), _obs_target_and_pain()
    base = _channel_scores(obs, 0.0, 1.0, False, cfg, {})
    ht = _channel_scores(obs, 0.0, 1.0, False, cfg, {"5HT": 1.0})
    assert ht["REST"] > base["REST"]


def test_baseline_modulator_levels_are_noops():
    cfg, obs = BasalGangliaConfig(), _obs_target_and_pain()
    assert _channel_scores(obs, 0.0, 1.0, False, cfg, {}) == _channel_scores(
        obs, 0.0, 1.0, False, cfg, {"DA": 0.5, "NE": 0.0, "ACh": 0.0, "5HT": 0.5}
    )
