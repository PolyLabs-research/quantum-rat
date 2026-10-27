"""History: what the agent has sensed and done, and where, kept as decaying traces over its place code (M3; G52).

The agent's learned value was a function of where it is and nothing else, so it could not represent "good here until
I ate it": on a track whose food alternates between the ends, or with food that regrows where it was eaten, its memory
pointed back to the place it had just emptied (G46, G51). A mammal carries its recent history in its state (direction-
selective place cells on tracks, McNaughton, Barnes & O'Keefe 1983; splitter cells, Wood et al. 2000; win-shift
foraging, Olton & Schlosberg 1978). This module is that history, built so that any sense can feed it.

**Channels feed it.** A channel turns what the agent sensed or did this tick into events: a weighting over the place
features (where, in the agent's own estimate frame) and a strength. Each channel has its own bank of traces, one per
timescale, each a vector over the place features in [0, 1]: every tick each trace decays by exp(-1/tau), then each
event writes ``h <- h + (1 - h) * w * s``. Several timescales give a temporal basis (how long ago, not only whether;
after scale-invariant models of time in memory, Shankar & Howard 2012). The built-in channels:

- ``taste``: the agent ate (a primary reward above 0 on contact), at the place it is in.
- ``visit``: the agent is here; its single slow trace is the familiarity of each place (strength 1/familiarisation
  per tick present, forgetting over ``visit_forgetting`` ticks).
- ``sight``: the agent sees food (a vision ray hits a "target"), at the place the hit point is in, by its estimate.

Other senses (smell, touch, ...) are added by registering a channel in ``CHANNELS``: a function from what the engine
hands over (``HistoryInputs``) to events. Nothing else changes.

**What history means is learned, not built in.** For the channels named in ``reward_context``, the SR's expected
reward at each place feature becomes R_eff = R + sum_c sum_k u_ck h_ck, with u (one weight per channel and timescale,
shared by every place: the agent's schema of what, say, having eaten somewhere does to the food there) learned from
the same prediction errors as R. Where food is eaten and gone, u learns to discount the place just eaten at; where it
is there again next time (the gate's goal), u stays near 0. The successor matrix M, the knowledge of where the agent
can get to, is untouched by history.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

Event = Tuple[np.ndarray, float]  # (weights over the place features in [0, 1], strength in (0, 1])


@dataclass
class HistoryInputs:
    """What the engine hands the history channels each tick (all in the agent's own estimate frame)."""

    here: np.ndarray  # the place population's rates at the estimate, peak-normalised to 1
    primary_reward: float  # the map reward this tick (the contact bonus when the agent ate)
    vision: Sequence[Tuple[float, str, float]]  # (angle, kind, distance in units) per vision ray
    estimate: Tuple[float, float, float]  # (x, y, heading)
    rates_at: Callable[[float, float], np.ndarray]  # peak-normalised place rates at an estimate-frame position


def unit_peak(rates: np.ndarray) -> np.ndarray:
    peak = float(np.max(rates)) if rates.size else 0.0
    return rates / peak if peak > 0.0 else np.zeros_like(rates)


def _taste(inp: HistoryInputs, cfg: "HistorySettings") -> List[Event]:
    return [(inp.here, 1.0)] if inp.primary_reward > 0.0 else []


def _visit(inp: HistoryInputs, cfg: "HistorySettings") -> List[Event]:
    return [(inp.here, 1.0 / cfg.visit_familiarisation)]


def _sight(inp: HistoryInputs, cfg: "HistorySettings") -> List[Event]:
    x, y, h = inp.estimate
    out: List[Event] = []
    for angle, kind, dist in inp.vision:
        if kind == "target":
            out.append((inp.rates_at(x + dist * math.cos(h + angle), y + dist * math.sin(h + angle)), 1.0))
    return out


# name -> (event function, settings attribute holding the channel's timescales in ticks)
CHANNELS: Dict[str, Tuple[Callable[[HistoryInputs, "HistorySettings"], List[Event]], str]] = {
    "taste": (_taste, "taste_timescales"),
    "visit": (_visit, "visit_timescales"),
    "sight": (_sight, "sight_timescales"),
}


@dataclass
class HistorySettings:
    channels: Tuple[str, ...] = ("taste", "visit")
    taste_timescales: Tuple[float, ...] = (10.0, 100.0, 1000.0)
    sight_timescales: Tuple[float, ...] = (10.0, 100.0, 1000.0)
    visit_familiarisation: float = 50.0
    visit_forgetting: float = 18000.0
    reward_context: Tuple[str, ...] = ("taste",)

    @property
    def visit_timescales(self) -> Tuple[float, ...]:
        return (self.visit_forgetting,)


@dataclass
class TraceBank:
    timescales: Tuple[float, ...]
    traces: np.ndarray  # (len(timescales), n)
    decay: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        self.decay = np.array([math.exp(-1.0 / t) for t in self.timescales], dtype=np.float64)

    def step_decay(self) -> None:
        self.traces *= self.decay[:, None]

    def write(self, weights: np.ndarray, strength: float) -> None:
        w = np.clip(weights * strength, 0.0, 1.0)
        self.traces += (1.0 - self.traces) * w[None, :]


class History:
    """The trace banks, one per enabled channel, and the learned schema weights for the reward-context channels."""

    def __init__(self, n: int, settings: HistorySettings) -> None:
        unknown = [c for c in settings.channels if c not in CHANNELS]
        if unknown:
            raise ValueError(f"unknown history channel(s) {unknown}; registered: {tuple(CHANNELS)}")
        missing = [c for c in settings.reward_context if c not in settings.channels]
        if missing:
            raise ValueError(f"reward_context channel(s) {missing} are not enabled channels")
        if settings.visit_familiarisation <= 0.0 or any(t <= 0.0 for c in settings.channels for t in getattr(settings, CHANNELS[c][1])):
            raise ValueError("history timescales must be positive")
        self.n = int(n)
        self.settings = settings
        self.banks: Dict[str, TraceBank] = {
            c: TraceBank(tuple(getattr(settings, CHANNELS[c][1])), np.zeros((len(getattr(settings, CHANNELS[c][1])), self.n)))
            for c in settings.channels
        }
        self.schema: Dict[str, np.ndarray] = {c: np.zeros(len(self.banks[c].timescales)) for c in settings.reward_context}
        self.events_this_tick: Dict[str, int] = {c: 0 for c in settings.channels}

    def decay(self) -> None:
        for bank in self.banks.values():
            bank.step_decay()

    def write(self, inputs: HistoryInputs) -> None:
        for name, bank in self.banks.items():
            events = CHANNELS[name][0](inputs, self.settings)
            self.events_this_tick[name] = len(events)
            for weights, strength in events:
                bank.write(weights, strength)

    def reward_adjustment(self) -> Optional[np.ndarray]:
        """sum over reward-context channels and timescales of u_ck * h_ck: what history adds to R, per place feature."""
        if not self.schema:
            return None
        adj = np.zeros(self.n)
        for c, u in self.schema.items():
            adj += np.sum(u[:, None] * self.banks[c].traces, axis=0)
        return adj

    def learn_schema(self, phi: np.ndarray, errors: np.ndarray, rate: float) -> None:
        """u_ck += rate * sum_i phi_i h_ck,i e_i (phi normalised to sum 1; e_i the per-feature reward prediction error)."""
        for c, u in self.schema.items():
            u += rate * np.sum(self.banks[c].traces * (phi * errors)[None, :], axis=1)

    def familiarity(self, phi: np.ndarray) -> float:
        """The familiarity of where the agent is: the visit trace averaged over the active place features (phi sums to 1)."""
        if "visit" not in self.banks:
            return 0.0
        return float(np.sum(phi * self.banks["visit"].traces[0]))

    def summary(self) -> Dict[str, object]:
        return {"channels": list(self.banks), "schema": {c: [round(float(v), 4) for v in u] for c, u in self.schema.items()},
                "events": dict(self.events_this_tick)}


__all__ = ["CHANNELS", "History", "HistoryInputs", "HistorySettings", "TraceBank", "unit_peak"]
