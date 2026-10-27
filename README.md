# Critical Rat / Quantum Rat v2

**A deterministic “simulation as instrument” research engine for agent behaviour, assays, tournaments, and analysis.**

This repo is built around strict boundaries and reproducibility:

* **World (ground truth)** steps deterministically.
* **Brain** never reads world state directly — it receives an `Observation` and returns an `Action`.
* **A single seed** controls the run; determinism is enforced via trace hashing in CI.
* **Assays** run headless (JSONL ticks + summary outputs), and **tournaments** are reproducible + fair.
* **Analysis** converts runs into tables + plots, and a local **lab console** lets you run the brain live and replay recorded runs tick-by-tick.

---

## What this is (and isn't)

This is an **engineering instrument first**: a deterministic, reproducible, testable
sandbox for building and measuring brain-inspired agents. The scaffolding (RNG discipline,
the World→Observation→Brain boundary, per-tick logging, the determinism gate, reproducible
tournaments) is the solid part and the point of the project.

The cognitive components are **deliberately simplified**, and at different stages of
maturity. Every number below was measured by a probe in `tools/probes/` (outputs recorded in
`tools/probes/README.md`) or, for the 30-seed intervals, by `experiments/g23_remeasure.py`
(tables in `docs/data/g23/`, G23); the names of the mechanisms are larger than the mechanisms.

* **What the mechanisms are.** The criticality lattice is bond percolation on a 16×16 torus:
  each active cell activates each neighbour with probability `coupling`. Its critical point is
  at coupling 0.5, not at the default 0.25; at 0.25 the lattice is subcritical (avalanche
  statistics are the same at 16×16 and 64×64, mean size ~4.2), and lattice-spanning avalanches
  first appear at 0.35. The κ statistic (Shew et al. 2009, reference exponent 1.5) is a 1.0
  placeholder for the first ~60–90 ticks, then stays within 0.89–1.09 over a 3,000-tick run at
  the defaults and settles near 0.91; it never reaches the 1.1 the TRN's κ branch needs, so that
  branch never fires at defaults. The gain from κ into action selection (`criticality_gain`) is
  0 by default, and at 1.0 it changes no position in the barren, beacon or foraging worlds
  (`tools/probes/dormant_couplings`). The perception loop is closed for vision and pain: rays
  and pain zones are cast against real world geometry, and the basal ganglia steer toward
  visible targets and away from walls and pain (`beacon`, `foraging`). The whiskers are computed
  from the same geometry (`core/sensors.py`) but are not read by action selection
  (`brain/systems/basal_ganglia.py`, `core/engine.py`); they reach the brain only through the
  observation checksum. The four neuromodulators are four scalar traces with small couplings
  into action selection (`core/neuromodulation.py`): dopamine is reward minus a running mean of
  reward (not a prediction error over states); acetylcholine equals a "novelty" bit that is 1
  whenever the observation checksum changed (1 on every tick at sensor noise 0.03);
  norepinephrine is half pain plus half that bit; serotonin is a lagged copy of dopamine's input
  (the running mean itself). In reward-free protocols at sensor noise 0, dopamine and serotonin
  sit at exactly 0.5 for the whole run (`tools/probes/neuromod_traces`).
