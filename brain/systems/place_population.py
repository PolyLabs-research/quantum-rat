"""A Gaussian place-cell population over the position estimate (M2b step 2, docs/prereg/m2b_place_population.md).

Cells sit on a regular grid of pitch ``spacing`` over the arena, rows of increasing y with x increasing within a row
(``brain.systems.value_learners.GaussianPlaceFeatures.grid``, unnormalised); cell j's rate at an estimate e is
r_j = max_rate * exp(-|e - c_j|^2 / (2 width^2)), the Gaussian form of RatInABox's place cells. The rates are a
deterministic function of the estimate: a rate model (plan section 2.1), with no spiking or rate noise, so the code
carries the estimate exactly and its error with respect to the body is the estimate's.

``decode`` inverts the code exactly for noiseless rates. For Gaussian tuning, u_j = -2 width^2 log(r_j / max_rate)
- |c_j|^2 = |e|^2 - 2 e.c_j, so for any two cells (c_j - c_k).e = (u_k - u_j) / 2: a linear system in e, solved by
least squares over the ``k`` most active cells against the most active one, with explicit 2 x 2 normal equations
(element-wise numpy and ``numpy.sum`` only, no BLAS product: docs/determinism.md). A check that the code and the
decoder agree, and the read-out the later steps use.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

import numpy as np

from brain.systems.value_learners import GaussianPlaceFeatures

DECODE_CELLS = 9  # the most active cells the decoder solves over (a 3 x 3 neighbourhood on the grid)


class PlacePopulation:
    """``n`` Gaussian place cells on a grid over the rectangle [-extent_x, extent_x] x [-extent_y, extent_y]."""

    def __init__(self, extent: Tuple[float, float], spacing: float = 1.0, width: float = 1.0, max_rate: float = 1.0) -> None:
        ex, ey = float(extent[0]), float(extent[1])
        if not (ex > 0.0 and ey > 0.0 and spacing > 0.0 and width > 0.0 and max_rate > 0.0):
            raise ValueError("extent, spacing, width and max_rate must be positive")
        self.extent = (ex, ey)
        self.spacing = float(spacing)
        self.width = float(width)
        self.max_rate = float(max_rate)
        self.features = GaussianPlaceFeatures.grid(-ex, ex, -ey, ey, self.spacing, self.width, normalise=False)
        self.cx = self.features.cx
        self.cy = self.features.cy
        self._c_sq = self.cx * self.cx + self.cy * self.cy
        self._two_w_sq = 2.0 * self.width * self.width

    @property
    def size(self) -> int:
        return self.features.size

    def centres(self) -> List[Tuple[float, float]]:
        return self.features.centres()

    def rates(self, x: float, y: float) -> np.ndarray:
        """The population's rates at the estimate (x, y), float64, in cell order."""
        return self.max_rate * self.features(x, y)

    def decode(self, rates: np.ndarray, k: int = DECODE_CELLS) -> Tuple[float, float]:
        """The estimate the rates encode (exact for noiseless rates); (nan, nan) when fewer than three cells fire."""
        r = np.asarray(rates, dtype=np.float64)
        order = np.argsort(-r, kind="stable")[:k]
        order = order[r[order] > 0.0]
        if order.size < 3:
            return math.nan, math.nan
        u = -self._two_w_sq * np.log(r[order] / self.max_rate) - self._c_sq[order]
        ref = 0
        ax = self.cx[order] - self.cx[order[ref]]
        ay = self.cy[order] - self.cy[order[ref]]
        b = 0.5 * (u[ref] - u)
        sxx, sxy, syy = float(np.sum(ax * ax)), float(np.sum(ax * ay)), float(np.sum(ay * ay))
        sxb, syb = float(np.sum(ax * b)), float(np.sum(ay * b))
        det = sxx * syy - sxy * sxy
        if not det > 1e-12:
            return math.nan, math.nan
        return (syy * sxb - sxy * syb) / det, (sxx * syb - sxy * sxb) / det

    def parameters(self) -> Dict[str, object]:
        return {"population": "gaussian_place", "n": self.size, "extent": list(self.extent), "spacing": self.spacing,
                "width": self.width, "max_rate": self.max_rate, "decode_cells": DECODE_CELLS}


__all__ = ["DECODE_CELLS", "PlacePopulation"]
