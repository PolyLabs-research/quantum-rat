"""Replay as an event object, and the goal-vector slot relabelled ``oracle_homing``.

``brain.systems.replay_events`` (docs/research_plan.md section 2, M1): every
microsleep replay is recorded as one ``ReplayEvent`` in ``engine.replay_log``,
with the cells it backed up in order; the headless runner and the console write
them to ``replay_events.jsonl``. The event is bookkeeping beside the backups:
the legacy trace hash is pinned by the determinism gate
(tests/determinism/test_trace_hash.py, which runs the same engine over the same
ticks as the committed baseline), and tests/engine/test_replay_recent.py and
tests/engine/test_goal_vector.py pin the backups and the goal memory exactly as
before. ``ValueMemoryConfig.goal_vector`` is now a read/write alias of the
field ``oracle_homing``.

These tests pin the legacy profile (EngineConfig() defaults) except where they
say research; see docs/decisions.md G22 and docs/profiles.md.
"""

from __future__ import annotations

import json
from dataclasses import fields
from typing import List, Optional, Tuple

import pytest

from brain.systems.replay_events import (
    DEFAULT_LOG_SIZE,
    REPLAY_EVENTS_FILE,
    OpenReplayEvent,
    ReplayEvent,
    ReplayLog,
)
from core.config import EngineConfig, ValueMemoryConfig
from core.engine import Engine
from experiments.runner import run
from ui import sim_session
from ui.sim_session import FRAME_REPLAY_EVENTS, SimSession

TICKS = 3000
EVENT_KEYS = {"tick_start", "tick_end", "trigger", "rule", "cells", "direction", "start_cell", "n_backups", "span"}

Row = Tuple[int, bool, Optional[Tuple[int, int]], int]  # (tick, replay_active, replay_cell, replay_span)


# ------------------------------------------------------------------ helpers


def _observe(engine: Engine, ticks: int) -> List[Row]:
    """Step tick by tick, reading the replay the engine reports on its context."""
    rows: List[Row] = []
    for _ in range(ticks):
        td = engine.run(1)[0]
        ctx = engine.context
        rows.append((td.tick, td.replay_active, ctx.replay_cell, ctx.replay_span))
    return rows


def _bouts(rows: List[Row]) -> List[Tuple[List[Row], bool]]:
    """Runs of consecutive replay ticks, each flagged complete unless the run ended inside it."""
    bouts: List[Tuple[List[Row], bool]] = []
    current: List[Row] = []
    for row in rows:
        if row[1]:
            current.append(row)
        elif current:
            bouts.append((current, True))
            current = []
    if current:
        bouts.append((current, False))
    return bouts


# ------------------------------------------------------------ the event log


def test_one_event_per_completed_microsleep_replay_with_the_cells_it_backed_up():
    engine = Engine(seed=1337)  # legacy defaults, barren world
    rows = _observe(engine, TICKS)
    bouts = _bouts(rows)
    completed = [bout for bout, done in bouts if done]
    # Measured at this seed: 51 bouts (1270 replay ticks), the last still in progress at tick 2999.
    assert len(bouts) == 51 and len(completed) == 50 and not bouts[-1][1]
    events = list(engine.replay_log)
    assert len(events) == len(completed) == 50
    for event, bout in zip(events, completed):
        ticks = [tick for tick, _, _, _ in bout]
        cells = [cell for _, _, cell, _ in bout]
        assert None not in cells  # the snapshot is never empty at these defaults
        assert (event.trigger, event.rule, event.direction) == ("microsleep", "reverse_trajectory", "reverse")
        assert (event.tick_start, event.tick_end) == (ticks[0], ticks[-1])
        assert event.n_backups == len(bout) == len(event.cells)
        assert list(event.cells) == cells
        assert event.start_cell == cells[0]
        assert event.span == bout[0][3] and 1 <= event.n_backups <= event.span
    assert sum(e.n_backups for e in events) == sum(len(bout) for bout in completed) == 1270 - len(bouts[-1][0])
    # The replay in progress when the run stopped is not an event yet.
    assert engine._replay_event is not None and engine._replay_event.cells


def test_legacy_indexing_emits_forward_trn_index_events_for_the_same_backups():
    config = EngineConfig()
    config.value_memory.replay_recent = False
    engine = Engine(seed=1337, config=config)
    rows = _observe(engine, 600)
    completed = [bout for bout, done in _bouts(rows) if done]
    backed = [[cell for _, _, cell, _ in bout if cell is not None] for bout in completed]
    with_backups = [(bout, cells) for bout, cells in zip(completed, backed) if cells]
    events = list(engine.replay_log)
    assert len(events) == len(with_backups) >= 2
    for event, (bout, cells) in zip(events, with_backups):
        assert (event.trigger, event.rule, event.direction) == ("microsleep", "trn_index", "forward")
        assert list(event.cells) == cells and event.n_backups == len(cells)
        assert (event.tick_start, event.tick_end) == (bout[0][0], bout[-1][0])
        assert 1 <= event.span <= engine.trn_gate.replay_window


