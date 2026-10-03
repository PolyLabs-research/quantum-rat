"""The two config profiles (docs/profiles.md): what each flag does, and that legacy is unchanged.

Each test is named for what it proves. The 3000-tick runs take about half a
second each. Positions, steps and estimates are compared to 1e-12 or 1e-9:
the engine's egomotion and path integration go through cos/sin and hypot, so
"equal" means equal up to floating-point rounding (measured below 1e-12).
"""

from __future__ import annotations

import math
from dataclasses import asdict, fields
from typing import Callable, List, Tuple

from brain.systems.spatial import wrap_angle
from brain.systems.trn_microsleep_replay import TRNGate
from core.config import EngineConfig, TRNConfig
from core.determinism import DEFAULT_SEED, DEFAULT_TICKS, build_current_trace, hash_trace, load_baseline
from core.engine import Engine
from core.physiology import Astrocyte
from experiments.protocols import OpenFieldProtocol
from metrics.schema import TickData
from tools.probes._common import run_engine
from tools.update_determinism_baseline import build_profile_trace

TICKS = 3000
BOUNDS = EngineConfig().world.bounds  # (10, 10): the default square box


# --- helpers ----------------------------------------------------------------


def _hard_coded_trn_state(microsleep_active: bool, atp: float, kappa: float) -> Tuple[str, float]:
    """TRNGate.trn_state as it read before the thresholds became configuration (verbatim)."""
    if microsleep_active or atp < 0.35:
        return "CLOSED", 0.0
    if atp >= 0.55 and kappa <= 1.1:
        return "OPEN", 1.0
    if 0.35 <= atp < 0.55 or kappa > 1.1:
        return "NARROW", 0.4
    return "NARROW", 0.4


def _step(a: TickData, b: TickData) -> float:
    return math.hypot(b.pos[0] - a.pos[0], b.pos[1] - a.pos[1])


def _on_bound(td: TickData) -> bool:
    """The body was clamped at (or sits exactly on) a wall of the box this tick."""
    return abs(td.pos[0]) >= BOUNDS[0] or abs(td.pos[1]) >= BOUNDS[1]


def _estimate_errors(trace: List[TickData]) -> List[float]:
    return [math.hypot(td.grid_x - td.pos[0], td.grid_y - td.pos[1]) for td in trace]


def _assert_steps_equal(trace: List[TickData], expected: Callable[[TickData, TickData], float]) -> int:
    """On every tick where the body was not clamped at a bound, the realised displacement equals
    ``expected(previous tick, this tick)``. Returns how many ticks were checked.

    ``World.step`` moves the agent ``action.thrust * energy_scale`` world units
    along its heading (``Agent.apply_motion``): there is no separate step
    length, so a FORWARD step is 1.0 unit, a TURN step 0.3 (TURN_THRUST) and
    REST 0, times the energy scale. The action logged at tick t-1 is the one
    the world applies at tick t (the pipeline runs world before brain).
    """
    checked = 0
    for t in range(1, len(trace)):
        if _on_bound(trace[t]):
            continue
        assert math.isclose(_step(trace[t - 1], trace[t]), expected(trace[t - 1], trace[t]), abs_tol=1e-12), t
        checked += 1
    return checked


def _open_field_run(config: EngineConfig, seed: int = 1337, ticks: int = TICKS):
    """experiments.protocols.OpenFieldProtocol tick by tick (as tools.probes._common.run_protocol),
    also keeping the engine's per-tick energy_scale and true heading, which TickData does not log."""
    engine = Engine(seed=seed, config=config)
    proto = OpenFieldProtocol()
    proto.setup(engine)
    rows: List[TickData] = []
    scales: List[float] = []
    headings: List[float] = []
    for i in range(ticks):
        td = engine.run(1, reset=(i == 0))[0]
        proto.on_tick(engine, td, i)
        rows.append(td)
        scales.append(engine.context.energy_scale)
        headings.append(engine.context.heading)
    return rows, scales, headings, proto


# --- (a) the gate thresholds ------------------------------------------------

ATP_GRID = (0.0, 0.1, 0.3, 0.349, 0.35, 0.351, 0.45, 0.549, 0.55, 0.551, 0.7, 1.0)
KAPPA_GRID = (0.0, 0.5, 0.9, 1.0, 1.099, 1.1, 1.101, 1.5, 2.0)


