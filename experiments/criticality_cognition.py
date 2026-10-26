"""Couple criticality to cognition: near-critical dynamics give maximal cortical gain.

Near-criticality is associated with maximal dynamic range / information
transmission. This sweep tunes the excitation/inhibition balance (via the
branching ratio sigma = 4 * coupling), lets each field settle, and reports the
converged kappa and the resulting cortical gain (``near_critical_gain``). The
gain peaks in the near-critical regime (kappa ~ 1) and falls off for sub- and
super-critical fields.

The engine multiplies vision_gain by this gain in proportion to
``BasalGangliaConfig.criticality_gain``, which is 0 by default; at 1.0 and the
default coupling the multiplier is 0.93-1.0 after warm-up and flips no decision
in the barren, beacon or foraging worlds (tools/probes/dormant_couplings). This
module only checks that the gain curve itself peaks where kappa is near 1, which
with the exponent-1.5 estimator is coupling ~0.32, not the lattice's critical
point (0.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from brain.systems.criticality import CriticalityConfig, near_critical_gain
from core.config import EngineConfig
from core.engine import Engine


@dataclass
class GainResult:
    coupling: float
    kappa: float
    gain: float


def _settle_kappa(coupling: float, seed: int = 1337, steps: int = 3000) -> float:
    engine = Engine(seed=seed, config=EngineConfig(criticality=CriticalityConfig(coupling=coupling)))
    for _ in range(steps):
        engine.criticality.step()
    return engine.criticality.kappa


def run_gain_sweep(
    couplings: Tuple[float, ...] = (0.15, 0.25, 0.30, 0.40),
    *,
    seed: int = 1337,
    width: float = 0.3,
) -> List[GainResult]:
    results = []
    for c in couplings:
        kappa = _settle_kappa(c, seed=seed)
        results.append(GainResult(coupling=c, kappa=kappa, gain=near_critical_gain(kappa, width)))
    return results


def assert_gain_peaks_near_criticality(results: List[GainResult]) -> None:
    peak = max(results, key=lambda r: r.gain)
    # The peak gain occurs at a near-critical branching ratio (sigma ~ 1, i.e.
    # coupling ~ 0.25-0.30), and exceeds both the subcritical and supercritical ends.
    assert 0.20 <= peak.coupling <= 0.35, f"gain peak at coupling {peak.coupling}, expected near-critical"
    assert peak.gain > results[0].gain, "peak gain should exceed the subcritical end"
    assert peak.gain > results[-1].gain, "peak gain should exceed the supercritical end"


def main() -> None:
    results = run_gain_sweep()
    assert_gain_peaks_near_criticality(results)
    for r in results:
        print(f"coupling={r.coupling:.2f} sigma={r.coupling * 4:.1f} kappa={r.kappa:.3f} gain={r.gain:.3f}")


if __name__ == "__main__":
    main()
