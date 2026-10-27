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

**Reproducing them after G43.** These four were made at `f4176d4`, when no scenario set the SR's
unlearning rate. Since G43 hidden food and beacon set it to 4 as their own setting, so the commands
above, run at a later commit, measure the scenarios as the console now runs them (the directories
`*_scenario_u4` below). To reproduce the G40 numbers at a later commit, add
`--set place.reward_unlearning_rate=0.5` (the learning rate: the same arithmetic as None), or run at
`f4176d4`.

| directory | what |
|---|---|
| `hidden_food_research_scenario_u4` | hidden food on research as the console runs it since G43 (U = 4), seeds 1–8, at `2de623c` |
| `beacon_research_scenario_u4` | beacon on research as the console runs it since G43 (U = 4), seeds 1–8, at `2de623c` |

**Reproducing them after G46.** Every table here was made while a vision ray still stopped at a hidden (or eaten)
food site, which the action selection read as an obstacle (the audit of 2026-10-27, `docs/decisions.md` G46). The
research profile no longer senses such sites, so the `*_research` hidden-food commands above, run at a later commit,
measure the corrected agent; to reproduce the tables here add `--set sensors.unseen_block_rays=true` (and, for
exactness, `--set reward.shape_hidden=true`, which changes nothing on research). The legacy profile keeps the old
sensing, and `experiments/sr_unlearning.py` pins it for its registered runs. The beacon and open-field tables have no
hidden object and are unaffected. What the hidden-food numbers become without the leak is G46's retest
(`docs/data/g46/`).

## The SR's unlearning rate (G41, preregistered: `docs/prereg/sr_unlearning_rate.md`)

`experiments/sr_unlearning.py`, hidden food on the research profile, 3,000 ticks; the files are
`unlearning_per_seed.csv`, `unlearning_bouts.csv`, `unlearning_summary.json` (the per-arm means, the paired
effects and the three bounds scored) and `manifest.json`.

| directory | what |
|---|---|
| `sr_unlearning_pilot` | seeds 1–8, arms `no_steer`, `u0.5`, `u1`, `u2`, `u4`: exploratory, it chose U = 4 by the preregistered rule |
| `sr_unlearning_confirmatory` | seeds 9–16, arms `no_steer`, `u0.5`, `u4`: K1, K2 and K3 pass (`python -m experiments.sr_unlearning --phase confirmatory --unlearning 4 --prereg docs/prereg/sr_unlearning_rate.md --out docs/data/console_ablation/sr_unlearning_confirmatory`) |