def test_trn_gate_from_config_thresholds_reproduces_the_hard_coded_table() -> None:
    gate = Engine(seed=1, config=EngineConfig()).trn_gate  # wired from TRNConfig's defaults
    assert (gate.closed_below_atp, gate.open_at_atp, gate.narrow_above_kappa, gate.narrow_gain) == (
        0.35,
        0.55,
        1.1,
        0.4,
    )
    seen = set()
    for active in (False, True):
        gate.microsleep.active = active
        for atp in ATP_GRID:
            for kappa in KAPPA_GRID:
                got = gate.trn_state(atp, kappa)
                assert got == _hard_coded_trn_state(active, atp, kappa), (active, atp, kappa)
                seen.add(got[0])
    assert seen == {"OPEN", "NARROW", "CLOSED"}


def test_trn_gate_defaults_match_trn_config() -> None:
    """TRNGate declares its own defaults for the fields TRNConfig carries; Engine always
    passes all of them, so a drift between the two would be invisible without this."""
    gate = TRNGate()
    assert {f.name: getattr(gate, f.name) for f in fields(TRNConfig)} == asdict(TRNConfig())


# --- (b) the profile diff ---------------------------------------------------

EXPECTED_RESEARCH_DIFF = [
    ("profile", "legacy", "research"),
    ("sensors.odometry_speed_noise", 0.0, 0.05),
    ("sensors.odometry_turn_noise", 0.0, 0.01),
    ("astrocyte.scales_motion", True, False),
    ("astrocyte.frozen", False, True),
    ("value_memory.dwell_extinction", 0.02, 0.0),
    ("spatial.gate_scales_egomotion", True, False),
    ("trn.narrow_above_kappa", 1.1, math.inf),
    ("trn.microsleep_enabled", True, False),
    ("basal_ganglia.dopamine_explore_gain", 0.6, 0.0),
    ("basal_ganglia.ach_precision_gain", 0.5, 0.0),
    ("basal_ganglia.ne_threat_gain", 0.5, 0.0),
    ("basal_ganglia.fiveht_patience_gain", 0.4, 0.0),
    ("basal_ganglia.softmax_temperature", 0.0, 0.1),
]


def test_research_differs_from_legacy_in_exactly_the_documented_fields() -> None:
    assert EngineConfig.legacy().diff(EngineConfig.research()) == EXPECTED_RESEARCH_DIFF
    assert EngineConfig.research().diff(EngineConfig.legacy()) == [(n, b, a) for n, a, b in EXPECTED_RESEARCH_DIFF]
    assert EngineConfig.research().diff(EngineConfig.research()) == []
    research = EngineConfig.research()
    # Set explicitly by research() but already the legacy value, so not in the diff.
    assert research.value_memory.generalization_radius == 0
    assert research.value_memory.goal_vector is False
    assert research.basal_ganglia.criticality_gain == 0.0
    assert research.profile == "research"
    assert EngineConfig.legacy().profile == EngineConfig().profile == "legacy"


def test_research_profile_changes_the_trace_at_the_gate_seed() -> None:
    assert build_profile_trace("research") != load_baseline()


# --- (c) the plan's acceptance for the research profile ---------------------


def _research_without_stochastic_elements() -> EngineConfig:
    """``EngineConfig.research()`` with its three seeded elements (M0b item 8) set to 0.

    The M0a acceptance below is a statement about the deterministic mechanics
    (the gate, the energy model, exact odometry), so it is checked with
    odometry noise and the softmax temperature at 0: with odometry noise on
    the estimate is meant to drift away from the body (the next test), and
    with the softmax on the trajectory is a different one. At 0 nothing is
    drawn from the two streams they use (tests/engine/test_seeds_as_samples.py),
    so this run is the research profile as it was at M0a.
    """
    cfg = EngineConfig.research()
    cfg.sensors.odometry_speed_noise = 0.0
    cfg.sensors.odometry_turn_noise = 0.0
    cfg.basal_ganglia.softmax_temperature = 0.0
    assert cfg.stochastic_elements() == []
    return cfg


