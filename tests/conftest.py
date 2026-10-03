"""Suite-wide setup; pytest loads this before any test module under ``tests/``."""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_ENV_BEFORE_PIN = dict(os.environ)
# Recorded here, independently of core's own flag, so a test can state that nothing
# in this process (a pytest plugin, an earlier conftest import) loaded numpy first.
_NUMPY_LOADED_BEFORE_PIN = "numpy" in sys.modules

import core  # noqa: E402,F401  # first, so pin_blas_threads runs before any test module imports numpy (docs/determinism.md, rule 2)
from core.determinism import BLAS_THREAD_VARS  # noqa: E402


@pytest.fixture(scope="session")
def thread_vars_preset_by_environment() -> dict:
    """The ``*_NUM_THREADS`` values the environment had set before ``core`` pinned the rest (an explicit value wins)."""
    return {name: _ENV_BEFORE_PIN[name] for name in BLAS_THREAD_VARS if name in _ENV_BEFORE_PIN}


@pytest.fixture(scope="session")
def numpy_loaded_before_pin() -> bool:
    """Whether numpy was already imported when this conftest imported ``core`` (it must not be)."""
    return _NUMPY_LOADED_BEFORE_PIN
