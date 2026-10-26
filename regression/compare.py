
import json
import math
import argparse
from pathlib import Path

REL_TOL = 1e-6
ABS_TOL = 1e-9


def _differs(a, b) -> bool:
    """Deep comparison with a numeric tolerance (so float noise is not a regression)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a != b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return not math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return True
        return any(_differs(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return True
        return any(_differs(x, y) for x, y in zip(a, b))
    return a != b


def compare_json_files(file1: Path, file2: Path, base1: Path, base2: Path) -> dict:
    """Compares two JSON files and returns a summary of differences."""
    report = {"file1": str(file1.relative_to(base1)), "file2": str(file2.relative_to(base2)), "differs": False, "details": {}}

    if not file1.exists():
        report["differs"] = True
        report["details"]["error"] = f"File not found: {file1}"
        return report

    if not file2.exists():
        report["differs"] = True
        report["details"]["error"] = f"File not found: {file2}"
        return report

    try:
        data1 = json.loads(file1.read_text())
        data2 = json.loads(file2.read_text())
    except json.JSONDecodeError as e:
        report["differs"] = True
        report["details"]["error"] = f"JSON decode error: {e}"
        return report

    if _differs(data1, data2):
        report["differs"] = True
        # For now, just a simple diff. A more detailed diff could be implemented.
        report["details"]["diff"] = "Content differs"

    return report


def compare_dirs(dir1: Path, dir2: Path) -> dict:
    """Recursively compares two directories of tournament results."""
    report = {"differs": False, "files": []}
    
    # We only care about json files for comparison. manifest.json is provenance
    # (git SHA, wall-clock, platform; metrics/manifest.py): it differs between
    # any two runs by design and is not behaviour, so it is left out.
    files1 = sorted(p for p in dir1.glob("**/*.json") if p.name != "manifest.json")
    files2 = sorted(p for p in dir2.glob("**/*.json") if p.name != "manifest.json")

    relative_files1 = {p.relative_to(dir1) for p in files1}
    relative_files2 = {p.relative_to(dir2) for p in files2}

    if relative_files1 != relative_files2:
        report["differs"] = True
        report["structure_diff"] = {
            "only_in_dir1": sorted([str(p) for p in relative_files1 - relative_files2]),
            "only_in_dir2": sorted([str(p) for p in relative_files2 - relative_files1]),
        }
        return report

    for rel_path in sorted(list(relative_files1)):
        file1 = dir1 / rel_path
        file2 = dir2 / rel_path
        file_report = compare_json_files(file1, file2, dir1, dir2)
        if file_report["differs"]:
            report["differs"] = True
        report["files"].append(file_report)
        
    return report

def main():
    parser = argparse.ArgumentParser(description="Compare two tournament run directories.")
    parser.add_argument("dir1", type=Path, help="First directory to compare (e.g., baseline).")
    parser.add_argument("dir2", type=Path, help="Second directory to compare (e.g., candidate).")
    parser.add_argument("--report-file", type=Path, help="File to save the JSON report.")
    args = parser.parse_args()

    report = compare_dirs(args.dir1, args.dir2)
    report["pass"] = not report["differs"]
    
    report_json = json.dumps(report, indent=2, sort_keys=True)
    
    if args.report_file:
        args.report_file.write_text(report_json)
    else:
        print(report_json)
        
    if not report["pass"]:
        raise SystemExit("Regression check FAILED: Directories differ.")
    else:
        print("Regression check PASSED: Directories are identical.")

if __name__ == "__main__":
    main()

