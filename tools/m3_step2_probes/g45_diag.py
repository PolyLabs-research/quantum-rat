import sys, math, statistics as st
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from experiments import rq4a_gate as rg
from core.engine import Engine
from core.world import WorldObject
from brain.contracts import Action
REACH = {"sensors.free_space_sensing": True, "value_memory.reachable_probes": True}
OPTS = {"none": {}, "range": {"basal_ganglia.wall_avoid_range": 1/6}, "commit": {"basal_ganglia.turn_commitment": 0.3},
        "both": {"basal_ganglia.wall_avoid_range": 1/6, "basal_ganglia.turn_commitment": 0.3}}
def job(a):
    opt, reach, session, seed = a
    ov = {**OPTS[opt], **(REACH if reach else {})}
    eng = Engine(seed=seed, config=rg.gate_config("sr", "per_feature", lateral_odometry=True, overrides=ov))
    goal = WorldObject(*rg.GOAL, rg.GOAL_RADIUS, session == "hidden" and "hidden" or "target"); eng.world.add_object(goal)
    first = True; hits = []; seen = near = n = turns = 0; bx, by = eng.world.bounds
    for trial, start in enumerate(rg.start_order(seed, 40), 1):
        sx, sy, sh = rg.STARTS[start]; a = eng.agent
        a.pos = a.last_pos = (sx, sy); a.heading = a.last_heading = sh
        st_ = eng.spatial.state; st_.grid_x, st_.grid_y, st_.hd_angle = sx, sy, sh
        if not first: eng.last_action = Action("REST", 0.0, 0.0)
        eng.reset_value_episode(); goal.kind = "hidden" if session == "hidden" else "target"
        ok = False
        for t in range(rg.TIMEOUT):
            td = eng.run(1, reset=first)[0]; first = False
            if trial > 20:
                n += 1
                seen += any(r.obj_type == "target" for r in eng.context.observation.vision_rays)
                x, y = a.pos; near += (bx - abs(x) < 1.0) or (by - abs(y) < 1.0)
                turns += td.action_name.startswith("TURN")
            if rg._reached(eng): ok = True; break
        if not ok and session == "hidden":
            goal.kind = "target"
            for t in range(rg.GUIDE):
                eng.run(1)
                if rg._reached(eng): break
        if trial > 20: hits.append(ok)
    return opt, reach, session, seed, sum(hits)/len(hits), seen/max(n,1), near/max(n,1), turns/max(n,1)
if __name__ == "__main__":
    jobs = [(o, r, ses, s) for o in OPTS for r in (False, True) for ses in ("visible", "hidden") for s in range(31, 43)]
    with ProcessPoolExecutor(28) as p: out = list(p.map(job, jobs, chunksize=1))
    for o in OPTS:
        for r in (False, True):
            for ses in ("visible", "hidden"):
                v = [x for x in out if x[0]==o and x[1]==r and x[2]==ses]
                m = lambda i: st.mean(x[i] for x in v)
                print(f"{o:7s} reach={'on ' if r else 'off'} {ses:7s} success {m(4):.3f}  target-in-view {m(5):.3f}  near-wall {m(6):.3f}  turn-share {m(7):.3f}")
