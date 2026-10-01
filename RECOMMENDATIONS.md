# Quantum Rat / Critical Rat v2 — Review & Recommendations

_A review of the project as of this branch. Findings were read directly from the
code and cross-checked. Line references point at the files as they stand today._

---

## Bottom line

**The engineering scaffolding is genuinely good. The science it wraps is, right now,
mostly decorative.** You have built the hard, boring, valuable half of a research
instrument — strict determinism, clean module boundaries, structured per-tick logging,
a regression gate, reproducible tournaments — to a standard most hobby projects never
reach. What is missing is the half everyone assumes is already there: the agent cannot
actually perceive its world, its "genome" changes nothing, and the neuroscience
subsystems emit numbers that model and influence nothing.

That is a *good* position to be in. The skeleton is sound and was the expensive part to
retrofit. The work ahead is to put real muscle on it, and to make the documentation stop
claiming muscle that isn't there yet.

The single most important sentence in this document: **close the perception loop and make
AgentDNA do something — until then, every assay and every leaderboard is measuring the
drift of a fixed, blind policy under a noise stream, not behaviour.**

---

## What is genuinely good (keep doing this)

- **The World → Observation → Brain boundary is real, not just claimed.** The brain's only
  decision function, `select_action` (`brain/systems/basal_ganglia.py`), receives an
  `Observation` plus derived scalars and nothing else. `Observation` carries egomotion,
  vision, whiskers and pain but no absolute position, and `Engine._brain_step`
  (`core/engine.py`) never hands it `agent.pos`. The advertised "no position cheating"
  invariant holds in code.
- **Clean dependency layering.** The only `core` import anywhere under `brain/` is
  `RNGStream`. Every other brain system depends solely on `brain.contracts`, so the
  cognitive layer is decoupled and swappable.
- **Determinism is enforced, not hoped for.** A single seeded RNG authority feeds named
  streams (`core/rng.py`), no raw `random`/`np.random` leaks anywhere, and a trace-hash
  gate plus per-protocol determinism tests lock it down.
- **The engine fails loudly.** Pipeline steps raise if an `Observation` is missing, and the
  replay gate asserts it can only fire inside microsleep. These guards are deliberate design.
- **The tick spine is tidy.** `core/pipeline.py` runs nine named steps in one fixed, readable
  order, wired in one place.

This discipline is the project's real asset. Do not let the cleanups below erode it.

---

## The three things that stop it being a research instrument today

These are the showstoppers. Everything else is secondary to these.

### 1. The perception loop is open — the agent is blind
`core/sensors.py` builds vision rays from `vision_stream.uniform(0,1)` with `obj_type=""`,
whiskers from `noise_stream.random() > 0.8`, and pain from `noise_stream.uniform(0,1)`.
Only the egomotion deltas come from the agent's own motion. `core/world.py` has only bounds
and a clamp — no walls, targets, hazards or predator. So the senses report noise about an
empty world. The t-maze "reward" (`grid_x >= 5.0`) measures how a fixed open-loop policy's
egomotion integrator drifts under a seeded noise stream, not navigation.

**Fix:** make `gather_observation` a function of real world geometry — cast the three vision
rays against walls/targets/hazards and populate the existing `VisionRay.obj_type`/`dist`;
set `pain_signal` from real contact; set whiskers from real proximity. Keep the noise streams
only as a small additive sensor-noise term. This is the highest-leverage change in the project.

### 2. AgentDNA changes nothing — tournaments rank luck
`Agent.configure_engine` (`agents/agent.py`) is literally `pass`. The genome
(`exploration_bias`, `pain_avoidance`, `turn_bias` in `agents/dna.py`) is generated and
fingerprinted but never applied. Every competitor runs the identical hardcoded brain, so the
leaderboard ranks agents purely by their RNG offset. Relatedly, `generate_population`'s own
docstring says "seed is currently unused," so the population never varies with the tournament
seed.

**Fix (two steps, in order):**
- Give `Engine.__init__` an optional `EngineConfig` injection seam and pass the relevant slice
  into each system constructor (`core/engine.py` lines ~74–83). Keep defaults byte-identical so
  the determinism baseline hash does not move.
