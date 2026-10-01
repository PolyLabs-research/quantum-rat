from experiments.criticality_validation import assert_monotonic_trends, run_sweep


def test_reduced_criticality_sweep_monotonic():
    results = run_sweep(steps=4000)  # enough avalanches for a stable kappa
    assert_monotonic_trends(results)