@pytest.mark.parametrize("replay_recent", [True, False])
def test_a_replay_that_backs_up_nothing_is_no_event(replay_recent):
    # An episode boundary before every tick (as in test_replay_recent): no
    # transition lies inside an episode, so replay backs up nothing under
    # either rule and the log stays empty although microsleep happened.
    config = EngineConfig()
    config.value_memory.replay_recent = replay_recent
    engine = Engine(seed=1337, config=config)
    replay_ticks = 0
    for _ in range(600):
        engine.value_memory.reset_episode()
        replay_ticks += engine.run(1)[0].replay_active
    assert replay_ticks > 0
    assert len(engine.replay_log) == 0


def test_a_reset_during_microsleep_closes_the_event_early():
    # The scenario of test_a_teleport_during_microsleep_ends_the_replay_of_the_previous_episode:
    # three backups into a sleep, the agent is teleported (begin_episode). The
    # event closes with those three, the rest of the sleep adds none, and the
    # next sleep opens a new one.
    from ui.scenarios import make_scenario, teleport_to_start

    scenario = make_scenario("open_field")
    config = scenario.config()
    config.sensors.noise = 0.03
    engine = Engine(seed=1, config=config)
    scenario.setup(engine)
    bout: List[Tuple[int, int]] = []
    for _ in range(2000):
        engine.run(1)
        ctx = engine.context
        if not ctx.replay_active:
            bout = []
            continue
        bout.append(ctx.replay_cell)
        if ctx.replay_back >= 3:
            break
    ctx = engine.context
    assert ctx.replay_active and ctx.replay_back == 3 and ctx.replay_span > 3
    n_before = len(engine.replay_log)
    cut_tick = ctx.tick
    teleport_to_start(engine)
    assert len(engine.replay_log) == n_before + 1
    event = engine.replay_log.latest(1)[0]
    assert (event.tick_start, event.tick_end) == (cut_tick - 2, cut_tick)
    assert event.n_backups == 3 and list(event.cells) == bout and event.span == ctx.replay_span
    asleep = 0
    while True:
        engine.run(1)
        if not engine.context.replay_active:
            break
        asleep += 1
        assert engine.context.replay_cell is None
    assert asleep >= 3  # the teleport did not end the sleep itself
    assert len(engine.replay_log) == n_before + 1  # and the rest of it was no event
    for _ in range(2000):
        engine.run(1)
        if engine.context.replay_cell is not None:
            break
    assert engine.context.replay_back == 1
    while engine.context.replay_active:
        engine.run(1)
    assert len(engine.replay_log) == n_before + 2
    assert engine.replay_log.latest(1)[0].tick_start > cut_tick


def test_research_profile_has_no_microsleep_and_so_no_replay_events():
    engine = Engine(seed=1337, config=EngineConfig.research())
    trace = engine.run(TICKS)
    assert sum(td.replay_active for td in trace) == 0
    assert len(engine.replay_log) == 0 and engine._replay_event is None


# --------------------------------------------------------- the event objects


def test_replay_event_to_dict_is_json_with_cells_as_lists():
    event = ReplayEvent(
        tick_start=10, tick_end=12, trigger="microsleep", rule="reverse_trajectory",
        cells=((1, 2), (1, 2), (0, 2)), direction="reverse", start_cell=(1, 2), n_backups=3, span=7,
    )
    d = event.to_dict()
    assert set(d) == EVENT_KEYS
    assert d["cells"] == [[1, 2], [1, 2], [0, 2]] and d["start_cell"] == [1, 2]
    assert json.loads(json.dumps(d)) == d
    with pytest.raises(AttributeError):
        event.n_backups = 4  # frozen


def test_open_event_collects_backups_and_closes_to_nothing_without_any():
    open_event = OpenReplayEvent(5, "microsleep", "reverse_trajectory", "reverse", span=4)
    open_event.tick(6)
    assert open_event.close() is None
    open_event.backup(6, (3, 4))
    open_event.backup(7, (2, 4))
    event = open_event.close()
    assert (event.tick_start, event.tick_end, event.n_backups, event.span) == (5, 7, 2, 4)
    assert event.cells == ((3, 4), (2, 4)) and event.start_cell == (3, 4)


