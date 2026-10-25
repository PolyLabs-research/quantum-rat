"""The place population, its decoder, its engine hook and the rate-map metrics (M2b step 2,
docs/prereg/m2b_place_population.md)."""

from __future__ import annotations

import math
import subprocess
import sys

import numpy as np
import pytest

from analysis.place_metrics import RateMapAccumulator, compare_maps, spatial_information, wall_distance
from brain.systems.place_population import DECODE_CELLS, PlacePopulation
from core.config import EngineConfig, PlaceConfig
from core.engine import Engine


def test_the_population_is_a_grid_of_gaussians_and_the_decoder_inverts_it() -> None:
    pop = PlacePopulation((10.0, 10.0), spacing=1.0, width=1.0, max_rate=2.0)
    assert pop.size == 400 and pop.centres()[0] == (-9.5, -9.5) and pop.centres()[1] == (-8.5, -9.5) and pop.centres()[-1] == (9.5, 9.5)
    r = pop.rates(0.5, -0.5)
    j = pop.centres().index((0.5, -0.5))
    assert r[j] == pytest.approx(2.0) and r.dtype == np.float64 and float(np.max(r)) == pytest.approx(2.0)
    assert r[pop.centres().index((1.5, -0.5))] == pytest.approx(2.0 * math.exp(-0.5))
    # Exact inside the arena and far outside it, beyond an edge as well as a corner: the first version took the nine
    # most active cells, which beyond an edge are one collinear column, and returned NaN at (21, 0.3) and (25, -3).
    for x, y in [(0.0, 0.0), (9.99, -9.99), (-10.0, 4.2), (3.3, 7.7), (12.0, -11.0), (-15.0, 0.25), (21.0, 0.3), (25.0, -3.0),
                 (30.0, 30.0), (0.0, -35.0)]:
        dx, dy = pop.decode(pop.rates(x, y))
        assert math.hypot(dx - x, dy - y) < 1e-9, (x, y)
    rng = np.random.default_rng(0)  # a local generator, not a behavioural stream
    for x, y in rng.uniform(-30.0, 30.0, size=(2000, 2)):
        dx, dy = pop.decode(pop.rates(float(x), float(y)))
        assert math.hypot(dx - x, dy - y) < 1e-6
    assert DECODE_CELLS == 9 and list(pop.neighbourhood(0)) == [0, 1, 20, 21] and len(pop.neighbourhood(21)) == 9
    silent = np.zeros(pop.size)
    assert all(math.isnan(v) for v in pop.decode(silent))
    two = np.zeros(pop.size)
    two[:2] = 0.5
    assert all(math.isnan(v) for v in pop.decode(two))  # fewer than three firing cells
    assert pop.parameters()["n"] == 400 and pop.parameters()["width"] == 1.0
    with pytest.raises(ValueError):
        PlacePopulation((10.0, 10.0), width=0.0)
    with pytest.raises(ValueError):
        PlaceConfig(spacing=-1.0)
    with pytest.raises(ValueError):
        PlaceConfig(extent=(10.0,))
    assert PlaceConfig(extent=[10, 5]).extent == (10.0, 5.0)
    for profile in (EngineConfig.legacy(), EngineConfig.research()):
        assert not profile.place.enabled


def test_the_engine_computes_the_rates_at_the_estimate_and_changes_nothing_else() -> None:
    cfg = EngineConfig.research()
    cfg.place.enabled = True
    eng = Engine(seed=3, config=cfg)
    assert eng.place.size == 400 and eng.place.extent == (10.0, 10.0)
    trace = eng.run(300, reset=True)
    st = eng.spatial.state
    np.testing.assert_array_equal(eng.place_rates, eng.place.rates(st.grid_x, st.grid_y))
    assert eng._ctx.place_rates is eng.place_rates
    plain = Engine(seed=3, config=EngineConfig.research())
    assert plain.place is None and plain.place_rates is None
    plain_trace = plain.run(300, reset=True)
    assert [td.pos for td in plain_trace] == [td.pos for td in trace]
    assert [td.obs_checksum for td in plain_trace] == [td.obs_checksum for td in trace]  # the population is not observed
    custom = EngineConfig.research()
    custom.place.enabled = True
    custom.place.extent = (5.0, 5.0)
    custom.place.spacing = 2.5
    assert Engine(seed=1, config=custom).place.size == 16


def test_importing_the_engine_still_does_not_import_numpy() -> None:
    code = "import sys, core.engine; print('numpy' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_rate_maps_and_their_comparison() -> None:
    pop = PlacePopulation((2.0, 2.0), spacing=1.0, width=1.0)
    acc = RateMapAccumulator(pop.size, (2.0, 2.0), bin_size=1.0)
    assert (acc.nx, acc.ny) == (4, 4) and acc.bin_of(-2.0, -2.0) == 0 and acc.bin_of(2.0, 2.0) == 15 and acc.bin_of(5.0, 0.1) == 11
    for x in np.linspace(-1.9, 1.9, 20):
        for y in np.linspace(-1.9, 1.9, 20):
            for _ in range(2):
                acc.add(float(x), float(y), pop.rates(float(x), float(y)))
    maps = acc.maps()
    assert maps.shape == (16, pop.size) and not np.any(np.isnan(maps))
    bx, by = acc.bin_centres()
    assert (bx[0], by[0]) == (-1.5, -1.5) and (bx[3], by[3]) == (1.5, -1.5)
    same = compare_maps(maps, maps, acc.counts, pop.cx, pop.cy, bx, by, min_samples=1, min_field_rate=0.1)
    assert np.allclose(same["correlation"], 1.0) and np.allclose(same["centroid_shift"], 0.0)
    assert np.allclose(same["info"], same["info_reference"])
    shifted = np.roll(maps, 1, axis=1)  # every cell takes its neighbour's map
    other = compare_maps(shifted, maps, acc.counts, pop.cx, pop.cy, bx, by, min_samples=1, min_field_rate=0.1)
    assert float(np.nanmean(other["correlation"])) < 0.9 and float(np.nanmean(other["centroid_shift"])) > 0.3
    unsampled = compare_maps(maps, np.zeros_like(maps), acc.counts, pop.cx, pop.cy, bx, by)
    assert np.all(np.isnan(unsampled["correlation"]))
    occ = np.full(4, 0.25)
    assert spatial_information(np.ones(4), occ) == pytest.approx(0.0)
    assert spatial_information(np.array([4.0, 0, 0, 0]), occ) == pytest.approx(2.0)
    assert math.isnan(spatial_information(np.zeros(4), occ))
    assert list(wall_distance(np.array([1.5, -0.5]), np.array([0.5, 1.9]), (2.0, 2.0))) == pytest.approx([0.5, 0.1])
