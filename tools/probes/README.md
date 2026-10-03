# Characterisation probes

The research-readiness audit of 2026-10-03 (8 subsystem audits, 3 programs, 2 judges, 1 critic) measured most of its claims with scratch scripts that lived in a session's temporary directory. This package commits those measurements as probes, one per claim, so the pre-program state of the model is reproducible on any commit and the conversion plan can cite a command instead of a memory.

Run one from the repo root:

```
python -m tools.probes.<name>              # full budget: the outputs recorded below
python -m tools.probes.<name> --scale 0.1  # a tenth of every tick / pass budget
```

Every probe exposes `run(scale=1.0) -> dict` (labelled, deterministic results; insertion order is the print order) and `main(argv)` which prints `label: value` lines. `scale` multiplies the tick and pass budgets, each floored so a probe still runs end to end at `--scale 0.02`; `tests/characterisation/test_probes_run.py` runs every probe at that kind of budget (about 3.5 s in all) and checks it is deterministic and prints what it returns, without pinning any number. Probes only read the engine; none modifies `core`, `brain`, `ui` or `tests`. The outputs below were recorded on commit eea946f (the engine the audit read) with Python 3.11.15 on Linux; `runtime` is wall-clock and machine-dependent, everything else is bit-reproducible on the same platform.

## The one number: kappa at defaults

The criticality audit said kappa at defaults "converges to 0.905-0.914" and that "max kappa over 3000 ticks is the 1.0 placeholder"; the sleep-energy audit said kappa was "in [0.917, 1.056] over 3000 ticks at seed 1". `kappa_defaults` runs both configurations. Both audits were right about their own run and wrong as a general statement:

- **Engine, defaults, 3000 ticks, seeds 1-4:** kappa is exactly 1.0 (the placeholder) until 20 avalanches have completed (tick 79-94 depending on seed; 62 at seed 1337), then a seed-dependent transient: seed 1 [0.917, 1.056], seed 2 [0.893, 1.037], seed 3 [0.905, 1.085], seed 4 [0.911, 1.064]; finals 0.923 / 0.901 / 0.907 / 0.913. The sleep-energy audit's seed-1 range is reproduced exactly. The criticality audit's "max is the placeholder" came from seed 7 (its probe3.py: 0.864-1.0) and does not hold at seeds 1-4, where the transient exceeds 1.0 for a stretch after warm-up.
- **Standalone field, seed 1337, 20,000 ticks:** kappa settles to 0.914 once the 4000-avalanche history is full (samples every 2000 ticks: 0.901, 0.905, 0.908, 0.912, 0.910, 0.908, 0.907, 0.907, 0.909, 0.914), reproducing the criticality audit's 0.905-0.914.
- **Reconciled:** at defaults kappa is a 1.0 placeholder for the first ~60-90 ticks, then a seed-dependent transient within [0.893, 1.085] over 3000 ticks, settling to ~0.91 once the history fills (~16,000 ticks). It never exceeds 1.1 in any of these runs (0 ticks over 4 x 3000), so the TRN `kappa > 1.1` branch is dead at defaults, and it is bit-identical across behavioural configs at the same seed (a function of (seed, tick) only). Any 3000-tick episode sees kappa, and hence `near_critical_gain`, move by ~0.2 for reasons that have nothing to do with the brain's state.

## Where the probes disagree with the audits' text

- **kappa range at defaults** (above): the criticality audit's "never exceeds the 1.0 placeholder over 3000 ticks" holds at seed 7 only; seeds 1-4 reach 1.04-1.09 during the warm-up transient.
- **Where the TRN kappa branch first fires** (`dormant_couplings`): the criticality audit put it at coupling >= ~0.40 (from the converged kappa, 1.049 at 0.35). The within-episode transient already exceeds 1.1 at coupling 0.35 (277 of 3000 ticks at seed 1). More important than the threshold: with pacing off the branch cannot change the gate at any coupling tried (0 ticks NARROW-by-kappa at 0.25-0.45), because after warm-up the agent is never at ATP >= 0.55; only with pacing on (pace_low 0.6) does it narrow the gate, and then for 277 / 2779 / 2671 ticks at 0.35 / 0.40 / 0.45.
- **What `criticality_gain = 1.0` does** (`dormant_couplings`): the audit called the default field "a near-constant ~0.91 multiplier on vision_gain, indistinguishable from lowering vision_gain by 9%". Measured: the multiplier is 0.927-1.0 after warm-up at seed 1, and it flips no decision at all in the barren world, in the beacon protocol (contact at tick 9 precedes the first kappa computation, so the gain is exactly the 1.0 placeholder) or over the 324-tick foraging run; "indistinguishable" is literal here.
- **Microsleep bout length** (`microsleep_bout_length`): the audit's "every one of 51 bouts lasted exactly 25 ticks" is true of the 50 bouts that complete within 3000 ticks; the 51st is cut at 20 by the end of the run, and a naive bout count reports it. The recovery rule still never fires (0 early endings; ATP reaches 0.443 on the last sleep tick).
- **The "2.7 m during sleep"** (`microsleep_replay_content`): the value-replay audit wrote that the body "moves 2.7 m" during the sleep; during the sleep itself the body does not move at all (REST, thrust 0). G17's number, reproduced exactly (median 2.72 m at noise 0 seed 1; 2.78 m median / 5.98 m max at noise 0.03 over seeds 1-4), is the displacement during the ~29-tick frozen window *before* onset while the place estimate stayed in the sleep-onset cell.
- **Nothing else moved.** Path-integration capture (71.58 of 264.27 m, 22.82 m, 2.17 rad), gate occupancy (59 / 399 / 2542), kernel inflation (4.267 / 6.070 / 10.0), replay reach (100, 273, 26 of 300), the memory-navigation ticks (9/13/17/17 vs 9/14/15/13; 87 vs 25 cells, max V 2.125), glycogen pinning (tick 148, 0.03), novelty (0.613 / 0.082 / 1.000), the modulator fractions, open-field motion (0.088 mean step, 42.6% zero, 85.1% centre, 2.9% wall) and the assay latencies reproduce the audits' numbers to the stated precision.

## Not committed

The criticality-computation program's feasibility probe (a NumPy Kinouchi-Copelli network, `criticality-computation/kc_feasibility.py`) is not a measurement of this repository and needs numpy, which `requirements.txt` does not list; it was left out. The G16/G21 bootstrap scripts the infrastructure audit mentions were not among the audit's scratch files.

## Probes

