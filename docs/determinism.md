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
bit-identical by rule (`docs/decisions.md` G22). To regenerate the research set:

    python3 tools/update_determinism_baseline.py --profile research --i-know-what-im-doing

One engine run writes all three hash kinds, the meta file and the reference trace, so
they always describe the same trace; the diff shows which kinds actually moved (a
physics-only change moves `physics` and `full`, a behavioural change moves `behaviour`
and `full`). `--out-dir DIR` writes the same files elsewhere to diff against the committed
ones without touching them; when the split was introduced both profiles' regenerated full
files were byte-identical to the committed ones.

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
function form is `compare_traces(reference, candidate, atol=..., field_atol=...)`.

To check another machine's trace, write it there and compare it here:

    python3 -c "from core.determinism import generate_profile_trace, write_reference_trace; \
      write_reference_trace(generate_profile_trace('legacy'), 'legacy_there.jsonl')"
    python3 tools/compare_traces.py tests/determinism/reference_trace_legacy.jsonl legacy_there.jsonl

`tests/determinism/test_cross_platform_tolerance.py` runs this for both profiles against
the current code and checks the tool flags a 1e-6 perturbation. CI's claim
(`.github/workflows/ci.yml`): same-platform bit identity, the exact-hash gates on Ubuntu;
cross-platform agreement within tolerance, this gate on macOS with the exact-hash gates
deselected. On the machine that wrote the references the agreement is exact.

## The numpy rules (`core/determinism.py`)

1. One `numpy.random.Generator(PCG64(child_seed))` per named stream:
   `numpy_generator(name, seed, agent_offset=0)`, with the child seed from `core.rng`'s
   derivation, so numpy streams sit in the same seed tree as the `random.Random` streams.
   Never the global `numpy.random` state.
2. Threads pinned: `pin_blas_threads()` sets `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
   `MKL_NUM_THREADS` and `NUMEXPR_NUM_THREADS` to `1` with `setdefault` (an explicit
   environment value wins). `core/__init__.py` calls it at import; the runtimes read the
   variables when numpy loads, so `import core` must precede the first `import numpy`. The
   test suite imports numpy at collection (`tests/analysis`) before `core`, so it does not
   rely on the pin; importing `core.engine` never imports numpy (`test_numpy_rules.py`).
3. float64 only.
4. Values cast to Python floats at the `TickData` boundary, so logs and hashes keep their types.
5. Hashed scalars accumulated in a fixed order, never over dict or set iteration.
6. The one BLAS product that will feed behaviour (the SR read-out V = M·R, M2b) runs with
   one BLAS thread and the run manifest records the kernel (`blas_info()`).

## Measured facts (plan §5 item 9; numpy 2.4.6, OpenBLAS 0.3.31, this machine)

- Bit-identical across 1, 2 and 4 threads and across forced OpenBLAS kernels:
  `Generator` draws, element-wise `exp`, numpy's pairwise `sum`.
- Not bit-identical: `np.dot` over 2 M elements and a 1500 × 1500 matrix product differ
  between thread counts and between kernels; repeatable at a fixed thread count and kernel.
- So "same platform" means same CPU family and pinned threads. `blas_info()` here reports
  `OpenBLAS 0.3.31.188.0 USE64BITINT DYNAMIC_ARCH NO_AFFINITY Haswell MAX_THREADS=64`.
