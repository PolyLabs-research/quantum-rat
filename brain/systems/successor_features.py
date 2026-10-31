"""Successor features over the place code, learned by TD (M2b step 3, docs/prereg/m2b_sr_fields.md).

The successor representation over a feature basis (Dayan 1993; Stachenfeld, Botvinick & Gershman 2017): psi(s), the
expected discounted sum of the features the agent will see from s, is read as M phi(s); M (n x n) is learned by TD from
the agent's own transitions, M <- M + lr * delta phi(s)^T with delta = phi(s) + discount * M phi(s') - M phi(s) (no
bootstrap across an episode boundary, where the target is phi(s) alone). M starts at the identity, so psi = phi before
any learning. The features are the place population's rates normalised to sum 1 (a partition of unity, as
``GaussianPlaceFeatures`` does by default), which keeps the TD iteration's fixed point finite at any discount below 1.

The SR field of feature j is psi_j as a function of position: how much of feature j the agent expects to see from
there. Under a directional policy it extends back from the feature's own field, towards where the agent comes from
(Stachenfeld et al. 2017, after Mehta et al. 2000); near a wall the agent cannot cross, it extends along the wall.

Element-wise numpy and ``numpy.sum`` only, no BLAS product (docs/determinism.md, numpy rules): the tables built from
it reproduce bit for bit across platforms. V = M R, the read-out the plan's row 2b names, is step 4's.
"""

from __future__ import annotations

import math
from typing import Dict

import numpy as np


class SuccessorFeatures:
    """``M`` (n x n), psi(s) = M phi(s), learned by TD(0) on feature vectors."""

    def __init__(self, n: int, learning_rate: float = 0.05, discount: float = 0.95) -> None:
        if n < 1:
            raise ValueError("n must be at least 1")
        if not (math.isfinite(learning_rate) and learning_rate > 0.0):
            raise ValueError("learning_rate must be a positive finite number")
        if not (math.isfinite(discount) and 0.0 <= discount < 1.0):
            raise ValueError("discount must be in [0, 1)")
        self.n = int(n)
        self.lr = float(learning_rate)
        self.gamma = float(discount)
        self.M = np.eye(self.n, dtype=np.float64)
        self.updates = 0

    def psi(self, phi: np.ndarray) -> np.ndarray:
        """M phi, as a row-wise element-wise product and sum (no BLAS)."""
        return np.sum(self.M * phi[None, :], axis=1)

    def update(self, phi: np.ndarray, phi_next: np.ndarray, terminal: bool = False, lr_scale: float = 1.0) -> float:
        """One TD backup of the transition phi -> phi_next; returns |delta| (the Euclidean norm of the error).
        ``lr_scale`` multiplies the learning rate for this backup (acetylcholine's encoding gain, G56; 1.0: as built)."""
        target = phi if terminal else phi + self.gamma * self.psi(phi_next)
        delta = target - self.psi(phi)
        self.M += (self.lr * lr_scale) * (delta[:, None] * phi[None, :])
        self.updates += 1
        return float(math.sqrt(float(np.sum(delta * delta))))

    def field(self, j: int, features: np.ndarray) -> np.ndarray:
        """Feature j's SR field over a set of positions, given their feature vectors (one row per position)."""
        return np.sum(features * self.M[j][None, :], axis=1)

    def fields(self, features: np.ndarray) -> np.ndarray:
        """Every feature's SR field: (positions x features), row p = psi at position p."""
        return np.stack([self.psi(row) for row in features])

    def parameters(self) -> Dict[str, object]:
        return {"learner": "successor_features_td0", "n": self.n, "learning_rate": self.lr, "discount": self.gamma,
                "init": "identity", "updates": self.updates}


def normalised(rates: np.ndarray) -> np.ndarray:
    """A rate vector divided by its sum (a partition of unity); all zeros stay zeros."""
    total = float(np.sum(rates))
    return rates / total if total > 0.0 else np.zeros_like(rates)


__all__ = ["SuccessorFeatures", "normalised"]
