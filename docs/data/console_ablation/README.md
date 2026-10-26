# Memory-steering ablations on the console scenarios (G40)

Diagnostic runs of `experiments/console_ablation.py`, made from a clean tree (each `manifest.json`
records the commit): eight seeds (1–8), 3,000 ticks, two arms on the same seeds, `steer` (the
scenario on the profile as the console runs it) and `no_steer` (`basal_ganglia.value_gain = 0`,
the learners still running). Each directory holds `ablation_per_seed.csv` (condition, task, seed,
metric, value), `ablation_bouts.csv` (every orbit bout with its duration, loops, radius, centre,
contacts, dominant turn term, memory influence and category) and `ablation_summary.json` (the
paired effects, BCa intervals over seeds, and the per-arm means). The per-tick decision logs are
not committed; `--keep-records` regenerates them.

| directory | command |
|---|---|
| `hidden_food_research` | `python -m experiments.console_ablation --scenario hidden_food --profile research --seeds 1-8 --ticks 3000 --out docs/data/console_ablation/hidden_food_research` |
| `hidden_food_legacy` | `... --scenario hidden_food --profile legacy --set sensors.noise=0.03 ...` (at noise 0 every legacy seed is one run) |
| `beacon_research` | `... --scenario beacon --profile research ...` |
| `open_field_research` | `... --scenario open_field --profile research ...` (no reward: a control in which the arms must be identical) |

What they showed is in `docs/decisions.md` G40. Not preregistered: a measurement of what memory
steering does to the circling and the finds in these scenarios, not a test of a rule.