| probe | claim it supports | full-budget runtime (s) |
|---|---|---|
| `kappa_defaults` | kappa at defaults: 1.0 placeholder for ~60-90 ticks, then a seed-dependent transient in [0.89, 1.09] over 3000 ticks, settling to ~0.91; never > 1.1; a function of (seed, tick) only | 4.15 |
| `criticality_critical_point` | the lattice is bond percolation, critical at coupling 0.5 not 0.25; default avalanche statistics are lattice-size independent; kappa = 1 crossing moves with the reference exponent and reads ~1.44 at the true critical point | 31.04 |
| `dormant_couplings` | criticality_gain defaults to 0 and at 1.0 flips no decision; the TRN kappa > 1.1 branch is dead at defaults and masked by low ATP unless pacing is on; the neuromod RNG stream is never drawn | 5.03 |
| `kernel_value_inflation` | with generalization_radius > 0 the goal cell bootstraps on itself: V(goal-1) 4.27 after 60 passes, 6.07 converged at radius 2; 10.0 = r/(1-gamma) at radius 1; gamma^d at radius 0 | 1.15 |
| `replay_reach` | after a 300-step trial 60 passes leave only 26 cells above the 1e-3 steering threshold and only the last 200 steps are stored; the goal cell itself is 0 at radius 0 | 0.09 |
| `memory_nav_fragility` | replay 9/13/17/17 vs no-replay 9/14/15/13 ticks: the 1-tick first-probe advantage reverses on later probes; one visible trial + consolidation gives max V 2.125 for a reward of 1 | 0.1 |
| `microsleep_replay_content` | 98% (94-100%) of each 50-transition sleep snapshot is same-cell transitions; the body moved a median 2.7 m (max 6.0 m) while the frozen estimate stayed in the sleep-onset cell | 1.86 |
| `path_integration_capture` | pacing off: gate CLOSED 2542 / NARROW 399 of 3000 ticks, 27% of the true path captured, 22.8 m final error, 2.17 rad heading error; pace_low 0.6: exactly 0 error (noiseless odometry) | 3.6 |
| `energy_limit_cycle` | with glycogen exhausted the store is one linear tank (atp += 0.015 - 0.04 demand); default agent: 51 sleeps in 3000 ticks, 85% of ticks gate CLOSED, mean ATP 0.35, sleeps every ~57 ticks | 0.48 |
| `glycogen_pinning` | glycogen is pinned at exactly 0.03 (the per-tick regen) from tick 148 on; the console's glycogen panel shows a constant | 0.47 |
| `microsleep_bout_length` | every complete bout lasts exactly 25 ticks; the recovery rule (ATP > 0.45 for 5 ticks) never fires because ATP rises 0.007/tick during sleep | 0.52 |
| `novelty_pinning` | novelty is a checksum-changed bit: 0.61 mean at noise 0 (0.08 asleep), 1.0 on every tick at noise 0.03, so ACh is pinned at 1 and NE floored at 0.5; wm_load saturates at 32 | 0.62 |
| `neuromod_traces` | reward-free protocols: DA = 5HT = 0.5 on 100% of ticks; noise 0.03 pins ACh at 1 and pain > 0 on ~50% of ticks from clamped noise; foraging DA < 0.5 on 64-68% of ticks and saturates at 1.0 on contact | 1.92 |
| `open_field_motion` | 42% of open-field steps are zero and the mean step is 0.088 of the nominal 1 m (energy_scale); 85% of ticks in the central 10 x 10 m, 2.9% near a wall; protocol score -2911 | 0.47 |
| `assay_triviality` | the headless water maze is solved in 5 ticks on-axis and never/by chance off-axis (2 of 5 placements never in 2000 ticks); the T-maze in 6 ticks; neither has walls, pool, platform or arms in the World | 1.12 |
| `seed_pseudoreplication` | at sensors.noise 0 seeds 1-4 give bit-identical trajectories (only the kappa series differs); at noise 0.03 they diverge by up to 18 m | 1.04 |
| `runtime` | default engine ~7,500-8,900 ticks/s and console scenarios ~6,000-7,000 ticks/s in pure Python on this machine (wall-clock; the only non-deterministic probe) | 1.86 |


### `kappa_defaults`

`python -m tools.probes.kappa_defaults` (4.15 s)

What kappa does at engine defaults, and the reconciliation of two audit numbers.

Claims (criticality audit and sleep-energy audit, 2026-10-03):

* The criticality audit said kappa at defaults (coupling 0.25, 16x16, exponent
  1.5) "converges to 0.905-0.914 and stays there" and that over 3000 engine
  ticks "max kappa is the 1.0 placeholder". The sleep-energy audit said kappa
  was "in [0.917, 1.056] over 3000 ticks at seed 1". Both are right about their
  own run: the first number is the long-run (20,000-tick, 4000-avalanche
  history) value of the standalone field at seed 1337; the second is the
  within-episode transient at seed 1, where the first few hundred avalanches
  carry kappa above 1 before the buffer fills. This probe runs both.
* kappa is pinned at exactly 1.0 until 20 avalanches have completed (62 ticks
  at seed 1337), then drops to ~0.9.
* kappa never exceeds 1.1 at defaults, so ``TRNGate.trn_state``'s kappa branch
  never fires (see also dormant_couplings).
* The kappa series is a function of (seed, tick) only: two engines with the
  same seed and different behavioural configs give bit-identical kappa series
  while their trajectories diverge.

Recorded output:

```
== kappa at engine defaults (criticality vs sleep-energy audit reconciliation)
config: EngineConfig() defaults: coupling 0.25, 16x16 torus, reference exponent 1.5, kappa after >= 20 avalanches, 4000-avalanche history; default barren world, sensors.noise 0
engine_ticks: 3000
engine_kappa_by_seed: {1: {first_tick_kappa_computed: 88, min: 0.9173, max_including_placeholder: 1.056, max_after_warmup: 1.056, final: 0.9231, ticks_kappa_gt_1_1: 0, avalanches: 716}, 2: {first_tick_kappa_computed: 86, min: 0.8934, max_including_placeholder: 1.0369, max_after_warmup: 1.0369, final: 0.9005, ticks_kappa_gt_1_1: 0, avalanches: 756}, 3: {first_tick_kappa_computed: 94, min: 0.9052, max_including_placeholder: 1.0852, max_after_warmup: 1.0852, final: 0.9074, ticks_kappa_gt_1_1: 0, avalanches: 740}, 4: {first_tick_kappa_computed: 79, min: 0.9106, max_including_placeholder: 1.0644, max_after_warmup: 1.0644, final: 0.9125, ticks_kappa_gt_1_1: 0, avalanches: 744}}
engine_kappa_range_over_seeds_after_warmup: [0.8934, 1.0852]
engine_ticks_kappa_gt_1_1_total: 0
standalone_seed1337_ticks_until_kappa_first_computed: 62
standalone_seed1337_long_run_ticks: 20000
standalone_seed1337_kappa_samples: [0.9014, 0.9046, 0.9084, 0.9117, 0.9099, 0.9082, 0.907, 0.9074, 0.9089, 0.914]
standalone_seed1337_kappa_final: 0.914
standalone_seed1337_avalanches_in_history: 4000
near_critical_gain_at_final_kappa: 0.9211
seed7_kappa_series_identical_across_behavioural_configs: True
seed7_positions_identical_across_behavioural_configs: False
reconciled: At defaults kappa is 1.0 (placeholder) for the first ~60 ticks, then a seed-dependent transient within [0.893, 1.085] over 3000 engine ticks (seeds (1, 2, 3, 4)), settling toward 0.914 once the 4000-avalanche history fills (~16,000 ticks); it never exceeds 1.1, so the TRN kappa branch is dead at defaults.
```

