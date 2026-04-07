"""
random_schedule.py — Generate randomised flight schedules for RL training.

Produces a list of Aircraft objects (same type as load_schedule() returns)
without touching schedule.json.

Schedule parameters (all randomised with a seed):
  • n_flights      — 6 to 14 flights
  • aircraft_type  — B737 / A320 / B777 / CRJ900 (uniform draw)
  • arrival times  — first arrival 0–600 s into sim; subsequent gaps 400–1800 s
  • turnaround     — 2700–5400 s (45–90 min) per aircraft type class
  • dep_only prob  — 20% chance a flight is pre-positioned (departure-only)

All times are raw simulation seconds (no conversion needed).
"""

from __future__ import annotations

import random
from typing import Optional

from sim.entities import Aircraft, AircraftState, ServiceRequirements, AIRCRAFT_TYPE_DEFAULTS

# Available gate nodes for pre-positioned (departure-only) aircraft
_GATE_NODES = ["GATE_A1", "GATE_A2", "GATE_A3", "GATE_B1", "GATE_B2", "GATE_B3"]
_GATE_IDS   = ["A1",      "A2",      "A3",      "B1",      "B2",      "B3"]

# Aircraft type pool
_AC_TYPES = ["B737", "A320", "B777", "CRJ900"]

# Turnaround time range per class (seconds)
_TURNAROUND_RANGE: dict[str, tuple[int, int]] = {
    "B737":   (2700, 4500),   # 45–75 min
    "A320":   (2700, 4500),
    "B777":   (3600, 5400),   # 60–90 min (larger aircraft)
    "CRJ900": (2100, 3600),   # 35–60 min (regional)
}


def generate_schedule(
    seed: Optional[int] = None,
    n_flights: Optional[int] = None,
) -> list[Aircraft]:
    """
    Generate and return a randomised list of Aircraft.

    Args:
        seed:      RNG seed for reproducibility. None = non-deterministic.
        n_flights: Override flight count (6–14). None = random.

    Returns:
        List of Aircraft sorted by (scheduled_arrival, scheduled_departure).
    """
    rng = random.Random(seed)

    n = n_flights if n_flights is not None else rng.randint(6, 14)

    aircraft_list: list[Aircraft] = []
    now = float(rng.randint(0, 600))   # randomise sim start offset

    for i in range(n):
        atype     = rng.choice(_AC_TYPES)
        defaults  = AIRCRAFT_TYPE_DEFAULTS[atype]
        dep_only  = rng.random() < 0.20   # 20% chance departure-only

        if dep_only:
            # Pre-positioned: already at a random gate, departure in 1–3 hours
            sched_arr = float("inf")
            sched_dep = float(rng.randint(1800, 10800))
            gate_idx  = rng.randrange(len(_GATE_IDS))
        else:
            # Turn flight: arrival then departure
            sched_arr = now
            turnaround_lo, turnaround_hi = _TURNAROUND_RANGE[atype]
            sched_dep = sched_arr + rng.randint(turnaround_lo, turnaround_hi)
            # Advance clock for next arrival
            now += rng.randint(400, 1800)

        reqs = ServiceRequirements(
            needs_fuel=True,
            fuel_amount=float(defaults["fuel_amount"]),
            needs_baggage_unload=(not dep_only),
            needs_baggage_load=True,
            baggage_count=int(defaults["baggage_count"]),
            needs_pushback=True,
        )

        initial_state = AircraftState.AT_GATE if dep_only else AircraftState.APPROACHING

        ac = Aircraft(
            flight_id=f"RND{i+1:02d}",
            aircraft_type=atype,
            scheduled_arrival=sched_arr,
            scheduled_departure=sched_dep,
            service_requirements=reqs,
            state=initial_state,
        )
        if dep_only:
            # Pre-assign gate + position so the dispatcher can find the aircraft
            ac.assigned_gate = _GATE_IDS[gate_idx]
            ac.position      = _GATE_NODES[gate_idx]
        aircraft_list.append(ac)

    aircraft_list.sort(key=lambda a: (a.scheduled_arrival, a.scheduled_departure))
    return aircraft_list
