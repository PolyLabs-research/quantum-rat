"""Criticality via a driven branching process on a lattice (Beggs & Plenz style).

This is the standard neuronal-avalanche model. With a separation of timescales,
the field is driven by a single seed activation only when it is quiescent; that
activity then propagates as a branching process -- each active cell activates
each of its 4 neighbours with probability ``p = coupling``, so the branching
ratio is ``sigma = 4 * coupling``. Each cell fires at most once per avalanche
(refractory), so an avalanche always terminates and its size is the number of
cells that fired.

- sigma < 1 (coupling < 0.25): subcritical -- avalanches die out quickly (small).
- sigma ~ 1 (coupling ~ 0.25): critical -- avalanche sizes follow a power law.
- sigma > 1 (coupling > 0.25): supercritical -- avalanches saturate the lattice.

``kappa`` is the Shew et al. (2009) statistic over the avalanche-size
distribution (reference power-law exponent 1.5): < 1 subcritical, ~ 1 critical,
> 1 supercritical.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Set, Tuple

from core.rng import RNGStream

Cell = Tuple[int, int]


@dataclass
class CriticalityConfig:
    field_size: int = 16
    coupling: float = 0.25  # per-neighbour activation probability; branching ratio = 4 * coupling
    power_law_exponent: float = 1.5  # mean-field branching-process size exponent
    kappa_points: int = 10  # m sample points for the kappa statistic
    kappa_min_avalanches: int = 20  # avalanches needed before kappa is meaningful
    avalanche_history: int = 4000  # cap on retained avalanche sizes
    gain_width: float = 0.3  # width of the near-critical cortical-gain curve (in kappa units)


@dataclass
class CriticalityMetrics:
    active: int  # cells activated this generation
    avalanche_size: int  # size of an avalanche that completed this tick, else 0
    kappa: float


def near_critical_gain(kappa: float, width: float = 0.3) -> float:
    """Cortical gain that peaks at criticality (kappa == 1) and falls off away from it.

    Near-criticality is associated with maximal dynamic range / information
    transmission, so this is used to scale sensory processing: a near-critical
    field processes input best; a sub- or super-critical field processes it worse.
    Returns a value in (0, 1].
    """
    return math.exp(-(((kappa - 1.0) / width) ** 2))


def compute_kappa(sizes: Sequence[int], *, exponent: float = 1.5, m: int = 10) -> float:
    """Shew et al. (2009) kappa from a set of avalanche sizes.

    Returns 1.0 (neutral) when the distribution is too thin to characterise.
    """
    usable = sorted(float(s) for s in sizes if s >= 1)
    n = len(usable)
    if n < 2:
        return 1.0
    s_min, s_max = usable[0], usable[-1]
    if s_max <= s_min:
        return 1.0

    beta = 1.0 - exponent  # CDF antiderivative exponent (e.g. -0.5)
    denom = (s_max ** beta) - (s_min ** beta)
    if denom == 0.0:
        return 1.0

    def f_theory(x: float) -> float:
        return ((x ** beta) - (s_min ** beta)) / denom

    def f_obs(x: float) -> float:
        lo, hi = 0, n
        while lo < hi:
            mid = (lo + hi) // 2
            if usable[mid] <= x:
                lo = mid + 1
            else:
                hi = mid
        return lo / n

    log_min, log_max = math.log(s_min), math.log(s_max)
    total = 0.0
    for k in range(m):
        frac = k / (m - 1) if m > 1 else 0.5
        beta_k = math.exp(log_min + frac * (log_max - log_min))
        total += f_theory(beta_k) - f_obs(beta_k)
    return 1.0 + total / m


class CriticalityField:
    """Driven branching process on a toroidal lattice with kappa tracking."""

    def __init__(self, stream: RNGStream, config: CriticalityConfig | None = None) -> None:
        self.config = config or CriticalityConfig()
        self.stream: RNGStream = stream
        self.kappa = 1.0
        self._active: Set[Cell] = set()
        self._fired: Set[Cell] = set()  # cells that fired in the current avalanche
        self._cur_size = 0
        self._sizes: List[int] = []

    def _neighbors(self, i: int, j: int) -> Tuple[Cell, ...]:
        n = self.config.field_size
        return (((i + 1) % n, j), ((i - 1) % n, j), (i, (j + 1) % n), (i, (j - 1) % n))

    def _seed_cell(self) -> Cell:
        n = self.config.field_size
        return (self.stream.randint(0, n - 1), self.stream.randint(0, n - 1))

    def _record_size(self, size: int) -> None:
        self._sizes.append(size)
        if len(self._sizes) > self.config.avalanche_history:
            self._sizes.pop(0)
        if len(self._sizes) >= self.config.kappa_min_avalanches:
            self.kappa = compute_kappa(
                self._sizes, exponent=self.config.power_law_exponent, m=self.config.kappa_points
            )

    def step(self) -> CriticalityMetrics:
        """Advance one generation of the branching process."""
        if not self._active:
            # Quiescent: drive a single seed (separation of timescales).
            seed = self._seed_cell()
            self._active = {seed}
            self._fired = {seed}
            self._cur_size = 1
            return CriticalityMetrics(active=1, avalanche_size=0, kappa=self.kappa)

        # Propagate: each active cell activates each neighbour with prob coupling.
        p = self.config.coupling
        next_active: Set[Cell] = set()
        for (i, j) in self._active:
            for nb in self._neighbors(i, j):
                if nb in self._fired:
                    continue
                if self.stream.random() < p:
                    next_active.add(nb)
        self._fired |= next_active
        self._cur_size += len(next_active)
        self._active = next_active

        if not next_active:
            # Avalanche terminated; record and reset for the next drive.
            completed = self._cur_size
            self._record_size(completed)
            self._cur_size = 0
            self._fired = set()
            return CriticalityMetrics(active=0, avalanche_size=completed, kappa=self.kappa)

        return CriticalityMetrics(active=len(next_active), avalanche_size=0, kappa=self.kappa)


__all__ = [
    "CriticalityField",
    "CriticalityConfig",
    "CriticalityMetrics",
    "compute_kappa",
    "near_critical_gain",
]
