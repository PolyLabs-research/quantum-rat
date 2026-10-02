"""Hidden food: an open task where place memory pays off (ui.scenarios.HiddenFood).

Six invisible food sites regrow 150 ticks after they are eaten. Without memory
the agent finds food only when its wall-following loop happens to brush a
site; with memory the value map learns each find and steers the agent back.

The guard runs the scenario headless through the sensitivity harness at sensor
noise 0, seed 1, from four start headings (0, pi/2, pi, 3pi/2), 3000 ticks
each, and compares the summed finds with memory steering at the scenario
default (value_gain 1.5) against memory off (value_gain 0). Measured: 45 vs 12
finds (3.75x; per heading 14/5/16/10 vs 4/3/3/2, so memory wins all four
pairs). The bound is >= 2x and >= 3 of 4 pairs won.

Wider measurements (harness, 3000 ticks, gain 1.5 vs 0): x2.74 over seeds 1-8
at noise 0.03 (6.50 vs 2.38 finds, 8 wins 0 losses), x2.74 on held-out seeds
9-16 (8-0), x4.08 over 8 headings at noise 0 (12.25 vs 3.00, 8-0); gains 0.4,
0.8 and 3.0 give x2.68-2.89 / x3.67-4.29.

The benefit has to come from the learned map: with the map frozen
(``value_memory.learning_rate`` 0, value_gain still 1.5) the value signals are
always zero and the runs are identical to memory off, so the same bound fails
(12 vs 12). ``test_frozen_map_gives_no_benefit`` checks that.
"""

from __future__ import annotations

import functools
import math
from typing import Optional, Tuple

from experiments.steering_sensitivity import Job, run_job

TICKS = 3000
HEADINGS = (0.0, math.pi / 2, math.pi, 3 * math.pi / 2)
MIN_RATIO = 2.0
MIN_WINS = 3
FROZEN_MAP = (("value_memory.learning_rate", 0.0),)


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


def test_frozen_map_gives_no_benefit():
    without = _scores(0.0)
    frozen = _scores(None, FROZEN_MAP)
    assert frozen == without  # zero map -> zero value signals -> the same runs
    assert not _memory_beats_no_memory(frozen, without)


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