def test_research_open_field_has_no_microsleep_full_thrust_steps_and_exact_path_integration() -> None:
    """docs/research_plan.md section 5, M0a item 2, at seed 1337 over 3000 ticks, with the
    M0b seeded elements off (see ``_research_without_stochastic_elements``)."""
    rows, scales, headings, proto = _open_field_run(_research_without_stochastic_elements())
    assert len(rows) == TICKS
    assert proto.summarize()["microsleep_count"] == 0
    assert sum(td.microsleep_active for td in rows) == 0
    assert sum(td.replay_active for td in rows) == 0
    assert all(td.trn_state == "OPEN" for td in rows)  # ATP frozen at 1.0 and the kappa branch off
    assert all(s == 1.0 for s in scales)
    assert all(td.atp == 1.0 for td in rows)
    # The realised step is the commanded thrust: 1.0 for FORWARD, 0.3 for a TURN.
    checked = _assert_steps_equal(rows, lambda prev, cur: prev.action_thrust)
    assert checked == TICKS - 1  # this run never touches a bound, so no tick was skipped
    assert {td.action_thrust for td in rows} >= {1.0, 0.3}  # both step sizes were exercised
    # Path integration equals the true position and heading on every tick: sensor
    # and odometry noise are 0, so odometry is exact, and the gate no longer scales it.
    assert max(_estimate_errors(rows)) < 1e-9
    assert max(abs(wrap_angle(td.hd_angle - h)) for td, h in zip(rows, headings)) < 1e-9
    # The legacy profile at the same seed (tools/probes/open_field_motion): 1270
    # microsleep ticks and a mean step of 0.088 of the nominal 1.0.
    legacy_rows, _, _, legacy_proto = _open_field_run(EngineConfig.legacy())
    assert legacy_proto.summarize()["microsleep_count"] == 1270
    legacy_mean = sum(_step(legacy_rows[t - 1], legacy_rows[t]) for t in range(1, TICKS)) / (TICKS - 1)
    research_mean = sum(_step(rows[t - 1], rows[t]) for t in range(1, TICKS)) / (TICKS - 1)
    assert legacy_mean < 0.1 < 0.7 < research_mean


def test_research_defaults_keep_the_energy_acceptance_and_let_the_estimate_drift() -> None:
    """The research profile as shipped (odometry noise 0.05 / 0.01 rad, softmax 0.1; M0b
    item 8) at seed 1337 over 3000 open-field ticks: the energy acceptance holds on
    every tick as above, and the path-integration estimate now drifts away from the
    body by more than 0.5 units within the run. Measured: the error first exceeds 0.5
    at tick 37, is 9.2 units at the end and 11.6 at most, with the body clamped at a
    wall on 753 ticks (the softmax wanders it to the walls; the deterministic run
    above never touches one). The sigmas are placeholders to be characterised in
    milestone 1, so only the direction of the drift is asserted."""
    rows, scales, headings, proto = _open_field_run(EngineConfig.research())
    assert proto.summarize()["microsleep_count"] == 0
    assert sum(td.replay_active for td in rows) == 0
    assert all(td.trn_state == "OPEN" for td in rows)
    assert all(s == 1.0 for s in scales)
    assert all(td.atp == 1.0 for td in rows)
    assert _assert_steps_equal(rows, lambda prev, cur: prev.action_thrust) > 0.5 * TICKS
    errors = _estimate_errors(rows)
    assert max(errors) > 0.5
    assert max(abs(wrap_angle(td.hd_angle - h)) for td, h in zip(rows, headings)) > 0.1


# --- (d) the gate flag on its own -------------------------------------------


def test_gate_scales_egomotion_off_alone_removes_the_path_integration_capture() -> None:
    """tools/probes/path_integration_capture's measurement (seed 1, 3000 ticks, barren
    default world, pacing off) with only ``spatial.gate_scales_egomotion`` changed."""

    def measure(flag: bool):
        cfg = EngineConfig()
        cfg.spatial.gate_scales_egomotion = flag
        trace, _ = run_engine(1, TICKS, cfg)
        return trace, _estimate_errors(trace)

    on_trace, on_err = measure(True)
    off_trace, off_err = measure(False)
    # Flag on (legacy, the probe's recorded numbers): the gate was not OPEN on
    # 2941 of 3000 ticks and the estimate ends 22.8209 units from the body.
    assert sum(td.trn_state != "OPEN" for td in on_trace) == 2941
    assert math.isclose(on_err[-1], 22.8209, abs_tol=5e-4)
    # Flag off: the gate is just as closed, but the estimate tracks the body
    # exactly until the body is first clamped at a wall of the box (tick 276).
    # Each clamp offsets the estimate once (the egomotion is the displacement
    # projected on the heading, and the clamp is not in it) and between clamps
    # the error does not move, so what remains is the wall clamp, not the gate:
    # 0.47 units at the end against 22.8.
    assert sum(td.trn_state != "OPEN" for td in off_trace) > 0.9 * TICKS
    touches = {t for t, td in enumerate(off_trace) if _on_bound(td)}
    first_touch = min(touches)
    assert max(off_err[:first_touch]) < 1e-9
    for t in range(1, TICKS):
        if t not in touches:
            assert abs(off_err[t] - off_err[t - 1]) < 1e-9, t
    assert off_err[-1] < 1.0


