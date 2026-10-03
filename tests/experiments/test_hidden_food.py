"""Hidden food: an open task where place memory pays off (ui.scenarios.HiddenFood).

Six invisible food sites regrow 150 ticks after they are eaten. Without memory
the agent finds food only when its wall-following loop happens to brush a
site; with memory the value map learns each find and steers the agent back.

The guard runs the scenario headless through the sensitivity harness at sensor
noise 0, seed 1, from four start headings (0, pi/2, pi, 3pi/2), 3000 ticks
each, and compares the summed finds with memory steering at the scenario
default (value_gain 1.5) against memory off (value_gain 0). Measured: 47 vs 12
finds (x3.92; per heading 16/5/16/10 vs 4/3/3/2, so memory wins all four
pairs). The bound is >= 2x and >= 3 of 4 pairs won.

Wider measurements (harness, 3000 ticks, gain 1.5 vs 0): x2.84 over seeds 1-8
at noise 0.03 (6.75 vs 2.38 finds, 8 wins 0 losses), x2.85 on held-out seeds
9-16 (12.12 vs 4.25, 8-0), x4.08 over 8 headings at noise 0 (12.25 vs 3.00,
8-0). See docs/decisions.md G21 for the controls.

The control (``test_the_benefit_needs_food_at_fixed_places``): every 150
ticks (the regrow time) every site jumps to a fresh random place in the same
food band, 2-3 m in from the walls, so there are no fixed places to remember.
Reshuffled sites are easier to stumble on (memory off finds 42 instead of 12),
so absolute finds are not the comparison; the benefit is. Measured on the same
four headings: 37 vs 42 finds (x0.88, 1 of 4 pairs won), so the guard above
fails, and the fixed-site benefit is 4.5 times the reshuffled one (bound 1.5).
Over the wider blocks the reshuffled benefit is x1.08 / x1.47 / x1.25 against
x2.84 / x2.85 / x4.08 with fixed sites (1.9-3.3 times). Memory still helps a
little without fixed sites, near a recent find while the food is there.
"""

from __future__ import annotations

import functools
import math
import random
from typing import Optional, Tuple

from experiments.steering_sensitivity import Job, run_job

TICKS = 3000
HEADINGS = (0.0, math.pi / 2, math.pi, 3 * math.pi / 2)
MIN_RATIO = 2.0
MIN_WINS = 3
MIN_BENEFIT_FACTOR = 1.5


@functools.lru_cache(maxsize=None)
def _scores(gain: Optional[float], overrides: Tuple[Tuple[str, float], ...] = ()) -> Tuple[int, ...]:
    return tuple(run_job(Job("hidden_food", gain, 1, 0.0, TICKS, overrides, h))["score"] for h in HEADINGS)


def _memory_beats_no_memory(with_memory: Tuple[int, ...], without: Tuple[int, ...]) -> bool:
    wins = sum(a > b for a, b in zip(with_memory, without))
    return sum(with_memory) >= MIN_RATIO * sum(without) and wins >= MIN_WINS


def test_memory_finds_far_more_hidden_food():
    without = _scores(0.0)
    with_memory = _scores(None)  # the scenario default, value_gain 1.5
    # The no-memory agent does find food by chance, so the ratio is not 0/0.
    assert sum(without) >= 4, without
    assert _memory_beats_no_memory(with_memory, without), (with_memory, without)


def _band_point(rng: random.Random) -> Tuple[float, float]:
    # uniform on the band 2.0-3.0 m in from the walls (the sites sit ~2.5 m in)
    while True:
        x, y = rng.uniform(-8.0, 8.0), rng.uniform(-8.0, 8.0)
        if 2.0 <= 10.0 - max(abs(x), abs(y)) <= 3.0:
            return x, y