### `criticality_critical_point`

`python -m tools.probes.criticality_critical_point` (31.04 s)

Where the lattice's critical point really is, and what kappa reads there.

Claims (criticality audit, 2026-10-03):

* The field is a synchronous SIR epidemic / bond percolation on a square torus,
  critical at coupling 0.5, not 0.25. At the default 0.25 avalanche statistics
  are lattice-size independent (mean ~4.2, largest 42-62 at L = 16 and 64),
  the signature of a subcritical process; lattice-spanning avalanches (>= half
  the cells) only appear at coupling >= 0.45 and dominate at 0.50.
* The kappa = 1 crossing near coupling 0.32 is an estimator artefact of the
  mean-field reference exponent 1.5; with the 2-D percolation exponent
  187/91 ~ 2.055 it crosses at ~0.25, and at the true critical point (0.5)
  kappa reads ~1.44 at every lattice size because spanning avalanches pile up
  at the lattice size. kappa does not locate criticality in this model under
  either exponent.

The audit swept 9 couplings at L = 16, 64 and 128 (about 90 s); this probe
keeps L = 16 and 64, five couplings and three seeds (about 25 s at scale 1).

Recorded output:

```
== critical point of the lattice vs the default coupling and the kappa estimator
config: CriticalityField standalone, 20000 generations per run, couplings (0.15, 0.25, 0.35, 0.45, 0.5), sizes (16, 64), seeds (1, 2, 3); kappa over the whole run with exponent 1.5 (code) and 2.055 (2-D)
sweep: {L16_c0.15: {n_avalanches: 7015, mean_size: 2.0666, max_size: 19, frac_spanning_half: 0, kappa_tau1.5: 0.7933, kappa_tau2.055: 0.8842}, L16_c0.25: {n_avalanches: 4909, mean_size: 4.2112, max_size: 53, frac_spanning_half: 0, kappa_tau1.5: 0.9053, kappa_tau2.055: 1.011}, L16_c0.35: {n_avalanches: 2720, mean_size: 12.8513, max_size: 134, frac_spanning_half: 0.0005, kappa_tau1.5: 1.0491, kappa_tau2.055: 1.1599}, L16_c0.45: {n_avalanches: 1014, mean_size: 76.9919, max_size: 233, frac_spanning_half: 0.3061, kappa_tau1.5: 1.2886, kappa_tau2.055: 1.3993}, L16_c0.50: {n_avalanches: 764, mean_size: 150.565, max_size: 249, frac_spanning_half: 0.7098, kappa_tau1.5: 1.4327, kappa_tau2.055: 1.5433}, L64_c0.15: {n_avalanches: 7017, mean_size: 2.0659, max_size: 19, frac_spanning_half: 0, kappa_tau1.5: 0.7932, kappa_tau2.055: 0.8841}, L64_c0.25: {n_avalanches: 4917, mean_size: 4.2024, max_size: 62, frac_spanning_half: 0, kappa_tau1.5: 0.906, kappa_tau2.055: 1.0119}, L64_c0.35: {n_avalanches: 2714, mean_size: 12.9635, max_size: 194, frac_spanning_half: 0, kappa_tau1.5: 1.0418, kappa_tau2.055: 1.1527}, L64_c0.45: {n_avalanches: 670, mean_size: 161.8876, max_size: 1776, frac_spanning_half: 0, kappa_tau1.5: 1.2205, kappa_tau2.055: 1.3223}, L64_c0.50: {n_avalanches: 200, mean_size: 1683.2334, max_size: 3341, frac_spanning_half: 0.5534, kappa_tau1.5: 1.4358, kappa_tau2.055: 1.5328}}
L16_coupling_where_kappa_tau1.5_crosses_1: 0.3159
L16_coupling_where_kappa_tau2.055_crosses_1: 0.2413
L64_coupling_where_kappa_tau1.5_crosses_1: 0.3192
L64_coupling_where_kappa_tau2.055_crosses_1: 0.2407
default_c0.25_mean_size_by_L: [4.2112, 4.2024]
default_c0.25_max_size_by_L: [53, 62]
c0.50_kappa_tau1.5_by_L: [1.4327, 1.4358]
smallest_coupling_with_spanning_avalanches_L16: 0.35
```

### `dormant_couplings`

`python -m tools.probes.dormant_couplings` (5.03 s)

Couplings that exist in code but do nothing at the defaults.

Claims (criticality, neuromodulation and sleep-energy audits, 2026-10-03):

* ``BasalGangliaConfig.criticality_gain`` defaults to 0.0, so the field has no
  causal effect; with it at 1.0 the default field is a near-constant ~0.91-0.93
  multiplier on ``vision_gain`` (near_critical_gain of a kappa near 0.9), not a
  state-dependent gain. ``vision_gain`` multiplies target closeness, so in the
  barren default world even that multiplier changes nothing; in the beacon
  protocol contact (tick 9) precedes the first kappa computation (~tick 88),
  so the gain is exactly the 1.0 placeholder; and over the 324-tick foraging
  run the ~0.93 multiplier flips no decision at seed 1.
* ``TRNGate.trn_state``'s ``kappa > 1.1 -> NARROW`` branch never fires at the
  default coupling. The audit put the first coupling at which it fires at
  ~0.40 (converged kappa); the within-episode transient crosses 1.1 already at
  0.35. Either way, with pacing off the agent is almost never at ATP >= 0.55
  after warm-up, so the branch cannot change the gate state; it only matters
  with pacing on (ATP held high), where it narrows the gate for the whole run.
* The ``neuromod`` RNG stream is allocated in ``Engine.__init__`` but never
  drawn from.

Recorded output:

