# Determinism: what is hashed, the baselines, the tolerance gate, the numpy rules

## What is hashed (`metrics/hash.py`)

Every tick is normalised (`TickData.to_ordered_dict`), serialised as canonical JSON
(sorted keys, no whitespace) and SHA-256'd; `RunHash` chains the per-tick digests
into one run digest. Three kinds of hash are taken of the same tick:

| kind | payload |
|---|---|
| `full` | the whole tick, exactly as hashed since the first baseline |
| `behaviour` | the tick without the physics fields |
| `physics` | `tick` plus the physics fields, in fixed order |

The physics fields are `PHYSICS_FIELDS = ("kappa", "avalanche_size", "criticality_active",
"replay_index")`: the criticality lattice's outputs and the replay cursor. The split lets
the lattice and the replay internals change without invalidating a behavioural baseline,
and makes a behavioural change visible on its own. Types are part of the hash (`1` and
`1.0`, `0.0` and `-0.0` hash differently), so nothing hashed may change type.

Measured (seed 1337, 200 ticks, legacy defaults): criticality coupling 0.20 / 0.30 /
0.35 / 0.40 leaves all 200 behaviour ticks unchanged while the physics hashes part at
tick 17 / 7 / 3 / 3 (the lattice is dormant at the defaults, `tools/probes/dormant_couplings`);
`basal_ganglia.forward_bias = 0.7` parts the behaviour hash. Under the research profile
the forward-bias change leaves the physics hash exactly as it was (no microsleep, so
`replay_index` stays -1, and the lattice draws from its own RNG stream).

## Baselines (`tests/determinism/`, seed 1337, 200 ticks, one set per profile)

| profile | full | behaviour | physics | reference trace |
|---|---|---|---|---|
| legacy | `baseline_hashes.json` | `baseline_behaviour_legacy.json` | `baseline_physics_legacy.json` | `reference_trace_legacy.jsonl` |
| research | `baseline_hashes_research.json` | `baseline_behaviour_research.json` | `baseline_physics_research.json` | `reference_trace_research.jsonl` |

