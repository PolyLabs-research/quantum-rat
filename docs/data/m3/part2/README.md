# M3 step 2, Part 2's pilot (G51, re-run under G52)

`python3 -m experiments.m3_part2 --phase pilot --workers 28`, exploratory on spent seeds (gate 31–42, track 31–42,
hidden food 1–8), under the bounds and selection rule of `docs/prereg/m3_step2.md` Part 2. `pilot/gate.csv`,
`track.csv`, `hidden_food.csv` and `open_field.csv` per configuration and seed; `summary.json` each configuration's
values against the eleven bounds, and the configuration the rule chose.

`pilot_g51_uncapped/`: the tables G51 read, made at `8dcd7eb`. Withdrawn (G52): on the track the per-feature reward
step at the unlearning rate 4 overshoots and the reward weights diverge, so every row with memory steering was made
with diverging weights (the no-steering and no-reward arms read none of them). Kept as G51's record.

`pilot/`: the same protocol re-run with the step capped at its target (`place.reward_step_cap`, G52); read in
`docs/decisions.md` G52.