```
== couplings that are dormant at engine defaults
config: seed 1, default barren world unless stated, 3000 ticks
ticks: 3000
criticality_gain_default: 0
crit_gain_multiplier_min_max_after_warmup: [0.9269, 1]
criticality_gain_1_changes_positions_barren_world: False
beacon_ticks_gain0_vs_gain1: [9, 9]
beacon_kappa_at_last_tick: 1
criticality_gain_1_changes_positions_beacon: False
foraging_ticks_gain0_vs_gain1: [324, 324]
foraging_kappa_at_last_tick: 0.9645
criticality_gain_1_changes_positions_foraging: False
trn_kappa_branch_by_coupling_pacing_off: {c0.25: {kappa_final: 0.9231, ticks_kappa_gt_1_1: 0, ticks_gate_narrowed_by_kappa: 0}, c0.30: {kappa_final: 0.9926, ticks_kappa_gt_1_1: 0, ticks_gate_narrowed_by_kappa: 0}, c0.35: {kappa_final: 1.0823, ticks_kappa_gt_1_1: 277, ticks_gate_narrowed_by_kappa: 0}, c0.40: {kappa_final: 1.1543, ticks_kappa_gt_1_1: 2779, ticks_gate_narrowed_by_kappa: 0}, c0.45: {kappa_final: 1.2819, ticks_kappa_gt_1_1: 2671, ticks_gate_narrowed_by_kappa: 0}}
smallest_coupling_with_kappa_gt_1_1_pacing_off: 0.35
smallest_coupling_where_kappa_narrows_gate_pacing_off: None
trn_kappa_branch_by_coupling_paced_0.6: {c0.25: {kappa_final: 0.9231, ticks_kappa_gt_1_1: 0, ticks_gate_narrowed_by_kappa: 0}, c0.30: {kappa_final: 0.9926, ticks_kappa_gt_1_1: 0, ticks_gate_narrowed_by_kappa: 0}, c0.35: {kappa_final: 1.0823, ticks_kappa_gt_1_1: 277, ticks_gate_narrowed_by_kappa: 277}, c0.40: {kappa_final: 1.1543, ticks_kappa_gt_1_1: 2779, ticks_gate_narrowed_by_kappa: 2779}, c0.45: {kappa_final: 1.2819, ticks_kappa_gt_1_1: 2671, ticks_gate_narrowed_by_kappa: 2671}}
smallest_coupling_with_kappa_gt_1_1_paced_0.6: 0.35
smallest_coupling_where_kappa_narrows_gate_paced_0.6: 0.35
neuromod_stream_state_unchanged_after_run: True
```

### `kernel_value_inflation`

`python -m tools.probes.kernel_value_inflation` (1.15 s)

The generalization kernel makes the value map bootstrap on itself.

Claim (value-replay audit, 2026-10-03): ``ValueMemory._td_update`` writes the
centre cell's bootstrap target into its Chebyshev neighbourhood with weight
``falloff^(|dx|+|dy|)``, so with ``generalization_radius > 0`` the goal cell is
pulled toward ``r + gamma * V(goal)`` through its own kernel. On a 12-cell
chain with one terminal reward of 1.0 (alpha 0.2, gamma 0.9):

* radius 0 converges to V(d) = gamma^d, V(goal-1) = 1.0 (correct);
* radius 2 (the maze and hidden-food setting) gives V(goal-1) ~ 4.27 after the
  standard 60 passes and ~6.07 at convergence;
* radius 1 converges to V = 10.0 = r / (1 - gamma).

V is therefore not an expected discounted return; its scale depends on the
radius, the pass count and the path geometry.

Recorded output:

```
== kernel value inflation on a 12-cell chain
config: ValueMemory(lr 0.2, gamma 0.9), 12-cell straight chain, reward 1.0 on arrival at the last cell, consolidate(passes) for passes in [60, 200, 1000, 5000]
analytic_gamma_d_radius0: [0.3487, 0.3874, 0.4305, 0.4783, 0.5314, 0.5905, 0.6561, 0.729, 0.81, 0.9, 1, 0]
radius0: {passes60: {V_goal_minus_1: 1, V_goal: 0, V_start: 0.3012, max_V: 1}, passes200: {V_goal_minus_1: 1, V_goal: 0, V_start: 0.3487, max_V: 1}, passes1000: {V_goal_minus_1: 1, V_goal: 0, V_start: 0.3487, max_V: 1}, passes5000: {V_goal_minus_1: 1, V_goal: 0, V_start: 0.3487, max_V: 1}}
radius1: {passes60: {V_goal_minus_1: 4.6441, V_goal: 4.5831, V_start: 1.3818, max_V: 4.6441}, passes200: {V_goal_minus_1: 8.3255, V_goal: 8.6736, V_start: 3.0828, max_V: 8.6736}, passes1000: {V_goal_minus_1: 9.5188, V_goal: 9.9996, V_start: 3.6342, max_V: 9.9996}, passes5000: {V_goal_minus_1: 9.5192, V_goal: 10, V_start: 3.6344, max_V: 10}}
radius2: {passes60: {V_goal_minus_1: 4.2667, V_goal: 4.2832, V_start: 1.5273, max_V: 4.2832}, passes200: {V_goal_minus_1: 5.9436, V_goal: 6.1351, V_start: 2.4339, max_V: 6.4459}, passes1000: {V_goal_minus_1: 6.0701, V_goal: 6.2748, V_start: 2.5023, max_V: 6.6473}, passes5000: {V_goal_minus_1: 6.0701, V_goal: 6.2748, V_start: 2.5023, max_V: 6.6473}}
radius2_passes60_values_along_chain: [1.527, 1.641, 1.788, 1.996, 2.231, 2.494, 2.783, 3.105, 3.481, 3.832, 4.267, 4.283]
radius2_passes60_values_two_cells_off_chain: [1.343, 1.507, 1.672, 1.873, 2.101, 2.355, 2.636, 2.947, 3.322, 3.625, 3.922, 3.258]
r_over_1_minus_gamma: 10
```

### `replay_reach`

`python -m tools.probes.replay_reach` (0.09 s)

How far back along a trajectory 60 reverse passes carry a usable gradient.

Claims (value-replay audit, 2026-10-03):

* Gradient reach is limited by gamma 0.9, alpha 0.2, 60 passes, capacity 200
  and the 1e-3 flatness threshold: after a 300-step trial only the last ~26
  cells carry V > 1e-3 (the steering threshold) and only the last 200 steps
  are stored at all (the first cell with any value is step 100).
* Reward-on-arrival leaves the goal cell itself at V = 0 at radius 0 (nothing
  is recorded after the terminal step): a value hole at the goal.
* Dwell extinction erases a self-made 0.5 peak to 0 in 60 passes with the
  0.02 charge, and so does plain replay of same-cell zero-reward transitions
  without it.

