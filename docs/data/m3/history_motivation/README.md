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

`fixed_schema/` and `forage/` (G53): `python3 -m experiments.m3_g53_probes --phase schema|forage --workers 28`, at
`1abdaf9` (clean tree, warnings as errors), the same seeds and battery; read in `docs/decisions.md` G53. `fixed_schema/`:
history on with the taste schema fixed to one of three sets of weights stated before the run (`learned`, `fast`, `lap`),
R keeping G36's rule, for both bodies. `forage/`: motivation on with G53's composition (hunger a reason on its own; the
reward trace setting vigour) for both bodies. Both scored by G53's statistics (traversals per run; the gate's control
as a margin: `docs/prereg/m3_step2.md`, amendment of 2026-10-28); `probe/` and `docs/data/m3/part2/pilot/` keep their
earlier scores, re-read under the same statistics in `tools/m3_hm_probes/diagnostics_out/rescored_g53.txt`.
