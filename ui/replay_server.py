"""Backwards-compatible entry point for the replay viewer.

The replay viewer is now part of the lab console in ``ui/server.py``; this module
keeps ``from ui.replay_server import app`` and ``python -m ui.replay_server``
working. Prefer ``python -m ui``.
"""

from ui.__main__ import main
from ui.server import create_app

# Reads $CRITICAL_RAT_RUNS_DIR (default "runs") on each request.
app = create_app()

if __name__ == "__main__":
    main()