Recorded output:

```
== reach of reverse replay along a long trajectory
config: ValueMemory(lr 0.2, gamma 0.9, capacity 200, radius 0); straight 300-step trajectory, reward 1.0 at the last step, consolidate(passes=60)
trajectory_steps: 300
stored_entries: 200
first_step_with_any_value: 100
first_step_with_V_above_steer_threshold: 273
steps_with_V_above_steer_threshold: 26
V_goal_minus_1: 1
V_goal_cell_radius0: 0
dwell_peak_0.5_after_60_passes_charge_0.02: 0
dwell_peak_0.5_after_60_passes_charge_0.0: 0
```

### `memory_nav_fragility`

`python -m tools.probes.memory_nav_fragility` (0.1 s)

The headline replay advantage is a single deterministic sample on a knife edge.

Claims (value-replay audit, 2026-10-03):

* ``run_memory_navigation`` (one visible trial, optional 60-pass consolidation,
  hidden probes) at the default goal (6, 3): replay 9 / 13 / 17 / 17 ticks
  (visible, then three hidden probes) vs no-replay 9 / 14 / 15 / 13, so the
  1-tick first-probe advantage reverses on later probes.
* After one 9-tick visible trial plus consolidation the map holds 87 cells
  with V > 1e-3 and max V = 2.125 for a single reward of 1.0 (kernel
  inflation, radius 2); without consolidation 25 cells and max V = 0.2.

Recorded output:

```
== memory-navigation replay advantage (knife edge)
config: experiments.memory_navigation defaults: seed 1337, goal (6.0, 3.0) r 1.5, radius-2 kernel, approach_weight 0, max_ticks 200, 60 consolidation passes, 1 visible trial + 3 hidden probes
ticks_to_goal_replay: [9, 13, 17, 17]
reached_replay: [True, True, True, True]
ticks_to_goal_no_replay: [9, 14, 15, 13]
reached_no_replay: [True, True, True, True]
map_after_consolidation: {visible_trial_ticks: 9, trajectory_entries: 9, cells_V_gt_1e-3: 87, max_V: 2.1252, goal_cell: [13, 3]}
map_online_only: {visible_trial_ticks: 9, trajectory_entries: 9, cells_V_gt_1e-3: 25, max_V: 0.2, goal_cell: None}
```

### `microsleep_replay_content`

`python -m tools.probes.microsleep_replay_content` (1.86 s)

What microsleep replay actually replays at engine defaults.

Claim (value-replay and sleep-energy audits, citing docs/decisions.md G17):
because the TRN gate multiplies egomotion into path integration and closes
(ATP < 0.35) some 25-50 ticks before a microsleep starts, the place estimate
is frozen while the body still moves. The 50-transition snapshot taken at
sleep onset is therefore almost entirely same-cell transitions (G17: median
98%, range 94-100%, at noise 0.03 over seeds 1-4), and the body moved a median
2.7 m (up to 5.9 m) during the frozen window before onset while the estimate
stayed in the sleep-onset cell. Microsleep replay mostly re-applies TD and
dwell extinction to the one cell the agent "fell asleep in".

The snapshot is read from ``Engine._replay_plan`` right after the first sleep
tick (a private attribute, read only). The frozen window is the run of ticks
before onset whose place bin equals the onset bin.

Recorded output:

```
== microsleep replay content at engine defaults
config: EngineConfig() defaults (pacing off), barren world, 3000 ticks
ticks: 3000
noise0_seed1: {sleeps_with_a_snapshot: 51, snapshot_span_min_max: [50, 50], same_cell_fraction_median: 0.98, same_cell_fraction_min_max: [0.94, 0.98], awake_ticks_gate_CLOSED_before_onset_median: 25, frozen_window_ticks_median: 29, body_displacement_in_frozen_window_m_median: 2.721, body_displacement_in_frozen_window_m_max: 3.6967}
noise0.03_seeds1-4_pooled: {sleeps: 206, same_cell_fraction_median_of_seed_medians: 0.98, same_cell_fraction_min: 0.94, body_displacement_in_frozen_window_m_median_of_seed_medians: 2.7752, body_displacement_in_frozen_window_m_max: 5.9812, frozen_window_ticks_mean_of_seed_medians: 28.625}
```

### `path_integration_capture`

`python -m tools.probes.path_integration_capture` (3.6 s)

Path integration is either perfect or crippled by the TRN gate, never noisy.

Claims (spatial audit, 2026-10-03, scratch gate_cause.py and drift.py):

* At engine defaults (no pacing) over 3000 open-field ticks the gate was
  CLOSED on 2542 and NARROW on 399 ticks (OPEN 2%), driven entirely by
  ATP < 0.55 (kappa never exceeded 1.1); the integrator captured 71.6 m of a
  264.3 m true path (27%), ending 22.8 m from the true position with a 2.17 rad
  heading error.
* With gate-safe pacing (pace_rest_bonus 5, pace_low 0.6) the error is exactly
  0.000 m: egomotion is noiseless ground truth, so the gate is the only source
  of "drift".
* Seeds 1-4 give identical numbers at noise 0 (see seed_pseudoreplication).

Recorded output:

```
== path-integration capture under the TRN gate
config: barren default world, 3000 ticks, seeds (1, 2, 3, 4); pacing off vs pace_low 0.6 (bonus 5)
pacing_off_seed1: {states: {OPEN: 59, NARROW: 399, CLOSED: 2542}, gated_frac: 0.9803, ticks_atp_lt_0_55: 2941, ticks_kappa_gt_1_1: 0, true_path_m: 264.2655, estimated_path_m: 71.5799, captured_frac: 0.2709, final_error_m: 22.8209, max_error_m: 25.0683, final_heading_error_rad: 2.1705}
pacing_off_final_error_m_by_seed: [22.8209, 22.8209, 22.8209, 22.8209]
pacing_off_captured_frac_by_seed: [0.2709, 0.2709, 0.2709, 0.2709]
pace_low_0.6_seed1: {states: {OPEN: 3000, NARROW: 0, CLOSED: 0}, gated_frac: 0, ticks_atp_lt_0_55: 0, ticks_kappa_gt_1_1: 0, true_path_m: 527.8852, estimated_path_m: 527.8852, captured_frac: 1, final_error_m: 0, max_error_m: 0, final_heading_error_rad: 0}
pace_low_0.6_final_error_m_by_seed: [0, 0, 0, 0]
pace_low_0.6_captured_frac_by_seed: [1, 1, 1, 1]
```

### `energy_limit_cycle`

`python -m tools.probes.energy_limit_cycle` (0.48 s)

The default (pacing-off) agent lives on the energy limit cycle.

