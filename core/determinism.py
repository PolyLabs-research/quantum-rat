"""Deterministic trace generation, baseline helpers and the numpy rules.

Single source of truth for the determinism gate, shared by the test suite,
the app's ``/determinism_check`` route, and the baseline-update tool
(docs/determinism.md).

These helpers previously lived under ``tests/determinism`` and were imported
by production/app code, which inverted the normal dependency direction
(shippable code depending on the test package). They now live here in
``core`` so tests depend on code, not the reverse.

Import discipline: ``core/__init__.py`` imports this module to pin the BLAS
thread counts before numpy can load, so everything heavy (the engine, the
config profiles, numpy itself) is imported lazily inside the functions that
need it. Importing ``core.engine`` never imports numpy.
"""

from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional

from core.rng import _derive_seed
from metrics.hash import HASH_KINDS, PHYSICS_FIELDS, RunHash
from metrics.logger import JsonlLogger
from metrics.schema import TickData

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps the import lazy
    from core.config import EngineConfig

DEFAULT_SEED = 1337
DEFAULT_TICKS = 200

PROFILE_NAMES = ("legacy", "research")

# The committed baselines live alongside the determinism tests.
BASELINE_DIR = Path(__file__).resolve().parent.parent / "tests" / "determinism"
BASELINE_PATH = BASELINE_DIR / "baseline_hashes.json"

# Thread-count variables read by the BLAS/OpenMP runtimes at library load.
BLAS_THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")

# Whether numpy was already in ``sys.modules`` when ``pin_blas_threads`` first ran
# (``None`` until it has). True means the pin came too late for this process:
# the loaded BLAS read the thread variables before they were set, so the
# environment says 1 and the library may run more. ``blas_info()`` and the run
# manifest record it, so provenance never claims a pin that is not in force.
NUMPY_LOADED_BEFORE_PIN: Optional[bool] = None


# --- profiles and traces ------------------------------------------------------


def profile_config(profile: str) -> "EngineConfig":
    """``EngineConfig.legacy()`` or ``EngineConfig.research()`` (docs/profiles.md)."""
    from core.config import EngineConfig

    if profile not in PROFILE_NAMES:
        raise ValueError(f"Unknown profile {profile!r}; expected one of {PROFILE_NAMES}")
    return getattr(EngineConfig, profile)()


def generate_trace(seed: int, ticks: int, *, agent_offset: int = 0) -> List[TickData]:
    """Produce a deterministic ``TickData`` sequence for the given seed (no config: legacy)."""
    from core.engine import Engine

    engine = Engine(seed=seed, agent_offset=agent_offset)
    return engine.run(ticks)


def generate_profile_trace(profile: str, seed: int = DEFAULT_SEED, ticks: int = DEFAULT_TICKS) -> List[TickData]:
    """The ``TickData`` sequence of ``profile_config(profile)`` at ``seed`` over ``ticks``."""
    from core.engine import Engine

    engine = Engine(seed=seed, config=profile_config(profile))
    return engine.run(ticks)


# --- hashing ------------------------------------------------------------------


def hash_trace(trace: Iterable[TickData], kind: str = "full") -> List[Dict[str, Any]]:
    """Per-tick hashes plus the whole-run hash of a trace, in the gate's format.

    The one ``RunHash`` accumulation loop behind every determinism baseline
    (the gate's own path, the profile baselines and the update tool).
    ``kind`` is ``full`` (every field, the historical baseline), ``behaviour``
    (the physics fields removed) or ``physics`` (tick index and the physics
    fields only); ``metrics.hash`` defines the split.
    """
    run_hash = RunHash(kind)
    hashes: List[Dict[str, Any]] = []
    for tick in trace:
        digest = run_hash.update(tick)
        hashes.append({"tick": tick.tick, "hash": digest})
    hashes.append({"tick": "run", "hash": run_hash.hexdigest()})
    return hashes


def build_current_trace(
    seed: int = DEFAULT_SEED, ticks: int = DEFAULT_TICKS, kind: str = "full"
) -> List[Dict[str, Any]]:
    """Build the per-tick + whole-run hash list for the current code (no config: legacy)."""
    return hash_trace(generate_trace(seed=seed, ticks=ticks), kind)