`baseline_meta.json` / `baseline_meta_research.json` record seed, ticks, schema version
and the file set. The legacy files are never re-recorded: the legacy profile is
bit-identical by rule (`docs/decisions.md` G22), and the tool refuses `--profile legacy`
in place (exit 2) unless `--out-dir` points elsewhere. To regenerate the research set
(the tool's default profile):

    python3 tools/update_determinism_baseline.py --profile research --i-know-what-im-doing

One engine run writes all three hash kinds, the meta file and the reference trace, so
they always describe the same trace; the diff shows which kinds actually moved (a
physics-only change moves `physics` and `full`, a behavioural change moves `behaviour`
and `full`). `--out-dir DIR` writes a profile's files elsewhere, with no flag needed, to
diff against the committed ones without touching them (the way to check the legacy set);
when the split was introduced both profiles' regenerated full files were byte-identical
to the committed ones.

Gates: `test_trace_hash.py` (full, both profiles), `test_trace_hash_split.py`
(behaviour and physics, both profiles, plus the coupling / forward-bias statements above
against the committed files), `test_physics_split.py` (the same statements measured
within one process, so they run on every platform).

## The cross-platform tolerance gate

`reference_trace_<profile>.jsonl` is the 200-tick JSONL `JsonlLogger` writes at seed 1337
(about 160 KB each). `tools/compare_traces.py` compares two traces tick by tick: ints,
strings, booleans and nulls exactly, floats within an absolute tolerance (default 1e-9;
`--field-atol NAME=TOL` per field or path such as `pos[0]`), a type change is a mismatch.
It reports the worst float deviation with its tick and field and exits 0 or 1; the
function form is `compare_traces(reference, candidate, atol=..., field_atol=...,
reference_observations=..., candidate_observations=...)`.

**The observation sidecar.** One field of a tick is a hash of floats: `obs_checksum` is
the SHA-256 of the `repr` of the whole Observation (`core.sensors.observation_checksum`),
so a last-bit difference in a ray distance that the float tolerance accepts still changes
the string, and comparing it exactly defeats the tolerance. The first macOS CI run
(2026-10-03, commit `ab262e0`) showed exactly that: 29 of 200 legacy checksums and 15 of
200 research checksums differed from the Linux references while the worst float
deviation in the traces was 9e-16 (`grid_y`) and 1e-16 (`kappa`), and no other field
differed, `wm_novelty` included. Since M2a each reference trace therefore has a sidecar,
`reference_observations_<profile>.jsonl` (about 60 KB), one `core.determinism
.observation_record` per tick from the same engine run: the tick index, `forward_delta`,
`turn_delta`, `pain_signal`, the two whisker bits and every ray's `dist`, `obj_type` and
`angle`. Given both sidecars (`--observations REF_OBS CAND_OBS`), the tool compares the
two records of every tick the same way as the trace (floats within the tolerance, labels,
bits and the index exactly; a disagreement is a mismatch reported under `observation.`),
and a differing `obs_checksum` on a tick whose records agree is a *tolerated hash
difference*, counted and reported with the worst float gap behind it, not a mismatch.
Without the sidecars a differing checksum is a mismatch, as before: the tool never
ignores a hash difference it cannot account for. `wm_novelty` (1.0 when the checksum
changed since the previous tick) stays an exact comparison: two platforms disagreeing
about whether the observation changed is a real difference. The sidecars are written by
`tools/update_determinism_baseline.py` beside the trace (the research one regenerates
with the research set); the legacy sidecar was written once, from the function form
(`write_observation_trace(generate_profile_trace_with_observations('legacy')[1], ...)`),
when the gate learned to read it, and is covered by the legacy rule from then on
(`baseline_meta.json` predates it and does not list it).

To check another machine's trace, write it and its sidecar there and compare them here:

    python3 -c "from core.determinism import *; t, o = generate_profile_trace_with_observations('legacy'); \
      write_reference_trace(t, 'legacy_there.jsonl'); write_observation_trace(o, 'legacy_there_observations.jsonl')"
    python3 tools/compare_traces.py tests/determinism/reference_trace_legacy.jsonl legacy_there.jsonl \
      --observations tests/determinism/reference_observations_legacy.jsonl legacy_there_observations.jsonl

`tests/determinism/test_cross_platform_tolerance.py` runs this for both profiles against
the current code and checks the tool itself: a 1e-6 perturbation is flagged with its tick
and field, a checksum difference is a mismatch without sidecars and with disagreeing ones
and is tolerated only with agreeing ones, and the committed sidecar is the committed
trace's observation tick for tick (a statement about two committed files, so it holds on
every platform; the bit-identity of the current observations with the sidecar is a
separate `exact_hash` test). CI's claim (`.github/workflows/ci.yml`): same-platform bit
identity, the exact-hash gates on Ubuntu; cross-platform agreement within tolerance, this
gate on macOS with the exact-hash gates deselected (every test marked `exact_hash`,
`pytest.ini`; `test_exact_hash_marker.py` requires the marker on every test that reads a
committed hash file, so a new gate cannot be missed; the tolerance-gate step applies the
same filter, since this file also holds the same-platform bit-identity test of the
sidecar). On the machine that wrote the references the agreement is exact and nothing is
tolerated. On the macOS runner (arm64, 2026-10-24, docs/decisions.md G26 D) both
profiles' tolerance comparisons pass with the sidecars, where the first macOS run had
failed on 29 and 15 checksums; the thread-pin status there reads `none_detected`.

## The numpy rules (`core/determinism.py`)

