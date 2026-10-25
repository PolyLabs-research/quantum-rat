"""Rate maps of a place population against the body's true position (M2b step 2, docs/prereg/m2b_place_population.md).

A rate map is what an experimenter would record: each cell's mean rate in square bins of the *true* position, over
the ticks the body spent in each bin. Under a perfect estimate it is the cell's field sampled on the bins; under a
drifting estimate it is the field blurred and shifted by the estimate's error. Maps of two populations recorded on
the same walk (the same body path, the same occupancy) compare bin by bin.

Element-wise numpy and ``numpy.sum`` only (docs/determinism.md).
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads
import numpy as np

DEFAULT_BIN = 1.0  # units (0.1 m), the cell spacing
MIN_SAMPLES = 5  # a bin enters a map comparison when the body spent at least this many ticks in it
MIN_FIELD_RATE = 0.5  # a cell is compared when its reference map reaches this rate in some visited bin


class RateMapAccumulator:
    """Per-bin sums of a population's rates and the bin's occupancy, over square bins of the true position."""

    def __init__(self, n_cells: int, extent: Tuple[float, float], bin_size: float = DEFAULT_BIN) -> None:
        ex, ey = float(extent[0]), float(extent[1])
        self.bin_size = float(bin_size)
        self.nx = int(round(2.0 * ex / self.bin_size))
        self.ny = int(round(2.0 * ey / self.bin_size))
        if self.nx < 1 or self.ny < 1:
            raise ValueError("the extent must hold at least one bin in each direction")
        self.extent = (ex, ey)
        self.sums = np.zeros((self.nx * self.ny, int(n_cells)), dtype=np.float64)
        self.counts = np.zeros(self.nx * self.ny, dtype=np.int64)

    def bin_of(self, x: float, y: float) -> int:
        """The bin of a true position, clamped into the arena (the body sits on the walls' lines)."""
        ix = min(self.nx - 1, max(0, int(math.floor((x + self.extent[0]) / self.bin_size))))
        iy = min(self.ny - 1, max(0, int(math.floor((y + self.extent[1]) / self.bin_size))))
        return iy * self.nx + ix

    def add(self, x: float, y: float, rates: np.ndarray) -> None:
        b = self.bin_of(x, y)
        self.sums[b] += rates
        self.counts[b] += 1

    def bin_centres(self) -> Tuple[np.ndarray, np.ndarray]:
        xs = -self.extent[0] + self.bin_size * (np.arange(self.nx) + 0.5)
        ys = -self.extent[1] + self.bin_size * (np.arange(self.ny) + 0.5)
        gx, gy = np.meshgrid(xs, ys)  # rows of increasing y, x increasing within a row: the bin order
        return gx.reshape(-1), gy.reshape(-1)

    def maps(self) -> np.ndarray:
        """Mean rate per (bin, cell); NaN in unvisited bins."""
        out = np.full_like(self.sums, np.nan)
        seen = self.counts > 0
        out[seen] = self.sums[seen] / self.counts[seen][:, None]
        return out


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    da, db = a - float(np.sum(a)) / a.size, b - float(np.sum(b)) / b.size
    den = math.sqrt(float(np.sum(da * da)) * float(np.sum(db * db)))
    return float(np.sum(da * db)) / den if den > 0.0 else math.nan


def compare_maps(maps: np.ndarray, reference: np.ndarray, counts: np.ndarray, centres_x: np.ndarray, centres_y: np.ndarray,
                 bins_x: np.ndarray, bins_y: np.ndarray, min_samples: int = MIN_SAMPLES,
                 min_field_rate: float = MIN_FIELD_RATE) -> Dict[str, np.ndarray]:
    """Per cell, against the reference maps on the bins both were recorded in (at least ``min_samples`` ticks): the
    Pearson correlation of the two maps, the distance between their rate-weighted centroids, and Skaggs spatial
    information of each (bits per unit rate). A cell whose reference map never reaches ``min_field_rate`` in a
    compared bin (its field was not sampled) reads NaN in every column."""
    keep = counts >= min_samples
    occ = counts[keep].astype(np.float64)
    occ = occ / float(np.sum(occ))
    bx, by = bins_x[keep], bins_y[keep]
    n = maps.shape[1]
    out = {k: np.full(n, np.nan) for k in ("correlation", "centroid_shift", "info", "info_reference", "peak_reference")}
    for j in range(n):
        m, r = maps[keep, j], reference[keep, j]
        peak = float(np.max(r)) if r.size else 0.0
        out["peak_reference"][j] = peak
        if peak < min_field_rate:
            continue
        out["correlation"][j] = _corr(m, r)
        wm, wr = float(np.sum(m)), float(np.sum(r))
        cm = (float(np.sum(m * bx)) / wm, float(np.sum(m * by)) / wm) if wm > 0 else (math.nan, math.nan)
        cr = (float(np.sum(r * bx)) / wr, float(np.sum(r * by)) / wr)
        out["centroid_shift"][j] = math.hypot(cm[0] - cr[0], cm[1] - cr[1])
        out["info"][j] = spatial_information(m, occ)
        out["info_reference"][j] = spatial_information(r, occ)
    return out


def spatial_information(rate_map: np.ndarray, occupancy: np.ndarray) -> float:
    """Skaggs et al. (1993) spatial information, bits per unit rate: sum_b p_b (r_b / mean) log2(r_b / mean)."""
    mean = float(np.sum(occupancy * rate_map))
    if not mean > 0.0:
        return math.nan
    ratio = rate_map / mean
    pos = ratio > 0.0
    return float(np.sum(occupancy[pos] * ratio[pos] * np.log2(ratio[pos])))


def wall_distance(cx: np.ndarray, cy: np.ndarray, extent: Tuple[float, float]) -> np.ndarray:
    """Each centre's distance to the nearest arena wall."""
    return np.minimum(extent[0] - np.abs(cx), extent[1] - np.abs(cy))


__all__ = ["DEFAULT_BIN", "MIN_FIELD_RATE", "MIN_SAMPLES", "RateMapAccumulator", "compare_maps", "spatial_information",
           "wall_distance"]
