# The gate with a barrier in the way (G47)

`python3 -m experiments.g47_barrier_gate --phase pilot|confirmatory --workers 28`, preregistered in
`docs/prereg/g47_barrier_gate.md`, read in `docs/decisions.md` G47. Each directory holds, per condition (`open_anchor`,
`open_carry`, `L_anchor`, `L_carry`), the gate's own tables (`gate_trials.csv`, `gate_per_seed.csv`, `gate_curve.csv`,
`gate_effects.csv`); `by_start_group.csv`, success and median latency per condition, source, session, seed and start
group (`blocked`: the west and south starts, whose straight line to the goal meets a wall in `L`; `direct`: the east
and north); `effects.csv`, per-cell means with BCa intervals and the paired effects (the barrier's cost, the memory
against no steering in `L`, the visible ceiling's cost); and `manifest.json`.

| directory | what |
|---|---|
| `pilot/` | spent seeds 31–42, exploratory: run to see that the gaps are passable and to size the effects (disclosed in the preregistration) |
| `confirmatory/` | fresh seeds 155–184, the registered run |
