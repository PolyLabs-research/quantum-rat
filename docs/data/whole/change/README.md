# The whole, part 2: foraging when the world changes (G58)

`python3 -m experiments.whole_change --phase pilot --workers 28`, under the draft preregistration
`docs/prereg/whole_change.md`; read in `docs/decisions.md` G58. From a clean tree with numerical warnings as errors.

`pilot/` (at `734262f`, 363 s): part 1's 27 configurations on seeds 1–12, 60-minute runs whose three visible patches
move without a signal at minute 30. `runs.csv`: per run, survival, the intake in the quarter-hours before and after the
move, the time near the old places (the five minutes after the move and the last quarter-hour), the first meal at a new
patch, the ground covered and noradrenaline either side of the move, efficiency and sleep; `energy_trace.csv`: the
reserve, the gut and sleep every 150 ticks; `summary.json`: the spark (A1–A3) and the verdict.
