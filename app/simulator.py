"""
app/simulator.py — Run KFIC simulations and produce replay JSON for the dashboard.

Exposes run_comparison(seed, model_path) which runs both FCFS and the RL policy
on the same randomly-generated schedule and returns a single dict suitable for
JSON serialisation.
"""
from __future__ import annotations

import os
import sys
from typing import Any

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from sim.world import build_taxiway_graph, build_gates, build_runways, NODE_POSITIONS
from sim.entities import AircraftState, VehicleState
from sim.dispatcher import Dispatcher
from env.airport_env import AirportEnv, _build_fleet
from env.random_schedule import generate_schedule

DEFAULT_MODEL = os.path.join(REPO_ROOT, "models", "v5_anticipation_final.zip")
SNAPSHOT_INTERVAL = 30.0   # seconds of sim time between timeline snapshots
SIM_HORIZON = 14400.0       # 4 hours (KFIC episode limit)
MAX_SNAPSHOTS = 300         # cap to keep response size reasonable

# ── Model cache (avoid re-loading 560 KB zip on every request) ────────────────
_model_cache: dict[str, Any] = {}


def _load_model(model_path: str):
    if model_path not in _model_cache:
        from sb3_contrib import MaskablePPO
        _model_cache[model_path] = MaskablePPO.load(model_path)
    return _model_cache[model_path]


# ── Graph export ──────────────────────────────────────────────────────────────

def get_graph() -> dict:
    """Return KFIC graph as dict for frontend SVG rendering."""
    G = build_taxiway_graph()
    nodes = []
    for n in G.nodes():
        pos = NODE_POSITIONS.get(n)
        if pos is None:
            continue
        ntype = G.nodes[n].get("type", "intersection")
        nodes.append({"id": n, "x": pos[0], "y": pos[1], "type": ntype})
    edges = [
        {"from": u, "to": v, "weight": round(d["weight"], 1)}
        for u, v, d in G.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}


# ── Snapshot capture ──────────────────────────────────────────────────────────

def _snapshot(dispatcher: Dispatcher, t: float) -> dict:
    vehicles = [
        {
            "id": v.vehicle_id,
            "pos": v.position,
            "state": v.state.value,
            "type": v.vehicle_type,
            "target": v.assigned_to,
        }
        for v in dispatcher.vehicles.values()
    ]
    aircraft = [
        {
            "id": ac.flight_id,
            "pos": ac.position,
            "state": ac.state.value,
            "gate": ac.assigned_gate,
        }
        for ac in dispatcher.aircraft.values()
        if ac.state != AircraftState.DEPARTED
    ]
    return {
        "t": round(t),
        "vehicles": vehicles,
        "aircraft": aircraft,
        "n_pending": len(dispatcher.pending_tasks),
        "n_active": len(dispatcher.active_tasks),
    }


def _downsample(timeline: list[dict]) -> list[dict]:
    """Keep at most MAX_SNAPSHOTS frames, evenly spaced."""
    if len(timeline) <= MAX_SNAPSHOTS:
        return timeline
    step = len(timeline) / MAX_SNAPSHOTS
    return [timeline[round(i * step)] for i in range(MAX_SNAPSHOTS)]


# ── FCFS runner ───────────────────────────────────────────────────────────────

def run_fcfs(seed: int) -> dict:
    """Run FCFS baseline on KFIC. Returns metrics + timeline + schedule."""
    G = build_taxiway_graph()
    gates = build_gates()
    runways = build_runways()
    fleet = _build_fleet()
    aircraft_list = generate_schedule(seed=seed, density="tight")

    dispatcher = Dispatcher(
        graph=G, gates=gates, runways=runways,
        aircraft=aircraft_list, vehicles=fleet,
    )
    for ac in aircraft_list:
        if ac.state == AircraftState.AT_GATE and ac.assigned_gate is not None:
            gate = dispatcher.gates.get(ac.assigned_gate)
            if gate is not None:
                gate.occupied_by = ac.flight_id

    schedule = [
        {
            "id": ac.flight_id,
            "gate": ac.assigned_gate,
            "arrival": round(ac.scheduled_arrival) if ac.scheduled_arrival < float("inf") else None,
            "departure": round(ac.scheduled_departure) if ac.scheduled_departure < float("inf") else None,
            "type": ac.aircraft_type,
        }
        for ac in aircraft_list
    ]

    timeline: list[dict] = []
    sim_time = 0.0
    next_snap = 0.0

    while sim_time <= SIM_HORIZON:
        if sim_time >= next_snap:
            timeline.append(_snapshot(dispatcher, sim_time))
            next_snap += SNAPSHOT_INTERVAL
        dispatcher.tick(sim_time, dt=1.0)
        sim_time += 1.0
        if all(a.state == AircraftState.DEPARTED for a in dispatcher.aircraft.values()):
            timeline.append(_snapshot(dispatcher, sim_time))
            break

    m = dispatcher.metrics()
    return {
        "schedule": schedule,
        "metrics": {
            "total_delay_min": m["total_delay_minutes"],
            "avg_delay_min": m["avg_delay_minutes"],
            "flights_departed": m["flights_departed"],
            "flights_total": len(aircraft_list),
            "conflicts": m["conflict_count"],
            "tasks_completed": m["tasks_completed"],
        },
        "timeline": _downsample(timeline),
    }


