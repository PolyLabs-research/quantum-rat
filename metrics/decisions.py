"""The decision log: one record per tick of what the agent decided and why (docs/decisions.md G40).

A record is a readout built from what the engine already computed for the tick
(``EngineContext``: the channel scores, the gated value signals, the observation,
the modulators) plus the derived views the console shows: the score's named
terms (``brain.systems.basal_ganglia.channel_terms``), the selection
probabilities at the profile's temperature, and **counterfactual** probabilities
with one term family removed from every score (``probs_without``): the same
softmax arithmetic with no draw, so the run is untouched. ``influence[t]`` is
the total variation distance between the actual probabilities and the ones
without term ``t``: memory's (vision's, wall avoidance's) immediate pull on
this tick's selection, 0 when it changed nothing and 1 when it decided it.

Positions are the body's (``x``, ``y``, ``heading``) and the estimate's
(``est_*``, in the path-integration frame, whose origin is where the agent
started). ``episode`` counts the engine's episode boundaries (``begin_episode``:
a reset or a scenario's teleport) and ``value_episode`` the learners'
(``reset_value_episode``), so a trajectory can be cut where the body was moved.
``target_visible`` is whether any vision ray reports a target this tick;
``target_contact`` the primary contact reward.

Nothing in the engine reads a record. The live console keeps them and writes
``decisions.jsonl`` into a recording; the headless runner writes the same file
with ``--log-decisions``; ``analysis.orbits`` reads it. The schema is this
module's ``RECORD_KEYS``; a test pins it, so a change here is a visible one.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from brain.systems.basal_ganglia import channel_terms, selection_probabilities
from metrics.logger import _canonical_json

DECISIONS_FILE = "decisions.jsonl"
COUNTERFACTUAL_TERMS: Tuple[str, ...] = ("memory", "vision", "wall")
RECORD_KEYS: Tuple[str, ...] = (
    "tick", "episode", "value_episode", "x", "y", "heading", "est_x", "est_y", "est_heading",
    "action", "thrust", "turn", "scores", "terms", "probs", "probs_without", "influence", "temperature", "source",
    "target_visible", "target_dist", "target_contact", "reward", "map_reward",
    "cue_gate", "wall_gate", "pacing", "microsleep", "replay", "goal_vector",
)


def _r(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def counterfactual_probabilities(
    scores: Mapping[str, float],
    terms: Mapping[str, Mapping[str, float]],
    temperature: float,
    remove: Sequence[str],
) -> Dict[str, float]:
    """The selection probabilities with the named term families subtracted from every channel's score.

    No draw is made and nothing is changed: it answers "what would the selection have
    looked like without this contribution, this tick", which is what a large
    contribution alone does not establish.
    """
    without = {
        channel: score - sum(terms.get(channel, {}).get(name, 0.0) for name in remove)
        for channel, score in scores.items()
    }
    return selection_probabilities(without, temperature)


def total_variation(p: Mapping[str, float], q: Mapping[str, float]) -> float:
    """Total variation distance between two distributions over the channels: 0.5 Σ |p - q|, in [0, 1]."""
    keys = set(p) | set(q)
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)


def decision_record(engine: Any) -> Dict[str, Any]:
    """This tick's record, read from the engine after ``engine.run(1)`` (before a scenario acts on the tick)."""
    ctx = engine.context
    obs = ctx.observation
    bg = engine.config.basal_ganglia
    scores: Dict[str, float] = dict(ctx.action_scores)
    terms: Dict[str, Dict[str, float]] = {}
    if obs is not None and scores:
        pacing_rest = bg.pace_rest_bonus if ctx.pacing_active else 0.0
        terms = channel_terms(obs, ctx.wm_novelty, ctx.trn_gate_value, ctx.microsleep_active, bg, ctx.neuromodulators,
                              *ctx.value_signals, ctx.criticality_gain, ctx.freeze_habituation, pacing_rest,
                         ctx.previous_action)
    probs = selection_probabilities(scores, bg.softmax_temperature) if scores else {}
    without = {name: counterfactual_probabilities(scores, terms, bg.softmax_temperature, (name,)) if scores else {}
               for name in COUNTERFACTUAL_TERMS}
    influence = {name: _r(total_variation(probs, without[name])) for name in COUNTERFACTUAL_TERMS}
    target_rays = [ray for ray in (obs.vision_rays if obs is not None else ()) if ray.obj_type == "target"]
    vision_range = engine.config.sensors.vision_range
    x, y = engine.agent.pos
    sp = engine.spatial.state
    return {
        "tick": int(ctx.tick),
        "episode": int(engine.episode),
        "value_episode": int(engine.value_episode),
        "x": _r(x, 3),
        "y": _r(y, 3),
        "heading": _r(engine.agent.heading),
        "est_x": _r(sp.grid_x, 3),
        "est_y": _r(sp.grid_y, 3),
        "est_heading": _r(sp.hd_angle),
        "action": ctx.action_name,
        "thrust": _r(ctx.action_thrust),
        "turn": _r(ctx.action_turn),
        "scores": {k: _r(v) for k, v in scores.items()},
        "terms": {ch: {k: _r(v) for k, v in t.items()} for ch, t in terms.items()},
        "probs": {k: _r(v) for k, v in probs.items()},
        "probs_without": {name: {k: _r(v) for k, v in p.items()} for name, p in without.items()},
        "influence": influence,
        "temperature": _r(bg.softmax_temperature),
        "source": engine.config.value_memory.source,
        "target_visible": bool(target_rays),
        "target_dist": _r(min(ray.dist for ray in target_rays) * vision_range, 3) if target_rays else None,
        "target_contact": bool(ctx.target_contact),
        "reward": _r(ctx.reward),
        "map_reward": _r(ctx.map_reward),
        "cue_gate": _r(ctx.cue_gate),
        "wall_gate": _r(ctx.wall_gate),
        "pacing": bool(ctx.pacing_active),
        "microsleep": bool(ctx.microsleep_active),
        "replay": bool(ctx.replay_active),
        "goal_vector": bool(ctx.goal_vector_active),
    }


def record_line(record: Mapping[str, Any]) -> str:
    """One canonical JSON line (sorted keys, compact separators, as the tick log is written)."""
    return _canonical_json(dict(record))


class DecisionLogWriter:
    """Writes ``decisions.jsonl`` beside ``ticks.jsonl``; opened on the first record, so a run that logs nothing
    leaves no file. A file left by an earlier run of the same directory is removed when the writer is made."""

    def __init__(self, outdir: Path) -> None:
        self.path = Path(outdir) / DECISIONS_FILE
        self.path.unlink(missing_ok=True)
        self.count = 0
        self._fh: Optional[IO[str]] = None

    def write(self, record: Mapping[str, Any]) -> None:
        if self._fh is None:
            self._fh = open(self.path, "w", encoding="utf-8")
        self._fh.write(record_line(record) + "\n")
        self.count += 1

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


def read_decisions(path: Path) -> list:
    """The records of a ``decisions.jsonl`` (or of a run directory holding one), in file order."""
    import json

    p = Path(path)
    if p.is_dir():
        p = p / DECISIONS_FILE
    with open(p, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_decisions(path: Path, records: Iterable[Mapping[str, Any]]) -> int:
    """Write records to ``path``; returns how many."""
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(record_line(record) + "\n")
            n += 1
    return n


__all__ = ["COUNTERFACTUAL_TERMS", "DECISIONS_FILE", "RECORD_KEYS", "DecisionLogWriter", "counterfactual_probabilities",
           "decision_record", "read_decisions", "record_line", "total_variation", "write_decisions"]
