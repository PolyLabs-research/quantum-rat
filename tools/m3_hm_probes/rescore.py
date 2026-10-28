"""G51's and G52's committed tables re-read under G53's statistics (traversals per run; the control as a margin).

    .venv/bin/python -m tools.m3_hm_probes.rescore      # prints both tables; writes diagnostics_out/rescored_g53.txt

The committed summary.json files keep the scores as they were made; this is the same data under the bounds
docs/prereg/m3_step2.md carries since its amendment of 2026-10-28.
"""

from __future__ import annotations

import csv
from pathlib import Path

from experiments import m3_part2 as p2

TABLES = {"Part 2 pilot, capped (G52)": Path("docs/data/m3/part2/pilot"),
          "history/motivation probe (G52)": Path("docs/data/m3/history_motivation/probe")}
OUT = Path("tools/m3_hm_probes/diagnostics_out/rescored_g53.txt")


def rows(path: Path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    lines = []
    for title, d in TABLES.items():
        gate, track, food = rows(d / "gate.csv"), rows(d / "track.csv"), rows(d / "hidden_food.csv")
        cfgs = sorted({r["config"] for r in track})
        lines.append(f"== {title}: {d}")
        lines.append(f"{'config':12s} {'pass':>4s} elig  " + "  ".join(f"{b[:12]:>12s}" for b in p2.BOUNDS))
        for c in cfgs:
            s = p2.score(c, gate, track, food)
            cells = [f"{s['values'][b]:11.2f}{'+' if s['passes'][b] else '-'}" for b in p2.BOUNDS]
            lines.append(f"{c:12s} {s['passed']:4d} {'yes ' if s['eligible'] else 'no  '}  " + "  ".join(cells))
    text = "\n".join(lines) + "\n"
    OUT.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