- Make `configure_engine` read `self.dna.params` and set concrete knobs. Wire **one** gene
  end-to-end first — e.g. feed `exploration_bias`/`pain_avoidance` into the basal-ganglia
  FORWARD-vs-REST weights (currently fixed at 0.8/0.5) — run a tournament, and confirm the
  leaderboard actually spreads. Then wire the rest and fix the unused `seed`.

This `EngineConfig` seam is the single highest-leverage refactor: it is also what lets
protocols and experiments vary a parameter without editing source.

### 3. The neuroscience subsystems are logged but inert
- **Neuromodulators** (`core/neuromodulation.py`) are a bounded random walk. DA/5HT/NE/ACh
  have no coupling to reward, arousal or precision, and no other subsystem ever reads them.
- **Replay** (`brain/systems/trn_microsleep_replay.py`) cycles a buffer index during microsleep
  but feeds nothing back; there is no plastic state to consolidate, so the spec's "replay
  improves performance" is unmet.
- **Criticality** `kappa` is an EMA of the consecutive active-count ratio, not the criticality
  κ statistic it is presented as; avalanche detection silently returns zero in the supercritical
  regime because the field never returns to exactly zero activity.
- **Reward** is `score += int(thrust > 0)` (`core/engine.py`) — it counts forward motion, not
  task success, so nothing is goal-directed.

**Fix:** for each subsystem, either make it causal (a neuromodulator must gate something; replay
must update a plastic substrate; κ must be computed properly against a real avalanche-size
distribution) **or relabel it honestly as a toy/bookkeeping stub.** Both are legitimate; silently
claiming the phenomenon is not.

---

## Also real, lower stakes

**Reproducibility / build**
- **CI is quietly broken.** `.github/workflows/ci.yml` runs `pytest`, but `requirements.txt`
  does not install it. Add `pytest` (pinned) and run `python -m pytest` (which also puts the
  repo root on `sys.path`, which `app/routes/api.py` relies on).
- `requirements.txt` lists **Flask twice**, and declares **`scipy`, `pyarrow`, `tabulate`
  (and `numpy`) which are never imported.** Dedupe and drop the unused ones.
- **No version pinning / no lockfile** — "reproducible" is aspirational until pins exist.
- **No packaging file** (`pyproject.toml`/`setup.py`); the project only runs from the repo root.
- **CI has no lint/format/type-check** step, only tests.

**Repo hygiene**
- **The v1 legacy is committed as a 421 KB binary** (`critical-rat.zip`, containing a 180 KB
  monolithic `app.py` and a 315 KB PNG). Use a `git tag legacy-v0.9` on the last v1 commit
  instead and delete the zip.
- **Regenerable outputs are committed** (`regression/report.json`, `analysis/` data). Add them
  to `.gitignore`.
- **The frozen spec is a binary `.docx`** — the document everything claims to derive from is
  undiffable. Export it to `docs/spec.md`.

**Honesty of docs**
- **`CHECKLIST_V2.md` — your self-declared "single source of truth" — is stale.** Milestones 4–8
  are unchecked but are implemented and proven in `artifacts/`. A 30–60 minute reconciliation
  pass (tick each box, cite the proving artifact inline, mark partials) makes it trustworthy again.
- **Milestone 0 "legacy preservation" never happened**, and the regression harness only compares
  v2 against itself despite `CHECKLIST_V2.md` claiming a legacy-drift comparison. Either do it or
  delete the claim (for a hobby build, deleting it is the honest cheap option).
- `README.md` claims `docs/` holds "architecture/spec notes" that do not exist.

**Code cleanups**
- **Production code imports the test suite**: `app/routes/api.py` does
  `from tests.determinism... import ...`. Promote `generate_trace`, `BASELINE_PATH`, the seed/tick
  constants into a first-class `core/determinism.py` and point tests, the app, and the baseline tool
  at it.
