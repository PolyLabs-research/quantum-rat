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

The lab console's Live tab has the same choice as a **profile switch** (G38): a scenario's own
settings (`ui.scenarios.profile_config`) are applied on the chosen profile's base and the fields
they move away from it are listed under the switch; on the research profile the arena and the
Place code panel draw the population, the SR value and the successor field. A headless
`python -m experiments.runner --protocol console_<scenario> --profile research` reproduces such a
session tick for tick, and a recording's manifest carries the profile.

## What differs

| Field | legacy | research | Why it is off in research |
|---|---|---|---|
| `profile` | `"legacy"` | `"research"` | The label. |
| `sensors.odometry_speed_noise` | `0.0` | `0.05` | Seeded multiplicative Gaussian error on the self-motion estimate's forward displacement, d' = d (1 + 0.05 xi): odometry is no longer exact ground truth. The body moves exactly as before. Placeholder value, characterised in M1 (docs/odometry.md; kept, G25 C1). |
| `sensors.odometry_turn_noise` | `0.0` | `0.01` | Seeded additive Gaussian error (radians) on the estimated heading change, N(0, 0.01) per tick (a heading random walk of about 0.5 rad standard deviation over 3,000 ticks). Placeholder value, characterised in M1 (docs/odometry.md; kept, G25 C1). |
| `sensors.forward_delta_limit` | `1.0` | `2.0` | The Observation's egomotion range, enforced after the odometry noise. At 1.0 a full-thrust FORWARD step of 1.0 sits at the top of the range, so a positive speed error is clamped away and a full-speed step's estimate averaged 0.980 instead of 1.0 (the clamp bias, −0.0198 per unit, docs/odometry.md); at 2.0 the error keeps both signs and averages 1.0 (M2a, G26). The body is unchanged. |
| `sensors.heading_oracle` | `False` | `True` | The Observation carries the body's allocentric heading plus a per-tick Gaussian error (M2b step 1, G33): plan section 2 item 1's declared heading oracle, a stated limitation of every result that uses it. On by default since M2b's exit (G37), with the five rows below: together they are the instrument the RQ4(a) gate passed with. |
| `sensors.heading_oracle_noise` | `0.0` | `0.05` | The oracle's error, sd 0.05 rad per tick (2.9°), drawn from its own stream `sensors_heading`: the fourth seeded element. The value the corrected estimate was characterised at (docs/m2b_place_code.md step 1; a sensitivity from 0 to 0.2 rad is measured there). |
| `sensors.wall_contact_sensing` | `False` | `True` | The Observation carries the egocentric angle of the outward normal of each arena wall the body touches (exact touch, x walls before y walls), which the reset below reads. |
| `sensors.unseen_block_rays` | `True` | `False` | A "hidden" or "collected" (eaten) object is not seen: vision rays and whiskers pass through it. Before the audit of 2026-10-27 (G46) a ray stopped at it and reported its kind, and the side openness the action selection reads took it for an obstacle, so the agent sensed every hidden food site and turned away from it; the label was ignored, the distance was not. The legacy profile keeps the old sensing, so its recorded results regenerate; G46 records what it did to them. |
| `reward.shape_hidden` | `True` | `False` | Approach shaping reads visible targets only; a hidden goal still rewards on contact. Before G46 the shaped reward also told the agent whether it was closing on hidden food (a hot/cold signal); on the legacy profile it reaches action selection through DA and 5HT, on the research profile it reached nothing (G46 measured the research runs byte-identical with it off). |
| `sensors.lateral_odometry` | `False` | `True` | The egomotion also carries the displacement perpendicular to the heading (G48), which the estimate integrates: a body sliding along a wall it pushes into felt only the part along its heading, and the unfelt slide carried the estimate through walls (G47's way round leaned on it). Adopted at G50. |
| `sensors.landmark_sensing` | `False` | `True` | The agent sees distal cues (`core.world.Cue`) as a name, a bearing and a distance with seeded errors, never a position (G48). Inert where the world has no cues (every console scenario so far). Adopted at G50. |
| `spatial.landmark_gain` | `0.0` | `0.1` | The estimate learns a map of the cues it sees and corrects itself toward where they put it (G48): told nothing of its start, the gate's success 95% with cues against 29% without. Adopted at G50. |
| `sensors.free_space_sensing` | `False` | `True` | The distance to the nearest solid along each direction of the value fan (G49). Adopted at G50. |
| `value_memory.reachable_probes` | `False` | `True` | Each direction's value is read only as far as the agent sees it could go (G49): round the L arena's wall from every walled-off start (100% against 35%), nothing else changed. Adopted at G50. |
| `spatial.gate_scales_egomotion` | `True` | `False` | The TRN gate multiplied egomotion before path integration, so low ATP froze the place estimate while the body moved (22.8 units of error after 3000 barren-world ticks, `tools/probes/path_integration_capture`). |
| `spatial.heading_source` | `"integrated"` | `"oracle"` | The heading estimate is the oracle's reading instead of the egomotion turns summed. The integrated heading's random walk (sd 0.01 rad per tick) was the drift's main term (docs/odometry.md); with the oracle the heading error is the oracle's own, sd 0.05 rad, and does not grow (M2b step 1). |
| `spatial.wall_reset` | `False` | `True` | On every tick the body touches a wall, the estimate's coordinate along that wall's normal is set to the wall's (Hardcastle, Ganguli & Giocomo 2015, for the reset only); the along-wall coordinate is untouched; the wall is identified by snapping the allocentric contact normal to the nearest arena axis. With the oracle it holds the 2 m open-field estimate at a late median error of 0.70 units (7 cm) over 30 seeds, against 10.2 for the integrated estimate (G33). `reset_bounds` stays `None`: the arena's own bounds. |
| `place.enabled` | `False` | `True` | A 400-cell Gaussian place population over the estimate (pitch and sd 1.0 unit, 0.1 m, on a regular grid over the arena; M2b step 2, G34): its rate maps correlate 0.91 with a perfect-estimate population's; 16,200 ticks/s on its own. Its rates feed the SR below and nothing else; no TickData field. `place.extent` is `None`, the arena's own bounds, so a run in a much larger arena must set it (or switch the population off): the cell count grows with the area. |
| `place.reward_rule` | `"nlms"` | `"per_feature"` | How the SR's reward weights R are learned: each active cell's weight tracks the reward seen while it is active, R += 0.5 φ (r − R), which cannot go negative when rewards do not. The preregistered NLMS regression ringed the goal with negative weights and failed the gate (G36); it stays available to reproduce that run. `place.reward_unlearning_rate` (None here: the same rate when nothing is seen) is the knob the circling measurement pointed to, preregistered in docs/prereg/sr_unlearning_rate.md (G41). It stays None in this profile: a higher rate trades the gate's stable goal against rewards that empty (G42); the console's hidden-food and beacon scenarios set 4 as their own setting (G43). |
| `astrocyte.scales_motion` | `True` | `False` | `World.step` multiplied thrust and turn by the ATP throttle, so step length was a physiology artefact (mean step 0.088 of the nominal 1.0, `tools/probes/open_field_motion`). |
| `astrocyte.frozen` | `False` | `True` | The astrocyte does not tick: ATP and glycogen stay at their initial values (1.0 and 3.0), the TRN gate stays OPEN (its κ branch is off too, next row), and energy cannot trigger sleep. |
| `trn.narrow_above_kappa` | `1.1` | `inf` | The κ branch of the gate was the second criticality coupling to behaviour (the FORWARD drive is `forward_bias` × gate value). With ATP frozen it was the only way the gate could leave OPEN, and at 1.1 it did at 2 of 41 seeds scanned (seeds 1-40 and 1337, 3,000 open-field ticks: seed 13 ticks 105-112, seed 27 ticks 196-197), cutting the FORWARD drive to 0.4× and changing the action from the first NARROW tick on. The research baseline (seed 1337, 200 ticks) is unchanged by it. |
| `trn.microsleep_enabled` | `True` | `False` | No microsleep bouts, hence no microsleep-gated replay. Sleep becomes a protocol phase in a later milestone. |
| `value_memory.dwell_extinction` | `0.02` | `0.0` | A non-stationary reward penalty with no RL or biological reading. |
| `value_memory.source` | `"tabular"` | `"sr"` | The steering reads V(p) = φ(p)·(Mᵀ R), the successor features' value over the place code (M2b steps 3 and 4), where it read the tabular map; the map still learns and stays M3's ablation. The source that passed RQ4(a) on fresh seeds: hidden-goal success 98.7% against 100% visible (G36). With it the engine runs at about 2,400 ticks/s in the open field. Without reward V is 0 everywhere, so a reward-free walk is the same body trajectory as under the map (measured at the gate seed, below). |
| `basal_ganglia.novelty_gain` | `0.2` | `0.0` | The checksum-changed "novelty" bit no longer adds to the FORWARD score (M2a, G26). The bit is still computed and logged (`wm_novelty`) and still feeds the ACh and NE traces. |
| `basal_ganglia.novelty_turn_gain` | `0.3` | `0.0` | The same bit's term on each TURN channel, the literal 0.3 that `_channel_scores` carried until M2a, now a field; 0 in research. In an empty arena this term is what made a TURN a 1-in-500 softmax draw; without it a TURN is an exp(−8) draw per channel (docs/odometry.md). |
| `basal_ganglia.dopamine_explore_gain` | `0.6` | `0.0` | Dopamine no longer scales exploration. The trace is still computed and logged. |
| `basal_ganglia.ach_precision_gain` | `0.5` | `0.0` | Acetylcholine no longer scales vision precision. Trace still logged. |
| `basal_ganglia.ne_threat_gain` | `0.5` | `0.0` | Norepinephrine no longer scales pain avoidance and freezing. Trace still logged. |
| `basal_ganglia.fiveht_patience_gain` | `0.4` | `0.0` | Serotonin no longer adds a REST drive. Trace still logged. |
| `basal_ganglia.softmax_temperature` | `0.0` | `0.1` | Seeded softmax action selection over the four channel scores (one draw per tick) instead of the deterministic argmax, so the arbiter is a sample too. The logged scores are unchanged. Placeholder value, not yet characterised: M1 measured the odometry only (docs/odometry.md, G25 D); G24 B5's sweep of the temperature waits for a research-profile assertion to tune it against (M2a's track). |