def test_replay_log_is_bounded_and_drains():
    def make(i: int) -> ReplayEvent:
        return ReplayEvent(i, i, "microsleep", "reverse_trajectory", ((i, 0),), "reverse", (i, 0), 1, 1)

    assert ReplayLog().maxlen == DEFAULT_LOG_SIZE == 256
    log = ReplayLog(maxlen=3)
    assert not log and log.latest(2) == [] and log.drain() == []
    for i in range(5):
        log.append(make(i))
    assert len(log) == 3 and [e.tick_start for e in log] == [2, 3, 4]  # the newest three, oldest first
    assert [e.tick_start for e in log.latest(2)] == [3, 4]
    assert [e.tick_start for e in log.latest(10)] == [2, 3, 4] and log.latest(0) == []
    assert [e.tick_start for e in log.drain()] == [2, 3, 4]
    assert len(log) == 0 and not log
    with pytest.raises(ValueError):
        ReplayLog(maxlen=0)


# ------------------------------------------------ the runner and the console


def test_runner_writes_replay_events_beside_the_run_files(tmp_path):
    run("open_field", seed=1337, ticks=600, outdir=tmp_path / "legacy")  # the first bout starts at tick 191
    out = tmp_path / "legacy"
    lines = (out / REPLAY_EVENTS_FILE).read_text().splitlines()
    summary = json.loads((out / "summary.json").read_text())
    assert summary["n_replay_events"] == len(lines) >= 2
    engine = Engine(seed=1337)  # the protocol's setup is the engine's own start pose
    engine.run(600)
    assert [json.loads(line) for line in lines] == [e.to_dict() for e in engine.replay_log]
    assert all(set(json.loads(line)) == EVENT_KEYS for line in lines)
    # Every protocol writes it, the console adapters included.
    run("console_open_field", seed=1337, ticks=600, outdir=tmp_path / "console")
    console = json.loads((tmp_path / "console" / "summary.json").read_text())
    assert console["n_replay_events"] == len((tmp_path / "console" / REPLAY_EVENTS_FILE).read_text().splitlines()) >= 2
    # No replay, no file: the research profile never sleeps.
    run("open_field", seed=1337, ticks=600, outdir=tmp_path / "research", profile="research")
    assert not (tmp_path / "research" / REPLAY_EVENTS_FILE).exists()
    assert json.loads((tmp_path / "research" / "summary.json").read_text())["n_replay_events"] == 0
    # A reused run directory does not keep the previous run's file either (the
    # default outdir is runs/<protocol>_<seed>, so a legacy run followed by a
    # research run of the same protocol and seed lands here).
    run("open_field", seed=1337, ticks=600, outdir=out, profile="research")
    assert not (out / REPLAY_EVENTS_FILE).exists()
    assert json.loads((out / "summary.json").read_text())["n_replay_events"] == 0


def test_console_frame_carries_the_latest_events_and_the_recording_writes_them(tmp_path):
    session = SimSession("open_field", seed=7)
    assert session.frame()["replay_events"] == []
    for _ in range(3):
        session.step(200)
    frame = session.frame()
    events = frame["replay_events"]
    assert 1 <= len(events) <= FRAME_REPLAY_EVENTS == 5
    assert events == list(session.replay_events)[-FRAME_REPLAY_EVENTS:]
    assert all(set(e) == EVENT_KEYS for e in events)
    assert len(session.replay_events) > len(events)  # the session keeps more than the frame shows
    assert len(session.engine.replay_log) == 0  # drained into the session every tick
    assert set(frame["replay"]) == {"active", "index", "cell", "back", "span"}  # the existing keys are untouched
    json.dumps(frame)
    run_id = session.record(tmp_path)
    lines = (tmp_path / run_id / REPLAY_EVENTS_FILE).read_text().splitlines()
    assert [json.loads(line) for line in lines] == list(session.replay_events)
    summary = json.loads((tmp_path / run_id / "summary.json").read_text())
    assert summary["n_replay_events"] == summary["n_replay_events_total"] == session.n_replay_events == len(lines)
    # The headless console protocol of the same scenario and seed logs the same events.
    run("console_open_field", seed=7, ticks=600, outdir=tmp_path / "headless")
    headless = [json.loads(line) for line in (tmp_path / "headless" / REPLAY_EVENTS_FILE).read_text().splitlines()]
    assert headless == list(session.replay_events)
    # A session that never slept records no events file.
    quiet = SimSession("foraging", seed=11)  # pacing on: no microsleep in 40 ticks
    quiet.step(40)
    quiet_id = quiet.record(tmp_path)
    assert not (tmp_path / quiet_id / REPLAY_EVENTS_FILE).exists()
    assert quiet.frame()["replay_events"] == []


