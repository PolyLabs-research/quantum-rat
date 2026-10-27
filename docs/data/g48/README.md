# The gate with distal cues the agent maps itself (G48)

`python3 -m experiments.g48_landmark_gate --phase pilot|confirmatory --workers 28`, preregistered in
`docs/prereg/g48_landmark_gate.md`, read in `docs/decisions.md` G48. Each directory holds, per condition
(`{open, L}_{anchor, carry}_{off, on}` with sideways odometry, and `L_{anchor, carry}_off_nolateral`, G47's agent), the
gate's tables (`gate_trials.csv` with the estimate's mean error, mean offset and offset on arrival per trial;
`gate_per_seed.csv`; `gate_effects.csv`); `by_start_group.csv` (success, median latency, estimate error and frame
spread per condition, source, session, seed and start group: `all`, `blocked`, `direct`); `effects.csv` (cell means
with BCa intervals and the paired effects); `manifest.json`.

| directory | what |
|---|---|
| `pilot_without_lateral/` | pilot 1, spent seeds 31–42, at `296ae86`, without sideways odometry: found the cue map drifting in the L arena |
| `pilot/` | pilot 3, the same seeds, the registered design (pilot 2's numbers for the shared conditions), at `7437788` |
| `confirmatory/` | fresh seeds 185–214, the registered run, at `7fd3160` |
