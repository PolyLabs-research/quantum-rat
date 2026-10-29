"""G53's probes: the fixed-schema and the forage configurations build engines; the schemas are the stated three."""

from __future__ import annotations

from core.config import EngineConfig
from core.engine import Engine
from experiments import m3_g53_probes as g


def test_the_configurations() -> None:
    schema, forage, vigour = g.configs("schema"), g.configs("forage"), g.configs("vigour")
    assert set(schema) == {f"B{b}_S{s}" for b in (0, 1) for s in ("learned", "fast", "lap")} and set(forage) == {"B0_M1", "B1_M1"}
    assert set(vigour) == {"B0_M1", "B0_M1_noexplore", "B0_M1_vig1", "B0_M1_noexplore_vig1"} and vigour["B0_M1"] == forage["B0_M1"]
    assert vigour["B0_M1_noexplore_vig1"]["motivation.reasons"] == ("forage",) and vigour["B0_M1_vig1"]["motivation.vigour_floor"] == 1.0
    assert schema["B0_Sfast"]["history.schema"] == {"taste": (-1.0, 0.0, 0.0)} and "motivation.enabled" not in schema["B0_Sfast"]
    for ov in (*schema.values(), *forage.values(), *vigour.values()):
        cfg = EngineConfig.research()
        for k, v in ov.items():
            cfg.set_field(k, v)
        e = Engine(seed=1, config=cfg)
        e.run(2)
        assert (e.history.fixed if ov.get("history.schema") else e.motivation is not None)  # None: the schema learned
