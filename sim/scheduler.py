"""
scheduler.py — Load schedule.json and produce an ordered flight queue.
"""

from __future__ import annotations
import json
from pathlib import Path
from sim.entities import (
    Aircraft, AircraftState, ServiceRequirements, AIRCRAFT_TYPE_DEFAULTS
)


def load_schedule(
    path: str | Path,
    gates: dict | None = None,
) -> list[Aircraft]:
    """
    Parse schedule.json and return a list of Aircraft sorted by
    scheduled_arrival (then scheduled_departure for dep-only flights).

    Args:
        path: Path to schedule JSON file.
        gates: Optional gate registry (gate_id → Gate). When provided,
               departure-only flights are pre-assigned to gates round-robin.
               When None, falls back to the default KFIC 6-gate layout.

    JSON schema per flight:
    {
        "flight_id": "AA101",
        "aircraft_type": "B737",
        "scheduled_arrival": 0,          // sim-seconds; null for dep-only
        "scheduled_departure": 3600,     // sim-seconds
        "is_arrival_only": false,        // no departure (e.g. positioning)
        "is_departure_only": false       // no arrival (pre-positioned)
    }
    """
    # Build gate lists for dep-only pre-assignment
    if gates is not None:
        gate_ids = sorted(gates.keys())
        gate_nodes = [gates[gid].position_node for gid in gate_ids]
    else:
        # Default KFIC gates (backwards compatible)
        gate_ids = ["A1", "A2", "A3", "B1", "B2", "B3"]
        gate_nodes = ["GATE_A1", "GATE_A2", "GATE_A3", "GATE_B1", "GATE_B2", "GATE_B3"]

    data = json.loads(Path(path).read_text())
    aircraft_list: list[Aircraft] = []
    dep_only_idx = 0

    for rec in data:
        atype = rec.get("aircraft_type", "B737")
        defaults = AIRCRAFT_TYPE_DEFAULTS.get(atype, AIRCRAFT_TYPE_DEFAULTS["B737"])

        dep_only = rec.get("is_departure_only", False)
        arr_only = rec.get("is_arrival_only", False)

        sched_arr = rec.get("scheduled_arrival")
        sched_dep = rec.get("scheduled_departure")

        # Convert to floats (minutes → seconds if schedule uses minutes)
        # schedule.json stores raw seconds
        if sched_arr is None:
            sched_arr = float("inf")
        else:
            sched_arr = float(sched_arr)

        sched_dep = float(sched_dep) if sched_dep is not None else float("inf")

        reqs = ServiceRequirements(
            needs_fuel=True,
            fuel_amount=float(defaults["fuel_amount"]),
            needs_baggage_unload=(not dep_only),
            needs_baggage_load=(not arr_only),
            baggage_count=int(defaults["baggage_count"]),
            needs_pushback=(not arr_only),
        )

        initial_state = AircraftState.APPROACHING
        if dep_only:
            # Already at gate when sim starts
            initial_state = AircraftState.AT_GATE

        ac = Aircraft(
            flight_id=rec["flight_id"],
            aircraft_type=atype,
            scheduled_arrival=sched_arr,
            scheduled_departure=sched_dep,
            service_requirements=reqs,
            state=initial_state,
        )

        if dep_only and gate_ids:
            # Pre-assign gate + position so the dispatcher can find the aircraft
            idx = dep_only_idx % len(gate_ids)
            ac.assigned_gate = gate_ids[idx]
            ac.position = gate_nodes[idx]
            dep_only_idx += 1

        aircraft_list.append(ac)

    aircraft_list.sort(key=lambda a: (a.scheduled_arrival, a.scheduled_departure))
    return aircraft_list
