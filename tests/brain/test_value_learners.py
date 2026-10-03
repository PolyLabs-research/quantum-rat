"""The value learners are proven on the 12-cell chain (docs/research_plan.md section 4, M1).

Chain: 12 cells along x at bin 0.5, start at cell 0, one cell per transition,
reward 1.0 on arriving at cell 11, which is terminal. The exact value of cell
i (0 ... 10) is gamma^d with d = 10 - i, and the goal bootstraps as 0. Every
run here uses lr 0.2 and gamma 0.9 (the probe's settings,
tools/probes/kernel_value_inflation.py), forward episodes, and stops at the
first pass whose largest change in V is below ``TOL`` or at the ``CAP``.

The chain table (``chain_table``) is computed once per module and read by the
tests that quote it; ``QUANTUM_RAT_WRITE_VALUE_TABLE=1`` rewrites the committed
copy in docs/data/m1/value_learners_chain.csv, which docs/value_learners.md
quotes. Whole module: about 10 s, most of it the four wide-width rows.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Dict, List

import pytest

from brain.systems.value_learners import (
    CHAIN_CELLS,
    ChainResult,
    GaussianPlaceFeatures,
    LinearTDLambda,
    TabularTD0,
    ValueFunction,
    chain_features,
    chain_positions,
    chain_targets,
    run_chain,
)
from brain.systems.value_memory import ValueMemory

LR = 0.2
GAMMA = 0.9
BOUND = 1.0 / (1.0 - GAMMA)  # the largest discounted return a reward of 1.0 can give
TOL = 1e-9  # per-pass change in V below which a run counts as converged
CAP = 2000  # passes; the wide widths do not converge within it (docs/value_learners.md)
FLOOR = 1e-7  # errors below this are at the convergence floor set by TOL and carry no ordering
WIDTHS = (0.125, 0.25, 0.5, 1.0, 2.0)  # in cells
NARROW = (0.125, 0.25, 0.5)
LAMBDAS = (0.0, 0.5, 0.9)
TRACES = ("replacing", "accumulating")
TABLE_CSV = Path(__file__).resolve().parents[2] / "docs" / "data" / "m1" / "value_learners_chain.csv"
TABLE_COLUMNS = (
    "learner",
    "width_cells",
    "lam",
    "traces",
    "passes",
    "converged",
    "max_abs_error",
    "max_value",
    "goal_value",
    "max_weight",
)


def _row(learner: str, width: float, lam: float, traces: str, result: ChainResult, max_weight: float) -> Dict[str, object]:
    return {
        "learner": learner,
        "width_cells": width,
        "lam": lam,
        "traces": traces,
        "passes": result.passes,
        "converged": result.converged,
        "max_abs_error": result.max_error,
        "max_value": result.max_value,
        "goal_value": result.goal_value,
        "max_weight": max_weight,
    }


def _format(rows: List[Dict[str, object]]) -> str:
    head = "learner width lam traces passes converged max|V-gamma^d| maxV V(goal) max_w"
    lines = [head]
    for r in rows:
        lines.append(
            f"{r['learner']} {r['width_cells']} {r['lam']} {r['traces']} {r['passes']} {r['converged']} "
            f"{r['max_abs_error']:.3e} {r['max_value']:.6f} {r['goal_value']:.4f} {r['max_weight']:.4f}"
        )
    return "\n".join(lines)


@pytest.fixture(scope="module")
def chain_table() -> List[Dict[str, object]]:
    """One row per (learner, width, lambda, traces): the tabular rule, then the
    linear rule at every width for lambda 0 and 0.9 with both trace kinds, plus
    lambda 0.5 at the narrow widths (the acceptance's lambda set)."""
    rows: List[Dict[str, object]] = []
    tab = TabularTD0(bin_size=0.5, learning_rate=LR, discount=GAMMA)
    result = run_chain(tab, CAP, tol=TOL)
    rows.append(_row("tabular_td0", 0.0, 0.0, "none", result, max(tab.values.values())))
    for width in WIDTHS:
        for lam in LAMBDAS:
            if lam == 0.5 and width not in NARROW:
                continue
            for traces in TRACES:
                lin = LinearTDLambda(chain_features(width), LR, GAMMA, lam, traces)
                result = run_chain(lin, CAP, tol=TOL)
                rows.append(_row("linear_td_lambda", width, lam, traces, result, float(lin.weights.max())))
    if os.environ.get("QUANTUM_RAT_WRITE_VALUE_TABLE") == "1":
        TABLE_CSV.parent.mkdir(parents=True, exist_ok=True)
        with TABLE_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=TABLE_COLUMNS)
            writer.writeheader()
            for r in rows:
                writer.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in r.items()})
    return rows


