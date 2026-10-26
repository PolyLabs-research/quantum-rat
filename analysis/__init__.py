"""Analysis: statistics, extraction and reports over run data.

Importing this package imports ``core`` first, so the BLAS thread pin
(``core.determinism.pin_blas_threads``, docs/determinism.md rule 2) is in
force before the numpy and pandas imports of its modules load the libraries.
"""

import core  # noqa: F401
