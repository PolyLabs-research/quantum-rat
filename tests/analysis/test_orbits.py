"""Orbit summaries (analysis.orbits) on synthetic trajectories: loops, orbits, bouts, attribution and categories (G40)."""

import math

import pytest

from analysis.orbits import CATEGORIES, TURN_RADIUS, bouts, loops, summarise, wrap_angle


def _rec(i, x, y, heading, action="FORWARD", terms=None, contact=False, episode=1, influence=0.0, p=0.0, p_without=0.0):
    return {
        "tick": i, "episode": episode, "x": x, "y": y, "heading": heading, "action": action,
        "terms": {action: terms} if terms else {}, "probs": {action: p}, "probs_without": {"memory": {action: p_without}},
        "influence": {"memory": influence}, "target_contact": contact, "target_visible": False, "reward": 1.0 if contact else 0.0,
    }


def circle(n, direction=1, radius=1.0, contacts=(), episode=1, start=0, terms=None, influence=0.5):
    """A sustained turn: TURN_STEP 0.3 rad and an arc of 0.3 * radius per tick, as the body moves."""
    terms = terms or {"memory": 0.4, "wall": 0.1, "vision": 0.0, "bias": 0.0, "novelty": 0.0}
    action = "TURN_LEFT" if direction > 0 else "TURN_RIGHT"
    out, h, x, y = [], 0.0, 0.0, 0.0
    for i in range(n):
        if i:
            h += direction * 0.3
            x += radius * 0.3 * math.cos(h)
            y += radius * 0.3 * math.sin(h)
        out.append(_rec(start + i, x, y, h, action, terms, (i in contacts), episode, influence, 0.8, 0.3))
    return out


def test_a_sustained_turn_is_a_loop_every_21_ticks_and_one_bout_of_orbits():
    records = circle(100)
    found = loops(records)
    assert [lp["ticks"] for lp in found] == [21, 21, 21, 21] and all(lp["direction"] == 1 for lp in found)
    assert all(lp["closure"] < 0.1 for lp in found)
    bt = bouts(records)
    assert len(bt) == 1
    b = bt[0]
    assert b["loops"] == 4 and b["direction"] == 1 and b["ticks"] == 84 and b["turn_channel"] == "TURN_LEFT"
    assert abs(b["mean_radius"] - TURN_RADIUS) < 0.01 and abs(TURN_RADIUS - 1.0) < 0.01
    assert b["dominant"] == "memory" and b["category"] == "memory" and b["memory_influence"] == pytest.approx(0.5)
    assert b["turn_prob"] == pytest.approx(0.8) and b["turn_prob_without_memory"] == pytest.approx(0.3)
    right = bouts(circle(60, direction=-1))
    assert len(right) == 1 and right[0]["direction"] == -1 and right[0]["turn_channel"] == "TURN_RIGHT"


def test_categories_follow_contacts_then_the_dominant_turn_term():
    productive = bouts(circle(60, contacts=(30,)))
    assert productive[0]["category"] == "productive" and productive[0]["contacts"] == 1 and productive[0]["reward"] == 1.0
    wall = bouts(circle(60, terms={"memory": 0.0, "wall": 0.6, "vision": 0.0, "bias": 0.0, "novelty": 0.0}))
    assert wall[0]["dominant"] == "wall" and wall[0]["category"] == "wall"
    other = bouts(circle(60, terms={"memory": 0.0, "wall": 0.0, "vision": 0.0, "bias": 0.3, "novelty": 0.0}))
    assert other[0]["dominant"] == "bias" and other[0]["category"] == "other"
    weak = bouts(circle(60, influence=0.01))  # memory-dominant turns, but memory barely moves the selection
    assert weak[0]["dominant"] == "memory" and weak[0]["category"] == "other"


def test_a_straight_walk_a_meander_and_a_boundary_make_no_loop():
    straight = [_rec(i, float(i), 0.0, 0.0) for i in range(100)]
    assert loops(straight) == []
    meander, h = [], 0.0
    for i in range(100):
        h += 0.3 if i % 2 else -0.3
        meander.append(_rec(i, float(i), 0.0, h))
    assert loops(meander) == []
    split = circle(15) + circle(15, episode=2, start=15)  # a teleport between two half turns
    assert loops(split) == []
    assert loops(circle(15) + circle(15, start=15)) != []  # the same two halves in one episode make a loop
    nudged = circle(100)
    nudged[10]["heading"] -= 0.6  # one tick turned the other way inside the loop
    assert len(loops(nudged)) == 4


def test_an_open_curve_is_a_loop_but_not_an_orbit():
    # A spiral that drifts: the same turning, with the body carried 0.2 units sideways every tick.
    records = circle(60)
    for i, r in enumerate(records):
        r["x"] += 0.2 * i
    found = loops(records)
    assert found and all(lp["closure"] > 0.25 for lp in found)
    assert bouts(records) == [] and summarise(records)["orbits"] == 0 and summarise(records)["loops"] == len(found)


def test_summarise_counts_the_whole_log():
    turned = circle(100, contacts=(30,))
    last = turned[-1]["heading"]  # the straight stretch keeps the last heading, so it adds no turning
    records = turned + [_rec(100 + i, 10.0 + i, 0.0, last) for i in range(50)]
    s = summarise(records)
    assert s["ticks"] == 150 and s["loops"] == 4 and s["orbits"] == 4 and s["orbit_ticks"] == 84
    assert abs(s["orbit_fraction"] - 84 / 150) < 1e-9 and s["contacts"] == 1 and s["distance_per_contact"] > 0
    assert set(s["by_category"]) == set(CATEGORIES) and s["by_category"]["productive"]["bouts"] == 1
    assert abs(s["turning_revolutions"] - (99 * 0.3) / (2 * math.pi)) < 1e-9
    assert wrap_angle(3 * math.pi) == -math.pi or abs(wrap_angle(3 * math.pi) - math.pi) < 1e-12
