"""Criticality sweep: kappa and mean avalanche size against coupling.

Sweeps the branching ratio (via ``coupling``, where sigma = 4 * coupling)
across couplings and checks two trends: the kappa estimator rises monotonically
with coupling and mean avalanche size grows. Where kappa crosses 1 depends on
the reference exponent (~0.32 with 1.5, ~0.24 with the 2-D value 2.055), and
the lattice's actual critical point is at 0.5
(tools/probes/criticality_critical_point).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from brain.systems.criticality import CriticalityConfig, CriticalityField
from core.rng import spawn_streams


@dataclass
class SweepResult:
    coupling: float
    kappa: float
    mean_avalanche: float
    avalanche_rate: float


def run_trial(coupling: float, steps: int = 4000) -> SweepResult:
    streams = spawn_streams(seed=123, names=["criticality"])
    field = CriticalityField(stream=streams["criticality"], config=CriticalityConfig(coupling=coupling))
    sizes: List[int] = []
    for _ in range(steps):
        metrics = field.step()
        if metrics.avalanche_size > 0:
            sizes.append(metrics.avalanche_size)
    mean_avalanche = sum(sizes) / len(sizes) if sizes else 0.0
    avalanche_rate = len(sizes) / steps
    return SweepResult(
        coupling=coupling,
        kappa=field.kappa,
        mean_avalanche=mean_avalanche,
        avalanche_rate=avalanche_rate,
    )


def run_sweep(couplings: Tuple[float, ...] = (0.15, 0.25, 0.40), steps: int = 4000) -> List[SweepResult]:
    return [run_trial(c, steps=steps) for c in couplings]


def assert_monotonic_trends(results: List[SweepResult]) -> None:
    kappas = [r.kappa for r in results]
    sizes = [r.mean_avalanche for r in results]

    # kappa rises monotonically with the branching ratio and crosses ~1.
    assert all(kappas[i] <= kappas[i + 1] + 1e-9 for i in range(len(kappas) - 1)), (
        f"kappa not monotonic across regimes: {kappas}"
    )
    assert kappas[0] < 1.0 < kappas[-1], (
        f"expected subcritical kappa < 1 < supercritical kappa, got {kappas}"
    )
    # Mean avalanche size grows with coupling.
    assert all(sizes[i] <= sizes[i + 1] for i in range(len(sizes) - 1)), (
        f"mean avalanche size not monotonic: {sizes}"
    )


def main() -> None:
    results = run_sweep()
    assert_monotonic_trends(results)
    for r in results:
        print(
            f"coupling={r.coupling:.2f} sigma={r.coupling * 4:.2f} kappa={r.kappa:.3f} "
            f"mean_avalanche={r.mean_avalanche:.2f} rate={r.avalanche_rate:.3f}"
        )


if __name__ == "__main__":
    main()