* **Results of the legacy profile** (today's defaults; see Profiles below). A plastic
  place-value map is learned by TD(0) and consolidated by replay; the agent uses it for
  memory-guided navigation back to a now-hidden goal (`experiments/memory_navigation.py`).
  Repeated recall reinforces the map rather than eroding it, and replay was a modest
  speed-up in one deterministic sample: at the default settings, over six goal positions the first replay
  probe is no slower on any goal and faster on five (138 vs 174 probe ticks in total; 13 vs 14 at
  the default goal, 42 vs 65 off axis). That margin is fragile (it disappears at gains 0.8-1.3 and
  under sensor noise, and on later probes at the default goal it reverses: 9/13/17/17 vs
  9/14/15/13 ticks); the robust benefit in the console's maze is more recalls per session (about
  300 vs 240 recalls in 3,000 ticks at seed 1337; the median recall is 10 vs 16 ticks over the
  first 1,500 ticks and 10 vs 10 by 3,000), not a faster first recall. Place values generalise to
  neighbouring cells (a Chebyshev kernel of radius 2 with falloff 0.5; there are no place fields), so this works at the engine's default spatial
  resolution and forward bias; the same kernel inflates the values (max V 2.1 after one visible
  trial for a reward of 1.0; on a 12-cell chain with one reward of 1.0, up to 6.6 at radius 2 and
  10 at radius 1, against 1.0 at radius 0), so V is not an expected return. Memory
  steering (`value_gain`, default 1.5) works over a wide band (0.4-3.0) without value-induced
  resting, pain freezes or wall pinning (`docs/decisions.md` G14-G16, re-measured in G20 and
  G21). Microsleep replay backs up the recent path in reverse order and never links transitions
  across an episode reset (G17); the reverse order is borrowed from awake reward replay, while
  rodent sleep replay is mostly forward. In the memory maze the agent recalls the hidden goal
  from every start heading (16 of 16, was 4 of 16): sleep replay also stores the goal's place, and
  where the replayed gradient has faded to nothing the agent turns toward it by path integration
  (G18). That place is forgotten after two visits in a row that find nothing, so the stored place
  of a goal that moved stops pulling the agent; the replayed value gradient can still lead it
  back to the old place until that gradient extinguishes (G21). In the hidden-food task, where
  food is meant to be invisible and regrows at fixed sites, memory steering appeared to find
  2.8-4.1x as much food as memory off (G19, G21), but **that benefit is withdrawn** (G46): the
  vision rays sensed the hidden sites as obstacles and turned the agent away from them, and memory
  steering only made up for that. With nothing hidden sensed, memory steering finds about half as
  much as memory off (19.4 against 40.8 per run on 30 fresh seeds, losing on every seed). All of these were measured with the legacy mechanisms on
  (the TRN gate scaling path integration, energy scaling of motion, the radius-2 value kernel),
  as single deterministic samples or a few seeds, and where a number comes from sensor noise 0,
  different seeds are copies of one run (`tools/probes/seed_pseudoreplication`). G23 re-measured
  the three headline numbers over 30 seeds with BCa confidence intervals (`docs/data/g23/`): the
  steering band survives (0.4-3.0 in both settings, value-induced REST at most 0.001 of ticks,
  3 ticks of 3,000, in any run); the hidden-food multiplier (measured with the sites sensed, withdrawn in G46) is 2.91 [2.43, 3.59] under sensor noise 0.03 alone, with
  one seed of 30 losing, and 1.34 [1.15, 1.52] once action selection has a 0.05 softmax
  temperature, because the exploring agent then finds 9.4 items on its own instead of 3.5; the
  maze recalls in 471 of 480 full-circle runs under sensor noise alone and in 371-380 once
  odometry noise and the softmax are on, the twelve off-axis headings recalling for 60-83% of
  seeds (turn noise 0.01 rad and the softmax temperature each cost about a tenth of the recalls
  on their own, speed noise 0.05 costs two of 471).
* **Results of the research profile** (M2a and M2b; `docs/research_plan.md` rows 2a and 2b). M2a
  compared seven replay rules on a tabular linear track over 30 paired seeds and two budget modes
  under a preregistered RQ1 protocol: every RQ1 bound is met by some rule, but no single rule meets
  them all, for reasons recorded as structural in G29–G32 (`docs/m2a_linear_track.md`, tag
  `v1.3-track-replay`). M2b built the embodied instrument: a declared heading oracle and a
  wall-contact reset hold the open-field estimate to 7 cm, a 400-cell place population sits on
  it, successor features learned over it skew backward on one-way laps, and steering by the SR's
  value passes the RQ4(a) gate on fresh seeds (hidden-goal success 98.7% against 100% visible and
  5% without value steering; `docs/m2b_place_code.md`, tag `v1.4-place-code`). Its limits: the
  heading is given, not inferred; the gate has one goal and known starts; replay over the place
  code is M3's. **The gate's success needs its start anchor** (G46): the true start is written into
  the agent's estimate at every trial. Told nothing, the agent finds the hidden goal on 37.7% of
  trials (99.8% anchored, 3.5% without value steering, fresh seeds); with neither the anchor nor
  the heading oracle and wall reset, on 6.2%. So the gate shows the use of a place memory given
  where the agent starts, not that the agent can work out where it is; M3 reports every result with
  and without the anchor. **With a wall in the way** (G47: solid barriers, seen as walls, nothing in
  the agent told of them), the SR appeared to reach the hidden goal from walled-off starts on 82% of
  trials, but that leaned on a sideways slide along the wall the agent could not feel, which carried
  its estimate through the wall (G48): an agent that feels it gets round on 33%, and fails even a
  visible goal behind the wall, because the value steering reads places across walls. **Distal cues
  the agent maps itself** (G48: it sees four cues outside the arena as names, bearings and distances,
  never positions, and learns where they are in its own frame) **give back what the start anchor
  gave**: told nothing of its start, it finds the hidden goal on 95% of trials (29% without the cues,
  100% told the start), nearly as fast. In the console's scenarios the SR steering circled sites it had just emptied and
  cost a third of the hidden-food finds (G40; measured with the hidden sites sensed, G46). A separate unlearning rate removes that (G41) but
  costs the gate 13 points of hidden-goal success at the rate that does it (G42), so the instrument
  keeps one rate and the two renewable-reward scenarios carry the faster one (G43).