def _rows(table: List[Dict[str, object]], **match: object) -> List[Dict[str, object]]:
    return [r for r in table if all(r[k] == v for k, v in match.items())]


def _one(table: List[Dict[str, object]], **match: object) -> Dict[str, object]:
    found = _rows(table, **match)
    assert len(found) == 1, (match, len(found))
    return found[0]


# --- the interface ----------------------------------------------------------


def test_both_learners_satisfy_the_value_function_protocol_and_value_memory_does_not_yet() -> None:
    assert isinstance(TabularTD0(), ValueFunction)
    assert isinstance(LinearTDLambda(chain_features(0.5)), ValueFunction)
    assert not isinstance(ValueMemory(), ValueFunction)  # adapted in M2b (docs/value_learners.md)


def test_parameters_are_json_serialisable_and_carry_the_discount() -> None:
    for learner in (TabularTD0(discount=GAMMA), LinearTDLambda(chain_features(0.5), discount=GAMMA, lam=0.9)):
        params = json.loads(json.dumps(learner.parameters()))
        assert params["discount"] == GAMMA
        assert "learning_rate" in params


def test_update_returns_the_td_error_and_a_terminal_bootstraps_on_zero() -> None:
    for learner in (TabularTD0(learning_rate=LR, discount=GAMMA), LinearTDLambda(chain_features(0.125), LR, GAMMA)):
        (x9, y9), (x10, y10), (x11, y11) = chain_positions()[9:12]
        assert learner.update(x10, y10, 1.0, x11, y11, True) == 1.0  # target is the reward alone
        assert learner.value(x10, y10) == pytest.approx(LR * 1.0, abs=1e-12)
        delta = learner.update(x9, y9, 0.0, x10, y10, False)
        assert delta == pytest.approx(GAMMA * LR, abs=1e-12)  # bootstraps on V(cell 10)


# --- features ---------------------------------------------------------------


def test_chain_features_sit_on_the_twelve_cell_centres_in_order() -> None:
    f = chain_features(0.5)
    assert f.size == CHAIN_CELLS
    assert f.centres() == chain_positions()
    assert f.centres()[0] == (0.25, 0.25) and f.centres()[-1] == (5.75, 0.25)


def test_normalised_features_are_a_partition_of_unity_and_bound_the_value_by_the_weights() -> None:
    f = chain_features(1.0)
    for x in (0.25, 1.1, 3.0, 5.75, 7.0):
        phi = f(x, 0.25)
        assert float(phi.sum()) == pytest.approx(1.0, abs=1e-12)
        assert float(phi.min()) >= 0.0
    lin = LinearTDLambda(f, LR, GAMMA)
    run_chain(lin, 50)
    lo, hi = float(lin.weights.min()), float(lin.weights.max())
    for x in (0.0, 0.25, 1.1, 3.0, 5.0, 5.75, 6.0):
        assert lo - 1e-12 <= lin.value(x, 0.25) <= hi + 1e-12


def test_feature_arguments_are_checked() -> None:
    with pytest.raises(ValueError):
        GaussianPlaceFeatures([], 0.5)
    with pytest.raises(ValueError):
        GaussianPlaceFeatures([(0.0, 0.0)], 0.0)
    with pytest.raises(ValueError):
        LinearTDLambda(chain_features(0.5), traces="dutch")
    with pytest.raises(ValueError):
        LinearTDLambda(chain_features(0.5), lam=1.5)


# --- (a) tabular ------------------------------------------------------------


def test_tabular_td0_converges_to_gamma_d_with_the_goal_at_zero_and_nothing_above_one(chain_table) -> None:
    row = _one(chain_table, learner="tabular_td0")
    assert row["converged"] and row["passes"] < CAP
    assert row["max_abs_error"] < 1e-2
    assert row["max_abs_error"] < FLOOR  # in fact at the convergence floor
    assert row["goal_value"] == 0.0
    assert row["max_value"] <= 1.0


def test_tabular_td0_values_are_the_probes_analytic_row() -> None:
    tab = TabularTD0(learning_rate=LR, discount=GAMMA)
    result = run_chain(tab, CAP, tol=TOL)
    assert [round(v, 4) for v in result.values] + [round(result.goal_value, 4)] == [
        0.3487, 0.3874, 0.4305, 0.4783, 0.5314, 0.5905, 0.6561, 0.729, 0.81, 0.9, 1.0, 0.0,
    ]
    assert result.monotone


