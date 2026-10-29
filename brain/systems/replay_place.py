"""The engine's side of Mattar & Daw's rule over the place code (M3 step 3; ``brain.systems.replay_mattar_daw``).

``PlaceQModel`` is the ``QReplayModel`` the gain x need rule reads when the learner is the action value over the place
features: a state is the place cell with the largest rate at a position (the Dyna model's cell-to-cell table is the
transition memory read that way); a stored transition carries its action, so ``action_of`` is never asked; the action
scores on given Q values are the memory terms the selector would read (the forward bias plus ``value_gain`` x Q), and
the policy is the selector's softmax at its temperature; need is the successor features' expected discounted occupancy
of a cell from where the agent acts next, psi(phi_acting)[cell], the SR row the plan names; the acting state is the
cell under the agent's estimate.
"""

from __future__ import annotations

import math
from typing import Dict, Mapping

import numpy as np

from brain.systems.action_value import ACTIONS


class PlaceQModel:
    def __init__(self, engine) -> None:  # core.engine.Engine with place, sr and action_learner on
        if engine.place is None or engine.sr is None or engine.action_learner is None:
            raise ValueError("PlaceQModel needs the place population, the successor features and the action value")
        self.engine = engine
        self._acting_phi: np.ndarray | None = None

    def state_index(self, x: float, y: float) -> int:
        return int(np.argmax(self.engine.place.rates(x, y)))

    def action_of(self, x: float, y: float, x_next: float, y_next: float) -> str:
        raise RuntimeError("a transition over the place code carries its action (StoredTransition.action)")

    def action_scores(self, q: Mapping[str, float]) -> Dict[str, float]:
        bg = self.engine.config.basal_ganglia
        return {a: (bg.forward_bias if a == "FORWARD" else 0.0) + bg.value_gain * q[a] for a in ACTIONS}

    def policy(self, scores: Mapping[str, float]) -> Dict[str, float]:
        temperature = self.engine.config.basal_ganglia.softmax_temperature
        if temperature <= 0.0:  # the argmax arbiter: all on the best, ties to the first in order
            best = max(scores.values())
            first = next(a for a in ACTIONS if scores[a] == best)
            return {a: (1.0 if a == first else 0.0) for a in ACTIONS}
        top = max(scores.values())
        weights = {a: math.exp((scores[a] - top) / temperature) for a in ACTIONS}
        total = math.fsum(weights.values())
        return {a: w / total for a, w in weights.items()}

    def learning_rate(self) -> float:
        return self.engine.config.action_value.learning_rate

    def discount(self) -> float:
        return self.engine.config.action_value.discount

    def need(self, from_state: int, to_state: int) -> float:
        phi = self._acting_phi
        if phi is None:
            phi = np.zeros(self.engine.place.size, dtype=np.float64)
            phi[from_state] = 1.0
        return float(self.engine.sr.psi(phi)[to_state])

    def acting_state(self) -> int:
        ctx = self.engine.context
        x, y = (ctx.grid_x, ctx.grid_y) if ctx is not None else (0.0, 0.0)
        rates = self.engine.place.rates(x, y)
        total = float(np.sum(rates))
        self._acting_phi = rates / total if total > 0.0 else None
        return int(np.argmax(rates))


__all__ = ["PlaceQModel"]