def test_a_recording_past_the_history_limit_writes_only_the_events_inside_its_ticks(tmp_path, monkeypatch):
    # The tick history is capped at HISTORY_LIMIT and the event keep at
    # REPLAY_EVENT_LIMIT, which are not tied: a long live session holds events
    # whose ticks have left the history. The recording writes only the kept
    # events that end inside ticks.jsonl (and counts those as n_replay_events),
    # and keeps the whole deque for the frame. Shrunk limits stand in for the
    # 50,000-tick history: 100 ticks of history out of 600 run (about two
    # bouts), 4 of the 7 events kept (about 200 ticks of bouts).
    monkeypatch.setattr(sim_session, "HISTORY_LIMIT", 100)
    monkeypatch.setattr(sim_session, "REPLAY_EVENT_LIMIT", 4)
    session = SimSession("open_field", seed=1337)
    for _ in range(3):
        session.step(200)
    first = session.history[0]["tick"]
    assert len(session.history) == 100 and first == session.tick - 99  # the newest 100 of 600 ticks
    assert len(session.replay_events) == 4 < session.n_replay_events == 7
    inside = [e for e in session.replay_events if e["tick_end"] >= first]
    assert 1 <= len(inside) < len(session.replay_events)  # some kept events end before the history
    run_id = session.record(tmp_path)
    lines = (tmp_path / run_id / REPLAY_EVENTS_FILE).read_text().splitlines()
    assert [json.loads(line) for line in lines] == inside
    first_recorded = json.loads((tmp_path / run_id / "ticks.jsonl").read_text().splitlines()[0])["tick"]
    assert first_recorded == first and all(json.loads(line)["tick_end"] >= first for line in lines)
    summary = json.loads((tmp_path / run_id / "summary.json").read_text())
    assert summary["n_replay_events"] == len(inside) and summary["n_replay_events_total"] == session.n_replay_events
    assert session.frame()["replay_events"] == list(session.replay_events)[-FRAME_REPLAY_EVENTS:]  # the frame keeps all


# ------------------------------------------------------------ oracle_homing


def test_oracle_homing_is_the_field_and_goal_vector_its_alias():
    assert "oracle_homing" in {f.name for f in fields(ValueMemoryConfig)}
    assert "goal_vector" not in {f.name for f in fields(ValueMemoryConfig)}
    cfg = EngineConfig()
    assert cfg.value_memory.oracle_homing is False and cfg.value_memory.goal_vector is False
    cfg.value_memory.goal_vector = True
    assert cfg.value_memory.oracle_homing is True
    cfg.value_memory.oracle_homing = False
    assert cfg.value_memory.goal_vector is False
    with pytest.raises(TypeError):
        ValueMemoryConfig(goal_vector=True)  # not a dataclass field: the alias is a property
    assert ValueMemoryConfig(oracle_homing=True).goal_vector is True
    assert EngineConfig.research().value_memory.oracle_homing is False


@pytest.mark.parametrize("key", ["value_memory.goal_vector", "value_memory.oracle_homing"])
def test_dotted_override_and_the_engine_work_through_either_name(key):
    config = EngineConfig()
    config.set_field(key, True)  # the one dotted setter (the harness's --set, the console's parameters)
    assert config.value_memory.oracle_homing is True and config.get_field(key) is True
    assert config.diff(EngineConfig()) == [("value_memory.oracle_homing", True, False)]
    engine = Engine(seed=1, config=config)
    engine.value_memory.goal_cell = (-12, 2)  # as in test_goal_vector: a flat map steers by the goal
    engine.run(1)
    assert engine.context.goal_vector_active


def test_the_dotted_setter_refuses_an_unknown_field():
    config = EngineConfig()
    for key in ("value_memory.goal_vectors", "value_memories.goal_vector", "goal_vector"):
        with pytest.raises(AttributeError, match="config has no field"):
            config.set_field(key, True)
        with pytest.raises(AttributeError, match="config has no field"):
            config.get_field(key)
    assert config.diff(EngineConfig()) == [] and not hasattr(config, "goal_vector")


def test_to_dict_carries_oracle_homing_and_from_dict_accepts_both_names():
    plain = EngineConfig().to_dict()["value_memory"]
    assert "oracle_homing" in plain and "goal_vector" not in plain
    assert EngineConfig.from_dict({"value_memory": {"goal_vector": True}}).value_memory.oracle_homing is True
    assert EngineConfig.from_dict({"value_memory": {"oracle_homing": True}}).value_memory.oracle_homing is True
    both = EngineConfig.from_dict({"value_memory": {"oracle_homing": True, "goal_vector": True}})
    assert both.value_memory.oracle_homing is True
    with pytest.raises(ValueError):
        EngineConfig.from_dict({"value_memory": {"oracle_homing": True, "goal_vector": False}})
    cfg = EngineConfig()
    cfg.value_memory.goal_vector = True
    assert EngineConfig.from_dict(json.loads(json.dumps(cfg.to_dict()))).diff(cfg) == []
