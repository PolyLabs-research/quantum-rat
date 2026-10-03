"""Provenance manifests: what produced a run, kept beside the data.

Every headless run (``experiments.runner``), every tournament
(``tournaments.manager``) and every console recording
(``ui.sim_session.SimSession.record``) writes a ``manifest.json`` next to its
data files. It records which code, configuration, seeds and platform produced
the run and how long it took, so a result can be traced back to exactly what
made it.

The manifest is provenance, not data. Nothing in it enters ``ticks.jsonl``,
``summary.json``, ``scene.json`` or any run hash, and it is the one file in a
run directory that carries wall-clock time (``created_at`` and ``timing``):
two runs of the same seed write identical data files and different manifests.
Nothing reads a manifest back into a simulation.

Keys written by :func:`build_manifest`:

- ``manifest_version``: this format's version (:data:`MANIFEST_VERSION`).
- ``created_at``: ISO-8601 UTC timestamp.
- ``git``: ``{sha, dirty, branch}`` from the ``git`` command run in the
  repository this module lives in. ``dirty`` is True when a tracked file has
  uncommitted changes (untracked files do not count, as with ``git describe
  --dirty``). Outside a repository, or without ``git``, ``sha`` and ``branch``
  are ``"unknown"`` and ``dirty`` is ``null``: we do not know, so we do not
  claim a clean tree.
- ``profile``: the config's profile label (``"legacy"`` or ``"research"``).
- ``config``: ``EngineConfig.to_dict()``: the full config as nested dicts,
  tuples as lists and non-finite floats as the strings ``"inf"``, ``"-inf"``
  and ``"nan"`` (the research profile's ``trn.narrow_above_kappa``), so the
  file is strict JSON; ``EngineConfig.from_dict`` reads them back as floats.
- ``dt_s``: the tick length in seconds when the config declares units
  (``config.units.dt_s``), else ``null``.
- ``protocol``: the protocol or scenario name.
- ``seeds``: the seeds the run used, as a list.
- ``ticks_requested``: how many ticks were asked for.
- ``platform``: ``{system, release, machine, python, numpy, blas,
  blas_runtime, blas_threads, numpy_loaded_before_pin}``, the numerical
  facts from ``core.determinism.blas_info()``. ``numpy`` is its version or
  ``null`` when it is not installed; ``blas`` is numpy's build-time BLAS
  description (name, version and the OpenBLAS configuration string, which
  names the kernel the build targets) or ``"unknown"``; ``blas_runtime`` is
  what the loaded libraries report through ``threadpoolctl`` (kernel,
  version and the thread count in force now, one entry per library), or
  ``null`` if that package cannot be imported; ``blas_threads`` holds the
  four ``*_NUM_THREADS`` environment variables as set (``null`` when unset);
  ``numpy_loaded_before_pin`` is True when numpy was imported before ``core``
  pinned those variables, in which case the variables say 1 but the loaded
  library did not read them (``blas_runtime`` then shows the real count).
- ``schema_version``: the ``TickData`` schema version of the data files.

:func:`finish_manifest` adds ``ticks_run`` and ``timing`` ``{wall_seconds,
ticks_per_second}`` once the run is over, and :func:`write_manifest` writes
the whole thing as indented JSON with sorted keys, refusing non-finite floats
(``allow_nan=False``) so the file is always strict JSON.
"""

from __future__ import annotations

import json
import math
import platform
import subprocess
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from metrics.schema import SCHEMA_VERSION

MANIFEST_VERSION = 1

# The repository this module lives in: metrics/manifest.py -> repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent

GIT_TIMEOUT_S = 5.0

NON_FINITE = {math.inf: "inf", -math.inf: "-inf"}


def _jsonable(value: Any) -> Any:
    """Strict-JSON form of a plain value tree: tuples become lists and non-finite
    floats the strings ``"inf"``, ``"-inf"`` or ``"nan"`` (``EngineConfig.to_dict``'s encoding)."""
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, float) and not math.isfinite(value):
        return "nan" if math.isnan(value) else NON_FINITE[value]
    return value


def config_to_dict(config: Any) -> Dict[str, Any]:
    """An ``EngineConfig`` (or any config dataclass) as nested, strict-JSON-ready dicts.

    ``EngineConfig.to_dict()`` when the object has one, so the manifest's
    ``config`` is exactly what ``EngineConfig.from_dict`` reads back; any
    other dataclass goes through ``dataclasses.asdict``, and a plain mapping
    is accepted as it is (so a manifest can be built from a config that was
    already serialised). In every case tuples become lists and non-finite
    floats the tagged strings of :func:`_jsonable`.
    """
    to_dict = getattr(config, "to_dict", None)
    if callable(to_dict) and not isinstance(config, type):
        return _jsonable(to_dict())
    if is_dataclass(config) and not isinstance(config, type):
        return _jsonable(asdict(config))
    if isinstance(config, dict):
        return _jsonable(dict(config))
    raise TypeError(f"config must be a dataclass instance or a dict, not {type(config).__name__}")