def test_value_memory_at_radius_zero_matches_tabular_td0_to_1e_12_on_the_same_passes() -> None:
    vm = ValueMemory(learning_rate=LR, discount=GAMMA, generalization_radius=0)
    tab = TabularTD0(bin_size=0.5, learning_rate=LR, discount=GAMMA)
    positions = chain_positions()
    for _ in range(300):
        vm.reset_episode()
        for i in range(CHAIN_CELLS):
            vm.record((i, 0), 1.0 if i == CHAIN_CELLS - 1 else 0.0)  # online TD(0), reward on arrival
        run_chain(tab, 1)
    diffs = [abs(vm.value_of((i, 0)) - tab.value(*positions[i])) for i in range(CHAIN_CELLS)]
    assert max(diffs) <= 1e-12
    assert max(diffs) == 0.0  # the same arithmetic in the same order (docstring of TabularTD0)
    assert tab.value(*positions[0]) > 0.3  # both have propagated value to the start


def test_value_memory_at_radius_one_inflates_to_r_over_one_minus_gamma_legacy_property() -> None:
    # The legacy kernel's self-bootstrap (tools/probes/kernel_value_inflation.py):
    # pinned here as a property of the legacy profile, with a tolerance, not fixed.
    vm = ValueMemory(learning_rate=LR, discount=GAMMA, generalization_radius=1)
    for i in range(CHAIN_CELLS):
        vm.record((i, 0), 1.0 if i == CHAIN_CELLS - 1 else 0.0)
    vm.consolidate(passes=5000)
    assert abs(max(vm.values.values()) - BOUND) < 1e-2
    assert abs(vm.value_of((CHAIN_CELLS - 1, 0)) - BOUND) < 1e-2  # the goal cell itself, 10.0


# --- (b) linear, narrow widths ---------------------------------------------


@pytest.mark.parametrize("width", NARROW)
@pytest.mark.parametrize("lam", LAMBDAS)
def test_linear_td_lambda_at_width_up_to_half_a_cell_reaches_gamma_d_within_1e_2(chain_table, width, lam) -> None:
    for traces in TRACES:
        row = _one(chain_table, learner="linear_td_lambda", width_cells=width, lam=lam, traces=traces)
        assert row["converged"] and row["passes"] < CAP, row
        assert row["max_abs_error"] < 1e-2, row
        assert row["max_abs_error"] < FLOOR, row  # at the convergence floor: no visible bias


# --- (c) every width ---------------------------------------------------------


def test_every_width_stays_below_one_over_one_minus_gamma_and_v_is_monotone_in_d(chain_table) -> None:
    for width in WIDTHS:
        for traces in TRACES:
            for lam in (0.0, 0.9):
                lin = LinearTDLambda(chain_features(width), LR, GAMMA, lam, traces)
                result = run_chain(lin, 100)  # a short budget: the bound and the ordering hold before convergence too
                assert result.max_value <= BOUND + 1e-9, (width, lam, traces)
                assert result.monotone, (width, lam, traces, result.values)
    for row in chain_table:
        assert row["max_value"] <= BOUND + 1e-9, row
        assert row["max_weight"] <= BOUND + 1e-9, row  # V <= max w (partition of unity), and max w stays small


def test_max_error_falls_as_the_width_shrinks_down_to_the_convergence_floor(chain_table) -> None:
    # Strict decrease from 2.0 to 1.0 to 0.5 cells; the three narrow widths all sit
    # at the floor TOL sets (about 5e-9), where their order is not meaningful, so
    # between two floor values only "both at the floor" is asserted.
    for traces in TRACES:
        for lam in (0.0, 0.9):
            errors = [
                _one(chain_table, learner="linear_td_lambda", width_cells=w, lam=lam, traces=traces)["max_abs_error"]
                for w in sorted(WIDTHS, reverse=True)
            ]
            for wide, narrow in zip(errors, errors[1:]):
                assert narrow < wide or (wide < FLOOR and narrow < FLOOR), (traces, lam, errors)
            assert errors[0] > errors[1] > errors[2], (traces, lam, errors)  # 2.0 > 1.0 > 0.5, well above the floor
            assert all(e < FLOOR for e in errors[2:]), (traces, lam, errors)
            assert errors[0] < 1e-2, (traces, lam, errors)  # even 2.0 cells is within 1e-2 after CAP passes


def test_wide_widths_do_not_converge_within_the_cap_but_keep_improving(chain_table) -> None:
    # The residual at 1.0 and 2.0 cells is a convergence residual, not a representation
    # bias: 12 features over 11 states represent gamma^d exactly (docs/value_learners.md).
    for width in (1.0, 2.0):
        row = _one(chain_table, learner="linear_td_lambda", width_cells=width, lam=0.0, traces="replacing")
        assert not row["converged"] and row["passes"] == CAP, row
    lin = LinearTDLambda(chain_features(2.0), LR, GAMMA, 0.0, "replacing")
    at_500 = run_chain(lin, 500).max_error
    at_1000 = run_chain(lin, 500).max_error
    assert at_1000 < at_500 < 2e-2, (at_500, at_1000)


# --- (d) the table -----------------------------------------------------------