Claims (sleep-energy audit, 2026-10-03):

* Once glycogen is exhausted the store is one linear tank, atp += 0.015 -
  0.04 * demand per tick (demand 0.2 + 0.8 |thrust|), balanced at demand
  0.375 (mean thrust ~0.22); FORWARD costs 0.040/tick, TURN 0.0176, REST
  0.008. From full at full thrust ATP crosses 0.30 after 47 ticks; at rest it
  sits at 1.0 (glycogen pinned at 0.03).
* In the core engine (pacing off) over 3000 open-field ticks at seed 1: gate
  CLOSED 2542 / NARROW 399 / OPEN 59; 51 microsleeps (1270 ticks asleep) and
  1272 awake ticks with the gate CLOSED (ATP < 0.35); mean ATP 0.353; sleeps
  recur every ~57 ticks (awake gap median 32, min 24). Headless open-field,
  t-maze and survival assays mostly measure this cycle.

Recorded output:

```
== energy limit cycle of the default agent
config: AstrocyteConfig defaults; seed 1 barren world, pacing off, 3000 ticks
atp_gain_per_tick_when_glycogen_exhausted: 0.015
demand_balancing_recharge: 0.375
cost_per_tick_FORWARD_TURN_REST: [0.025, 0.0026, -0.007]
rest_steady_state_atp_glycogen: [1, 0.03]
ticks_to_atp_below_0_30_at_full_thrust_from_fresh: 47
trn_states: {OPEN: 59, NARROW: 399, CLOSED: 2542}
microsleep_ticks: 1270
microsleep_onsets: 51
complete_microsleep_bouts: 50
awake_ticks_gate_CLOSED: 1272
gate_CLOSED_frac: 0.8473
atp_mean_min_max: [0.3528, 0.274, 1]
awake_gap_between_sleeps_median_min: [32, 24]
actions: {FORWARD: 288, TURN_LEFT: 537, TURN_RIGHT: 905, REST: 1270}
mean_logged_thrust: 0.2402
```

### `glycogen_pinning`

`python -m tools.probes.glycogen_pinning` (0.47 s)

Glycogen is a pass-through, not a store.

Claim (sleep-energy audit, 2026-10-03): glycogen is exhausted within ~150
ticks of exploring and then pinned at exactly 0.03 (= glycogen_regen, the
per-tick regeneration that is immediately transferred to ATP) for the rest of
the run (mean ~0.10 over 3000 ticks). From then on the two-compartment energy
model collapses to a single linear tank, and the console's glycogen panel
displays a constant.

Recorded output:

```
== glycogen pinning at the per-tick regeneration
config: seed 1, EngineConfig() defaults (pacing off), barren world, 3000 ticks
glycogen_regen: 0.03
glycogen_initial: 2.98
glycogen_min_max_mean: [0.03, 2.98, 0.103]
first_tick_glycogen_pinned_at_regen: 148
frac_ticks_pinned_after_first: 1
ticks_glycogen_above_0_1_after_first: 0
```

### `microsleep_bout_length`

`python -m tools.probes.microsleep_bout_length` (0.52 s)

Every microsleep lasts exactly 25 ticks: the recovery rule is dead.

Claim (sleep-energy audit, 2026-10-03): a microsleep ends early when ATP >
0.45 for 5 consecutive ticks, but during sleep demand is 0.2 so ATP rises only
0.007/tick from ~0.275 and reaches 0.45 on about the 25th tick; every one of
the 51 bouts in 3000 ticks lasted the full ``trn.duration`` of 25 ticks. Bout
length is a constant, not a function of anything.

Recorded output:

```
== microsleep bout length at engine defaults
config: seed 1, EngineConfig() defaults (pacing off), barren world, 3000 ticks; TRNConfig duration 25, recovery_atp 0.45 for 5 ticks
atp_rise_per_sleep_tick: 0.007
complete_bouts: 50
run_ended_during_a_bout: True
distinct_bout_lengths: [25]
bouts_ended_early_by_recovery_rule: 0
atp_at_onset_mean: 0.2753
atp_at_last_sleep_tick_mean: 0.4433
awake_gap_median_min: [32, 24]
```

### `novelty_pinning`

`python -m tools.probes.novelty_pinning` (0.62 s)

Working-memory "novelty" is a checksum-changed bit, pinned at 1 under noise.

Claims (sleep-energy, neuromodulation and action-selection audits, 2026-10-03):

* ``WorkingMemory.update`` sets novelty = 1.0 iff sha256(repr(Observation))
  differs from the previous tick's. At sensor noise 0 that means "the agent
  moved": mean novelty 0.613 over 2000 open-field ticks, 0.082 during sleep.
* At the console's noise 0.03 the repr of noisy float ray distances changes
  every tick, so novelty is 1.000 on every tick including sleep; ACh
  (= novelty) is pinned at 1.0 and NE (= 0.5 pain + 0.5 novelty) is floored
  at 0.5, so vision_gain is a constant 0.9 instead of 0.6.
* ``wm_load`` saturates at the 32-entry capacity and is read by nothing.

Recorded output:

```
== novelty bit pinned by sensor noise
config: seed 1, barren world, pacing off, 2000 ticks, sensors.noise 0 vs 0.03
noise_0.0: {novelty_mean: 0.6125, novelty_mean_during_microsleep: 0.0816, novelty_mean_while_thrusting: 0.9731, frac_ticks_novelty_1: 0.6125, ACh_mean: 0.6125, NE_min: 0, wm_load_max: 32}
noise_0.03: {novelty_mean: 1, novelty_mean_during_microsleep: 1, novelty_mean_while_thrusting: 1, frac_ticks_novelty_1: 1, ACh_mean: 1, NE_min: 0.5, wm_load_max: 32}
```

### `neuromod_traces`

`python -m tools.probes.neuromod_traces` (1.92 s)

The four modulator traces in the stock headless protocols.

Claims (neuromodulation audit, 2026-10-03, scratch trace_stats.py; 1500
ticks, seeds 1-2):

* open_field and survival_arena_toy (`survival_arena` when recorded) at noise 0:
  DA == 0.5 and 5HT == 0.5 on 100%
  of ticks (no reward ever), ACh == 1 on 63% of ticks, NE mean 0.32.
* At sensors.noise 0.03: novelty == 1 on 100% of ticks in every scenario, so
  ACh is pinned at 1.0 and NE sits at 0.50-0.51; pain > 0 on ~50% of ticks
  purely from clamped uniform noise, giving DA a +/-0.01 jitter around 0.5.