`research()` also sets `value_memory.generalization_radius = 0`,
`value_memory.oracle_homing = False` (the goal-vector slot, relabelled in M1 as
an explicit oracle control condition) and `basal_ganglia.criticality_gain = 0.0`
(the criticality coupling to cognition); these are already the legacy defaults
(the console's maze scenarios set the radius to 2 themselves), so they are not
in the diff. `goal_vector` is kept as a read/write alias of `oracle_homing` on
`ValueMemoryConfig`, so existing code and `--set value_memory.goal_vector=...`
still work; `to_dict` writes `oracle_homing` and `from_dict` accepts either
name. Kappa, avalanche sizes and the modulators are logged in both.
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
bit at `sensors.noise` 0. The research profile has four seeded elements on by
default (three since M0b, the heading oracle's error since M2b's exit), each on
its own named stream (a new name derives its own child seed, so the existing
streams are untouched), and each draws nothing at 0:

- Odometry noise (`core.sensors._compute_egomotion`, stream `sensors_odometry`):
  on every tick the raw forward displacement is multiplied by
  `1 + odometry_speed_noise * xi` and the raw heading change gets
  `+ N(0, odometry_turn_noise)`, forward draw first, then turn, before the
  usual clamps; the spatial system integrates the noisy deltas and the body is
  not touched (two `gauss` draws per tick). The forward clamp is the profile's
  `sensors.forward_delta_limit`: at the legacy 1.0 a FORWARD step (1.0) sat at
  the top of the range, so on full-thrust ticks only slowing speed errors
  reached the estimate (M1 measured the resulting 2% shortfall); the research
  profile's 2.0 (M2a) keeps both signs, so the error is zero-mean
  (docs/odometry.md).
- Softmax action selection (`brain.systems.basal_ganglia.softmax_sample`, stream
  `action_softmax`): at `softmax_temperature` tau > 0 the action is sampled with
  probability proportional to exp((s_i - max s) / tau) over the channels in the
  argmax's fixed order, from one `random()` draw per tick walked over the
  cumulative sums; the scores logged in `action_scores` are still the scores.
  At tau = 0 the deterministic argmax with its tie order runs as before.
- The heading oracle's error (`core.sensors`, stream `sensors_heading`): on
  every tick the Observation's heading is the body's plus N(0,
  `heading_oracle_noise`); nothing is drawn at 0 or with the oracle off (M2b
  step 1; on by default since G37). The spatial system reads it as the heading
  estimate (`heading_source = "oracle"`), so the heading error is this draw and
  not a random walk.
- The guard (`core.seeds.require_seeds_are_samples`): `EngineConfig
  .stochastic_elements()` lists which of `sensors.noise`,
  `sensors.odometry_speed_noise`, `sensors.odometry_turn_noise` and
  `basal_ganglia.softmax_temperature` are above 0, and the oracle's sd while
  the oracle is on; asking for more than one
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

Open field, seed 1337, 3000 ticks, `EngineConfig.research()` with its four
seeded elements set to 0 (the M0a acceptance is about the deterministic
mechanics): 0 microsleep ticks, `trn_state` OPEN on every tick, `energy_scale`
1.0 and ATP 1.0 on every tick, the realised step equal to the commanded thrust
on every tick (1.0 for FORWARD, 0.3 for a TURN; `World.step` moves the agent
`thrust * energy_scale` world units, there is no separate step length), and
the path-integration estimate equal to the true position throughout (sensor
and odometry noise are 0, so odometry is exact; the oracle at sd 0 is the true
heading; the body never touches a wall in this run, so the reset never fires;
the difference is floating-point rounding, below 1e-12). The M2b fields do not
move this run: without reward the SR value is 0 everywhere, so the steering is
what it was under the map. The legacy profile at the same seed gives a mean
step of 0.088 and 1270 microsleep ticks.

At the research defaults (seeded elements on) the energy statements hold tick
for tick and the estimate's error is bounded instead of growing. Measured at
M2b's exit (G37; the oracle heading at sd 0.05 and the wall reset on): its
error first exceeds 0.5 units at tick 82, is 0.88 units at tick 3000 and 3.5
at most (median 0.63); the softmax wanders the body to the walls (clamped on
1,230 of 3000 ticks, against none in the deterministic run), mean step 0.52,
28 REST ticks. The body's walk is the M2a one to the tick (the same 1,230 wall
ticks, mean step and REST count): the oracle draws on its own stream and
without reward the SR value is 0 everywhere, so the M2b fields move the
estimate and not the body (the regenerated research baseline moved its
behaviour and full hashes and not its physics hash, for the same reason). What
remains of the error is the oracle's own noise (a heading error of 0.18 rad at
most in this run) and the egomotion contract's under-read of wall slides
(docs/m2b_place_code.md step 1). At M2a the integrated estimate read tick 20,
11.8 units at the end and 15.8 at most, its drift the heading estimate's random
walk (sd 0.01 rad per tick) plus the wall clamps (before M2a: tick 37, 9.2 and
11.6 units, 753 wall ticks, mean step 0.57, 3 REST ticks; the decoupled bit
lowers every TURN score by 0.3 in an empty arena, so the softmax turns less
often and the clamp holds the body at a wall longer). Throughput at these
defaults is about 2,400 ticks/s in the open field (the SR learner's cost; the
population alone runs at 16,200), above the plan's floor of 1,000.

