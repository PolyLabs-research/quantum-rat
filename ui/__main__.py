"""Run the lab console locally: ``python -m ui``.

Opens http://127.0.0.1:8000 in your browser. Ctrl+C stops it.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

from ui.server import LOOPBACK_HOSTS, create_app


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m ui", description="Quantum Rat lab console (live simulator + replay viewer)")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default 127.0.0.1, this machine only)")
    parser.add_argument("--port", type=int, default=None, help="port (default: $PORT, else 8000)")
    parser.add_argument(
        "--runs-dir",
        default=None,
        help="where recorded runs are read and written (default: $CRITICAL_RAT_RUNS_DIR, else ./runs)",
    )
    parser.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    args = parser.parse_args(argv)
    # Flags win; otherwise fall back to the environment variables the old
    # replay server read, then to the built-in defaults.
    if args.runs_dir is None:
        args.runs_dir = os.environ.get("CRITICAL_RAT_RUNS_DIR") or "runs"
    if args.port is None:
        raw = os.environ.get("PORT") or "8000"
        try:
            args.port = int(raw)
        except ValueError:
            parser.error(f"the PORT environment variable must be a whole number, got {raw!r}")
    return args


def main(argv=None) -> None:
    args = parse_args(argv)
    local = args.host in LOOPBACK_HOSTS
    runs_dir = Path(args.runs_dir).resolve()
    app = create_app(runs_dir, local_only=local)

    shown_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    url = f"http://{shown_host}:{args.port}/"
    print(f"Quantum Rat lab console: {url}")
    print(f"Runs directory: {runs_dir}")
    if not local:
        print(
            f"WARNING: bound to {args.host}, so other machines on your network can reach this console "
            "and run simulations or write runs. There is no authentication.",
            file=sys.stderr,
        )
    print("Press Ctrl+C to stop.")

    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    app.run(host=args.host, port=args.port, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
