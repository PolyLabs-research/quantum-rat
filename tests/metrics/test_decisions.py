"""The decision log (metrics.decisions): the record, its counterfactuals, the episode counters and the writer (G40)."""

import json

from brain.systems.basal_ganglia import selection_probabilities
from core.config import EngineConfig
from core.engine import Engine
from metrics.decisions import (
    COUNTERFACTUAL_TERMS, DECISIONS_FILE, RECORD_KEYS, DecisionLogWriter, counterfactual_probabilities, decision_record,
    read_decisions, record_line, total_variation, write_decisions,
)


def test_a_record_has_the_schema_and_reads_the_engine():
    eng = Engine(seed=3, config=EngineConfig.research())
    eng.run(50, reset=True)
    rec = decision_record(eng)
    assert tuple(rec) == RECORD_KEYS
    assert rec["tick"] == 49 and rec["episode"] == 1 and rec["value_episode"] == 0
    assert rec["action"] == eng.context.action_name and set(rec["terms"]) == set(rec["scores"]) == set(eng.context.action_scores)
    assert abs(sum(rec["probs"].values()) - 1.0) < 1e-6 and set(rec["probs_without"]) == set(COUNTERFACTUAL_TERMS)
    assert all(0.0 <= v <= 1.0 for v in rec["influence"].values())
    assert rec["x"] == round(eng.agent.pos[0], 3) and rec["est_x"] == round(eng.spatial.state.grid_x, 3)
    assert rec["source"] == "sr" and rec["temperature"] == 0.1 and rec["target_visible"] is False and rec["target_dist"] is None
    line = record_line(rec)
    assert json.loads(line) == json.loads(json.dumps(rec)) and "\n" not in line


def test_counterfactuals_remove_exactly_the_named_term_and_nothing_else():
    scores = {"FORWARD": 1.0, "TURN_LEFT": 0.7, "TURN_RIGHT": 0.2, "REST": 0.0}
    terms = {"TURN_LEFT": {"memory": 0.5, "bias": 0.2}, "FORWARD": {"memory": -0.3, "bias": 1.3}}
    p = selection_probabilities(scores, 0.1)
    q = counterfactual_probabilities(scores, terms, 0.1, ("memory",))
    assert q == selection_probabilities({"FORWARD": 1.3, "TURN_LEFT": 0.2, "TURN_RIGHT": 0.2, "REST": 0.0}, 0.1)
    assert q["TURN_LEFT"] < p["TURN_LEFT"]
    assert counterfactual_probabilities(scores, terms, 0.1, ("vision",)) == p  # nothing to remove
    assert total_variation(p, p) == 0.0 and 0.0 < total_variation(p, q) <= 1.0
    assert total_variation({"A": 1.0}, {"B": 1.0}) == 1.0
    assert counterfactual_probabilities(scores, terms, 0.0, ("memory",))["FORWARD"] == 1.0  # argmax at temperature 0


def test_episode_counters_count_resets_and_teleports_and_the_learners_boundaries():
    from ui.scenarios import teleport_to_start

    eng = Engine(seed=1, config=EngineConfig.research())
    assert eng.episode == 0 and eng.value_episode == 0
    eng.run(5, reset=True)
    assert eng.episode == 1
    teleport_to_start(eng)
    assert eng.episode == 2 and eng.value_episode == 0
    eng.reset_value_episode()
    assert eng.value_episode == 1
    eng.run(1)
    rec = decision_record(eng)
    assert rec["episode"] == 2 and rec["value_episode"] == 1


def test_writer_and_reader_round_trip(tmp_path):
    eng = Engine(seed=2, config=EngineConfig.research())
    eng.run(1, reset=True)
    writer = DecisionLogWriter(tmp_path)
    assert not writer.path.exists()  # opened on the first record
    for _ in range(3):
        eng.run(1)
        writer.write(decision_record(eng))
    writer.close()
    records = read_decisions(tmp_path)
    assert [r["tick"] for r in records] == [1, 2, 3] and writer.count == 3 and set(records[0]) == set(RECORD_KEYS)
    assert write_decisions(tmp_path / "copy.jsonl", records) == 3 and read_decisions(tmp_path / "copy.jsonl") == records
    assert (tmp_path / DECISIONS_FILE).read_text().splitlines()[0] == record_line(records[0])
