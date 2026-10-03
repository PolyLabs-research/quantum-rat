# Config profiles: legacy and research

`EngineConfig()` is the **legacy** profile: today's behaviour, bit-identical to
the determinism baseline and to every result in `docs/decisions.md` up to G21.
`EngineConfig.research()` is the **research** profile: the same engine with the
mechanisms `docs/research_plan.md` section 6 lists as confounds switched off,
and (since M0b item 8) with seeded noise on, so that its seeds are samples.
Nothing is deleted; every difference is a configuration field, and `profile`
is a label only (not logged, so it never enters a trace hash).

## Selecting a profile

```python
from core.config import EngineConfig
from core.engine import Engine

engine = Engine(seed=1337, config=EngineConfig.research())  # or EngineConfig.legacy()
EngineConfig.legacy().diff(EngineConfig.research())         # the table below, as tuples
```

## What differs

| Field | legacy | research | Why it is off in research |
|---|---|---|---|
| `profile` | `"legacy"` | `"research"` | The label. |
| `sensors.odometry_speed_noise` | `0.0` | `0.05` | Seeded multiplicative Gaussian error on the self-motion estimate's forward displacement, d' = d (1 + 0.05 xi): odometry is no longer exact ground truth. The body moves exactly as before. Placeholder value, characterised in M1. |
| `sensors.odometry_turn_noise` | `0.0` | `0.01` | Seeded additive Gaussian error (radians) on the estimated heading change, N(0, 0.01) per tick (a heading random walk of about 0.5 rad standard deviation over 3,000 ticks). Placeholder value, characterised in M1. |
| `spatial.gate_scales_egomotion` | `True` | `False` | The TRN gate multiplied egomotion before path integration, so low ATP froze the place estimate while the body moved (22.8 units of error after 3000 barren-world ticks, `tools/probes/path_integration_capture`). |
| `astrocyte.scales_motion` | `True` | `False` | `World.step` multiplied thrust and turn by the ATP throttle, so step length was a physiology artefact (mean step 0.088 of the nominal 1.0, `tools/probes/open_field_motion`). |
| `astrocyte.frozen` | `False` | `True` | The astrocyte does not tick: ATP and glycogen stay at their initial values (1.0 and 3.0), the TRN gate stays OPEN (its κ branch is off too, next row), and energy cannot trigger sleep. |
| `trn.narrow_above_kappa` | `1.1` | `inf` | The κ branch of the gate was the second criticality coupling to behaviour (the FORWARD drive is `forward_bias` × gate value). With ATP frozen it was the only way the gate could leave OPEN, and at 1.1 it did at 2 of 41 seeds scanned (seeds 1-40 and 1337, 3,000 open-field ticks: seed 13 ticks 105-112, seed 27 ticks 196-197), cutting the FORWARD drive to 0.4× and changing the action from the first NARROW tick on. The research baseline (seed 1337, 200 ticks) is unchanged by it. |
| `trn.microsleep_enabled` | `True` | `False` | No microsleep bouts, hence no microsleep-gated replay. Sleep becomes a protocol phase in a later milestone. |
| `value_memory.dwell_extinction` | `0.02` | `0.0` | A non-stationary reward penalty with no RL or biological reading. |
| `basal_ganglia.dopamine_explore_gain` | `0.6` | `0.0` | Dopamine no longer scales exploration. The trace is still computed and logged. |
| `basal_ganglia.ach_precision_gain` | `0.5` | `0.0` | Acetylcholine no longer scales vision precision. Trace still logged. |
| `basal_ganglia.ne_threat_gain` | `0.5` | `0.0` | Norepinephrine no longer scales pain avoidance and freezing. Trace still logged. |
| `basal_ganglia.fiveht_patience_gain` | `0.4` | `0.0` | Serotonin no longer adds a REST drive. Trace still logged. |
| `basal_ganglia.softmax_temperature` | `0.0` | `0.1` | Seeded softmax action selection over the four channel scores (one draw per tick) instead of the deterministic argmax, so the arbiter is a sample too. The logged scores are unchanged. Placeholder value, characterised in M1. |