* foraging: DA < 0.5 on 64-68% of ticks (the reward EMA goes positive, so
  every zero-reward step is a "disappointment") and hits exactly 1.0 on
  contact; 5HT ranges 0.33-0.72. beacon: DA saturates at 1.0 on contact.

Recorded output (re-run on 2026-10-03 after `survival_arena` was renamed `survival_arena_toy` in dcf28b8: only the four `survival_arena_*` keys changed, every number is unchanged from the eea946f recording):

```
== neuromodulator traces in the stock protocols
config: stock protocols, 1500 ticks max, seeds (1, 2), sensors.noise 0 vs 0.03
open_field_noise0.0_seed1: {n: 1500, novelty_eq_1: 0.632, ACh_mean: 0.632, DA_eq_0.5: 1, DA_lt_0.5: 0, DA_min_max: [0.5, 0.5], DA_eq_1.0: 0, NE_mean: 0.316, pain_gt_0: 0, 5HT_min_max: [0.5, 0.5], reward_nonzero: 0, expected_reward_final: 0}
open_field_noise0.0_seed2: {n: 1500, novelty_eq_1: 0.632, ACh_mean: 0.632, DA_eq_0.5: 1, DA_lt_0.5: 0, DA_min_max: [0.5, 0.5], DA_eq_1.0: 0, NE_mean: 0.316, pain_gt_0: 0, 5HT_min_max: [0.5, 0.5], reward_nonzero: 0, expected_reward_final: 0}
open_field_noise0.03_seed1: {n: 1500, novelty_eq_1: 1, ACh_mean: 1, DA_eq_0.5: 0, DA_lt_0.5: 0.3933, DA_min_max: [0.4887, 0.5082], DA_eq_1.0: 0, NE_mean: 0.5041, pain_gt_0: 0.5113, 5HT_min_max: [0.4909, 0.4989], reward_nonzero: 0.5113, expected_reward_final: -0.006}
open_field_noise0.03_seed2: {n: 1500, novelty_eq_1: 1, ACh_mean: 1, DA_eq_0.5: 0.0007, DA_lt_0.5: 0.3833, DA_min_max: [0.4888, 0.5066], DA_eq_1.0: 0, NE_mean: 0.5038, pain_gt_0: 0.532, 5HT_min_max: [0.4927, 0.5], reward_nonzero: 0.532, expected_reward_final: -0.0115}
beacon_noise0.0_seed1: {n: 9, novelty_eq_1: 1, ACh_mean: 1, DA_eq_0.5: 0.1111, DA_lt_0.5: 0, DA_min_max: [0.5, 1], DA_eq_1.0: 0.1111, NE_mean: 0.5, pain_gt_0: 0, 5HT_min_max: [0.5, 0.7697], reward_nonzero: 0.8889, expected_reward_final: 0.5394}
beacon_noise0.0_seed2: {n: 9, novelty_eq_1: 1, ACh_mean: 1, DA_eq_0.5: 0.1111, DA_lt_0.5: 0, DA_min_max: [0.5, 1], DA_eq_1.0: 0.1111, NE_mean: 0.5, pain_gt_0: 0, 5HT_min_max: [0.5, 0.7697], reward_nonzero: 0.8889, expected_reward_final: 0.5394}
beacon_noise0.03_seed1: {n: 9, novelty_eq_1: 1, ACh_mean: 1, DA_eq_0.5: 0, DA_lt_0.5: 0.1111, DA_min_max: [0.4902, 1], DA_eq_1.0: 0.1111, NE_mean: 0.5073, pain_gt_0: 0.7778, 5HT_min_max: [0.4989, 0.765], reward_nonzero: 1, expected_reward_final: 0.53}
beacon_noise0.03_seed2: {n: 9, novelty_eq_1: 1, ACh_mean: 1, DA_eq_0.5: 0.1111, DA_lt_0.5: 0, DA_min_max: [0.5, 1], DA_eq_1.0: 0.1111, NE_mean: 0.5011, pain_gt_0: 0.3333, 5HT_min_max: [0.5, 0.7691], reward_nonzero: 0.8889, expected_reward_final: 0.5381}
foraging_noise0.0_seed1: {n: 324, novelty_eq_1: 0.6481, ACh_mean: 0.6481, DA_eq_0.5: 0.0031, DA_lt_0.5: 0.6759, DA_min_max: [0.1839, 1], DA_eq_1.0: 0.0062, NE_mean: 0.3241, pain_gt_0: 0, 5HT_min_max: [0.4324, 0.7152], reward_nonzero: 0.608, expected_reward_final: 0.1598}
foraging_noise0.0_seed2: {n: 324, novelty_eq_1: 0.6481, ACh_mean: 0.6481, DA_eq_0.5: 0.0031, DA_lt_0.5: 0.6759, DA_min_max: [0.1839, 1], DA_eq_1.0: 0.0062, NE_mean: 0.3241, pain_gt_0: 0, 5HT_min_max: [0.4324, 0.7152], reward_nonzero: 0.608, expected_reward_final: 0.1598}
foraging_noise0.03_seed1: {n: 306, novelty_eq_1: 1, ACh_mean: 1, DA_eq_0.5: 0, DA_lt_0.5: 0.6373, DA_min_max: [0.2663, 1], DA_eq_1.0: 0.0065, NE_mean: 0.5039, pain_gt_0: 0.4967, 5HT_min_max: [0.3487, 0.7126], reward_nonzero: 0.8072, expected_reward_final: 0.1303}
foraging_noise0.03_seed2: {n: 303, novelty_eq_1: 1, ACh_mean: 1, DA_eq_0.5: 0.0033, DA_lt_0.5: 0.6469, DA_min_max: [0.2695, 1], DA_eq_1.0: 0.0033, NE_mean: 0.5039, pain_gt_0: 0.538, 5HT_min_max: [0.3328, 0.7148], reward_nonzero: 0.8383, expected_reward_final: 0.1329}
survival_arena_toy_noise0.0_seed1: {n: 1500, novelty_eq_1: 0.632, ACh_mean: 0.632, DA_eq_0.5: 1, DA_lt_0.5: 0, DA_min_max: [0.5, 0.5], DA_eq_1.0: 0, NE_mean: 0.316, pain_gt_0: 0, 5HT_min_max: [0.5, 0.5], reward_nonzero: 0, expected_reward_final: 0}
survival_arena_toy_noise0.0_seed2: {n: 1500, novelty_eq_1: 0.632, ACh_mean: 0.632, DA_eq_0.5: 1, DA_lt_0.5: 0, DA_min_max: [0.5, 0.5], DA_eq_1.0: 0, NE_mean: 0.316, pain_gt_0: 0, 5HT_min_max: [0.5, 0.5], reward_nonzero: 0, expected_reward_final: 0}
survival_arena_toy_noise0.03_seed1: {n: 1500, novelty_eq_1: 1, ACh_mean: 1, DA_eq_0.5: 0, DA_lt_0.5: 0.3933, DA_min_max: [0.4887, 0.5082], DA_eq_1.0: 0, NE_mean: 0.5041, pain_gt_0: 0.5113, 5HT_min_max: [0.4909, 0.4989], reward_nonzero: 0.5113, expected_reward_final: -0.006}
survival_arena_toy_noise0.03_seed2: {n: 1500, novelty_eq_1: 1, ACh_mean: 1, DA_eq_0.5: 0.0007, DA_lt_0.5: 0.3833, DA_min_max: [0.4888, 0.5066], DA_eq_1.0: 0, NE_mean: 0.5038, pain_gt_0: 0.532, 5HT_min_max: [0.4927, 0.5], reward_nonzero: 0.532, expected_reward_final: -0.0115}
```

