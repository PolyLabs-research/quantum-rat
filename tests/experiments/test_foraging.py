"""Multi-landmark foraging: a sighted agent collects all targets, a blind one almost none."""

from core.config import BasalGangliaConfig, EngineConfig, SensorConfig
from core.engine import Engine
from experiments.protocols.foraging import ForagingProtocol


def _run_forage(vision_gain: float, max_ticks: int = 600, seed: int = 1337):
    cfg = EngineConfig(
        basal_ganglia=BasalGangliaConfig(vision_gain=vision_gain),
        sensors=SensorConfig(vision_rays=5, fov=2.4),  # wide field so targets off to the side are seen
    )
    engine = Engine(seed=seed, config=cfg)
    proto = ForagingProtocol()
    proto.setup(engine)
    for i in range(max_ticks):
        tick = engine.run(1, reset=(i == 0))[0]
        proto.on_tick(engine, tick, i)
        if proto.is_done(engine, tick, i):
            break
    return proto.summarize()


def test_sighted_agent_forages_all_targets():
    s = _run_forage(0.6)
    assert s["collected"] == s["n_targets"]


def test_blind_agent_forages_far_fewer():
    assert _run_forage(0.0)["collected"] <= 1


def test_vision_improves_foraging():
    assert _run_forage(0.6)["collected"] > _run_forage(0.0)["collected"]


def test_foraging_is_deterministic():
    assert _run_forage(0.6) == _run_forage(0.6)
