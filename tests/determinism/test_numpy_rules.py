"""The numpy rules of docs/determinism.md, as far as code can check them.

The engine does not use numpy yet (the first BLAS product that feeds behaviour
is M2b); these tests pin the entry points: importing the engine never imports
numpy, importing ``core`` pins the thread counts before numpy can load (which
``tests/conftest.py`` does for the suite, so the pin is in force inside every
test run), numpy streams are seeded from the ``core.rng`` seed tree, and
``blas_info`` reports the build without raising.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from core.determinism import BLAS_THREAD_VARS, blas_info, numpy_generator, pin_blas_threads
from core.rng import _derive_seed

ROOT = Path(__file__).resolve().parents[2]


def _python(code: str, env: Optional[Dict[str, str]] = None) -> str:
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def _env_without_thread_vars() -> Dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in BLAS_THREAD_VARS}


def test_importing_the_engine_does_not_import_numpy() -> None:
    assert _python("import core.engine, sys; print('numpy' in sys.modules)") == "False"


def test_importing_core_pins_the_thread_counts_before_numpy_loads() -> None:
    code = (
        "import json, os, sys\n"
        "import core\n"
        f"pinned = {{k: os.environ.get(k) for k in {BLAS_THREAD_VARS!r}}}\n"
        "before = 'numpy' in sys.modules\n"
        "import numpy\n"
        "print(json.dumps([pinned, before]))\n"
    )
    pinned, numpy_was_loaded = json.loads(_python(code, env=_env_without_thread_vars()))
    assert pinned == {var: "1" for var in BLAS_THREAD_VARS}
    assert numpy_was_loaded is False
    # A value already in the environment is left alone.
    env = _env_without_thread_vars()
    env["OPENBLAS_NUM_THREADS"] = "3"
    pinned, _ = json.loads(_python(code, env=env))
    assert pinned["OPENBLAS_NUM_THREADS"] == "3"
    assert {var: pinned[var] for var in BLAS_THREAD_VARS if var != "OPENBLAS_NUM_THREADS"} == {
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }


def test_the_thread_counts_are_pinned_inside_this_test_run(thread_vars_preset_by_environment) -> None:
    """``tests/conftest.py`` imports ``core`` before any test module, so the pin is in
    force for the whole suite; numpy is loaded by now (this module imports it). A value
    the environment set before the run is left alone, so only the others must read 1."""
    assert "core" in sys.modules and "numpy" in sys.modules
    for var in BLAS_THREAD_VARS:
        assert os.environ.get(var) == thread_vars_preset_by_environment.get(var, "1"), var


def test_a_test_run_started_without_the_variables_sees_openblas_pinned_to_one_thread() -> None:
    """The subprocess form of the statement above: a pytest run whose environment has none
    of the four variables set sees ``OPENBLAS_NUM_THREADS == "1"`` (and the other three)
    inside its tests, from the conftest alone."""
    target = f"{Path(__file__).relative_to(ROOT)}::test_the_thread_counts_are_pinned_inside_this_test_run"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", target],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=_env_without_thread_vars(),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


def test_numpy_generator_is_reproducible_across_processes_and_distinct_per_name() -> None:
    code = (
        "import json\n"
        "from core.determinism import numpy_generator\n"
        "print(json.dumps({name: numpy_generator(name, 1337).random(4).tolist() for name in ('a', 'b')}))\n"
    )
    first = json.loads(_python(code))
    second = json.loads(_python(code))
    assert first == second
    assert first["a"] != first["b"]
    assert numpy_generator("a", 1337).random(4).tolist() == first["a"]
    assert numpy_generator("a", 1337, agent_offset=1).random(4).tolist() != first["a"]
    assert numpy_generator("a", 1338).random(4).tolist() != first["a"]
    # The child seed is core.rng's derivation, so the stream sits in the same seed tree.
    expected = np.random.Generator(np.random.PCG64(_derive_seed(1337, name="a", agent_offset=0)))
    assert expected.random(4).tolist() == first["a"]


def test_numpy_generator_draws_float64_that_cast_to_python_floats() -> None:
    draws = numpy_generator("odometry", 7).normal(0.0, 1.0, size=3)
    assert draws.dtype == np.float64
    assert all(type(float(x)) is float for x in draws)


def test_pin_blas_threads_sets_unset_variables_and_keeps_preset_ones(monkeypatch) -> None:
    for var in BLAS_THREAD_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OMP_NUM_THREADS", "4")
    effective = pin_blas_threads()
    assert effective == {
        "OMP_NUM_THREADS": "4",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
    assert {var: os.environ[var] for var in BLAS_THREAD_VARS} == effective
    assert pin_blas_threads() == effective  # idempotent


def test_blas_info_returns_the_keys_and_is_json_serialisable() -> None:
    info = blas_info()
    assert list(info) == ["numpy_version", *BLAS_THREAD_VARS, "blas", "lapack"]
    assert info["numpy_version"] == np.__version__
    assert all(isinstance(info[key], str) for key in ("numpy_version", "blas", "lapack"))
    assert all(info[var] is None or isinstance(info[var], str) for var in BLAS_THREAD_VARS)
    json.dumps(info)