`research()` also sets `value_memory.generalization_radius = 0`,
`value_memory.goal_vector = False` and `basal_ganglia.criticality_gain = 0.0`
(the criticality coupling to cognition); these are already the legacy defaults
(the console's maze scenarios set the radius to 2 themselves), so they are not
in the diff. Kappa, avalanche sizes and the modulators are logged in both.
`units` (`UnitsConfig`: 0.2 s per tick, 0.1 m per unit; docs/units.md, M0b item 6)
is declared once and identical in both profiles, so it is not in the diff either.

ATP also reaches action selection through the gate value, a route
`scales_motion` does not touch: the FORWARD drive is `forward_bias` × gate
value, REST gains 0.1 × (1 − gate value), and a microsleep bout forces REST.
`scales_motion = False` on its own leaves that route live (seed 1337, 3,000
open-field ticks: `energy_scale` is 1.0 throughout, yet the mean step is 0.24,
1,231 steps are zero and FORWARD is never chosen on the 1,297 awake CLOSED
ticks). The research profile removes it because `frozen` holds ATP at 1.0 and
the κ branch is off, so the gate is OPEN on every tick.

The TRN gate thresholds (`trn.closed_below_atp` 0.35, `trn.open_at_atp` 0.55,
`trn.narrow_above_kappa` 1.1, `trn.narrow_gain` 0.4) are now configuration, at
the values that were hard-coded before; the research profile sets
`narrow_above_kappa` to `inf` (table above) and keeps the other three.

## Seeds are samples (M0b item 8)

At the legacy defaults no behavioural path draws from the RNG (the seed reaches
only the dormant criticality lattice), so N seeds are N copies of one run:
`tools/probes/seed_pseudoreplication` measures seeds 1-4 identical to the last
bit at `sensors.noise` 0. The research profile has three seeded elements on by
default, each on its own named stream (a new name derives its own child seed,
so the four existing streams are untouched), and each draws nothing at 0:

- Odometry noise (`core.sensors._compute_egomotion`, stream `sensors_odometry`):
  on every tick the raw forward displacement is multiplied by
  `1 + odometry_speed_noise * xi` and the raw heading change gets
  `+ N(0, odometry_turn_noise)`, forward draw first, then turn, before the
  usual clamps; the spatial system integrates the noisy deltas and the body is
  not touched (two `gauss` draws per tick). The clamp is kept as it is, and
  a FORWARD step (1.0) sits at the top of the egomotion range, so on
  full-thrust ticks only slowing speed errors reach the estimate; a TURN's
  0.3 gets both signs. M1 takes this into account when it characterises
  the sigma.
- Softmax action selection (`brain.systems.basal_ganglia.softmax_sample`, stream
  `action_softmax`): at `softmax_temperature` tau > 0 the action is sampled with
  probability proportional to exp((s_i - max s) / tau) over the channels in the
  argmax's fixed order, from one `random()` draw per tick walked over the
  cumulative sums; the scores logged in `action_scores` are still the scores.
  At tau = 0 the deterministic argmax with its tie order runs as before.
- The guard (`core.seeds.require_seeds_are_samples`): `EngineConfig
  .stochastic_elements()` lists which of `sensors.noise`,
  `sensors.odometry_speed_noise`, `sensors.odometry_turn_noise` and
  `basal_ganglia.softmax_temperature` are above 0; asking for more than one
  seed when none is raises `PseudoReplicationError`. `experiments
  .steering_sensitivity` (`run_jobs`, `sweep`, `sweep_both`, `--seeds`) and
  `experiments.memory_navigation` (`run_memory_navigation_seeds`, `--seeds`)
  call it; `--allow-identical-seeds` (kwarg `allow_identical_seeds=True`) runs
  the seeds anyway after printing one warning line.

Measured (tests/engine/test_seeds_as_samples.py, barren default world): at the
research defaults seeds 1-4 give four different position trajectories, each
pair first differing at tick 3-5, and the same seed twice gives the same trace
hash; at the legacy defaults the two new streams' states are unchanged after a
run and the legacy baseline is bit-identical. The softmax sampler returns the
argmax on 54 tie-free score vectors at tau = 1e-9 and matches the softmax
probabilities within 0.008 over 20,000 draws at tau = 1 on a four-channel
example. With the softmax at 0 and odometry noise on, the body's 300-tick path
is identical to the exact-odometry run while the estimate differs from the
first tick.

The three values are placeholders: M1 characterises them (what sigma and tau
give biologically reasonable path-integration drift and action variability)
and M2b adds the wall-contact reset the drift makes necessary. What they do
to a legacy-profile result is already measured (docs/decisions.md G23,
section G): on the off-axis memory maze over 30 seeds, turn noise 0.01 rad
alone takes the runs that recall from 471 to 424 of 480 and a softmax
temperature of 0.05 alone to 430, while speed noise 0.05 alone leaves 469;
the two losses add, and the research temperature of 0.1 is twice what was
run there. M1 therefore characterises turn noise and temperature separately
and together, with the speed sweep last.

## What the research profile measures as (tests/engine/test_profiles.py)

Open field, seed 1337, 3000 ticks, `EngineConfig.research()` with its three
seeded elements set to 0 (the M0a acceptance is about the deterministic
mechanics): 0 microsleep ticks, `trn_state` OPEN on every tick, `energy_scale`
1.0 and ATP 1.0 on every tick, the realised step equal to the commanded thrust
on every tick (1.0 for FORWARD, 0.3 for a TURN; `World.step` moves the agent
`thrust * energy_scale` world units, there is no separate step length), and
the path-integration estimate equal to the true position throughout (sensor
and odometry noise are 0, so odometry is exact; the difference is
floating-point rounding, below 1e-12). The legacy profile at the same seed
gives a mean step of 0.088 and 1270 microsleep ticks.

At the research defaults (seeded elements on) the energy statements hold tick
for tick and the estimate drifts: its error first exceeds 0.5 units at tick 37,
is 9.2 units at tick 3000 and 11.6 at most; the softmax wanders the body to
the walls (clamped on 753 of 3000 ticks, against none in the deterministic
run), mean step 0.57, 3 REST ticks. The drift is the heading estimate's random
walk (sd 0.01 rad per tick) plus the wall clamps below; both are what M1 and
M2b work on.

## What the research profile does not have yet

- A wall-contact reset: the box clamps the body at a wall, and that clamp is not
  in the egomotion (the displacement projected on the heading), so each wall
  contact offsets the estimate once (0.47 units after 48 clamp ticks at seed 1
  with only the gate flag off; the gate's own capture was 22.8). M2b adds the
  reset.
- A place population and a successor representation (M2b).
- Replay as an event stream between ticks: with microsleep off there is no
  replay at all in this profile until M1 refactors it into an event object.
- The checksum "novelty" bit decoupled: it still enters action selection in
  both profiles (`basal_ganglia.novelty_gain` 0.2 on FORWARD and a literal 0.3
  on each TURN channel); plan section 6 lists it as logged-only in research,
  which M1 does together with the `oracle_homing` relabel of the goal-vector
  slot. The TRN replay buffer and `wm_load` are logged only.
- Behavioural assertions of its own: the barren-world gates pass whatever the
  science does (plan section 6).

## Baselines

The determinism gate holds one set of baselines per profile, each at seed 1337
over 200 ticks, in `tests/determinism/` (docs/determinism.md is the canonical
description: what each hash kind contains, the tolerance gate and the numpy
rules):

| profile | full hash | behaviour hash | physics hash | reference trace |
|---|---|---|---|---|
| legacy | `baseline_hashes.json` | `baseline_behaviour_legacy.json` | `baseline_physics_legacy.json` | `reference_trace_legacy.jsonl` |
| research | `baseline_hashes_research.json` | `baseline_behaviour_research.json` | `baseline_physics_research.json` | `reference_trace_research.jsonl` |

`baseline_meta.json` and `baseline_meta_research.json` record seed, ticks,
schema version and the file set. The legacy set is never re-recorded by a
profile change (bit-identical by rule, G22; the behaviour and physics files
and the reference trace were added by M0b item 7 without moving the full
hash). The research set was re-recorded for M0b item 8, when the seeded
elements went on by default in `research()`, and again when their odometry
placeholders were lowered (87f824e). Regenerate the research set with
`python3 tools/update_determinism_baseline.py --profile research
--i-know-what-im-doing` (once per milestone, per profile); one engine run
writes all three hash kinds, the meta file and the reference trace.