1. One `numpy.random.Generator(PCG64(child_seed))` per named stream:
   `numpy_generator(name, seed, agent_offset=0)`, with the child seed from `core.rng`'s
   derivation, so numpy streams sit in the same seed tree as the `random.Random` streams.
   Never the global `numpy.random` state.
2. Threads pinned: `pin_blas_threads()` sets `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
   `MKL_NUM_THREADS` and `NUMEXPR_NUM_THREADS` to `1` with `setdefault` (an explicit
   environment value wins). `core/__init__.py` calls it at import; the runtimes read the
   variables when numpy loads, so `import core` must precede the first `import numpy`
   (`analysis/__init__.py` imports `core` first for the same reason, since its modules
   import numpy and pandas). The first call records whether numpy was already loaded in
   `core.determinism.NUMPY_LOADED_BEFORE_PIN` and warns when it was: the variables are
   then set but the loaded library did not read them, and `blas_info()` and the run
   manifest say so (`numpy_loaded_before_pin`) rather than claim a pin that is not in
   force. `tests/conftest.py` imports `core` before any test module, so the pin is in force
   for the whole suite (`test_numpy_rules.py` checks, inside the run, that numpy was not
   loaded first, that the four variables read 1 and that the loaded OpenBLAS reports one
   thread through `threadpoolctl`; and the same in a fresh pytest subprocess started with
   none of the variables set); importing `core.engine` never imports numpy.
3. float64 only.
4. Values cast to Python floats at the `TickData` boundary, so logs and hashes keep their types.
5. Hashed scalars accumulated in a fixed order, never over dict or set iteration.
6. The one BLAS product that will feed behaviour (the SR read-out V = M·R, M2b) runs with
   one BLAS thread, and the run manifest records, from `blas_info()`, numpy's build-time
   BLAS string (`platform.blas`, the kernel the build targets) and what the loaded
   library reports through `threadpoolctl` (`platform.blas_runtime`: the kernel it chose
   for this CPU, its version and the thread count in force), plus
   `numpy_loaded_before_pin`. What that report means is stated explicitly
   (`platform.blas_runtime_status`): `detected` (a BLAS library reported itself),
   `none_detected` (`threadpoolctl` knows no BLAS in the process: numpy against Apple's
   Accelerate on the macOS runner gives an empty list) or `unavailable`; and
   `platform.blas_threads_verified` is True only when a BLAS library was detected and
   reported the pinned count, so a manifest from a platform where no library could be
   asked says the variables are set and the pin unverified, never that it was confirmed.
   The suite's thread-pin test is split the same way: the variables and the import order
   are asserted on every platform, the live OpenBLAS count only where OpenBLAS is loaded
   (`tests/determinism/test_numpy_rules.py`). The manifest is strict JSON: the research
   profile's `trn.narrow_above_kappa = inf` is written as the string `"inf"`
   (`EngineConfig.to_dict`) and read back as a float by `from_dict`.

## Measured facts (plan §5 item 9; numpy 2.4.6, OpenBLAS 0.3.31, this machine)

- Bit-identical across 1, 2 and 4 threads and across forced OpenBLAS kernels:
  `Generator` draws, element-wise `exp`, numpy's pairwise `sum`.
- Not bit-identical: `np.dot` over 2 M elements and a 1500 × 1500 matrix product differ
  between thread counts and between kernels; repeatable at a fixed thread count and kernel.
- So "same platform" means same CPU family and pinned threads. `blas_info()` here reports
  the build as `scipy-openblas 0.3.31.188.0 (OpenBLAS 0.3.31.188.0 USE64BITINT DYNAMIC_ARCH
  NO_AFFINITY Haswell MAX_THREADS=64)` and the runtime, through `threadpoolctl`, as
  OpenBLAS 0.3.31.188.0 on the `SkylakeX` kernel with `num_threads` 1 (the pin), pthreads
  threading layer: the build string names the oldest kernel the build targets, the
  runtime entry the one chosen for this CPU, which is the kernel the claim rests on.
