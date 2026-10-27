# Preregistration: the retest after the audit (G46)

**Written:** 2026-10-27, after the audit's exploratory probe and before any run of the fixed engine on the seeds below
(the commit that adds this document is the registration; the decisions entry will be G46). **Scope:** two leaks fixed
on the research profile, the claims they touched re-measured on fresh seeds, and the weight of the gate's one
unmeasured declared aid measured. No bound here gates a merge; each part has a reading rule written in advance.

## Why

The owner asked whether the agent is allowed to cheat: behaviour should be emergent, not given. An audit of
2026-10-27 traced every input of the brain to its source (a second, independent read of the code, then each finding
re-measured). The brain never reads the true position, the goal's position, the trial or its phase. It found:

1. **Hidden food was sensed.** A vision ray stopped at a "hidden" (or eaten, "collected") object and reported its
   kind (`core/sensors.py`, `_cast_ray`); the action selection ignores the kind but reads each side's openness from
   any ray's distance (`brain/systems/basal_ganglia.py`, `_vision_signals`), so a hidden site on a side ray read as an
   obstacle and the wall-escape turn went away from it. G19 says the rays hit hidden objects and "the policy ignores
   the kind": true of the label, not of the distance. `experiments/protocols/foraging.py` calls an eaten item
   "invisible to vision"; it was not.
2. **A hot/cold signal on the legacy profile.** Approach shaping rewarded closing the true distance to the nearest
   target, a hidden one included (`Engine._compute_reward`, `_nearest_target`); on the legacy profile the shaped
   reward reaches action selection through DA and 5HT. G41 D says hidden food's `approach_weight` is 0 under the
   scenario's settings; it is 1.0. On the research profile it reaches nothing (runs byte-identical with it off).
3. **The gate tells the agent where it is put down** (`experiments/rq4a_gate.py`: the true start pose is written
   into the estimate at every trial start). Declared (`docs/prereg/m2b_gate.md`, G36 D); its weight never measured.

## The fixes (on from this registration's commit)

`sensors.unseen_block_rays = False` (a hidden or eaten object is not seen: rays and whiskers pass through it) and
`reward.shape_hidden = False` (shaping reads visible targets only; a hidden goal still rewards on contact), both in
`EngineConfig.research()`. The legacy profile keeps the old values, so its recorded results regenerate; every gate
registration before this one pins the old sensing (`PREREGS[...]["pre_g46"]`), as does `experiments/sr_unlearning.py`.
The research and legacy determinism baselines contain no hidden object and are unchanged (the full suite passes).
The gate also gains `still_start` (a trial's first tick no longer repeats the last trial's last action from the new
start; one tick, every earlier run carried it over) and `start_estimate` / `estimate` options for Part G.

## Disclosed: the audit's probe (exploratory; `python3 -m tools.g46_audit`; spent seeds)

Hidden food, seeds 1–8, 3,000 ticks, finds (steer / no_steer; steer − no_steer; seeds steer wins):

| condition | steer | no_steer | diff | wins |
|---|---|---|---|---|
| research, sites sensed (pre-G46) | 27.25 | 26.50 | +0.75 | 3/8 |
| research, not sensed (G46) | 40.50 | 51.88 | −11.38 | 0/8 |
| legacy (noise 0: one run), as recorded | 16 | 4 | +12 | — |
| legacy, rays fixed | 21 | 42 | −21 | — |
| legacy, shaping fixed | 6 | 2 | +4 | — |
| legacy, both fixed | 22 | 39 | −17 | — |

The gate, seeds 31–42, SR hidden success over trials 21–40 (the confirmatory settings and pre-G46 sensing): told the
start (as registered) 0.979; told the centre 0.400; told nothing (`carry`) 0.308; anchored without the heading oracle
or the wall reset 0.988; told nothing and neither aid 0.025; anchored with the sensing fixed 0.975; no steering 0.058.

**Also disclosed: one check of the scoring code** on seeds 17–19 and 125–127 (among the registered seeds) at smoke
budgets (300 ticks; 8 trials), run to see that the prediction scoring below executes; its numbers carry nothing about
the predictions at those budgets and were not used to write them (they were written from the probe above). The smoke
test (`--quick`) runs on spent seeds (1–2, 31–32).

## Part H: hidden food, fresh seeds 17–46 (30), 3,000 ticks

