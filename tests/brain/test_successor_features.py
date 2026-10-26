"""Successor features over a feature basis, learned by TD (M2b step 3, docs/prereg/m2b_sr_fields.md)."""

from __future__ import annotations

import numpy as np
import pytest

from brain.systems.successor_features import SuccessorFeatures, normalised


def test_identity_start_and_the_update() -> None:
    sr = SuccessorFeatures(3, learning_rate=0.5, discount=0.9)
    phi = np.array([0.2, 0.8, 0.0])
    np.testing.assert_array_equal(sr.psi(phi), phi)  # M starts at the identity
    nxt = np.array([0.0, 0.0, 1.0])
    delta = phi + 0.9 * nxt - phi
    sr.update(phi, nxt)
    np.testing.assert_allclose(sr.M, np.eye(3) + 0.5 * np.outer(delta, phi))
    term = SuccessorFeatures(3, 0.5, 0.9)
    assert term.update(phi, nxt, terminal=True) == pytest.approx(0.0)  # the target is phi alone: no error at the start
    np.testing.assert_array_equal(term.M, np.eye(3))
    assert term.updates == 1 and term.parameters()["init"] == "identity"
    with pytest.raises(ValueError):
        SuccessorFeatures(3, discount=1.0)
    with pytest.raises(ValueError):
        SuccessorFeatures(0)
    np.testing.assert_array_equal(normalised(np.array([1.0, 3.0])), [0.25, 0.75])
    np.testing.assert_array_equal(normalised(np.zeros(2)), [0.0, 0.0])


def test_one_hot_features_converge_to_the_tabular_sr_of_a_loop() -> None:
    """With one-hot features psi(s) = M e_s is column s of M, and TD converges to M = (I - gamma P^T)^-1 for the
    loop 0 -> 1 -> 2 -> 0: column s holds the discounted future occupancy of every state from s."""
    n, gamma = 3, 0.9
    sr = SuccessorFeatures(n, learning_rate=0.2, discount=gamma)
    eye = np.eye(n)
    for _ in range(3000):
        for s in range(n):
            sr.update(eye[s], eye[(s + 1) % n])
    P = np.zeros((n, n))
    for s in range(n):
        P[s, (s + 1) % n] = 1.0
    np.testing.assert_allclose(sr.M, np.linalg.inv(np.eye(n) - gamma * P.T), atol=1e-8)
    # The SR field of state 1 over the three states: highest at 1 itself, then at 0 (one step before it), then 2.
    field = sr.field(1, eye)
    assert field[1] > field[0] > field[2]
    np.testing.assert_allclose(sr.fields(eye)[:, 1], field)
