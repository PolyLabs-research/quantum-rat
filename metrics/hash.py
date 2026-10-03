"""Hash utilities for TickData traces.

Three hash kinds (docs/determinism.md):

``full``
    the whole normalised tick, exactly as hashed since the first baseline;
``behaviour``
    the normalised tick with the physics fields removed;
``physics``
    the tick index plus the physics fields only.

The physics fields are the criticality lattice's outputs and the replay
cursor (``PHYSICS_FIELDS``). Keeping them in a hash of their own means the
lattice and the replay internals can change without invalidating a
behavioural baseline, and a behavioural change is visible on its own.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Mapping, Union

from .logger import _canonical_json, _normalize_tick
from .schema import TickData

TickLike = Union[TickData, Mapping[str, Any]]

PHYSICS_FIELDS = ("kappa", "avalanche_size", "criticality_active", "replay_index")
HASH_KINDS = ("full", "behaviour", "physics")


def hash_payload(tick: TickLike, kind: str = "full") -> Mapping[str, Any]:
    """The mapping that ``tick_hash`` canonicalises for ``kind``.

    ``full`` is ``_normalize_tick`` unchanged. ``behaviour`` drops the physics
    fields (absent ones are simply not there). ``physics`` keeps ``tick`` and
    the physics fields in ``PHYSICS_FIELDS`` order; a missing one raises
    ``KeyError`` rather than hashing a shorter record.
    """
    payload = _normalize_tick(tick)
    if kind == "full":
        return payload
    if kind == "behaviour":
        return {key: value for key, value in payload.items() if key not in PHYSICS_FIELDS}
    if kind == "physics":
        subset: Dict[str, Any] = {"tick": payload["tick"]}
        for key in PHYSICS_FIELDS:
            subset[key] = payload[key]
        return subset
    raise ValueError(f"Unknown hash kind {kind!r}; expected one of {HASH_KINDS}")


def tick_hash(tick: TickLike, kind: str = "full") -> str:
    """Return a deterministic hash for a single tick (``full`` by default)."""
    canonical = _canonical_json(hash_payload(tick, kind))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RunHash:
    """Accumulator for a full run; feeds on per-tick hashes of one ``kind``."""

    def __init__(self, kind: str = "full") -> None:
        if kind not in HASH_KINDS:
            raise ValueError(f"Unknown hash kind {kind!r}; expected one of {HASH_KINDS}")
        self.kind = kind
        self._hasher = hashlib.sha256()

    def update(self, tick: TickLike) -> str:
        digest = tick_hash(tick, self.kind)
        self._hasher.update(digest.encode("utf-8"))
        return digest

    def hexdigest(self) -> str:
        return self._hasher.hexdigest()


__all__ = ["HASH_KINDS", "PHYSICS_FIELDS", "RunHash", "hash_payload", "tick_hash"]
