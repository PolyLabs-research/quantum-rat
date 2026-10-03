"""Seeds are samples: the pseudo-replication guard (docs/research_plan.md, M0b item 8).

At the legacy defaults no behavioural path draws from the RNG: the seed
reaches only the criticality lattice, which is dormant, so N seeds are N
copies of one run (tools/probes/seed_pseudoreplication: at ``sensors.noise``
0, seeds 1-4 give positions and action sequences identical to the last bit).
A number quoted "over N seeds" on such a config is one sample. This module
refuses that claim unless the caller says in so many words that the seeds
are allowed to be identical.

The stochastic elements a config can have on are the four parameters in
``core.config.STOCHASTIC_PARAMETERS``: sensor noise on the rangefinder and
pain, odometry speed noise and odometry turn noise on the self-motion estimate
(``core.sensors``), and the softmax temperature on action selection
(``brain.systems.basal_ganglia``). ``EngineConfig.stochastic_elements`` lists
the ones that are on.
"""

from __future__ import annotations

import sys
from typing import List, Optional, TextIO

from core.config import STOCHASTIC_PARAMETERS, EngineConfig


class PseudoReplicationError(ValueError):
    """Several seeds were asked for on a config with no stochastic element on."""


def require_seeds_are_samples(
    config: EngineConfig,
    n_seeds: int,
    *,
    allow_identical_seeds: bool = False,
    out: Optional[TextIO] = None,
) -> List[str]:
    """Check that running ``n_seeds`` seeds of ``config`` gives ``n_seeds`` samples.

    Returns ``config.stochastic_elements()`` (empty when nothing is on). When
    ``n_seeds > 1`` and nothing is on, raises :class:`PseudoReplicationError`
    naming the four parameters, unless ``allow_identical_seeds`` is True, in
    which case one warning line goes to ``out`` (stderr by default) and the
    call returns. ``n_seeds <= 1`` always passes: one seed is one sample.
    """
    elements = config.stochastic_elements()
    if n_seeds > 1 and not elements:
        message = (
            f"{n_seeds} seeds asked for, but no stochastic element is on, so every seed is the "
            f"same run (one sample, not {n_seeds}). Set one of {', '.join(STOCHASTIC_PARAMETERS)} "
            f"above 0, or pass allow_identical_seeds (--allow-identical-seeds) to run them anyway."
        )
        if not allow_identical_seeds:
            raise PseudoReplicationError(message)
        print(f"warning: {message}", file=out if out is not None else sys.stderr)
    return elements


__all__ = ["PseudoReplicationError", "require_seeds_are_samples"]
