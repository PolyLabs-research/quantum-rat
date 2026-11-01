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

`smell_pilot/` (`python3 -m experiments.whole_change --phase smell --workers 28`, at `fcb20d8`, 287 s): the 29
configurations on seeds 1–12, 60-minute runs whose three hidden patches move without a signal at minute 30. `runs.csv`:
part 2's columns and the meals before the move; `energy_trace.csv`: the reserve, the gut and sleep every 150 ticks;
`summary.json`: the validity checks (V1, V2), the spark (A1–A3) and the verdict. The disclosed check behind G60's
reading: `tools/whole_probes/smell_budget.py`.

## The third design: a short reach, an economy in balance (G62)

Under the draft preregistration `docs/prereg/whole_smell_short.md`: the odour's length 0.5 units (three patches mark
12% of the floor at the encounter threshold), the food's energy set by the economy rule, the reward scale following it.

`short_design/` (`python3 -m experiments.whole_change --phase design3 --workers 24`, at `3406cb4`, 17.5 s): the economy
rule (§1.2). The whole on design seeds 4001–4004 at every rung of the ladder (K 0.065–0.20), each run stopped at the
move. `runs.csv`: per rung and seed, the meals before the move, the reserve over the ten minutes before it and at it,
the share asleep; `summary.json`: the rule (K = 0.08, the smallest rung in balance).

`short_pilot/` (`python3 -m experiments.whole_change --phase smell3 --workers 28`, at `5761933`, 275 s): the 29
configurations on seeds 1–12 at K = 0.08 (the reward scale 7.88), the three hidden patches moving at minute 30.
`runs.csv`, `energy_trace.csv` and `summary.json` as the second design's.
