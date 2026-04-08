"""
random_schedule.py — Generate randomised flight schedules for RL training.

Produces a list of Aircraft objects (same type as load_schedule() returns)
without touching schedule.json.

Two density modes:

  "loose" — original behaviour:
    • n_flights: 6–14
    • arrivals: even spacing, inter-arrival gap 400–1800 s
    • turnaround: 2700–5400 s (45–90 min) → median slack ~60 min
    • dep_only: 20% chance (departure at 1800–10 800 s)

  "tight" — dense, contention-creating:
    • n_flights: 10–20
    • arrivals: 2–3 clustered waves, within-wave gap 0–120 s, between-wave 1800–3600 s
    • turnaround: min_parallel_service_time + small buffer (0–600/900 s by type)
      → 100% of flights have <15 min slack; ~50%+ have <5 min slack
    • dep_only: 10% chance (departure at 600–3600 s — tighter window)

Default density is "tight".

Minimum parallel service times (seconds) — FT, BT_unload, BT_load dispatched
concurrently so min completion = max(fuel, unload, load):
  B737:   max(50, 60, 60) = 60 s
  A320:   max(45, 55, 55) = 55 s
  B777:   max(120, 150, 150) = 150 s
  CRJ900: max(20, 30, 30) = 30 s

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

# Turnaround time range per class for LOOSE mode (seconds)
_LOOSE_TURNAROUND: dict[str, tuple[int, int]] = {
    "B737":   (2700, 4500),   # 45–75 min
    "A320":   (2700, 4500),
    "B777":   (3600, 5400),   # 60–90 min
    "CRJ900": (2100, 3600),   # 35–60 min
}

# Minimum parallel service time per aircraft type for TIGHT mode (seconds)
# = max(fuel_time, baggage_unload_time, baggage_load_time) when all run in parallel
_MIN_SERVICE: dict[str, int] = {
    "B737":   60,    # max(5000/100=50, 120*0.5=60, 120*0.5=60) = 60
    "A320":   55,    # max(4500/100=45, 110*0.5=55, 110*0.5=55) = 55
    "B777":   150,   # max(12000/100=120, 300*0.5=150, 300*0.5=150) = 150
    "CRJ900": 30,    # max(2000/100=20, 60*0.5=30, 60*0.5=30) = 30
}

# Buffer added on top of min service time for TIGHT mode (lo, hi seconds)
# slack = scheduled_departure - arrival_time - min_service ∈ [lo, hi]
_TIGHT_BUFFER: dict[str, tuple[int, int]] = {
    "B737":   (0, 600),    # 0–10 min slack
    "A320":   (0, 600),    # 0–10 min slack
    "B777":   (0, 900),    # 0–15 min slack
    "CRJ900": (0, 300),    # 0–5 min slack
}


def generate_schedule(
    seed: Optional[int] = None,
    n_flights: Optional[int] = None,
    density: str = "tight",
) -> list[Aircraft]:
    """
    Generate and return a randomised list of Aircraft.

    Args:
        seed:      RNG seed for reproducibility. None = non-deterministic.
        n_flights: Override flight count. None = random (6–14 loose, 10–20 tight).
        density:   "loose" (original) or "tight" (dense, contention-creating).

    Returns:
        List of Aircraft sorted by (scheduled_arrival, scheduled_departure).
    """
    if density == "tight":
        return _generate_tight(seed=seed, n_flights=n_flights)
    return _generate_loose(seed=seed, n_flights=n_flights)


def _generate_loose(
    seed: Optional[int],
    n_flights: Optional[int],
) -> list[Aircraft]:
    """Original schedule generator — even spacing, loose turnarounds."""
    rng = random.Random(seed)
    n = n_flights if n_flights is not None else rng.randint(6, 14)

    aircraft_list: list[Aircraft] = []
    now = float(rng.randint(0, 600))

    for i in range(n):
        atype    = rng.choice(_AC_TYPES)
        defaults = AIRCRAFT_TYPE_DEFAULTS[atype]
        dep_only = rng.random() < 0.20

        if dep_only:
            sched_arr = float("inf")
            sched_dep = float(rng.randint(1800, 10800))
            gate_idx  = rng.randrange(len(_GATE_IDS))
        else:
            sched_arr = now
            lo, hi    = _LOOSE_TURNAROUND[atype]
            sched_dep = sched_arr + rng.randint(lo, hi)
            now      += rng.randint(400, 1800)

        aircraft_list.append(_make_aircraft(i, atype, sched_arr, sched_dep, dep_only, rng))

    aircraft_list.sort(key=lambda a: (a.scheduled_arrival, a.scheduled_departure))
    return aircraft_list


def _generate_tight(
    seed: Optional[int],
    n_flights: Optional[int],
) -> list[Aircraft]:
    """
    Dense, contention-creating schedule.

    Structure:
      • 2–3 arrival waves, each with 3–8 flights
      • Within a wave: arrivals spaced 0–120 s apart
      • Between waves: 1800–3600 s gap
      • Turnaround = min_service_time + small buffer → 100% flights <15 min slack
      • 10% dep-only flights (departure at 600–3600 s, tighter than loose)
    """
    rng = random.Random(seed)
    n = n_flights if n_flights is not None else rng.randint(10, 20)

    n_waves = rng.randint(2, 3)
    # Distribute flights as evenly as possible across waves
    base, rem = divmod(n, n_waves)
    wave_sizes = [base + (1 if i < rem else 0) for i in range(n_waves)]

    aircraft_list: list[Aircraft] = []
    flight_idx = 0
    wave_start = float(rng.randint(0, 300))   # earlier start than loose

    for w, wave_n in enumerate(wave_sizes):
        wave_time = wave_start
        for _ in range(wave_n):
            atype    = rng.choice(_AC_TYPES)
            dep_only = rng.random() < 0.10    # 10% dep-only (fewer than loose)

            if dep_only:
                sched_arr = float("inf")
                sched_dep = float(rng.randint(600, 3600))   # 10–60 min tight window
                gate_idx  = rng.randrange(len(_GATE_IDS))
            else:
                sched_arr = wave_time
                mst       = _MIN_SERVICE[atype]
                lo, hi    = _TIGHT_BUFFER[atype]
                sched_dep = sched_arr + mst + rng.randint(lo, hi)
                wave_time += rng.randint(0, 120)   # tight within-wave spacing

            aircraft_list.append(
                _make_aircraft(flight_idx, atype, sched_arr, sched_dep, dep_only, rng)
            )
            flight_idx += 1

        # Gap between waves
        if w < n_waves - 1:
            wave_start = wave_time + rng.randint(1800, 3600)

    aircraft_list.sort(key=lambda a: (a.scheduled_arrival, a.scheduled_departure))
    return aircraft_list


def _make_aircraft(
    idx: int,
    atype: str,
    sched_arr: float,
    sched_dep: float,
    dep_only: bool,
    rng: random.Random,
) -> Aircraft:
    defaults = AIRCRAFT_TYPE_DEFAULTS[atype]
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
        flight_id=f"RND{idx+1:02d}",
        aircraft_type=atype,
        scheduled_arrival=sched_arr,
        scheduled_departure=sched_dep,
        service_requirements=reqs,
        state=initial_state,
    )
    if dep_only:
        gate_idx       = rng.randrange(len(_GATE_IDS))
        ac.assigned_gate = _GATE_IDS[gate_idx]
        ac.position      = _GATE_NODES[gate_idx]
    return ac
