"""Where the lattice's critical point really is, and what kappa reads there.

Claims (criticality audit, 2026-10-03):

* The field is a synchronous SIR epidemic / bond percolation on a square torus,
  critical at coupling 0.5, not 0.25. At the default 0.25 avalanche statistics
  are lattice-size independent (mean ~4.2, largest 42-62 at L = 16 and 64),
  the signature of a subcritical process; lattice-spanning avalanches (>= half
  the cells) only appear at coupling >= 0.45 and dominate at 0.50.
* The kappa = 1 crossing near coupling 0.32 is an estimator artefact of the
  mean-field reference exponent 1.5; with the 2-D percolation exponent
  187/91 ~ 2.055 it crosses at ~0.25, and at the true critical point (0.5)
  kappa reads ~1.44 at every lattice size because spanning avalanches pile up
  at the lattice size. kappa does not locate criticality in this model under
  either exponent.

The audit swept 9 couplings at L = 16, 64 and 128 (about 90 s); this probe
keeps L = 16 and 64, five couplings and three seeds (about 25 s at scale 1).
"""

from __future__ import annotations

from brain.systems.criticality import CriticalityConfig, CriticalityField, compute_kappa
from core.rng import spawn_streams
from tools.probes._common import Results, budget, mean, probe_main

COUPLINGS = (0.15, 0.25, 0.35, 0.45, 0.50)
SIZES = (16, 64)
SEEDS = (1, 2, 3)
TAU_2D = 187.0 / 91.0  # 2-D percolation cluster-size exponent


def avalanche_sizes(coupling: float, size: int, steps: int, seed: int) -> list:
    stream = spawn_streams(seed=seed, names=["criticality"])["criticality"]
    field = CriticalityField(stream, CriticalityConfig(coupling=coupling, field_size=size, avalanche_history=10**9))
    out = []
    for _ in range(steps):
        m = field.step()
        if m.avalanche_size > 0:
            out.append(m.avalanche_size)
    return out


def run(scale: float = 1.0) -> Results:
    steps = budget(20000, scale, 400)
    out: Results = {
        "config": f"CriticalityField standalone, {steps} generations per run, couplings {COUPLINGS}, "
        f"sizes {SIZES}, seeds {SEEDS}; kappa over the whole run with exponent 1.5 (code) and {TAU_2D:.3f} (2-D)",
    }
    rows = {}
    for size in SIZES:
        for c in COUPLINGS:
            per_seed = [avalanche_sizes(c, size, steps, s) for s in SEEDS]
            half = 0.5 * size * size
            rows[f"L{size}_c{c:.2f}"] = {
                "n_avalanches": int(mean([len(s) for s in per_seed])),
                "mean_size": mean([mean(s) for s in per_seed if s]),
                "max_size": max((max(s) for s in per_seed if s), default=0),
                "frac_spanning_half": mean([sum(1 for x in s if x >= half) / len(s) for s in per_seed if s]),
                "kappa_tau1.5": mean([compute_kappa(s, exponent=1.5) for s in per_seed]),
                "kappa_tau2.055": mean([compute_kappa(s, exponent=TAU_2D) for s in per_seed]),
            }
    out["sweep"] = rows

    def crossing(size: int, key: str):
        prev = None
        for c in COUPLINGS:
            k = rows[f"L{size}_c{c:.2f}"][key]
            if prev is not None and prev[1] < 1.0 <= k:
                # linear interpolation between the two couplings
                return prev[0] + (c - prev[0]) * (1.0 - prev[1]) / (k - prev[1])
            prev = (c, k)
        return None

    for size in SIZES:
        out[f"L{size}_coupling_where_kappa_tau1.5_crosses_1"] = crossing(size, "kappa_tau1.5")
        out[f"L{size}_coupling_where_kappa_tau2.055_crosses_1"] = crossing(size, "kappa_tau2.055")
    out["default_c0.25_mean_size_by_L"] = [rows[f"L{s}_c0.25"]["mean_size"] for s in SIZES]
    out["default_c0.25_max_size_by_L"] = [rows[f"L{s}_c0.25"]["max_size"] for s in SIZES]
    out["c0.50_kappa_tau1.5_by_L"] = [rows[f"L{s}_c0.50"]["kappa_tau1.5"] for s in SIZES]
    out["smallest_coupling_with_spanning_avalanches_L16"] = next(
        (c for c in COUPLINGS if rows[f"L16_c{c:.2f}"]["frac_spanning_half"] > 0), None
    )
    return out


main = probe_main(run, "critical point of the lattice vs the default coupling and the kappa estimator")

if __name__ == "__main__":
    main()
