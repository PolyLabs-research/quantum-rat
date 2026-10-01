"""Proof that the perception loop is closed.

A sighted agent steers to a visible beacon; the same agent with vision
disabled (basal_ganglia.vision_gain == 0) does not. If these ever converge,
the agent's behaviour no longer depends on what it senses.
"""

from core.config import BasalGangliaConfig, EngineConfig
from core.engine import Engine
from experiments.protocols.beacon import BeaconProtocol


def _run_beacon(vision_gain: float, ticks: int = 120, seed: int = 1337):
    cfg = EngineConfig(basal_ganglia=BasalGangliaConfig(vision_gain=vision_gain))
    engine = Engine(seed=seed, config=cfg)
    proto = BeaconProtocol()
    proto.setup(engine)
    for i in range(ticks):
        tick = engine.run(1)[0]
        proto.on_tick(engine, tick, i)
        if proto.is_done(engine, tick, i):
            break
    return proto.summarize()


def test_sighted_agent_reaches_beacon():
    summary = _run_beacon(vision_gain=0.6)
    assert summary["reached"] is True
    assert 0 <= summary["time_to_target"] < 40


def test_blind_agent_does_not_reach_beacon():
    summary = _run_beacon(vision_gain=0.0)
    assert summary["reached"] is False


def test_vision_materially_changes_outcome():
    sighted = _run_beacon(vision_gain=0.6)
    blind = _run_beacon(vision_gain=0.0)
    assert sighted["reached"] and not blind["reached"]
    assert sighted["min_distance"] < blind["min_distance"]


def test_beacon_run_is_deterministic():
    assert _run_beacon(vision_gain=0.6) == _run_beacon(vision_gain=0.6)