def test_chain_table_matches_the_committed_csv(chain_table) -> None:
    assert TABLE_CSV.exists(), f"missing {TABLE_CSV}; write it with QUANTUM_RAT_WRITE_VALUE_TABLE=1"
    with TABLE_CSV.open(newline="", encoding="utf-8") as f:
        committed = list(csv.DictReader(f))
    assert len(committed) == len(chain_table), _format(chain_table)
    for want, got in zip(chain_table, committed):
        for key in ("learner", "traces"):
            assert got[key] == want[key], _format(chain_table)
        for key in ("passes",):
            assert int(got[key]) == want[key], _format(chain_table)
        assert got["converged"] == str(want["converged"]), _format(chain_table)
        for key in ("width_cells", "lam", "max_abs_error", "max_value", "goal_value", "max_weight"):
            assert abs(float(got[key]) - float(want[key])) <= 1e-9, (key, _format(chain_table))


# --- (e) traces --------------------------------------------------------------


def test_replacing_and_accumulating_traces_both_converge_on_the_chain(chain_table) -> None:
    for lam in LAMBDAS:
        for traces in TRACES:
            row = _one(chain_table, learner="linear_td_lambda", width_cells=0.5, lam=lam, traces=traces)
            assert row["converged"] and row["max_abs_error"] < FLOOR, row
    # Eligibility traces propagate the reward further back per pass: fewer passes to converge.
    assert (
        _one(chain_table, learner="linear_td_lambda", width_cells=0.5, lam=0.9, traces="replacing")["passes"]
        < _one(chain_table, learner="linear_td_lambda", width_cells=0.5, lam=0.0, traces="replacing")["passes"]
    )


def test_lambda_zero_is_td_zero_for_both_trace_kinds() -> None:
    results = []
    for traces in TRACES:
        lin = LinearTDLambda(chain_features(0.5), LR, GAMMA, 0.0, traces)
        results.append(run_chain(lin, 30).values)
    assert results[0] == results[1]


def test_traces_are_cleared_at_the_episode_boundary() -> None:
    lin = LinearTDLambda(chain_features(0.5), LR, GAMMA, 0.9, "accumulating")
    run_chain(lin, 1)
    assert float(lin.trace.max()) == 0.0  # the terminal transition ended the episode
    (x0, y0), (x1, y1) = chain_positions()[:2]
    lin.update(x0, y0, 0.0, x1, y1, False)
    assert float(lin.trace.max()) > 0.0
    lin.reset_episode()
    assert float(lin.trace.max()) == 0.0


# --- (f) determinism ---------------------------------------------------------


def test_two_runs_give_identical_floats() -> None:
    def runs(make):
        return [run_chain(make(), 60, tol=TOL) for _ in range(2)]

    for make in (
        lambda: TabularTD0(learning_rate=LR, discount=GAMMA),
        lambda: LinearTDLambda(chain_features(0.5), LR, GAMMA, 0.9, "accumulating"),
        lambda: LinearTDLambda(chain_features(2.0), LR, GAMMA, 0.5, "replacing"),
    ):
        a, b = runs(make)
        assert a.values == b.values and a.goal_value == b.goal_value and a.passes == b.passes


# --- (g) unnormalised features ----------------------------------------------


def test_unnormalised_features_at_width_one_cell_neither_exceed_the_bound_nor_break_monotonicity_on_the_centres() -> None:
    # Recorded, not required: on-policy linear TD converges with or without the
    # normalisation, and the chain only reads V at the centres, where the
    # unnormalised learner converges as well (docs/value_learners.md).
    lin = LinearTDLambda(chain_features(1.0, normalise=False), LR, GAMMA, 0.0, "replacing")
    result = run_chain(lin, CAP, tol=TOL)
    assert result.max_value <= BOUND + 1e-9
    assert result.monotone
    assert result.max_error < 1e-2


def test_unnormalised_features_dip_between_the_centres_where_normalised_ones_interpolate() -> None:
    # At a quarter-cell width the features of two neighbouring cells sum to 0.27
    # halfway between them, so V there reads a quarter of its neighbours: a valley
    # between every pair of cells. The partition of unity reads between them.
    (x9, y), (x10, _) = chain_positions()[9:11]
    mid = 0.5 * (x9 + x10)
    plain = LinearTDLambda(chain_features(0.25, normalise=False), LR, GAMMA)
    unity = LinearTDLambda(chain_features(0.25, normalise=True), LR, GAMMA)
    for lin in (plain, unity):
        run_chain(lin, CAP, tol=TOL)
        assert lin.value(x9, y) == pytest.approx(0.9, abs=1e-6)
        assert lin.value(x10, y) == pytest.approx(1.0, abs=1e-6)
    assert plain.value(mid, y) < 0.3
    assert 0.9 <= unity.value(mid, y) <= 1.0