# ── RL runner ─────────────────────────────────────────────────────────────────

def _action_description(dispatcher: Dispatcher, action: int, max_tasks: int = 16) -> str:
    action_hold = max_tasks + 8  # 24
    if action == action_hold:
        return "HOLD"
    if action >= max_tasks:
        ant_idx = action - max_tasks
        ants = dispatcher.anticipated_tasks
        if ant_idx < len(ants):
            at = ants[ant_idx]
            gate = at.gate_node_estimate or "TBD"
            return f"Reserve → {at.service_type} @ {gate}"
        return f"Reserve #{ant_idx}"
    if action < len(dispatcher.pending_tasks):
        t = dispatcher.pending_tasks[action]
        return f"Assign → {t.service_type} @ {t.gate_node} ({t.flight_id})"
    return f"Task #{action}"


def run_rl(seed: int, model_path: str = DEFAULT_MODEL) -> dict:
    """Run RL policy on KFIC with given seed. Returns metrics + timeline + decisions."""
    model = _load_model(model_path)
    env = AirportEnv(randomise=True, seed=seed)
    obs, _ = env.reset(seed=seed)

    timeline: list[dict] = []
    decisions: list[dict] = []
    last_snap_t = -SNAPSHOT_INTERVAL

    done = False
    while not done:
        t = env._sim_time  # type: ignore[attr-defined]
        if t - last_snap_t >= SNAPSHOT_INTERVAL:
            timeline.append(_snapshot(env.dispatcher, t))  # type: ignore[attr-defined]
            last_snap_t = t

        action, _ = model.predict(obs, action_masks=env.action_masks(), deterministic=True)
        action = int(action)

        decisions.append({
            "t": round(t),
            "action": action,
            "desc": _action_description(env.dispatcher, action),  # type: ignore[attr-defined]
        })

        obs, _reward, terminated, truncated, _info = env.step(action)
        done = terminated or truncated

    # Final snapshot
    timeline.append(_snapshot(env.dispatcher, env._sim_time))  # type: ignore[attr-defined]

    hold_count = sum(1 for d in decisions if d["desc"] == "HOLD")
    m = env.dispatcher.metrics()  # type: ignore[attr-defined]
    return {
        "metrics": {
            "total_delay_min": m["total_delay_minutes"],
            "avg_delay_min": m["avg_delay_minutes"],
            "flights_departed": m["flights_departed"],
            "flights_total": len(env.dispatcher.aircraft),  # type: ignore[attr-defined]
            "conflicts": m["conflict_count"],
            "tasks_completed": m["tasks_completed"],
            "n_decisions": len(decisions),
            "hold_rate_pct": round(100 * hold_count / max(len(decisions), 1), 1),
        },
        "timeline": _downsample(timeline),
        "decisions": decisions[-150:],  # last 150 for the log
    }


# ── Comparison ────────────────────────────────────────────────────────────────

def run_comparison(seed: int, model_path: str = DEFAULT_MODEL) -> dict:
    """Run FCFS and RL on same seed, return full comparison payload."""
    fcfs = run_fcfs(seed)
    rl = run_rl(seed, model_path)

    fd = fcfs["metrics"]["total_delay_min"]
    rd = rl["metrics"]["total_delay_min"]
    delta = round(rd - fd, 1)
    winner = "rl" if delta < -0.5 else ("fcfs" if delta > 0.5 else "tie")

    return {
        "seed": seed,
        "graph": get_graph(),
        "schedule": fcfs["schedule"],
        "fcfs": {"metrics": fcfs["metrics"], "timeline": fcfs["timeline"]},
        "rl": {
            "metrics": rl["metrics"],
            "timeline": rl["timeline"],
            "decisions": rl["decisions"],
        },
        "comparison": {
            "fcfs_delay": fd,
            "rl_delay": rd,
            "delta_min": delta,
            "winner": winner,
        },
    }
