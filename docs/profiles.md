# Config profiles: legacy and research

`EngineConfig()` is the **legacy** profile: today's behaviour, bit-identical to
the determinism baseline and to every result in `docs/decisions.md` up to G21.
`EngineConfig.research()` is the **research** profile: the same engine with the
mechanisms `docs/research_plan.md` section 6 lists as confounds switched off.
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

`research()` also sets `value_memory.generalization_radius = 0`,
`value_memory.goal_vector = False` and `basal_ganglia.criticality_gain = 0.0`
(the criticality coupling to cognition); these are already the legacy defaults
(the console's maze scenarios set the radius to 2 themselves), so they are not
in the diff. Kappa, avalanche sizes and the modulators are logged in both.

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

## What the research profile measures as (tests/engine/test_profiles.py)

Open field, seed 1337, 3000 ticks, `EngineConfig.research()`: 0 microsleep
ticks, `trn_state` OPEN on every tick, `energy_scale` 1.0 and ATP 1.0 on every
tick, the realised step equal to the commanded thrust on every tick (1.0 for
FORWARD, 0.3 for a TURN; `World.step` moves the agent `thrust * energy_scale`
world units, there is no separate step length), and the path-integration
estimate equal to the true position throughout (sensor noise is 0, so odometry
is exact; the difference is floating-point rounding, below 1e-12). The legacy
profile at the same seed gives a mean step of 0.088 and 1270 microsleep ticks.

## What the research profile does not have yet

- Noisy odometry: egomotion is still exact ground truth, so every seed gives the
  same path at noise 0 (M0b item 8; characterised in M1).
- A wall-contact reset: the box clamps the body at a wall, and that clamp is not
  in the egomotion (the displacement projected on the heading), so each wall
  contact offsets the estimate once (0.47 units after 48 clamp ticks at seed 1
  with only the gate flag off; the gate's own capture was 22.8). M2b adds the
  reset.
- Physical units: the arena is still 20 x 20 units with no declared metre or
  second (M0b item 6).
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

The determinism gate holds one baseline per profile, both at seed 1337 over
200 ticks: `tests/determinism/baseline_hashes.json` (legacy, never re-recorded
by a profile change) and `tests/determinism/baseline_hashes_research.json`.
Regenerate one with `python -m tools.update_determinism_baseline --profile
research --i-know-what-im-doing` (once per milestone, per profile).
