"""A tabular successor representation learned by TD (Dayan 1993; docs/research_plan.md section 2, item 2).

``TabularSR`` holds M, an n x n matrix over integer state indices: M[s, s'] is the
expected discounted number of future visits to s' from s under the behaviour that
produced the transitions it was trained on. One TD update per experienced transition
s -> s' (``update``): M[s, :] <- M[s, :] + lr (e_s + discount M[s', :] - M[s, :]), with
``e_s`` the one-hot of s and the successor row taken as zero when s' is terminal. M
starts at the identity (every state occupies itself once), so a row is a usable
"need" from the first step. The M2a gain x need replay rule
(``brain.systems.replay_gain_need``) reads ``need(from, to) = M[from, to]``; nothing
reads M back into the value table or the policy, so learning it changes no decision.

Elementwise numpy only (adds, scalar multiplies), no ``dot``, float64, no RNG
(docs/determinism.md, the numpy rules). The plan's M2b replaces the tabular M with
one over a place population; this is the tabular baseline it asks for.
"""

from __future__ import annotations

from typing import Dict, Mapping

import core  # noqa: F401  # pins the BLAS thread counts before numpy loads (docs/determinism.md rule 2)
import numpy as np


class TabularSR:
    """M over ``n_states`` integer-indexed states, learned by TD(0) on experienced transitions."""

    def __init__(self, n_states: int, learning_rate: float = 0.2, discount: float = 0.95) -> None:
        if n_states < 1:
            raise ValueError("n_states must be >= 1")
        if not (0.0 < learning_rate <= 1.0) or not (0.0 <= discount <= 1.0):
            raise ValueError("learning_rate in (0, 1] and discount in [0, 1]")
        self.n = int(n_states)
        self.lr = float(learning_rate)
        self.gamma = float(discount)
        self.M = np.eye(self.n, dtype=np.float64)
        self.updates = 0
        self.initialised_from_structure = False

    def update(self, state: int, next_state: int, terminal: bool) -> float:
        """One TD update of row ``state``; returns the largest absolute change in the row."""
        if not 0 <= state < self.n or not 0 <= next_state < self.n:
            raise IndexError("state indices must lie in [0, n_states)")
        target = np.zeros(self.n, dtype=np.float64)
        target[state] = 1.0
        if not terminal:
            target = target + self.gamma * self.M[next_state]
        delta = target - self.M[state]
        self.M[state] = self.M[state] + self.lr * delta
        self.updates += 1
        return float(np.max(np.abs(self.lr * delta)))

    def initialise_from(self, transitions: Mapping[int, Mapping[int, float]], iterations: int = 300) -> int:
        """Set M to the SR of a known transition structure: ``transitions[s]`` maps successor states to
        their probabilities under some policy. Iterates M <- I + discount * sum_s' p(s'|s) M[s'] from the
        identity (elementwise row sums, no matrix product) until the largest change falls below 1e-12 or
        ``iterations`` passes; returns the passes made. Mattar & Daw 2018 give their agent the environment's
        transition structure; this is the tabular equivalent, after which ``update`` learns on experience."""
        if any(not 0 <= s < self.n for s in transitions):
            raise IndexError("state indices must lie in [0, n_states)")
        eye = np.eye(self.n, dtype=np.float64)
        M = eye.copy()
        passes = 0
        for passes in range(1, iterations + 1):
            new = eye.copy()
            for s, succ in transitions.items():
                for s_next, p in succ.items():
                    new[s] = new[s] + (self.gamma * p) * M[s_next]
            change = float(np.max(np.abs(new - M)))
            M = new
            if change < 1e-12:
                break
        self.M = M
        self.initialised_from_structure = True
        return passes

    def need(self, from_state: int, to_state: int) -> float:
        """Expected discounted future occupancy of ``to_state`` from ``from_state``."""
        return float(self.M[from_state, to_state])

    def row(self, from_state: int) -> np.ndarray:
        return self.M[from_state].copy()

    def parameters(self) -> Dict[str, object]:
        return {"model": "tabular_sr", "n_states": self.n, "learning_rate": self.lr, "discount": self.gamma,
                "init": "structure (uniform-random policy)" if self.initialised_from_structure else "identity"}


__all__ = ["TabularSR"]
