"""Protocol base classes for headless experiments."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from core.config import EngineConfig
from metrics.schema import TickData


class Protocol(ABC):
    name: str = "base"

    def engine_config(self) -> Optional[EngineConfig]:
        """The engine configuration this protocol needs, or None to take the runner's.

        The default is None: the runner then builds the engine from its base
        profile (``--profile``, legacy unless asked otherwise). A protocol that
        returns a config decides the whole configuration itself, profile label
        included, and the runner's base profile does not apply. The console
        scenarios' adapters return the scenario's own config this way.
        """
        return None

    @abstractmethod
    def setup(self, engine: Any) -> None:
        """Deterministically configure engine/world before running."""

    @abstractmethod
    def on_tick(self, engine: Any, tickdata: TickData, tick_index: int) -> None:
        """Hook invoked every tick."""

    @abstractmethod
    def is_done(self, engine: Any, tickdata: TickData, tick_index: int) -> bool:
        """Return True to end the episode early."""

    @abstractmethod
    def summarize(self) -> Dict[str, Any]:
        """Return summary metrics and score."""


__all__ = ["Protocol"]
