"""The energy model must sustain a resting agent and tax a sprinting one.

Previously ATP (and glycogen) drained monotonically to zero regardless of
behaviour, so any long assay mostly measured a sleeping/dying agent. Now
demand scales with effort and glycogen regenerates, so rest is sustainable
while sustained sprinting still depletes (and triggers microsleep).
"""

from core.config import AstrocyteConfig, TRNConfig
from core.physiology import Astrocyte


def test_resting_agent_sustains_energy_above_microsleep_trigger():
    astro = Astrocyte()
    rest_demand = AstrocyteConfig().rest_demand
    trigger = TRNConfig().trigger_atp
    throttles = [astro.tick(demand=rest_demand) for _ in range(500)]
    assert astro.atp > trigger  # never drains into microsleep territory
    assert min(throttles[-100:]) > 0.0  # stable, non-zero throttle at steady state


def test_sustained_sprinting_depletes_energy():
    astro = Astrocyte()
    for _ in range(300):
        astro.tick(demand=1.0)
    assert astro.atp < 0.2  # sustained max effort draws ATP down toward the floor