* **Honest limits / in progress.** The criticality gain has no measured effect on behaviour at
  the default coupling (above), and the assays remain simple single-episode or few-trial tasks.
  Memory steering earns its keep only where the task needs memory: it is everything in the
  memory maze (0 vs ~147 recalls), roughly neutral in foraging and the hazard field (within about
  ±9% of memory off), and 3-11% negative in the beacon chase, where every remembered spot is
  stale. Hidden food is not accurate site memory: it is memory-driven search near recent finds, and
  without the sensing leak of G46 that search costs food rather than finding more. A
  map read 22° rotated (phantom peaks >= 2.8 m from any site) keeps about half to nearly all of
  the extra finds, depending on the seed block, and with the sites re-drawn at random every 150
  ticks memory still gives x1.1-1.5, so it needs a real map but not precise sites (G21). The agent
  circles one remembered site and never tours the six, and memory costs food when the agent's own
  exploration would find the sites anyway (sites on its wall loop, an interior explorer). Hidden
  food's score also varies by up to ~30% with the gain, so with it included the harness band
  where every scenario stays within 20% of its best shrinks (noise 0.03: 0.4-1.5, worst fraction
  0.83 at the default gain 1.5; pacing off: 0.4-1.0 or 0.4-0.8, worst 0.88 / 0.76 at 1.5); the
  0.4-3.0 band holds for the other four scenarios. Microsleep replay of the "recent path" mostly
  replays one place (98% of each sleep snapshot is same-cell transitions): a closed sensory gate
  freezes the place estimate for the ticks before sleep while the body moves on (a median 2.7 m),
  a model artefact. With pacing off the gate is closed or narrowed on 98% of open-field ticks and
  path integration captures 27% of the true path; with gate-safe pacing (`pace_low` 0.6, the maze
  and hidden-food setting) it is exact, because egomotion is noiseless; the console's beacon,
  foraging and hazard scenarios pace at 0.4, which still narrows the gate on about a third of
  ticks and leaves 23.7 units of error. The energy model is a limit cycle at defaults: glycogen is
  pinned at 0.03 from tick ~148, every microsleep bout lasts exactly 25 ticks, and 42% of
  open-field steps are zero. The maze and hidden-food fixes rely on resting before ATP reaches
  the gate threshold (`TRNConfig.open_at_atp`, 0.55), and a visible-trial search can still fail. The large score gains in the beacon, foraging
  and hazard scenarios of the lab console come mostly from fatigue pacing, which is on in those
  scenarios only, not in the core engine. The replay advantage is a single deterministic sample
  and breaks at some gains, steering parameters and noise levels
  (`tests/experiments/test_replay_geometry.py`).

So: **this is not a validated model of a real rodent brain.** It's a place to build such
models one defensible piece at a time, with the engineering guaranteeing that whatever you
measure is reproducible. `docs/research_plan.md` is the programme and its status,
`docs/decisions.md` the rationale behind each step (G1–G43), and `docs/prereg/` the
preregistrations; `RECOMMENDATIONS.md` is the original review the programme started from, kept as
a record (it predates most of the work).

### Profiles