# --- baseline files -----------------------------------------------------------


def baseline_path(profile: str = "legacy", kind: str = "full", directory: Optional[Path] = None) -> Path:
    """The hash-list file for ``(profile, kind)``.

    The two full baselines keep their historical names (``baseline_hashes.json``
    for legacy, ``baseline_hashes_research.json``); the split kinds are
    ``baseline_<kind>_<profile>.json``. ``directory`` rebases the file (the
    update tool's ``--out-dir``).
    """
    if profile not in PROFILE_NAMES:
        raise ValueError(f"Unknown profile {profile!r}; expected one of {PROFILE_NAMES}")
    if kind not in HASH_KINDS:
        raise ValueError(f"Unknown hash kind {kind!r}; expected one of {HASH_KINDS}")
    base = Path(directory) if directory is not None else BASELINE_DIR
    if kind == "full":
        return base / ("baseline_hashes.json" if profile == "legacy" else f"baseline_hashes_{profile}.json")
    return base / f"baseline_{kind}_{profile}.json"


def baseline_meta_path(profile: str = "legacy", directory: Optional[Path] = None) -> Path:
    """The metadata file written next to a profile's baselines."""
    base = Path(directory) if directory is not None else BASELINE_DIR
    return base / ("baseline_meta.json" if profile == "legacy" else f"baseline_meta_{profile}.json")


def reference_trace_path(profile: str = "legacy", directory: Optional[Path] = None) -> Path:
    """The committed 200-tick JSONL trace the cross-platform tolerance gate compares against."""
    if profile not in PROFILE_NAMES:
        raise ValueError(f"Unknown profile {profile!r}; expected one of {PROFILE_NAMES}")
    base = Path(directory) if directory is not None else BASELINE_DIR
    return base / f"reference_trace_{profile}.jsonl"


def load_baseline(profile: str = "legacy", kind: str = "full") -> List[Dict[str, Any]]:
    """Load a committed baseline hash list (the legacy full one by default)."""
    path = baseline_path(profile, kind)
    if not path.exists():
        raise FileNotFoundError(f"Baseline file missing: {path}")
    return json.loads(path.read_text())


def write_reference_trace(trace: Iterable[TickData], path: Path) -> Path:
    """Write ``trace`` as the canonical JSONL that ``JsonlLogger`` produces."""
    with JsonlLogger(path) as logger:
        for tick in trace:
            logger.write_tick(tick)
    return Path(path)


# --- numpy rules (docs/determinism.md) ----------------------------------------


def pin_blas_threads() -> Dict[str, str]:
    """Pin the BLAS/OpenMP thread counts to 1 unless already set; return the effective values.

    ``os.environ.setdefault`` so an explicit setting in the environment wins.
    The runtimes read these variables when the numpy extension loads, so this
    must run before the first ``import numpy``; ``core/__init__.py`` calls it
    at import for that reason. The first call records whether numpy was
    already loaded in :data:`NUMPY_LOADED_BEFORE_PIN` and warns when it was:
    the variables are still set, but the library that is already in memory
    did not read them, so the pin is not in force for this process.
    """
    global NUMPY_LOADED_BEFORE_PIN
    if NUMPY_LOADED_BEFORE_PIN is None:
        NUMPY_LOADED_BEFORE_PIN = "numpy" in sys.modules
        if NUMPY_LOADED_BEFORE_PIN:
            warnings.warn(
                "numpy was imported before core pinned the BLAS thread counts; the pin is not in "
                "force for this process (import core before numpy, docs/determinism.md rule 2)",
                RuntimeWarning,
                stacklevel=2,
            )
    effective: Dict[str, str] = {}
    for var in BLAS_THREAD_VARS:
        effective[var] = os.environ.setdefault(var, "1")
    return effective


def numpy_generator(name: str, seed: int, agent_offset: int = 0) -> Any:
    """One ``numpy.random.Generator(PCG64(child_seed))`` for a named stream.

    The child seed is ``core.rng``'s derivation for ``(seed, agent_offset,
    name)``, so a numpy stream sits in the same seed tree as the
    ``random.Random`` streams the engine already uses: the same name gives the
    same draws in any process, and two names give unrelated draws.
    """
    import numpy as np

    child_seed = _derive_seed(seed, name=name, agent_offset=agent_offset)
    return np.random.Generator(np.random.PCG64(child_seed))


