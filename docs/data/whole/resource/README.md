# The whole, part 1: resource management (G56)

`python3 -m experiments.whole_resource --phase calibrate|pilot`, under the draft preregistration
`docs/prereg/whole_resource.md` (amendments P1, P2); read in `docs/decisions.md` G56. Every run from a clean tree with
numerical warnings as errors.

`calibration/` (at `519e8e9`, 6 s): the base on seeds 1001–1004 with nothing charged, so it cannot starve; `summary.json`
holds what it would have spent, its meals and K = 0.065 (P2).

`pilot/` (at `b8cf343`, 215 s): the 27 configurations (the base, the whole, the whole minus each of the twelve parts,
the base plus each, the whole with memory unread) on seeds 1–12, 9,000 ticks each. `runs.csv`: the per-run measures of
the draft's §4; `energy_trace.csv`: the reserve, the gut and sleep every 50 ticks; `summary.json`: the scores and the
emergence verdict as preregistered (the whole does not show the spark as defined: R2 could not be scored).

The same runs read tick by tick (post hoc, no bounds) are `tools/whole_probes/need_activity.py`, with its output
beside it.

`confirm/` (at `9756bba`, 1,005 s; amendment A1): the 27 configurations on fresh seeds 13–42 in the pilot's arena
(`full`) and the held-out one with half the food, moved (`half`). `runs.csv`: the pilot's columns plus the arena and
A1's measures (the level and within-run spread of the reserve over the second half, the within-run hunger contrast,
the share of awake ticks moving); `energy_trace.csv`: every 150 ticks; `summary.json`: A1's scores and the verdict
(the whole fails R1′(c): its level falls 0.22 from `full` to `half`). Read in `docs/decisions.md` G57.