### `open_field_motion`

`python -m tools.probes.open_field_motion` (0.47 s)

What open-field motion looks like: step lengths are a physiology artefact.

Claims (sensors-world-tasks audit, 2026-10-03, scratch probe.py):

* Over 3000 open-field ticks (seed 1337, pacing off) 42% of steps are zero
  and the mean step is 0.088 of the nominal 1.0 m FORWARD (max 0.985), because
  the astrocyte's energy_scale multiplies thrust and turn in ``World.step``.
* The agent is anti-thigmotactic: 85% of ticks in the central 10 x 10 m, 2.9%
  within 1 m of a wall (wall avoidance acts at 12 m range), the inverse of
  real rats.
* The open-field protocol score is a large negative number (-2911 at 3000
  ticks) because it subtracts 2 per microsleep tick.

Recorded output:

```
== open-field motion statistics
config: OpenFieldProtocol, seed 1337, EngineConfig() defaults (pacing off), 3000 ticks, 20x20 m box
step_mean_max: [0.0881, 0.985]
frac_zero_steps: 0.4261
frac_steps_ge_0_9: 0.0027
frac_ticks_within_1m_of_wall: 0.0287
frac_ticks_in_central_10x10: 0.8507
distance_travelled: 264.0506
microsleep_ticks: 1270
protocol_score: -2910.9494
```

### `assay_triviality`

`python -m tools.probes.assay_triviality` (1.12 s)

The headless water-maze and T-maze protocols are solved by walking forward.

Claims (sensors-world-tasks audit, 2026-10-03, scratch probe.py):

* ``MorrisWaterMazeProtocol`` has no pool, no cues and no platform object in
  the World; the platform is a protocol-side circle at (5, 0) on the start
  heading, reached in 5 ticks by any agent that moves forward. Off-axis
  platforms are reached only by chance: (0, 5) at tick 865, (-5, 5) at 176,
  (5, -5) and (-6, -2) never in 2000 ticks; start heading pi reaches the
  default platform at tick 1804.
* ``TMazeProtocol`` has no T: reward is x >= 5 in the open box, reached in 6
  ticks from the default pose.
* ``thigmotaxis_ticks`` counts distance from the origin >= 8.5 m while the
  agent lives in a square.

Recorded output:

```
== triviality of the headless water-maze and T-maze assays
config: seed 1337, EngineConfig() defaults, up to 2000 ticks per run
mwm_platform_5_0: {reached: True, time_to_platform: 5, thigmotaxis_ticks: 0}
mwm_platform_0_5: {reached: True, time_to_platform: 865, thigmotaxis_ticks: 261}
mwm_platform_-5_5: {reached: True, time_to_platform: 176, thigmotaxis_ticks: 43}
mwm_platform_5_-5: {reached: False, time_to_platform: -1, thigmotaxis_ticks: 261}
mwm_platform_-6_-2: {reached: False, time_to_platform: -1, thigmotaxis_ticks: 261}
mwm_default_platform_heading_0.00: {reached: True, time_to_platform: 5}
mwm_default_platform_heading_1.57: {reached: True, time_to_platform: 98}
mwm_default_platform_heading_3.14: {reached: True, time_to_platform: 1804}
tmaze_heading_0.00: {reached: True, time_to_reward: 6}
tmaze_heading_1.57: {reached: True, time_to_reward: 84}
tmaze_heading_3.14: {reached: True, time_to_reward: 40}
```

### `seed_pseudoreplication`

`python -m tools.probes.seed_pseudoreplication` (1.04 s)

At sensors.noise 0, N seeds are N copies of one behavioural run.

Claims (spatial, sensors and infrastructure audits, 2026-10-03):

* With ``sensors.noise = 0`` (the engine default) no behavioural path draws
  from the RNG: the seed reaches only the criticality lattice, whose kappa
  never crosses a behavioural threshold at defaults, so seeds 1-4 give
  trajectories identical to the last bit. Claims phrased "seeds 1-8 at noise
  0" are one sample, not eight.
* At noise 0.03 the seeds diverge (sensor noise is drawn per tick).
* The kappa series does differ across seeds (it is the only thing that does).

Recorded output:

```
== seed pseudo-replication at sensors.noise 0
config: barren default world, pacing off, 1000 ticks, seeds (1, 2, 3, 4), noise 0 vs 0.03
noise_0.0: {max_position_deviation_from_seed1_m: 0, action_sequences_identical: True, final_positions: [[2.2543, -2.9476], [2.2543, -2.9476], [2.2543, -2.9476], [2.2543, -2.9476]], kappa_series_identical: False}
noise_0.03: {max_position_deviation_from_seed1_m: 17.7814, action_sequences_identical: False, final_positions: [[0.5421, -4.8161], [-2.6555, -4.4271], [-3.8233, -0.7717], [4.8291, -1.1568]], kappa_series_identical: False}
```

### `runtime`

`python -m tools.probes.runtime` (1.86 s)

Engine throughput: the only non-deterministic probe (wall-clock, this machine).

Claims (completeness, judge and critic, 2026-10-03): the default barren
engine runs at ~8,000-8,900 ticks/s in pure Python 3.11 on one core; the
console scenarios with objects, memory steering and noise 0.03 run at
~5,000-7,000 ticks/s (beacon, hidden_food, memory_maze). Any program that
adds numpy populations must restate this number.

Only the tick counts are deterministic; ticks/s depends on the machine and
is recorded in README.md as indicative.

Recorded output:

```
== engine throughput (machine-dependent)
config: 3000 ticks per run; wall-clock, single process, this machine
ticks_per_run: 3000
default_engine_ticks_per_s: 7517
beacon_ticks_per_s: 6161
hidden_food_ticks_per_s: 6986
memory_maze_ticks_per_s: 6523
```