- **Two Flask servers with unclear roles.** `ui/replay_server.py` is the real GUI;
  `app/server.py` + `app/routes/api.py` drive a live engine but `serialize_tick` returns a ~50-field
  hardcoded-zeros dict matching a v1 frontend that no longer exists, and has no frontend of its own.
  Simplest: delete `app/`. Or gut `serialize_tick` to the real `TickData` fields and give it a tiny
  frontend. Do not keep carrying the dead legacy schema.
- **`criticality_active` is computed every tick but never logged**, so it is dead in the determinism
  gate and all analysis. Add it to the `TickData(...)` call and regenerate the baseline.
- **The entire regression harness** (`run_regression.py` + `compare.py` + its baseline) is executed
  by nothing in CI or tests — maintenance burden that looks like protection but provides none. Wire
  it into CI or delete it.
- **The agent collapses into terminal energy depletion** — with the astrocyte always ticked at
  `demand=1.0`, glycogen and ATP drain to zero and the agent spends most of a long run in forced
  microsleep/REST. Fix the energy equilibrium before trusting any long assay, and add a test that
  ATP stays above the floor for a resting agent.
- **Assays use inconsistent position references** — t-maze scores off the drifting internal estimate
  `grid_x` while Morris water maze and survival arena use true `pos`. Pick one convention.
- **Dead code:** the unused `Application` class in `app/server.py`; a stale `@pytest.mark.xfail` in
  `tests/egomotion/test_egomotion_stub.py` that now xpasses (a latent CI landmine under strict xfail);
  scattered unused imports/methods.
- Two different classes are both named `Agent` (`core/entities.py` and `agents/agent.py`) — a
  namespace collision waiting to confuse.

---

## Prioritized roadmap for a solo maintainer

### NOW — regain a trustworthy, reproducible base (≈ half a day, no feature work)
1. Fix CI: add `pytest` to deps, dedupe Flask, drop `scipy`/`numpy`/`pyarrow`/`tabulate`, run
   `python -m pytest`. Confirm it passes on a clean checkout.
2. Remove `critical-rat.zip`; tag the last v1 commit `legacy-v0.9` instead. Add generated outputs
   to `.gitignore`.
3. Export the spec `.docx` → `docs/spec.md`.
4. Reconcile `CHECKLIST_V2.md` with reality and cite the proving artifacts.
5. Fix the stale xfail; log `criticality_active`; move the determinism helpers out of `tests/` into
   `core/determinism.py`.
6. Formally **cut** legacy parity in `docs/decisions.md`, or commit to doing the drift test.

### NEXT — close the loop (this is the unlock)
7. Add the `EngineConfig` injection seam to `Engine`, defaults byte-identical.
8. Make `gather_observation` read real world geometry; add one perceivable object to `World` and one
   protocol that genuinely depends on sensing it.
9. Make `AgentDNA.configure_engine` apply one gene end-to-end; run a tournament and watch the
   leaderboard spread. Fix `generate_population`'s dead `seed`.
10. Fix the energy equilibrium so behaviour isn't dominated by forced microsleep. Make assay position
    references consistent.
11. Delete or repurpose the vestigial `app/` server.