_GIT_ERRORS = (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired)


def _git(args: Iterable[str], cwd: Path, git: str) -> str:
    out = subprocess.run(
        [git, *args], cwd=str(cwd), capture_output=True, text=True, check=True, timeout=GIT_TIMEOUT_S
    )
    return out.stdout.strip()


def git_info(cwd: Optional[Path] = None, *, git: str = "git") -> Dict[str, Any]:
    """``{sha, dirty, branch}`` of the repository this code lives in.

    ``cwd`` (default :data:`REPO_ROOT`) is where ``git`` runs; its top-level
    directory must be :data:`REPO_ROOT`, or the result is unknown: a copy of
    this package installed inside some other checkout must not report that
    checkout's commit as the code's provenance. ``dirty`` counts tracked files
    only. When ``git`` is missing or times out, or ``cwd`` is not inside this
    repository, ``sha`` and ``branch`` are ``"unknown"`` and ``dirty`` is
    ``None``; when only the status lookup fails, ``sha`` and ``branch`` are
    kept and ``dirty`` alone is ``None``.
    """
    unknown = {"sha": "unknown", "dirty": None, "branch": "unknown"}
    where = Path(cwd) if cwd is not None else REPO_ROOT
    try:
        toplevel = Path(_git(["rev-parse", "--show-toplevel"], where, git)).resolve()
        if toplevel != REPO_ROOT:
            return unknown
        sha = _git(["rev-parse", "HEAD"], where, git)
        branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], where, git)
    except _GIT_ERRORS:
        return unknown
    try:
        status = _git(["status", "--porcelain", "--untracked-files=no"], where, git)
    except _GIT_ERRORS:
        return {"sha": sha, "dirty": None, "branch": branch}
    return {"sha": sha, "dirty": bool(status), "branch": branch}


def platform_info() -> Dict[str, Any]:
    """The machine, interpreter and numerical libraries, as the manifest records them.

    The numerical facts are ``core.determinism.blas_info()``'s, so the string
    docs/determinism.md quotes and the one a manifest records are one thing.
    """
    from core.determinism import BLAS_THREAD_VARS, blas_info  # lazy: metrics must not import core at load

    info = blas_info()
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "numpy": None if info["numpy_version"] == "unknown" else info["numpy_version"],
        "blas": info["blas"],
        "blas_runtime": info["blas_runtime"],
        "blas_threads": {name: info[name] for name in BLAS_THREAD_VARS},
        "numpy_loaded_before_pin": info["numpy_loaded_before_pin"],
    }


def build_manifest(
    config: Any,
    *,
    protocol: str,
    seeds: Iterable[int],
    ticks_requested: int,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """The manifest for a run that is about to start (see the module docstring).

    ``extra`` adds caller-specific keys at the top level (a tournament's
    protocol list, a console recording's parameter overrides); it may not
    reuse a standard key.
    """
    units = getattr(config, "units", None)
    dt_s = getattr(units, "dt_s", None)
    manifest: Dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git": git_info(),
        "profile": getattr(config, "profile", None),
        "config": config_to_dict(config),
        "dt_s": float(dt_s) if dt_s is not None else None,
        "protocol": str(protocol),
        "seeds": [int(s) for s in seeds],
        "ticks_requested": int(ticks_requested),
        "platform": platform_info(),
        "schema_version": SCHEMA_VERSION,
    }
    if extra:
        clash = sorted(set(extra) & set(manifest))
        if clash:
            raise ValueError(f"extra manifest keys clash with standard ones: {clash}")
        manifest.update(_jsonable(dict(extra)))
    return manifest


def finish_manifest(manifest: Dict[str, Any], *, ticks_run: int, wall_seconds: float) -> Dict[str, Any]:
    """Record how the run went: ticks actually run and the wall-clock throughput.

    ``ticks_per_second`` is ``null`` when no time elapsed (nothing to divide by).
    Returns the manifest for chaining.
    """
    wall = float(wall_seconds)
    manifest["ticks_run"] = int(ticks_run)
    manifest["timing"] = {
        "wall_seconds": wall,
        "ticks_per_second": (int(ticks_run) / wall) if wall > 0.0 else None,
    }
    return manifest


def write_manifest(path: Path, manifest: Dict[str, Any]) -> None:
    """Write the manifest as indented, strict JSON with sorted keys (and a final newline).

    ``allow_nan=False``: a non-finite float anywhere in the manifest raises
    ``ValueError`` instead of writing ``Infinity`` or ``NaN``, which are not
    JSON; the config encodes its infinities as strings (:func:`config_to_dict`).
    """
    Path(path).write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n")


__all__ = [
    "MANIFEST_VERSION",
    "REPO_ROOT",
    "build_manifest",
    "config_to_dict",
    "finish_manifest",
    "git_info",
    "platform_info",
    "write_manifest",
]
