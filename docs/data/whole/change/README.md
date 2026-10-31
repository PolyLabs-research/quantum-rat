# The whole, part 2: foraging when the world changes (G58)

`python3 -m experiments.whole_change --phase pilot --workers 28`, under the draft preregistration
`docs/prereg/whole_change.md`; read in `docs/decisions.md` G58. From a clean tree with numerical warnings as errors.

`pilot/` (at `734262f`, 363 s): part 1's 27 configurations on seeds 1–12, 60-minute runs whose three visible patches
move without a signal at minute 30. `runs.csv`: per run, survival, the intake in the quarter-hours before and after the
move, the time near the old places (the five minutes after the move and the last quarter-hour), the first meal at a new
patch, the ground covered and noradrenaline either side of the move, efficiency and sleep; `energy_trace.csv`: the
reserve, the gut and sleep every 150 ticks; `summary.json`: the spark (A1–A3) and the verdict.

## The second design, by smell (G60)

Under the draft preregistration `docs/prereg/whole_smell.md` and its pre-run amendment P1: the three patches are
hidden (smelled, not seen), and the parts run on amendment A2's reward scale with olfaction the thirteenth.

`smell_design/` (`python3 -m experiments.whole_change --phase design --workers 4`, at `416cbd3`, 6.7 s): the
feasibility rule (§2). The whole on design seeds 2001–2004, each run stopped at the move, so nothing after it was
seen before the pilot. `runs.csv`: per seed, the meals before the move, the reserve there and the share asleep;
`summary.json`: the rule (mean 24.75 meals, the bound 6: passes, no fourth patch).
