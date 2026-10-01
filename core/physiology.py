"""Simple deterministic astrocyte energy model.

Demand is supplied by the caller (the engine scales it by the agent's current
action), so resting is cheap and moving is expensive. Glycogen regenerates
slowly (baseline feeding) and ATP is capped at baseline, so a resting agent
settles at a sustainable steady state instead of draining to zero and getting
stuck in forced microsleep.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Astrocyte:
    atp: float = 1.0
    glycogen: float = 3.0
    glycogen_max: float = 3.0
    atp_baseline: float = 1.0
    atp_cost: float = 0.04
    glycogen_to_atp_yield: float = 0.5
    glycogen_recharge: float = 0.05
    glycogen_regen: float = 0.03
    atp_floor: float = 0.0

    def tick(self, demand: float = 1.0) -> float:
        """Update energy stores; return a throttle factor in [0,1] from ATP level."""
        cost = self.atp_cost * max(demand, 0.0)
        if self.atp >= cost:
            self.atp -= cost
        else:
            deficit = cost - self.atp
            self.atp = self.atp_floor
            pull = min(self.glycogen, deficit / max(self.glycogen_to_atp_yield, 1e-6))
            self.glycogen -= pull
            self.atp += pull * self.glycogen_to_atp_yield

        # Passive recharge from glycogen when below baseline.
        if self.glycogen > 0 and self.atp < self.atp_baseline:
            transfer = min(self.glycogen_recharge, self.glycogen)
            self.glycogen -= transfer
            self.atp += transfer * self.glycogen_to_atp_yield

        # Passive glycogen regeneration (baseline feeding), capped at the store size.
        self.glycogen = min(self.glycogen_max, self.glycogen + self.glycogen_regen)

        # Clamp to non-negative ranges; ATP never exceeds baseline.
        self.atp = max(self.atp_floor, min(self.atp, self.atp_baseline))
        self.glycogen = max(0.0, self.glycogen)

        return max(0.0, min(1.0, self.atp / self.atp_baseline))


__all__ = ["Astrocyte"]