# --- (e) the energy flags on their own --------------------------------------


def test_frozen_alone_holds_atp_at_one_and_never_sleeps() -> None:
    cfg = EngineConfig()
    cfg.astrocyte.frozen = True
    trace, _ = run_engine(1337, TICKS, cfg)
    assert {td.atp for td in trace} == {1.0}
    assert {td.glycogen for td in trace} == {3.0}
    assert sum(td.microsleep_active for td in trace) == 0
    assert all(td.trn_state == "OPEN" for td in trace)  # kappa never exceeded 1.1 in this run
    # scales_motion is still on, but the throttle it scales by is 1.0.
    assert _assert_steps_equal(trace, lambda prev, cur: prev.action_thrust) > 0.9 * TICKS


def test_microsleep_disabled_alone_never_starts_a_bout_although_atp_crosses_the_trigger() -> None:
    cfg = EngineConfig()
    cfg.trn.microsleep_enabled = False
    trace, _ = run_engine(1337, TICKS, cfg)
    assert min(td.atp for td in trace) < cfg.trn.trigger_atp
    assert sum(td.microsleep_active for td in trace) == 0
    assert sum(td.replay_active for td in trace) == 0
    assert any(td.trn_state == "CLOSED" for td in trace)  # the gate still closes on low ATP


def test_scales_motion_off_alone_keeps_the_astrocyte_rule_but_unties_the_step_from_atp() -> None:
    runs = {}
    for flag in (True, False):
        cfg = EngineConfig()
        cfg.astrocyte.scales_motion = flag
        runs[flag], _ = run_engine(1337, TICKS, cfg)
    on, off = runs[True], runs[False]
    # The astrocyte rule is unchanged either way: replaying the commanded thrusts
    # through a bare Astrocyte with the engine's demand rule reproduces the
    # logged ATP and glycogen exactly.
    a = EngineConfig().astrocyte
    for trace in (on, off):
        astro = Astrocyte()
        prev_thrust = 0.0  # begin_episode starts from REST
        for td in trace:
            astro.tick(demand=a.rest_demand + a.motion_demand * min(1.0, abs(prev_thrust)))
            assert (td.atp, td.glycogen) == (astro.atp, astro.glycogen), td.tick
            prev_thrust = td.action_thrust
    # ATP still falls and microsleep still happens with scales_motion off.
    assert min(td.atp for td in off) < 0.3
    assert sum(td.microsleep_active for td in off) > 0
    # The two runs share their ATP series exactly for as long as they share
    # their commanded actions. The body's different trajectory changes what it
    # sees, so the actions part (tick 5 at this seed) and ATP parts one tick
    # later (demand is charged for the previous tick's action), not because the
    # astrocyte changed.
    first_action_diff = next(t for t in range(TICKS) if on[t].action_name != off[t].action_name)
    first_atp_diff = next(t for t in range(TICKS) if on[t].atp != off[t].atp)
    assert first_atp_diff == first_action_diff + 1
    assert all(on[t].atp == off[t].atp for t in range(first_atp_diff))
    # Positions differ from the first moving tick on, because the step tracks
    # thrust * ATP with the flag on and the thrust alone with it off.
    assert on[1].pos != off[1].pos
    assert _assert_steps_equal(on, lambda prev, cur: prev.action_thrust * cur.atp) > 0.9 * TICKS
    assert _assert_steps_equal(off, lambda prev, cur: prev.action_thrust) > 0.9 * TICKS


# --- (f) legacy is unchanged ------------------------------------------------


def test_legacy_profile_is_unchanged_and_matches_the_committed_baseline() -> None:
    assert EngineConfig().diff(EngineConfig.legacy()) == []
    baseline = load_baseline()  # tests/determinism/baseline_hashes.json: seed 1337, 200 ticks
    assert build_current_trace() == baseline  # the gate's own path (no config at all)
    assert build_profile_trace("legacy") == baseline  # EngineConfig.legacy() through the tool
    trace = Engine(seed=DEFAULT_SEED, config=EngineConfig.legacy()).run(DEFAULT_TICKS)
    assert hash_trace(trace) == baseline  # the labelled config, hashed with the gate's RunHash