`experiments/g46_retest.py`, `experiments.console_ablation.run_one` per cell (the scenario as the console runs it,
plus the cell's overrides). Finds per run.

- **Research profile.** Arms `no_steer` (`basal_ganglia.value_gain` 0), `steer_u4` (the scenario's own setting,
  U = 4, G43) and `steer_one_rate` (U = None, the research profile's default). Conditions `pre_g46`
  (`sensors.unseen_block_rays` and `reward.shape_hidden` True) and `g46` (the profile).
- **Legacy profile at sensor noise 0.03** (G23's setting B, so seeds are samples; the pseudo-replication guard runs
  on every cell). Arms `steer` (memory on, the scenario's value gain) and `no_steer`. Conditions `pre_g46` (the
  profile as recorded), `rays_fixed` (`unseen_block_rays` False only) and `g46` (both False).

Statistics: per cell the mean with a BCa 95% interval; per condition the paired difference steer − no_steer (each
steering arm against `no_steer`) with its BCa interval and the seeds won; per arm the paired fix effect
(g46 − pre_g46); for legacy the ratio of means (steer ÷ no_steer). 10,000 resamples.

**Predictions** (from the probe):

- **H1.** Research `pre_g46` replicates G41/G43: `steer_u4` − `no_steer` within ±3 finds, interval spanning 0.
- **H2 (primary).** Research `g46`: `no_steer` 45–55 finds, `steer_u4` 37–47; `steer_u4` − `no_steer` below 0 with
  the interval's upper end below 0. `steer_one_rate` below `steer_u4`.
- **H3.** Legacy `pre_g46`: memory on beats off, ratio 2.4–3.6 (G23 B: 2.91 [2.43, 3.59]).
- **H4 (primary).** Legacy `g46`: memory on loses to off, `steer` − `no_steer` interval's upper end below 0.
- **H5 (reported).** Legacy `rays_fixed` alone reverses the sign (the rays carry the reversal; the shaping adds finds
  to both arms).

**Reading rules.** If H2 and H4 hold: the hidden-food memory claims (README; G19, G21, G23 claim 1; G41 K3 and G43,
"steering matches no steering") are withdrawn as products of the leaks and replaced by G46's numbers. If either
interval spans 0: the claims are withdrawn all the same (they were measured with the leaks) and the record says
"no measurable benefit". If memory wins under `g46`: the claims stand in direction, restated with G46's numbers. The
scenario's U = 4 was chosen under the leak; re-choosing it is a separate question, not this test's.

## Part G: the gate's start, fresh seeds 125–154 (30)

The confirmatory settings (per-feature rule, one rate, the three sources, both sessions, 40 trials, the gate reads
21–40), on the research profile with the fixes, `still_start` on. Four conditions:

| condition | told at each trial start | heading | wall reset |
|---|---|---|---|
| `anchor` | the true start pose (the registered protocol) | oracle | on |
| `centre` | the arena's centre (heading left as it is) | oracle | on |
| `carry` | nothing (the estimate carries on from where the last trial ended) | oracle | on |
| `embodied` | nothing | integrated | off |

Per condition the gate's own tables (`experiments.rq4a_gate`: per seed, curve, effects, with hidden ÷ visible and
its BCa interval per source, and the paired source contrasts); across conditions the paired SR hidden differences
(`anchor` against each other).

**Predictions** (from the probe):

- **G1.** `anchor`: SR hidden ≥ 0.95 and hidden ÷ visible ≥ 0.8 (the gate stands with the sensing fixed).
- **G2.** `centre` and `carry`: SR hidden 0.20–0.55, and SR − none above 0 (interval's lower end above 0): the place
  memory still helps without the anchor, far short of the anchored gate.
- **G3.** `embodied`: SR hidden not above the no-steering control (SR − none interval's lower end at or below 0).
- **G4 (reported).** Visible success per condition and source; the tabular source beside the SR.

**Reading rules.** G1 fails: the fix broke the gate; diagnose before anything else. G1 holds: the record states that
the gate's success needs the start anchor (by how much, from G2 and G3), and from here every M3 result is reported
with and without it; the honest replacement for the anchor is something the agent can sense and localise from
(landmarks), the owner's next step.

## Outputs and acceptance

`python3 -m experiments.g46_retest --workers 28` writes `docs/data/g46/hidden_food/` and `docs/data/g46/gate/<condition>/`
from a clean tree. The full test suite passes; the determinism baselines are unchanged. After the run, hidden-food
seeds 17–46 and gate seeds 125–154 are spent.

## What would change this document

Nothing after the first run. A finding wanting another condition is a new preregistered step.
