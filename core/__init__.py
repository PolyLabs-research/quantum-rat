"""Core components and shared infrastructure for Agent 01.

Importing ``core`` pins the BLAS/OpenMP thread counts to 1
(``core.determinism.pin_blas_threads``, docs/determinism.md). The runtimes
read ``OMP_NUM_THREADS`` and friends when the numpy extension loads, so the
pin only takes effect when ``core`` is imported before the first
``import numpy``; a value already set in the environment is left alone.
"""

from core.determinism import pin_blas_threads as _pin_blas_threads

_pin_blas_threads()
