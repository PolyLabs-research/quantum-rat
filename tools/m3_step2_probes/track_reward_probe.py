import sys, statistics as st, math
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from experiments import body_characterisation as bc
from core.engine import Engine
from core.world import WorldObject
BASE = {"sensors.free_space_sensing": True, "value_memory.reachable_probes": True, "sensors.lateral_odometry": True}
SHORT = {"basal_ganglia.wall_avoid_range": 1/6, "basal_ganglia.turn_commitment": 0.3}
CFGS = {"A_current": {}, "B_short": SHORT}
ENDS = (-9.0, 9.0)
def job(a):
    c, steer, rewarded, seed = a
    ov = {**BASE, **CFGS[c]}
    if not steer: ov["basal_ganglia.value_gain"] = 0.0
    cfg = bc.condition_config(ov, bc.TRACK_BOUNDS)
    eng = Engine(seed=seed, config=cfg)
    sites = [WorldObject(x, 0.0, 0.5, "collected") for x in ENDS]
    for s in sites: eng.world.add_object(s)
    active = 1  # the far end from the start at the centre... start pose: centre facing +x
    if rewarded: sites[active].kind = "hidden"
    eng.run(1, reset=True)
    laps = []; last = 0; ends_reached = []; prev_end = None; end_ticks = []
    for t in range(3000):
        eng.run(1)
        x, y = eng.agent.pos
        if rewarded and math.hypot(x - sites[active].x, y) <= 0.5 + 1e-9:
            sites[active].kind = "collected"; active = 1 - active; sites[active].kind = "hidden"
            laps.append(t - last); last = t
        end = -1 if x <= -8.0 else (1 if x >= 8.0 else None)
        if end is not None and end != prev_end:
            if prev_end is not None: end_ticks.append(t)
            prev_end = end
    traversals = len(end_ticks)
    tpl = st.median([b - a for a, b in zip([0] + end_ticks, end_ticks)]) if end_ticks else 3000
    return c, steer, rewarded, seed, len(laps), (st.median(laps[5:]) if len(laps) > 6 else float("nan")), traversals, tpl
if __name__ == "__main__":
    jobs = [(c, s, r, seed) for c in CFGS for s in (True, False) for r in (True, False) for seed in range(31, 39)]
    with ProcessPoolExecutor(28) as p: out = list(p.map(job, jobs, chunksize=1))
    for c in CFGS:
        for r in (True, False):
            for s in (True, False):
                v = [o for o in out if o[0] == c and o[1] == s and o[2] == r]
                rew = [o[5] for o in v if o[5] == o[5]]
                print(f"{c:10s} reward={'yes' if r else 'no '} steer={'sr  ' if s else 'none'} rewards {st.mean(o[4] for o in v):6.1f}  "
                      f"ticks/reward (after 5) {st.median(rew) if rew else float('nan'):6.1f}  traversals {st.mean(o[6] for o in v):6.1f}  ticks/traversal {st.mean(o[7] for o in v):7.1f}")