Two configuration profiles exist. The **legacy profile** is `EngineConfig()` as it is today:
the console scenarios were built on it (since G38 the console runs them on either profile), the
G-entries in `docs/decisions.md` up to G21 were measured under it, and its traces are pinned
bit-for-bit by the determinism gate. What the gate hashes, the
baselines per profile and the cross-platform tolerance gate are described in
`docs/determinism.md`. The **research profile**
(`EngineConfig.research()`, added in M0a, commit 95667ce) switches the toy mechanisms off for
the research programme: the TRN gate no longer scales path integration, the energy model no
longer scales motion and microsleep is off, the value kernel radius is 0, dwell extinction is 0,
and the criticality and neuromodulator couplings are 0 (the traces are still logged), ATP is held
at baseline with the gate's κ branch off, and the goal-vector slot is off. Since M0b it has
seeded odometry noise and a seeded softmax temperature (placeholder values; the odometry noise
characterised in M1 and kept, `docs/odometry.md`; the temperature not yet, G25 D), so that its
seeds are samples, and declared physical units (0.2 s per tick, 0.1 m per unit, identical in both
profiles: `docs/units.md`). Since M1 its odometry noise is characterised (`docs/odometry.md`) and
every microsleep replay is an event object (the offline consolidation sweep,
`ValueMemory.consolidate`, is not yet; G25 D). Since M2a (G26) its Observation's forward range is
2.0 instead of 1.0, so the odometry speed error is zero-mean (under the legacy range a full-speed
step's estimate averaged 0.980), and the checksum "novelty" bit no longer enters its action
selection (still logged); the research baselines were regenerated once for both. Since M2b's exit
(G37) it carries the declared heading oracle (sd 0.05 rad per tick), the wall-contact position
reset, a 400-cell place population over the estimate and the successor-feature value V = M·R as
the steering's source, the instrument RQ4(a) passed with (`docs/m2b_place_code.md`); the research
baselines were regenerated once more for it (the body's walk at the gate seed is unchanged; the
estimate is what moved). With microsleep off its engine still produces no replay events; M2a's
replay rules run outside the engine on a tabular linear track (below), and replay over the place
code is M3's. See `docs/profiles.md` and `docs/research_plan.md` (§6).

### The first replay result (M2a, first pass)

`experiments/linear_track_replay.py` (docs/m2a_linear_track.md; data in `docs/data/m2a/track/`):
a tabular TD(0) agent (`TabularTD0`) runs 40 laps of a 40-cell linear track between two rewarded
ends, its actions a softmax over the value one step ahead, and after every rewarded lap makes
exactly 20 replay backups under one of three rules (uniform over the stored transitions, the lap
just run in reverse, or in proportion to the current |TD error|) or none. Over 30 paired seeds,
reverse replay cuts the steps needed for the 40 laps by 2,825 [BCa 95%: 2,147 to 3,497] from
14,490, prioritised replay by 4,016 [3,310 to 4,813] (faster on every seed) and uniform replay by
−224 [−820 to +112], a null. The state is the true cell (an oracle), the budget fixed, four rules
of the plan's nine: the textbook ordering on a sparse-reward chain, measured with intervals, and
the instrument for the embodied comparison (M3) rather than a result about rodents. Reproduce with
`python3 -m experiments.linear_track_replay --workers 4` (7 s). The rest of M2a (G27–G32) took the
comparison to the preregistered RQ1 protocol with seven rules; its reading is under "Results of the
research profile" above and in `docs/m2a_linear_track.md`.

---

## Install

Python 3.11 (`requires-python >= 3.11`; CI runs 3.11). From a checkout:

```bash
pip install -e ".[console,dev]"
```

The package itself (`pip install -e .`) brings numpy, scipy, pandas, pyarrow and matplotlib; the
`console` extra adds Flask for `python -m ui` and the `dev` extra adds pytest. `requirements.txt`
lists the same version ranges. For the exact versions the suite was last run against, install
from the lockfile and then the package without its dependencies:

```bash
pip install -r requirements.lock
pip install -e . --no-deps
```

`requirements.lock` records the Python version and date it was resolved on; regenerate it with
`pip freeze` in a fresh virtual environment after `pip install -e ".[console,dev]"`.

---

## Run the lab console locally

```bash
pip install -r requirements.txt
python -m ui                  # opens http://127.0.0.1:8000 in your browser
```

Options: `--port 8000`, `--runs-dir runs` (where recordings are read and written), `--no-browser`.
Without the flags, the `PORT` and `CRITICAL_RAT_RUNS_DIR` environment variables are used if set.
It needs nothing beyond Flask: the page is plain HTML/CSS/JS with no CDN or build step, so it
works offline.

**Live tab.** Pick a profile and one of six scenarios and watch the brain think while it runs.
The **profile switch** (G38) runs a scenario on the legacy engine (the toy mechanisms the
scenarios were built for) or on the **research profile** (`docs/profiles.md`: seeded odometry
noise and softmax, the declared heading oracle, the wall-contact reset, the 400-cell place
population and the successor-representation value steering; ATP frozen, so no fatigue or
microsleep). A scenario keeps its own settings on either base (the maze's value-map radius and
goal memory, the foraging senses, the pacing, and on hidden food and beacon the SR's unlearning
rate, G43) and the switch lists which fields those move away from the profile. `python -m experiments.runner --protocol console_<scenario> --profile research`
reproduces such a session tick for tick. The table says what each scenario shows on the legacy
profile; the console's scenario notes say what changes on the research profile.

| Scenario | What it shows |
|---|---|
| Open field | Exploration, fatigue, microsleep and replay; avalanches on the criticality lattice. The lattice is subcritical at the default coupling 0.25 and critical at 0.5, just above the slider's 0.45; spanning avalanches appear from 0.35 |
| Beacon chase | Vision-driven pursuit; dopamine hits 1.0 on arrival; the value map's memory of old beacon spots |
| Foraging patch | Five food items, wide field of view; reward builds the value map |
| Hazard field | Food behind hazards; pain raises norepinephrine and the value map turns red there |
| Hidden food | Invisible food at six fixed sites regrows after it is eaten; the value map marks recent finds and the agent searches near them (not site memory, G21). On the research profile nothing hidden is sensed (G46); the legacy profile keeps the old sensing, which saw the sites as obstacles |
| Memory maze | Hidden-goal recall: one visible trial, sleep/replay, then navigate to the hidden goal from memory |

Panels: the arena (value map, vision rays coloured by what they hit, whiskers, pain zones, trail,
and a dashed "ghost" where path integration *thinks* the body is), the basal-ganglia decision
scores, memory steering (from the value map, or from the SR value on the research profile), the
four neuromodulator traces, ATP/glycogen and the
sensory gate, the 16×16 criticality lattice with live avalanches, the κ gauge and log-log
avalanche-size histogram with a reference line of slope −1.5 (a reference, not a fit: the lattice
is subcritical at the default coupling), path-integration drift, an event log and a full readout
table. On the research profile the arena also draws the **place code** (G38): the population's
activity at the estimate, the **SR value** V = φ·MᵀR at every cell centre (the diverging ramp of
the value map; it is what steers there), the **successor field from here** (expected future
occupancy) and, on either profile, the latest **replay events** as trails of the cells they
backed up, in order; a **Place code** panel shows the activity and the successor field on the
population's own grid with the decode error, the SR value here, the reward weights and the SR
update count. Parameters (action selection, neuromodulator gains, E/I coupling, senses, sensor
noise, and the research profile's odometry noise, oracle noise, softmax temperature and the SR's
reward learning and unlearning rates) change live. **Record to replay** saves the session as a run; its manifest and
summary carry the profile.

The view explains what is in force (G39). **Mechanisms in force** lists every mechanism the
panels describe with its status under the effective configuration, active, readout only (a gain
of 0) or off, and a one-line detail, recomputed when a slider moves; the scenario notes beneath
it are written per profile. The **Decision** panel shows each action score as its named terms
(bias, vision, memory, wall, pain, novelty, the REST drives), the total and the selection
probability (the softmax at the profile's temperature; 1 on the argmax at 0), and names the
value source the memory steer reads. The arena's default layers follow that source: the active
one is on, the other map is a diagnostic, and the colour scale of each map is printed beside
the title. **Behaviour** readouts (distance walked, wall-contact share, finds, ticks since the
last find, distance per find, reward) tell useful behaviour from cycling. Memory controls name
their learner: "Forget the rewards" clears the SR's reward weights as well as the tabular map,
and the maze's consolidation says when it changes the diagnostic map only; the maze's
inter-trial rest is physiology updates, frozen with the research profile's energy.

**Measuring the circling** (G40). Every live session keeps a per-tick **decision log** and a
recording writes it as `decisions.jsonl` beside `ticks.jsonl` (`metrics/decisions.py`): position,
heading, the estimate, the action, the scores and their terms, the selection probabilities, the
probabilities **without** the memory, vision or wall term (the same softmax with the term
removed: no draw, the run untouched) and each term's immediate influence as the total-variation
shift it makes, target visibility and distance, contacts, reward and the episode boundaries. The
headless runner writes the same file with `--log-decisions`. `python -m analysis.orbits <run>`
cuts a log into loops (one full turn of accumulated heading), orbits (loops that close on
themselves) and bouts of same-direction orbits, each with its duration, loops, mean radius,
contacts, the dominant term among the turns that made it and memory's mean immediate influence,
and sorts the bouts into productive (a target was touched), memory (memory-dominant turns with an
influence above the bound), wall and other. `python -m experiments.console_ablation` runs a
scenario on matched seeds with memory steering on and off (`value_gain` 0; the learners still
run) and pairs the arms by seed on finds, unique sites, distance per find, wall contact and the
orbit measures (`analysis/stats.py`, BCa intervals); its runs on the console scenarios are in
`docs/data/console_ablation/` and read in G40. The Decision panel shows the counterfactual column
and influence live; the Behaviour readouts show the turning and closure of the last 300 ticks.
What the measurement led to (G41, preregistered in `docs/prereg/sr_unlearning_rate.md`): a separate
**unlearning rate** for the SR's per-feature reward rule (`place.reward_unlearning_rate`; None, the
default, is the rule as it was). At U = 4 on fresh seeds the memory-category orbits fall from 1,157
to 67 ticks per run and hidden-food finds rise from 16.3 to 28.4, level with no steering (27.3),
though only because the hidden sites were sensed and held no steering down (without that, no
steering finds 53.0 and U = 4 steering 41.2; G46);
the "SR reward unlearning rate" slider shows it live. It is not the research default: at U = 4
the RQ4(a) gate's hidden-goal success falls from 98.7% to 85.8% (G42), because a stable goal wants
slow unlearning. The owner's decision (G43): the instrument keeps one rate, and the two console
scenarios whose reward empties and moves on, hidden food and beacon, carry U = 4 as their own
setting.

Keys: `Space` play/pause, `→` step. Deep links work, e.g.
`/live?scenario=memory_maze&seed=7&speed=300&paused=1` or `/live?profile=research&scenario=open_field`.

**Replay tab.** Opens any run in the runs directory: live recordings, headless experiment runs
(`python -m experiments.runner --protocol foraging --ticks 2000`) and tournaments recorded with
`--include-ticks`. Scrub or play through the trajectory, click a chart or a "key moment"
(rewards, pain, microsleeps, trial resets) to jump there, and inspect every logged field of the
tick. Runs now save a `scene.json` (arena layout + start pose) so the replay can draw the world.

**Safety.** The console is a single-user local tool with no authentication. It binds to
`127.0.0.1` by default, refuses requests whose `Host` is not a loopback name (DNS-rebinding
guard), only accepts JSON POSTs (so another website can't drive it with a form), and caps request
sizes and steps per call. `--host 0.0.0.0` exposes it to your network; it warns when you do.

---

## What’s in here

### Engine features (current)
* **Central RNG authority** + injected RNG streams.
* **Per-tick TickData logging** (JSONL) + stable hashing.
* **Determinism regression gate** (baseline hashes + CI).
* **Sensors → Observation contract** (no “position cheating”).
* **Physiology + neuromodulation** logged.
* **Criticality field** (bond percolation on a torus) + avalanche detection + κ (kappa).
* **TRN gating**, microsleep + replay gating.
* **Spatial system** driven by egomotion (HD + grid integrator + place id), with an optional
  declared heading oracle and wall-contact reset.
* **Place code** (on in the research profile): a Gaussian place population over the estimate and
  successor features learned over it by TD, whose value V = φ·MᵀR can steer.
* **Working memory** (bounded; its "novelty" is a checksum-changed bit) + basal ganglia action
  selection (the argmax, or a seeded softmax on the research profile).
* **Action-driven world movement** (no random wandering).
* **Closed perception loop:** sensors raycast real world geometry (walls + `WorldObject`
  targets/hazards); the brain steers toward visible targets and away from walls.
* **`EngineConfig` seam** (`core/config.py`): every subsystem is tunable without editing source.

### Assays / Protocols (headless)
* `beacon` — navigate to a visible target (a direct test that sensing drives behaviour)
* `foraging` — collect several scattered targets (sighted agents collect them all, blind ones almost none)
* `open_field`
* `t_maze_toy`, `morris_water_maze_toy`, `survival_arena_toy` — toys kept under the legacy
  profile: no T, no pool or probe trial, no hazard the agent can sense; the first two are solved
  by walking forward (6 and 5 ticks). See their module docstrings and
  `tools/probes/assay_triviality`. The regression harness runs `open_field,beacon,foraging`.
* `console_open_field`, `console_beacon`, `console_foraging`, `console_hazard_field`,
  `console_hidden_food`, `console_memory_maze` — the lab console's six scenarios run headless
  (`experiments/protocols/console.py`), with each scenario's own settings on the runner's
  `--profile` (legacy by default, as the console's switch) and the engine stepped before the
  scenario on every tick, as the live session does: a headless run writes the same `ticks.jsonl`
  (and run hash) a live session of that scenario records at that seed on that profile. They also
  write `events.jsonl`, the scenario's event log, and never end early.
* Every run writes `manifest.json` beside `ticks.jsonl`, `scene.json` and `summary.json`
  (`metrics/manifest.py`): git SHA and dirty flag, the full `EngineConfig` and its profile,
  seeds, platform, Python and numpy versions, BLAS build and `*_NUM_THREADS` settings,
  wall-clock and ticks/s. Provenance only: it enters no hash, and it is the one file in a run
  with wall-clock time in it. Tournaments write one at their root; console recordings too.
  `--profile legacy|research` picks the base config: a bare protocol runs on it as it is, and a
  `console_*` protocol puts its scenario's own settings on it, as the console's switch does (G38);
  the manifest records the profile that ran and the one requested.
* `--log-decisions` also writes `decisions.jsonl`, one record per tick of the decision and what
  made it (`metrics/decisions.py`, G40); a live console recording always writes it.
* A run in which the engine replayed also writes `replay_events.jsonl`, one replay event per line
  (`brain/systems/replay_events.py`: the ticks it ran over, its trigger and rule, the cells it
  backed up in order), and `summary.json` carries `n_replay_events`; the research profile never
  sleeps, so it writes neither the file nor any event.
* `experiments/linear_track_replay.py` — the M2a linear-track replay comparison (above): four
  conditions × 30 seeds, one tidy per-seed table, learning curves, paired effects with BCa
  intervals, every replay event, and a manifest; `--quick` for a smoke run (needs `--out`).
  `analysis/replay_metrics.py` reads replay events by the plan's definition (at least 4
  distinct cells spanning 0.3 m) off its event file; `experiments/linear_track_sensitivity.py`
  re-runs the comparison with one parameter changed at a time (11 variants).
  `experiments/linear_track_rq1.py` runs the preregistered RQ1 protocol
  (`docs/prereg/rq1_track_tabular.md`: reward blocks, a pre-run pause beside the reward
  pause, fixed and thresholded budgets, the plan's event definition) in three versions: step 2
  on the floors (`--version step2`, `docs/data/m2a/rq1/`), step 3 with the plan's reference
  rule gain × need and its gain-only and need-only ablations (`--version step3`,
  `docs/prereg/rq1_track_gain_need.md`, a tabular successor representation for need,
  `brain/systems/successor.py` and `brain/systems/replay_gain_need.py`; `docs/data/m2a/rq1_step3/`)
  step 4 with each reward change in its own session against a baseline block and the
  thresholded θ scaled by the learner's value scale (`--version step4`,
  `docs/prereg/rq1_track_step4.md`, `--pilot` for the θ pilot; `docs/data/m2a/rq1_step4/`), and
  step 5, the same protocol on a tabular Q learner (`brain/systems/value_learners.TabularQ`)
  with the floors rerun on it and the Mattar & Daw rule with and without its forward n-step
  extension (`--version step5`, `brain/systems/replay_mattar_daw.py`,
  `docs/prereg/rq1_track_mattar_daw.md`; `docs/data/m2a/rq1_step5/`), and step 6, the default,
  step 5 plus the two Mattar & Daw rules with need read over positions and a θ pilot on the
  no-replay agent (`docs/prereg/rq1_track_step6.md`; `docs/data/m2a/rq1_step6/`);
  `experiments/linear_track_dose_response.py` runs the fixed-budget effect at 5 to 40 backups
  per pause (`docs/data/m2a/rq1/`).
* `experiments/odometry_characterisation.py` — the research profile's odometry noise characterised
  (`docs/odometry.md`; tables in `docs/data/m2a/odometry/`, the M1 record in `docs/data/m1/`).
* `experiments/estimate_correction.py` — M2b step 1: the declared heading oracle and the
  wall-contact position reset (`sensors.heading_oracle`, `sensors.wall_contact_sensing`,
  `spatial.heading_source`, `spatial.wall_reset`; off on the legacy profile, on in the research
  profile since G37), characterised in the
  2 m open field over 30 seeds (`docs/prereg/m2b_estimate.md`; `docs/data/m2b/estimate/`).
* `experiments/place_population.py` — M2b step 2: a 400-cell Gaussian place population over the
  estimate (`EngineConfig.place`, `brain/systems/place_population.py`; on in the research profile
  since G37), its
  rate maps against true position (`analysis/place_metrics.py`), an exact decoder and the engine's
  throughput with it (`docs/prereg/m2b_place_population.md`; `docs/data/m2b/place/`).
* `experiments/sr_fields.py` — M2b step 3: successor features over the place code, learned by
  TD (`brain/systems/successor_features.py`), on forced laps of a 2 m track (one-way and two-way)
  and on the agent's own walk in the open field (`docs/prereg/m2b_sr_fields.md`; `docs/data/m2b/sr/`).
* `experiments/rq4a_gate.py` — M2b step 4: the RQ4(a) gate, relative to the visible-goal ceiling
  (the owner's decision, G36), with the SR's value read-out V = M·R steering
  (`value_memory.source = "sr"`, the research profile's since G37; `"tabular"`, the legacy default,
  and `"none"` as ablation and control) (`docs/prereg/m2b_gate.md` and `m2b_gate_confirmatory.md`;
  `docs/data/m2b/gate/` and `gate_confirmatory/`). The gate sets the SR's reward rule as registered
  whatever the profile's default; `--reward-unlearning-rate` runs an exploratory variant (G42).
* `experiments/console_ablation.py` — a console scenario on matched seeds with memory steering on
  and off, every tick logged and cut into orbits, paired effects with BCa intervals (G40;
  `docs/data/console_ablation/`).
* `experiments/sr_unlearning.py` — the preregistered A/B of the SR's reward unlearning rate on
  hidden food (`docs/prereg/sr_unlearning_rate.md`, G41; data in `docs/data/console_ablation/`).

### Tournaments
* **AgentDNA** + deterministic fingerprinting; genes feed `EngineConfig` so agents differ behaviourally.
* **TournamentManager** + CLI runner.
* **Fairness:** Same environment/protocol seeds across agents; only agent offsets differ.
* **Stable leaderboard** ordering with explicit tie-break.

### Analysis
* Extract tournament/experiment runs to **Parquet**.
* Compute κ distribution, avalanche distributions, sleep/replay rates, score distributions.
* Generate `analysis/report/report.md` + plots.
* `analysis/stats.py`: BCa bootstrap intervals, paired per-seed effects, Cliff's δ, TOST
  equivalence and the pseudo-replication guard every multi-seed claim goes through
  (`docs/stats.md`).
* `analysis/orbits.py`: loops, orbits and bouts from a decision log, each attributed to the term
  that drove its turns (G40). `analysis/place_metrics.py` and `analysis/replay_metrics.py`: rate
  maps against true position, and replay events by the plan's definition.
* `tools/compare_traces.py`: the cross-platform tolerance gate, floats within 1e-9 and everything
  else exact; with the reference traces' observation sidecars it tolerates a differing
  `obs_checksum` only when the observation it hashes agrees within tolerance (`docs/determinism.md`).

### Lab console (`python -m ui`)
* **Live**: six scenarios run on the real engine, on the legacy or the research profile, with live
  brain panels (the place code and the successor representation on the research profile), the
  mechanisms in force, each decision's terms and counterfactuals, behaviour readouts and live
  parameters; every recording carries its decision log.
* **Replay**: browse runs, play/scrub trajectories with the arena scene, charts and a tick inspector.
* See "Run the lab console locally" above.

---

## Repo layout (high level)

```text
core/        – Engine, world, sensors, rng, pipeline
brain/       – Contracts + systems (criticality, TRN, spatial, WM, BG, etc.)
metrics/     – TickData schema, logger, hashing, run manifests, the decision log
experiments/ – Protocol framework + headless runner
tournaments/ – Tournament manager + runner
agents/      – AgentDNA and agent container
analysis/    – Extract → metrics → report + plots
ui/          – Lab console: server, live sessions, scenarios, static frontend
tools/       – Characterisation probes (tools/probes) and baseline utilities
tests/       – Determinism gate + unit/integration tests
docs/        – Decisions log, research plan, preregistrations, committed data, spec notes
artifacts/   – Agent proof artifacts, run evidence, etc.
```

---

## Licence and citation

The code is under the MIT licence (`LICENSE`). The documentation in `docs/` (including the
decisions log) and the figures are under CC BY 4.0 (`LICENSE-docs`,
https://creativecommons.org/licenses/by/4.0/). To cite the software, use `CITATION.cff` (GitHub
renders it as "Cite this repository"). Releases are tagged per milestone (`docs/research_plan.md`
§7): `v1.0-honest` is Milestone 0a, the legacy/research profile split (G22); `v1.1-base` is
Milestone 0b, the instrument base (G24); `v1.2-value` is Milestone 1, the value rule and odometry
(G25); `v1.3-track-replay` is Milestone 2a, tabular replay on the linear track (G26–G32); and
`v1.4-place-code` is Milestone 2b, the place code and the RQ4(a) gate (G33–G37). The first three
were tagged retroactively on 2026-10-27 at the commits the decision log names (each checked against
the test count and package version the log records). The package version stays 1.2.0
(`pyproject.toml`, `CITATION.cff`) until the owner bumps it.