def _blas_description(dependency: Any) -> str:
    """One line for a numpy build dependency entry: name, version and, for OpenBLAS, the
    configuration string that names the kernel the build targets; ``unknown`` when absent."""
    if not isinstance(dependency, dict) or not dependency.get("found", True):
        return "unknown"
    parts = [str(dependency[key]).strip() for key in ("name", "version") if dependency.get(key)]
    text = " ".join(p for p in parts if p)
    configuration = dependency.get("openblas configuration")
    if isinstance(configuration, str) and configuration.strip():
        configuration = " ".join(configuration.split())
        text = f"{text} ({configuration})" if text else configuration
    return text or "unknown"


BLAS_RUNTIME_KEYS = ("user_api", "internal_api", "version", "num_threads", "architecture", "threading_layer")


def blas_runtime() -> Optional[List[Dict[str, Any]]]:
    """What the BLAS/OpenMP libraries loaded in this process report, via ``threadpoolctl``.

    One entry per library with its kernel (``architecture``), version and the
    thread count it is running with now, which is the number the pin is meant
    to hold at 1. ``None`` when ``threadpoolctl`` is not importable or fails.
    Only libraries already loaded are listed, so the list is empty before the
    first ``import numpy``.
    """
    try:
        import threadpoolctl
    except ImportError:  # pragma: no cover - threadpoolctl is a dependency
        return None
    try:
        info = threadpoolctl.threadpool_info()
    except Exception:  # noqa: BLE001 - best effort, never fails a run
        return None
    return [{k: entry.get(k) for k in BLAS_RUNTIME_KEYS if k in entry} for entry in info]


def blas_info() -> Dict[str, Any]:
    """numpy version, the four thread variables, the build-time BLAS/LAPACK descriptions,
    the runtime libraries (:func:`blas_runtime`) and :data:`NUMPY_LOADED_BEFORE_PIN`.

    The one source of the numerical-library facts a manifest records
    (``metrics.manifest.platform_info``). Never raises: without numpy every
    description reads ``unknown``, and the thread variables are reported as
    they stand (``None`` when unset).
    """
    info: Dict[str, Any] = {"numpy_version": "unknown"}
    for var in BLAS_THREAD_VARS:
        info[var] = os.environ.get(var)
    info["blas"] = "unknown"
    info["lapack"] = "unknown"
    info["blas_runtime"] = None
    info["numpy_loaded_before_pin"] = NUMPY_LOADED_BEFORE_PIN
    try:
        import numpy as np
    except Exception:  # pragma: no cover - exercised only where numpy is absent
        return info
    info["numpy_version"] = str(getattr(np, "__version__", "unknown"))
    config: Any = None
    try:
        config = np.show_config(mode="dicts")
    except Exception:
        try:
            config = getattr(np.__config__, "CONFIG", None)
        except Exception:
            config = None
    if isinstance(config, dict):
        dependencies = config.get("Build Dependencies") or {}
        if isinstance(dependencies, dict):
            info["blas"] = _blas_description(dependencies.get("blas"))
            info["lapack"] = _blas_description(dependencies.get("lapack"))
    info["blas_runtime"] = blas_runtime()
    return info


__all__ = [
    "BASELINE_DIR",
    "BASELINE_PATH",
    "BLAS_RUNTIME_KEYS",
    "BLAS_THREAD_VARS",
    "DEFAULT_SEED",
    "DEFAULT_TICKS",
    "HASH_KINDS",
    "PHYSICS_FIELDS",
    "PROFILE_NAMES",
    "baseline_meta_path",
    "baseline_path",
    "blas_info",
    "blas_runtime",
    "build_current_trace",
    "generate_profile_trace",
    "generate_trace",
    "hash_trace",
    "load_baseline",
    "NUMPY_LOADED_BEFORE_PIN",
    "numpy_generator",
    "pin_blas_threads",
    "profile_config",
    "reference_trace_path",
    "write_reference_trace",
]
