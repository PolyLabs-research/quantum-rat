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
`tools/probes/README.md`); the names of the mechanisms are larger than the mechanisms.

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
  food is invisible and regrows at fixed sites, memory steering finds 2.8-4.1x as much food as
  memory off (by searching near recent finds, not by remembering sites; see the next paragraph)
  and loses no paired run (G19, G21). All of these were measured with the legacy mechanisms on
  (the TRN gate scaling path integration, energy scaling of motion, the radius-2 value kernel),
  and where a number comes from sensor noise 0, different seeds are copies of one run
  (`tools/probes/seed_pseudoreplication`); they are re-measured with confidence intervals as the
  first result of the research programme (`docs/research_plan.md`, G23).
* **Honest limits / in progress.** The criticality gain has no measured effect on behaviour at
  the default coupling (above), and the assays remain simple single-episode or few-trial tasks.
  Memory steering earns its keep only where the task needs memory: it is everything in the
  memory maze (0 vs ~147 recalls), roughly neutral in foraging and the hazard field (within about
  ±9% of memory off), and 3-11% negative in the beacon chase, where every remembered spot is
  stale. Hidden food is not accurate site memory: it is memory-driven search near recent finds. A
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
measure is reproducible. See `RECOMMENDATIONS.md` for what's done and what's next, and
`docs/decisions.md` for the rationale behind each step.

### Profiles

Two configuration profiles exist. The **legacy profile** is `EngineConfig()` as it is today:
every console scenario runs under it, the G-entries in `docs/decisions.md` were measured under
it, and its traces are pinned bit-for-bit by the determinism gate. The **research profile**
(`EngineConfig.research()`, added in M0a, commit 95667ce) switches the toy mechanisms off for
the research programme: the TRN gate no longer scales path integration, the energy model no
longer scales motion and microsleep is off, the value kernel radius is 0, dwell extinction is 0,
and the criticality and neuromodulator couplings are 0 (the traces are still logged), ATP is held
at baseline with the gate's κ branch off, and the goal-vector slot is off. It has no noisy
odometry, physical units, place population or replay events yet: with microsleep off there is no
replay at all in this profile until M1 (`docs/profiles.md`). See `docs/profiles.md` and
`docs/research_plan.md` (§6).

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

**Live tab.** Pick one of six scenarios and watch the brain think while it runs:

| Scenario | What it shows |
|---|---|
| Open field | Exploration, fatigue, microsleep and replay; avalanches on the criticality lattice. The lattice is subcritical at the default coupling 0.25 and critical at 0.5, just above the slider's 0.45; spanning avalanches appear from 0.35 |
| Beacon chase | Vision-driven pursuit; dopamine hits 1.0 on arrival; the value map's memory of old beacon spots |
| Foraging patch | Five food items, wide field of view; reward builds the value map |
| Hazard field | Food behind hazards; pain raises norepinephrine and the value map turns red there |
| Hidden food | Invisible food at six fixed sites regrows after it is eaten; the value map marks recent finds and the agent searches near them (not site memory, G21) |
| Memory maze | Hidden-goal recall: one visible trial, sleep/replay, then navigate to the hidden goal from memory |

Panels: the arena (value map, vision rays coloured by what they hit, whiskers, pain zones, trail,
and a dashed "ghost" where path integration *thinks* the body is), the basal-ganglia decision
scores, memory steering from the value map, the four neuromodulator traces, ATP/glycogen and the
sensory gate, the 16×16 criticality lattice with live avalanches, the κ gauge and log-log
avalanche-size histogram with a reference line of slope −1.5 (a reference, not a fit: the lattice
is subcritical at the default coupling), path-integration drift, an event log and a full readout
table. Parameters (action selection, neuromodulator gains, E/I coupling, senses, sensor noise)
change live. **Record to replay** saves the session as a run.

Keys: `Space` play/pause, `→` step. Deep links work, e.g.
`/live?scenario=memory_maze&seed=7&speed=300&paused=1`.

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
* **Spatial system** driven purely by egomotion (HD + grid integrator + place id).
* **Working memory** (bounded; its "novelty" is a checksum-changed bit) + deterministic basal
  ganglia action selection.
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
  (`experiments/protocols/console.py`), with each scenario's own engine config and the engine
  stepped before the scenario on every tick, as the live session does: a headless run writes
  the same `ticks.jsonl` (and run hash) a live session of that scenario records at that seed.
  They also write `events.jsonl`, the scenario's event log, and never end early.
* Every run writes `manifest.json` beside `ticks.jsonl`, `scene.json` and `summary.json`
  (`metrics/manifest.py`): git SHA and dirty flag, the full `EngineConfig` and its profile,
  seeds, platform, Python and numpy versions, BLAS build and `*_NUM_THREADS` settings,
  wall-clock and ticks/s. Provenance only: it enters no hash, and it is the one file in a run
  with wall-clock time in it. Tournaments write one at their root; console recordings too.
  `--profile legacy|research` picks the base config for protocols that do not supply their own
  (the `console_*` ones do, and theirs wins; the manifest records both).

### Tournaments
* **AgentDNA** + deterministic fingerprinting; genes feed `EngineConfig` so agents differ behaviourally.
* **TournamentManager** + CLI runner.
* **Fairness:** Same environment/protocol seeds across agents; only agent offsets differ.
* **Stable leaderboard** ordering with explicit tie-break.

### Analysis
* Extract tournament/experiment runs to **Parquet**.
* Compute κ distribution, avalanche distributions, sleep/replay rates, score distributions.
* Generate `analysis/report/report.md` + plots.

### Lab console (`python -m ui`)
* **Live**: six scenarios run on the real engine with live brain panels and live parameters.
* **Replay**: browse runs, play/scrub trajectories with the arena scene, charts and a tick inspector.
* See "Run the lab console locally" above.

---

## Repo layout (high level)

```text
core/        – Engine, world, sensors, rng, pipeline
brain/       – Contracts + systems (criticality, TRN, spatial, WM, BG, etc.)
metrics/     – TickData schema, logger, hash utilities
experiments/ – Protocol framework + headless runner
tournaments/ – Tournament manager + runner
agents/      – AgentDNA and agent container
analysis/    – Extract → metrics → report + plots
ui/          – Lab console: server, live sessions, scenarios, static frontend
tools/       – Characterisation probes (tools/probes) and baseline utilities
tests/       – Determinism gate + unit/integration tests
docs/        – Decisions log, research plan, architecture/spec notes
artifacts/   – Agent proof artifacts, run evidence, etc.
```

---

## Licence and citation

The code is under the MIT licence (`LICENSE`). The documentation in `docs/` (including the
decisions log) and the figures are under CC BY 4.0 (`LICENSE-docs`,
https://creativecommons.org/licenses/by/4.0/). To cite the software, use `CITATION.cff` (GitHub
renders it as "Cite this repository"). Releases are tagged per milestone (`docs/research_plan.md`
§7): `v1.0-honest` is Milestone 0a, the legacy/research profile split (G22).
