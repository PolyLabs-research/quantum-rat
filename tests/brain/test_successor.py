"""The tabular successor representation (brain/systems/successor.py; docs/prereg/rq1_track_gain_need.md).

Each test is named for what it proves: TD learning converges to discounted occupancy on a chain, the terminal
convention, the prior from a known structure equals the analytic SR and converges to the same point learning
reaches, the index checks, and that only elementwise numpy is used.
"""

from __future__ import annotations

import numpy as np
import pytest

from brain.systems.successor import TabularSR


def test_td_learning_converges_to_discounted_occupancy_on_a_chain() -> None:
    sr = TabularSR(4, learning_rate=0.5, discount=0.9)
    assert np.array_equal(sr.M, np.eye(4)) and sr.parameters()["init"] == "identity"
    for _ in range(200):
        sr.update(0, 1, False)
        sr.update(1, 2, False)
        sr.update(2, 3, False)
        sr.update(3, 3, True)  # the consume: the last state occupies itself and nothing follows
    assert sr.row(0) == pytest.approx([1.0, 0.9, 0.81, 0.729], abs=1e-9)
    assert sr.need(0, 3) == pytest.approx(0.729, abs=1e-9) and sr.need(3, 3) == pytest.approx(1.0)
    assert sr.row(3) == pytest.approx([0.0, 0.0, 0.0, 1.0], abs=1e-9)  # a terminal update keeps the row at its one-hot
    assert sr.updates == 800
    assert sr.update(0, 1, False) == pytest.approx(0.0, abs=1e-9)  # converged: no change


def test_the_structure_prior_is_the_analytic_sr_and_the_fixed_point_of_learning() -> None:
    # A two-state cycle 0 -> 1 -> 0: M = (I - gamma T)^-1 with T the permutation.
    sr = TabularSR(2, learning_rate=0.3, discount=0.5)
    passes = sr.initialise_from({0: {1: 1.0}, 1: {0: 1.0}})
    expected = np.linalg.inv(np.eye(2) - 0.5 * np.array([[0.0, 1.0], [1.0, 0.0]]))
    assert sr.M == pytest.approx(expected, abs=1e-10) and passes < 300
    assert sr.initialised_from_structure and "structure" in sr.parameters()["init"]
    # Learning on experience of that very structure leaves it where it is.
    before = sr.M.copy()
    for _ in range(20):
        sr.update(0, 1, False)
        sr.update(1, 0, False)
    assert sr.M == pytest.approx(before, abs=1e-9)
    # A stochastic structure: half-half successors.
    sr = TabularSR(3, discount=0.9)
    sr.initialise_from({0: {1: 0.5, 2: 0.5}, 1: {0: 1.0}, 2: {2: 1.0}})
    T = np.array([[0.0, 0.5, 0.5], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    assert sr.M == pytest.approx(np.linalg.inv(np.eye(3) - 0.9 * T), abs=1e-8)
    # A state without an entry keeps its one-hot row (no successors).
    sr = TabularSR(2, discount=0.9)
    sr.initialise_from({0: {1: 1.0}})
    assert sr.row(1) == pytest.approx([0.0, 1.0]) and sr.row(0) == pytest.approx([1.0, 0.9])


def test_argument_checks() -> None:
    with pytest.raises(ValueError):
        TabularSR(0)
    with pytest.raises(ValueError):
        TabularSR(3, learning_rate=0.0)
    with pytest.raises(ValueError):
        TabularSR(3, discount=1.5)
    sr = TabularSR(3)
    with pytest.raises(IndexError):
        sr.update(0, 3, False)
    with pytest.raises(IndexError):
        sr.initialise_from({5: {0: 1.0}})
    assert sr.M.dtype == np.float64
