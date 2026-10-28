# History and motivation over M3 step 2's battery (G52)

`probe/`: `python3 -m experiments.m3_hm_probe --workers 28`, at `f4ec447` (clean tree, warnings as errors), exploratory
on the Part 2 pilot's spent seeds (gate 31–42, track 31–42, hidden food 1–8); read in `docs/decisions.md` G52. Eight
configurations: two bodies (`B0` the research profile, `B1` the orienting response with G45's wall response, Part 2's
`o1_n_S`) × history off/on (`H1`: taste and visit channels, taste conditioning the SR's expected reward) × motivation
off/on (`M1`; with history off it carries the visit channel alone, for novelty). Every configuration runs on Part 2's
`BASE` (the per-feature step capped at its target). `gate.csv`, `track.csv` (with `traversals_late` and `rest_share`),
`hidden_food.csv`, `open_field.csv` per configuration and seed; `summary.json` the values against Part 2's eleven bounds
and the track arms' means; `manifest.json`. No selection, no registration.

The three checks behind the reading (the cap outside the track, the control without the explore reason, the learned
taste schema) are `tools/m3_hm_probes/diagnostics.py`, output in `tools/m3_hm_probes/diagnostics_out/`.
