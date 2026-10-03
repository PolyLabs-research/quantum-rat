"""Gate current tournament behaviour against the committed regression baseline.

The other regression test checks the comparison logic against a throwaway
baseline; this one validates the committed `regression/baseline/` fixture, so
an unintended change in tournament behaviour is caught in CI. When a behaviour
change is intended, regenerate the baseline:

    python3 -m tournaments.runner --seed 1337 --n-agents 4 --ticks 200 \
        --protocols open_field,beacon,foraging --out regression/baseline
"""

import json
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_regression_matches_committed_baseline():
    with tempfile.TemporaryDirectory() as d:
        report = Path(d) / "report.json"
        result = subprocess.run(
            [
                "python3",
                "-m",
                "regression.run_regression",
                "--baseline",
                str(REPO / "regression" / "baseline"),
                "--report-file",
                str(report),
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"regression failed:\n{result.stdout}\n{result.stderr}"
        data = json.loads(report.read_text())
        assert data["pass"] is True
