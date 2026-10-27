"""Orbit summaries from a decision log (docs/decisions.md G40): measure the circling before changing a rule.

Reads ``decisions.jsonl`` (``metrics.decisions``) and cuts the trajectory into
loops, orbits and bouts, each with what the decision terms say drove it:

- **Loop**: the shortest run of ticks over which the body's accumulated signed
  heading change reaches one full turn (|Σ Δheading| ≥ 2π), scanning forward
  from where the previous loop ended. Δheading is wrapped to (−π, π] and the
  accumulation restarts at an episode boundary (a teleport is not a turn) and
  whenever the sign of the running sum flips (a meander is not a loop).
  ``closure`` = net displacement over distance walked, 0 for a closed curve.
- **Orbit**: a loop whose closure is at most ``closure_max`` (0.25 by default:
  it ends within a quarter of the way it walked from where it started).
- **Bout**: consecutive orbits in the same direction, chained end to start.
  Duration, loops, mean radius (distance / 2π per loop), target contacts and
  reward during the bout, the share of ticks with a target in view, and the
  **attribution**: over the bout's ticks whose action is the turn in the
  bout's direction, the mean of each term's contribution to that turn channel
  (memory, wall, vision, bias, novelty); the largest is the dominant term.
  ``memory_influence`` is the mean total-variation shift of the selection
  without the memory term (the counterfactual in every record), and
  ``turn_prob`` / ``turn_prob_without_memory`` the mean probability of that
  turn with and without it.
- **Category** of a bout, in this order: ``productive`` (a target was touched
  during it: circling regrowing food collects), ``memory`` (the dominant turn
  term is memory and its mean influence is at least ``influence_min``, 0.05:
  persistence at a valued place), ``wall`` (the dominant term is wall
  avoidance), else ``other`` (bias or vision). These are what the three
  interventions the review named would act on.

A turn also moves the body ``TURN_THRUST`` (0.3) units while it rotates
``TURN_STEP`` (0.3) rad, so a sustained turn has radius 0.3 / (2 sin 0.15) ≈
1.00 unit and takes 21 ticks per revolution; a bout's mean radius above that
says the loop had FORWARD steps in it.

Command line::

    python -m analysis.orbits runs/<run_dir>            # or a decisions.jsonl path
    python -m analysis.orbits runs/<run_dir> --json     # the summary as JSON
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from metrics.decisions import read_decisions

TWO_PI = 2.0 * math.pi
TURN_RADIUS = 0.3 / (2.0 * math.sin(0.15))  # the sustained-turn radius, in units
DEFAULT_CLOSURE_MAX = 0.25
DEFAULT_INFLUENCE_MIN = 0.05
ATTRIBUTED_TERMS = ("memory", "wall", "vision", "bias", "novelty")
CATEGORIES = ("productive", "memory", "wall", "other")


def wrap_angle(a: float) -> float:
    return (a + math.pi) % TWO_PI - math.pi


def _steps(records: Sequence[Mapping[str, Any]]):
    """(index, dheading, step_length, boundary) per record after the first; boundary marks an episode change."""
    out = []
    for i in range(1, len(records)):
        a, b = records[i - 1], records[i]
        boundary = b.get("episode") != a.get("episode")
        dh = 0.0 if boundary else wrap_angle(b["heading"] - a["heading"])
        step = 0.0 if boundary else math.hypot(b["x"] - a["x"], b["y"] - a["y"])
        out.append((i, dh, step, boundary))
    return out


def loops(records: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """The loops of a trajectory (see the module docstring), each with start/end indices, direction and closure.

    The running signed turning restarts at an episode boundary and whenever it crosses zero (the turning so far
    cancelled out: a meander). A single opposite turn inside a loop does not break it; only a net reversal does.
    """
    found: List[Dict[str, Any]] = []
    start = 0
    total = 0.0
    dist = 0.0
    for i, dh, step, boundary in _steps(records):
        if boundary:
            start, total, dist = i, 0.0, 0.0
            continue
        if total == 0.0:
            if dh == 0.0:
                continue  # straight so far: no loop in progress
            start, total, dist = i - 1, dh, step
        else:
            new_total = total + dh
            if new_total == 0.0:
                start, total, dist = i, 0.0, 0.0
                continue
            if (new_total > 0) != (total > 0):
                start, total, dist = i - 1, dh, step  # crossed zero: start over from this tick
            else:
                total, dist = new_total, dist + step
        if abs(total) >= TWO_PI:
            a, b = records[start], records[i]
            net = math.hypot(b["x"] - a["x"], b["y"] - a["y"])
            found.append({
                "start": start, "end": i, "ticks": i - start, "direction": 1 if total > 0 else -1,
                "distance": dist, "net": net, "closure": (net / dist) if dist > 0 else 0.0,
                "episode": records[i].get("episode"),
            })
            start, total, dist = i, 0.0, 0.0  # the next loop starts where this one ended
    return found


def _turn_channel(direction: int) -> str:
    return "TURN_LEFT" if direction > 0 else "TURN_RIGHT"


def _attribute(records: Sequence[Mapping[str, Any]], start: int, end: int, direction: int) -> Dict[str, Any]:
    channel = _turn_channel(direction)
    sums = {name: 0.0 for name in ATTRIBUTED_TERMS}
    n_turn = 0
    influence = 0.0
    p_turn = 0.0
    p_turn_without = 0.0
    n = 0
    for rec in records[start + 1:end + 1]:
        n += 1
        influence += rec.get("influence", {}).get("memory", 0.0)
        p_turn += rec.get("probs", {}).get(channel, 0.0)
        p_turn_without += rec.get("probs_without", {}).get("memory", {}).get(channel, 0.0)
        if rec.get("action") == channel:
            n_turn += 1
            t = rec.get("terms", {}).get(channel, {})
            for name in ATTRIBUTED_TERMS:
                sums[name] += t.get(name, 0.0)
    means = {name: (sums[name] / n_turn if n_turn else 0.0) for name in ATTRIBUTED_TERMS}
    dominant = max(means, key=lambda k: means[k]) if n_turn and max(means.values()) > 0 else None
    return {
        "turn_channel": channel, "turn_ticks": n_turn, "mean_terms": means, "dominant": dominant,
        "memory_influence": influence / n if n else 0.0,
        "turn_prob": p_turn / n if n else 0.0, "turn_prob_without_memory": p_turn_without / n if n else 0.0,
    }


def bouts(
    records: Sequence[Mapping[str, Any]],
    closure_max: float = DEFAULT_CLOSURE_MAX,
    influence_min: float = DEFAULT_INFLUENCE_MIN,
) -> List[Dict[str, Any]]:
    """Bouts of consecutive same-direction orbits, with their attribution and category."""
    out: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for lp in loops(records):
        orbit = lp["closure"] <= closure_max
        if not orbit:
            if current is not None:
                out.append(current)
                current = None
            continue
        if current is not None and current["direction"] == lp["direction"] and current["end"] == lp["start"]:
            current["end"] = lp["end"]
            current["loops"] += 1
            current["distance"] += lp["distance"]
        else:
            if current is not None:
                out.append(current)
            current = {"start": lp["start"], "end": lp["end"], "direction": lp["direction"], "loops": 1,
                       "distance": lp["distance"], "episode": lp["episode"]}
    if current is not None:
        out.append(current)
    for b in out:
        a, z = records[b["start"]], records[b["end"]]
        span = records[b["start"] + 1:b["end"] + 1]
        b["ticks"] = b["end"] - b["start"]
        b["tick_start"], b["tick_end"] = a.get("tick"), z.get("tick")
        b["net"] = math.hypot(z["x"] - a["x"], z["y"] - a["y"])
        b["closure"] = (b["net"] / b["distance"]) if b["distance"] > 0 else 0.0
        b["mean_radius"] = b["distance"] / (TWO_PI * b["loops"])
        b["contacts"] = sum(1 for r in span if r.get("target_contact"))
        b["reward"] = sum(r.get("reward", 0.0) for r in span)
        b["target_visible_fraction"] = (sum(1 for r in span if r.get("target_visible")) / len(span)) if span else 0.0
        b["centre"] = (sum(r["x"] for r in span) / len(span), sum(r["y"] for r in span) / len(span)) if span else (a["x"], a["y"])
        b.update(_attribute(records, b["start"], b["end"], b["direction"]))
        if b["contacts"] > 0:
            b["category"] = "productive"
        elif b["dominant"] == "memory" and b["memory_influence"] >= influence_min:
            b["category"] = "memory"
        elif b["dominant"] == "wall":
            b["category"] = "wall"
        else:
            b["category"] = "other"
    return out


def summarise(
    records: Sequence[Mapping[str, Any]],
    closure_max: float = DEFAULT_CLOSURE_MAX,
    influence_min: float = DEFAULT_INFLUENCE_MIN,
) -> Dict[str, Any]:
    """The whole-log summary: distance, turning, loops, orbits, bouts by category and the mean memory influence."""
    steps = _steps(records)
    distance = sum(step for _, _, step, _ in steps)
    turning = sum(dh for _, dh, _, _ in steps)
    turning_abs = sum(abs(dh) for _, dh, _, _ in steps)
    lps = loops(records)
    bts = bouts(records, closure_max, influence_min)
    orbit_ticks = sum(b["ticks"] for b in bts)
    by_cat = {c: {"bouts": 0, "ticks": 0, "loops": 0, "contacts": 0} for c in CATEGORIES}
    for b in bts:
        c = by_cat[b["category"]]
        c["bouts"] += 1
        c["ticks"] += b["ticks"]
        c["loops"] += b["loops"]
        c["contacts"] += b["contacts"]
    n = len(records)
    mem = [r.get("influence", {}).get("memory", 0.0) for r in records]
    contacts = sum(1 for r in records if r.get("target_contact"))
    return {
        "ticks": n,
        "distance": distance,
        "net_displacement": math.hypot(records[-1]["x"] - records[0]["x"], records[-1]["y"] - records[0]["y"]) if n else 0.0,
        "turning_revolutions": turning / TWO_PI,
        "turning_abs_revolutions": turning_abs / TWO_PI,
        "loops": len(lps),
        "orbits": sum(1 for lp in lps if lp["closure"] <= closure_max),
        "bouts": bts,
        "orbit_ticks": orbit_ticks,
        "orbit_fraction": (orbit_ticks / n) if n else 0.0,
        "by_category": by_cat,
        "contacts": contacts,
        "distance_per_contact": (distance / contacts) if contacts else None,
        "mean_memory_influence": (sum(mem) / n) if n else 0.0,
        "closure_max": closure_max,
        "influence_min": influence_min,
    }


def format_summary(summary: Mapping[str, Any], max_bouts: int = 20) -> str:
    lines = [
        f"ticks {summary['ticks']}, distance {summary['distance']:.1f}, net {summary['net_displacement']:.1f}, "
        f"turning {summary['turning_revolutions']:+.1f} rev (|{summary['turning_abs_revolutions']:.1f}|), "
        f"loops {summary['loops']}, orbits {summary['orbits']}, in orbit {100 * summary['orbit_fraction']:.0f}% of ticks, "
        f"contacts {summary['contacts']}, mean memory influence {summary['mean_memory_influence']:.3f}",
        "by category: " + ", ".join(f"{c}: {v['bouts']} bouts / {v['ticks']} ticks / {v['contacts']} contacts" for c, v in summary["by_category"].items()),
    ]
    if summary["bouts"]:
        lines.append(f"{'start':>7} {'ticks':>6} {'loops':>5} dir {'radius':>6} {'closure':>7} {'contacts':>8} {'dominant':>8} {'mem.infl':>8} {'P(turn)':>7} {'w/o mem':>7} category")
        for b in summary["bouts"][:max_bouts]:
            lines.append(f"{b['tick_start']:>7} {b['ticks']:>6} {b['loops']:>5} {'L' if b['direction'] > 0 else 'R':>3} {b['mean_radius']:>6.2f} {b['closure']:>7.2f} "
                         f"{b['contacts']:>8} {str(b['dominant']):>8} {b['memory_influence']:>8.3f} {b['turn_prob']:>7.2f} {b['turn_prob_without_memory']:>7.2f} {b['category']}")
        if len(summary["bouts"]) > max_bouts:
            lines.append(f"... {len(summary['bouts']) - max_bouts} more bouts")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="a run directory holding decisions.jsonl, or the file itself")
    parser.add_argument("--closure", type=float, default=DEFAULT_CLOSURE_MAX, help="orbit closure bound (default %(default)s)")
    parser.add_argument("--influence", type=float, default=DEFAULT_INFLUENCE_MIN, help="memory influence bound for the memory category (default %(default)s)")
    parser.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = parser.parse_args(argv)
    records = read_decisions(Path(args.path))
    summary = summarise(records, args.closure, args.influence)
    print(json.dumps(summary, indent=1) if args.json else format_summary(summary))
    return summary


if __name__ == "__main__":
    main()
