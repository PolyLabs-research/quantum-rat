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
- ``config``: the full ``EngineConfig`` as nested dicts (tuples become lists).
  The research profile's ``trn.narrow_above_kappa`` is infinite, which the
  standard library writes as ``Infinity`` and reads back as ``inf``.
- ``dt_s``: the tick length in seconds when the config declares units
  (``config.units.dt_s``), else ``null``.
- ``protocol``: the protocol or scenario name.
- ``seeds``: the seeds the run used, as a list.
- ``ticks_requested``: how many ticks were asked for.
- ``platform``: ``{system, release, machine, python, numpy, blas,
  blas_runtime, blas_threads}``. ``numpy`` is its version or ``null`` when it
  is not installed; ``blas`` is numpy's build-time BLAS description (name,
  version and the OpenBLAS configuration string, which names the kernel the
  build targets) or ``"unknown"``; ``blas_runtime`` is the kernel and thread
  count the loaded library reports through ``threadpoolctl`` when that package
  is installed, else ``null``; ``blas_threads`` holds the four ``*_NUM_THREADS``
  environment variables as set (``null`` when unset).
- ``schema_version``: the ``TickData`` schema version of the data files.

:func:`finish_manifest` adds ``ticks_run`` and ``timing`` ``{wall_seconds,
ticks_per_second}`` once the run is over, and :func:`write_manifest` writes
the whole thing as indented JSON with sorted keys.
"""

from __future__ import annotations

import json
import os
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

THREAD_ENV_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")

GIT_TIMEOUT_S = 5.0


def _tuples_to_lists(value: Any) -> Any:
    """JSON has no tuples: turn every tuple into a list, recursively."""
    if isinstance(value, (list, tuple)):
        return [_tuples_to_lists(v) for v in value]
    if isinstance(value, dict):
        return {k: _tuples_to_lists(v) for k, v in value.items()}
    return value


def config_to_dict(config: Any) -> Dict[str, Any]:
    """An ``EngineConfig`` (or any config dataclass) as nested, JSON-ready dicts.

    ``dataclasses.asdict`` with tuples turned into lists; a plain mapping is
    accepted as-is (and converted the same way), so a manifest can be built
    from a config that was already serialised.
    """
    if is_dataclass(config) and not isinstance(config, type):
        return _tuples_to_lists(asdict(config))
    if isinstance(config, dict):
        return _tuples_to_lists(dict(config))
    raise TypeError(f"config must be a dataclass instance or a dict, not {type(config).__name__}")


def _git(args: Iterable[str], cwd: Path, git: str) -> str:
    out = subprocess.run(
        [git, *args], cwd=str(cwd), capture_output=True, text=True, check=True, timeout=GIT_TIMEOUT_S
    )
    return out.stdout.strip()


def git_info(cwd: Optional[Path] = None, *, git: str = "git") -> Dict[str, Any]:
    """``{sha, dirty, branch}`` of the repository at ``cwd`` (default: this one).

    ``dirty`` counts tracked files only. When ``git`` is missing, times out or
    ``cwd`` is not inside a repository, ``sha`` and ``branch`` are
    ``"unknown"`` and ``dirty`` is ``None``.
    """
    where = Path(cwd) if cwd is not None else REPO_ROOT
    try:
        sha = _git(["rev-parse", "HEAD"], where, git)
        branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], where, git)
        status = _git(["status", "--porcelain", "--untracked-files=no"], where, git)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {"sha": "unknown", "dirty": None, "branch": "unknown"}
    return {"sha": sha, "dirty": bool(status), "branch": branch}


def _numpy_version() -> Optional[str]:
    try:
        import numpy
    except ImportError:
        return None
    return str(numpy.__version__)


def _blas_description() -> str:
    """numpy's build-time BLAS: name, version and configuration, or "unknown"."""
    try:
        import numpy

        deps = numpy.show_config(mode="dicts").get("Build Dependencies", {})
        blas = deps.get("blas", {})
    except Exception:  # noqa: BLE001  (best effort: any numpy, or none at all)
        return "unknown"
    if not isinstance(blas, dict) or not blas.get("found", False):
        return "unknown"
    parts = [str(blas.get("name", "")).strip(), str(blas.get("version", "")).strip()]
    text = " ".join(p for p in parts if p)
    configuration = str(blas.get("openblas configuration", "")).strip()
    if configuration:
        text = f"{text} ({configuration})" if text else configuration
    return text or "unknown"


def _blas_runtime() -> Optional[list]:
    """What the loaded BLAS reports at run time (via threadpoolctl), or None."""
    try:
        import threadpoolctl
    except ImportError:
        return None
    try:
        info = threadpoolctl.threadpool_info()
    except Exception:  # noqa: BLE001
        return None
    keep = ("user_api", "internal_api", "version", "num_threads", "architecture", "threading_layer")
    return [{k: entry.get(k) for k in keep if k in entry} for entry in info]


def platform_info() -> Dict[str, Any]:
    """The machine, interpreter and numerical libraries, as the manifest records them."""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "numpy": _numpy_version(),
        "blas": _blas_description(),
        "blas_runtime": _blas_runtime(),
        "blas_threads": {name: os.environ.get(name) for name in THREAD_ENV_VARS},
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
        manifest.update(_tuples_to_lists(dict(extra)))
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
    """Write the manifest as indented JSON with sorted keys (and a final newline)."""
    Path(path).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


__all__ = [
    "MANIFEST_VERSION",
    "REPO_ROOT",
    "THREAD_ENV_VARS",
    "build_manifest",
    "config_to_dict",
    "finish_manifest",
    "git_info",
    "platform_info",
    "write_manifest",
]