@functools.lru_cache(maxsize=None)
def _reshuffled_scores(gain: float) -> Tuple[int, ...]:
    """Finds per heading when every site jumps to a random place in the band every REGROW ticks.

    The jump happens before the tick's engine step, so the engine sees a moved
    site first; the jumps are the same for every gain (their own RNG)."""
    from core.engine import Engine
    from experiments.steering_sensitivity import _apply_heading
    from ui.scenarios import HiddenFood

    scores = []
    for heading in HEADINGS:
        scenario = HiddenFood()
        config = scenario.config()
        config.sensors.noise = 0.0
        config.basal_ganglia.value_gain = gain
        engine = Engine(seed=1, config=config)
        scenario.setup(engine)
        _apply_heading(engine, heading)
        rng = random.Random(1001)
        for tick in range(TICKS):
            if tick > 0 and tick % scenario.REGROW == 0:
                for item in scenario.items:
                    item.x, item.y = _band_point(rng)
            scenario.on_tick(engine, engine.run(1)[0].tick)
        scores.append(scenario.collected)
    return tuple(scores)


def test_the_benefit_needs_food_at_fixed_places():
    fixed = _scores(None), _scores(0.0)
    reshuffled = _reshuffled_scores(1.5), _reshuffled_scores(0.0)
    assert _memory_beats_no_memory(*fixed)
    assert not _memory_beats_no_memory(*reshuffled), reshuffled  # measured 37 vs 42
    fixed_benefit = sum(fixed[0]) / sum(fixed[1])
    reshuffled_benefit = sum(reshuffled[0]) / sum(reshuffled[1])
    assert fixed_benefit >= MIN_BENEFIT_FACTOR * reshuffled_benefit, (fixed, reshuffled)  # x3.92 vs x0.88


def test_sites_are_invisible_and_regrow_in_place():
    from brain.systems.basal_ganglia import cue_gate_weight
    from core.engine import Engine
    from ui.scenarios import HiddenFood

    scenario = HiddenFood()
    engine = Engine(seed=1, config=scenario.config())
    scenario.setup(engine)
    site = scenario.items[0]
    # Facing the first site from 3 m away: the rays hit it, but not as food.
    engine.agent.pos = engine.agent.last_pos = (site.x - 3.0, site.y)
    engine.agent.heading = engine.agent.last_heading = 0.0
    engine.run(1)
    obs = engine.context.observation
    assert any(ray.obj_type == "hidden" for ray in obs.vision_rays)
    assert not any(ray.obj_type == "target" for ray in obs.vision_rays)
    assert cue_gate_weight(obs, engine.config.basal_ganglia.cue_gate_gain) == 1.0
    # Standing on it eats it; it regrows at the same place REGROW ticks later.
    engine.agent.pos = (site.x, site.y)
    scenario.on_tick(engine, 10)
    assert site.kind == "collected" and scenario.collected == 1 and scenario.site_counts[0] == 1
    scenario.on_tick(engine, 10 + scenario.REGROW - 1)
    assert site.kind == "collected" and scenario.collected == 1
    engine.agent.pos = (0.0, 0.0)
    scenario.on_tick(engine, 10 + scenario.REGROW)
    assert site.kind == "hidden" and (site.x, site.y) == scenario.SITES[0]
    assert scenario.blocks(500) == [1]


def test_a_site_that_regrows_under_the_agent_is_eaten_only_after_an_engine_step_sees_it():
    # Regrowth used to be checked before collection in the same on_tick, so a
    # site regrowing under the agent was "found" with no contact reward and no
    # map write (3 of 52 finds at gain 1.5, seeds 1-8, noise 0.03).
    from core.engine import Engine
    from ui.scenarios import HiddenFood

    scenario = HiddenFood()
    config = scenario.config()
    config.basal_ganglia.value_gain = 0.0
    config.basal_ganglia.forward_bias = 0.0
    engine = Engine(seed=1, config=config)
    scenario.setup(engine)
    site = scenario.items[0]
    engine.agent.pos = engine.agent.last_pos = (site.x, site.y)
    engine.run(1)
    assert engine.context.target_contact
    scenario.on_tick(engine, 0)
    assert site.kind == "collected" and scenario.collected == 1
    engine.run(1)
    assert not engine.context.target_contact  # eaten: no food here now
    scenario.on_tick(engine, scenario.REGROW)  # regrows while the agent is standing on it
    assert site.kind == "hidden" and scenario.collected == 1
    engine.agent.pos = engine.agent.last_pos = (site.x, site.y)
    engine.run(1)
    assert engine.context.target_contact and engine.context.map_reward > 0.0
    scenario.on_tick(engine, scenario.REGROW + 1)
    assert site.kind == "collected" and scenario.collected == 2
