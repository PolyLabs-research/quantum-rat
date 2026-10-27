# The retest after the audit (G46)

`python3 -m experiments.g46_retest --workers 28`, from a clean tree at the registration's code (`68d5461`; the
manifest records the commit), preregistered in `docs/prereg/g46_retest.md`; read in `docs/decisions.md` G46.

| path | what |
|---|---|
| `hidden_food/per_seed.csv` | finds, unique sites, wall and orbit fractions and the trace digest per profile, condition, arm and seed (17–46) |
| `hidden_food/effects.csv` | per cell the mean finds with a BCa 95% interval; steering − no steering per condition (paired, with seeds won and lost); steering ÷ no steering on legacy; the fix's effect per arm |
| `gate/<condition>/` | the gate's own tables (`gate_trials.csv`, `gate_per_seed.csv`, `gate_curve.csv`, `gate_effects.csv`) for `anchor`, `centre`, `carry` and `embodied`, seeds 125–154 |
| `gate/cross_condition_effects.csv` | each condition against `anchor` (SR and tabular, hidden success), and each source against no steering within each condition |
| `summary.json` | the predictions H1–H5 and G1–G3 scored as registered, and the pseudo-replication guard per cell |
| `manifest.json` | the configuration, the commit, the command and the timing |

The audit's exploratory probe (spent seeds; disclosed in the preregistration) is `python3 -m tools.g46_audit`.
