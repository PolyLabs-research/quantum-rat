
import subprocess
import tempfile
from pathlib import Path

def run_regression_script(baseline_dir: Path, report_file: Path):
    """Helper to run the regression script."""
    cmd = [
        "python3",
        "-m",
        "regression.run_regression",
        "--baseline", str(baseline_dir),
        "--report-file", str(report_file),
    ]
    # The script will exit with a non-zero code if regression fails, so we don't check=True
    subprocess.run(cmd, capture_output=True, text=True)


def test_regression_report_stability():
    """
    Runs the regression script twice and asserts that the reports are identical.
    This ensures that the comparison logic itself is deterministic.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # We need a baseline to compare against. For this test, we can use the
        # committed baseline, but it's better to create a temporary one to
        # keep the test self-contained.
        baseline_dir = tmpdir_path / "baseline"
        
        # Generate a temporary baseline
        subprocess.run([
            "python3", "-m", "tournaments.runner",
            "--seed", "1337", "--n-agents", "4", "--ticks", "200",
            "--protocols", "open_field,beacon,foraging", "--out", str(baseline_dir)
        ], check=True)

        report1_path = tmpdir_path / "report1.json"
        report2_path = tmpdir_path / "report2.json"

        # Run regression twice
        run_regression_script(baseline_dir, report1_path)
        run_regression_script(baseline_dir, report2_path)

        # The reports should be identical
        report1_content = report1_path.read_text()
        report2_content = report2_path.read_text()

        assert report1_content == report2_content

        # Since we are comparing against the same baseline generated with the same code,
        # the regression should pass.
        import json
        report_data = json.loads(report1_content)
        assert report_data["pass"] is True
