# M3 step 2, Part 1: reachable value probes over every task (G49)

`python3 -m experiments.m3_reachable --workers 28`, preregistered in `docs/prereg/m3_step2.md` (Part 1, `b3bc4fe`),
fresh seeds 215–244, read in `docs/decisions.md` G49. `gate/<condition>_<off|on>/` holds the gate's tables per
condition (`open_anchor`, `open_cues`, `L_anchor`, `L_cues`) and probe setting; `gate/by_start_group.csv` success and
median latency per condition, probes, source, session, seed and start group; `hidden_food.csv` and `reflex.csv` (the
track and the open field, the reflex alone) per seed; `effects.csv` the paired effects (probes on − off everywhere,
memory against no steering); `summary.json` R1–R5 scored as registered; `manifest.json`. The exploration behind the
preregistration is in `tools/m3_step2_probes/`.