### LATER — earn the science claims
12. Write `docs/validation.md` that splits "done" into **engineering-done** (deterministic, logged,
    tested — mostly complete) and **science-validated** (the phenomenon demonstrably emerges). For each
    claim, name one experiment and its expected signature (e.g. "sweep E/I, expect κ to cross ~1 with a
    power-law avalanche-size distribution"). That file is the real research roadmap.
13. Make the criticality κ/avalanche metrics correct, then re-derive the sweep test (the current
    monotonic test is a false positive — at 50 steps it passes only because all avalanches are zero).
14. Make neuromodulators causal and give replay a plastic substrate to consolidate — or relabel both as
    toys. Add behavioural assertions to the assay tests (does t-maze reward beat chance? does path
    integration track truth?), not just determinism/schema checks.

### CUT / DEFER
- **Cut:** legacy v1 parity.
- **Defer:** the evolution loop (already marked optional), unifying the two servers (just document the
  roles for now), and any new assays or features until at least one scientific claim is validated.

---

## The reframing question worth answering first

Decide, in one sentence in the README, **what this project is**:

- an **engineering sandbox** — a beautifully deterministic simulation harness whose cognitive content
  is deliberately stubbed, or
- a **scientific model** — a claim that criticality/neuromodulation/replay/spatial-cognition actually
  emerge and drive behaviour.

Right now the code is the former and the docs imply the latter. Pick one and align the naming, the
README, and the spec to it. If you choose the scientific framing, the "NEXT" and "LATER" sections above
are the gap you are committing to close. If you choose the sandbox framing, you are most of the way done
and the honest relabelling is cheap. Either is a fine project. The only bad option is leaving the gap
undeclared.

---

## Progress update (2026-10-01)

The findings above are the original review. The **NOW** and **NEXT** lists have since
been implemented on this branch; the **LATER** list remains open.

### NOW — done
- CI/deps fixed: `pytest` added, duplicate Flask removed, unused `scipy`/`numpy`/`tabulate`
  dropped (`pyarrow` kept for Parquet); CI runs `python -m pytest`.
- Legacy zip removed; v1 preserved at commit `0b81d62` (tag `legacy-v0.9`). Generated
  outputs untracked and gitignored.
- Spec exported to `docs/spec.md`; `CHECKLIST_V2.md` reconciled; decisions recorded.
- Stale xfail replaced with real egomotion tests; `criticality_active` now logged (was
  silently 0); determinism helpers moved to `core/determinism.py`.

### NEXT — done (the unlock)
- **EngineConfig seam** (`core/config.py`): every subsystem is now configurable; the brain
  reads `config.basal_ganglia` each tick.
- **Perception loop closed**: the World holds `WorldObject` targets/hazards, sensors raycast
  real geometry (vision/pain/whiskers), and the basal ganglia steer toward visible targets
  and away from walls. A new `beacon` assay plus `tests/experiments/test_beacon_perception.py`
  prove a sighted agent reaches the target and a blind one does not.
- **AgentDNA wired end-to-end**: `configure_engine` applies genes to behaviour, the leaderboard
  spreads across agents, and `generate_population` uses its seed
  (`tests/tournaments/test_dna_effect.py`).
- **Energy equilibrium**: effort-scaled demand + glycogen regeneration — a resting agent
  sustains, sustained effort still triggers microsleep (`tests/physiology/test_energy_equilibrium.py`).
- **Assay positions consistent**: `t_maze` now scores off true `pos`.
- **Vestigial `app/` server removed** (see `docs/decisions.md` DEC-2).

Test count went from 40 to 50, all passing.

### LATER — still open (earn the science claims)
- Make the criticality κ/avalanche metrics correct and re-derive a non-trivial sweep assertion.
- Make neuromodulators causal (they are still logged but inert) and give replay a plastic
  substrate to consolidate — or relabel both as toys.
- Add behavioural assertions to the other assays (does t_maze beat chance? does path
  integration track truth?), and wire the regression harness into CI.
- Decide and state, in the README, whether this is an engineering sandbox or a scientific model.

### LATER — mostly done (2026-10-01)
- **Criticality made real**: reimplemented as a driven branching process; `kappa` is now
  the Shew et al. (2009) statistic over the avalanche-size distribution, and the sweep asserts
  κ rises through ~1 while mean avalanche size grows with the branching ratio.
- **Dopamine made causal**: a per-tick reward (target approach/contact minus pain) now drives a
  reward-prediction-error dopamine signal that modulates exploration. NE/ACh/5HT became
  state-derived readouts (not yet control signals — still open).
- **Replay consolidates**: a plastic place-value map is updated online and, during microsleep,
  the replay gating drives TD backups that propagate value backward along the trajectory.
  Using that map for navigation is still open.
- **Behavioural assertions + regression gate**: path integration is validated against ground
  truth; the regression harness now runs in the suite against the committed baseline, with a
  numeric tolerance instead of exact equality.
- **Framing stated**: the README now says plainly this is an engineering instrument with
  grounded-but-simplified cognition, not a validated brain model.

Still open: make NE/ACh/5HT control signals; use the consolidated value map for memory-guided
navigation (and show replay improves navigation end-to-end); richer multi-trial assays. Test
count is now 59, all passing.
