"""Multi-landmark foraging: a sighted agent clears the patch, a blind one collects
only what it bumps into (2 of 5, then nothing more in 600 ticks), at under a
tenth of the sighted agent's rate (measured ~18x)."""

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
    # This used to assert the blind agent collects at most 1 item. That was
    # partly an artefact: the blind agent camped on a self-made value peak (the
    # value-induced REST trap; it rested on 87% of ticks) and so stopped bumping
    # into food. With dwell extinction, primary-only map content, cue gating
    # and split steering (no value-induced REST) it keeps moving and
    # stumbles on 2 of 5 by chance, then nothing more. Vision is still what
    # makes foraging work, so assert that directly: the sighted agent clears the
    # patch, the blind one collects under half of it, and the sighted agent's
    # collection rate is at least 10x the blind agent's (measured: ~18x).
    sighted, blind = _run_forage(0.6), _run_forage(0.0)
    assert sighted["all_collected"]
    assert 2 * blind["collected"] < blind["n_targets"]
    sighted_rate = sighted["collected"] / sighted["ticks_run"]
    blind_rate = blind["collected"] / blind["ticks_run"]
    assert sighted_rate >= 10 * blind_rate


def test_vision_improves_foraging():
    assert _run_forage(0.6)["collected"] > _run_forage(0.0)["collected"]


def test_foraging_is_deterministic():
    assert _run_forage(0.6) == _run_forage(0.6)