## What the research profile does not have yet

- (Done at M2b's exit, G37: the wall-contact reset, the place population and
  the successor representation, table above. Before the reset each wall
  contact offset the estimate once, because the box's clamp is not in the
  egomotion: 0.47 units after 48 clamp ticks at seed 1 with only the gate flag
  off; the gate's own capture was 22.8.)
- Replay as an event stream inside the engine: M1 made each microsleep replay
  an event object (`brain/systems/replay_events.py`; `engine.replay_log`,
  written to `replay_events.jsonl` by the headless runner and the console's
  recording), but inside the engine its only trigger is still microsleep and
  its only rules the two that existed, so with microsleep off this profile's
  engine produces no replay events. M2a's first replay rules (uniform,
  reverse-trajectory and |TD error|-prioritised, `brain/systems/replay_rules.py`,
  trigger `reward`) run outside the engine, on the tabular linear track of
  `experiments.linear_track_replay` (docs/m2a_linear_track.md); wiring them
  into the engine's tick is M3's. The offline consolidation sweep
  (`ValueMemory.consolidate`, the console maze's sleep after each visible
  trial and `experiments.memory_navigation`'s sleep phase) is a replay that
  is not an event yet (G25 D).
- (Done at M2a: the checksum "novelty" bit is decoupled from action selection
  in this profile, `novelty_gain` and `novelty_turn_gain` 0, table above; the
  bit, ACh and NE are still logged. The TRN replay buffer and `wm_load` are
  logged only.)
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
schema version and the file set; since M2a each reference trace also has an
observation sidecar, `reference_observations_<profile>.jsonl`, for the
cross-platform gate (docs/determinism.md). The legacy set is never
re-recorded by a profile change (bit-identical by rule, G22; the behaviour and
physics files and the reference trace were added by M0b item 7, and the
legacy sidecar by M2a, without moving the full hash). The research set was
re-recorded for M0b item 8, when the seeded elements went on by default in
`research()`, again when their odometry placeholders were lowered (87f824e),
and again at M2a, when the forward range became 2.0 and the novelty bit left
action selection (G26; the behaviour and full hashes moved, the physics hash
did not), and again at M2b's exit, when the heading oracle, the wall reset, the
place population and the SR value source went on by default (G37; again the
behaviour and full hashes moved and the physics hash did not: the body's walk
at the gate seed is unchanged). Regenerate the research set with
`python3 tools/update_determinism_baseline.py --profile research
--i-know-what-im-doing` (once per milestone; research is the tool's default
profile, and it refuses to write the legacy set in place); one engine run
writes all three hash kinds, the meta file, the reference trace and its
sidecar.
