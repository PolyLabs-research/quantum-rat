
import argparse
import subprocess
import tempfile
from pathlib import Path

def run_regression(baseline_dir: Path, report_file: Path) -> None:
    """
    Runs a regression test by comparing a new tournament run against a baseline.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        candidate_dir = Path(tmpdir) / "candidate"
        
        # 1. Run the tournament to generate the candidate data
        print(f"Running tournament to generate candidate in {candidate_dir}...")
        tournament_cmd = [
            "python3",
            "-m",
            "tournaments.runner",
            "--seed", "1337",
            "--n-agents", "4",
            "--ticks", "200",
            "--protocols", "open_field,beacon,foraging",
            "--out", str(candidate_dir),
        ]
        subprocess.run(tournament_cmd, check=True, capture_output=True, text=True)
        print("Tournament run finished.")

        # 2. Compare the candidate against the baseline
        print(f"Comparing candidate ({candidate_dir}) against baseline ({baseline_dir})...")
        compare_cmd = [
            "python3",
            "-m",
            "regression.compare",
            str(baseline_dir),
            str(candidate_dir),
            "--report-file", str(report_file),
        ]
        
        try:
            subprocess.run(compare_cmd, check=True, capture_output=True, text=True)
            print(f"Regression PASSED. Report at {report_file}")
        except subprocess.CalledProcessError as e:
            print(f"Regression FAILED. Report at {report_file}")
            print("--- COMPARE STDOUT ---")
            print(e.stdout)
            print("--- COMPARE STDERR ---")
            print(e.stderr)
            # Re-raise to make sure the script exits with a non-zero code
            raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="Run regression tests.")
    parser.add_argument("--baseline", type=Path, default=Path("regression/baseline"), help="Path to the baseline directory.")
    parser.add_argument("--report-file", type=Path, default=Path("regression/report.json"), help="File to save the JSON report.")
    args = parser.parse_args()

    args.report_file.parent.mkdir(parents=True, exist_ok=True)
    
    run_regression(args.baseline, args.report_file)


if __name__ == "__main__":
    main()
