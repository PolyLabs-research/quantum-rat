"""G53's probes: the fixed-schema and the forage configurations build engines; the schemas are the stated three."""

from __future__ import annotations

from core.config import EngineConfig
from core.engine import Engine
from experiments import m3_g53_probes as g


def test_the_configurations() -> None:
    schema, forage = g.configs("schema"), g.configs("forage")
    assert set(schema) == {f"B{b}_S{s}" for b in (0, 1) for s in ("learned", "fast", "lap")} and set(forage) == {"B0_M1", "B1_M1"}
    assert schema["B0_Sfast"]["history.schema"] == {"taste": (-1.0, 0.0, 0.0)} and "motivation.enabled" not in schema["B0_Sfast"]
    for ov in (*schema.values(), *forage.values()):
        cfg = EngineConfig.research()
        for k, v in ov.items():
            cfg.set_field(k, v)
        e = Engine(seed=1, config=cfg)
        e.run(2)
        assert (e.history.fixed if "history.schema" in ov else e.motivation is not None)
