"""The history/motivation probe (G52): eight configurations, the pilot's two included unchanged."""

from __future__ import annotations

from core.config import EngineConfig
from core.engine import Engine
from experiments import m3_hm_probe as hm
from experiments import m3_part2 as p2


def test_the_configurations() -> None:
    assert set(hm.CONFIGS) == {f"B{b}_H{h}M{m}" for b in (0, 1) for h in (0, 1) for m in (0, 1)}
    assert hm.CONFIGS["B0_H0M0"] == p2.CONFIGS["o0_n_L"] and hm.CONFIGS["B1_H0M0"] == p2.CONFIGS["o1_n_S"]
    assert hm.CONFIGS["B0_H0M1"]["history.channels"] == ("visit",) and hm.CONFIGS["B0_H0M1"]["history.reward_context"] == ()
    for name, ov in hm.CONFIGS.items():  # every one builds an engine
        cfg = EngineConfig.research()
        for k, v in ov.items():
            cfg.set_field(k, v)
        Engine(seed=1, config=cfg).run(2)
