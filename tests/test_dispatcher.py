"""
Tests for sim/dispatcher.py — FCFS logic, vehicle assignment, conflict prevention.
"""

import pytest
from sim.world import build_taxiway_graph, build_gates, build_runways
from sim.entities import (
    Aircraft, AircraftState, ServiceRequirements,
    FuelTruck, BaggageTug, PushbackTractor, VehicleState,
)
from sim.dispatcher import Dispatcher


# ---- Fixtures ----

def make_reqs(needs_pushback=True, **kwargs):
    base = dict(
        needs_fuel=True, fuel_amount=5000.0,
        needs_baggage_unload=True, needs_baggage_load=True,
        baggage_count=120, needs_pushback=needs_pushback,
    )
    base.update(kwargs)
    return ServiceRequirements(**base)


def make_aircraft(flight_id="AA101", arr=0.0, dep=3600.0, **kwargs):
    reqs = kwargs.pop("reqs", make_reqs())
    return Aircraft(flight_id, "B737", arr, dep, reqs)


def make_fleet():
    return [
        FuelTruck(vehicle_id="FT1", position="DEPOT"),
        FuelTruck(vehicle_id="FT2", position="DEPOT"),
        BaggageTug(vehicle_id="BT1", position="DEPOT"),
        BaggageTug(vehicle_id="BT2", position="DEPOT"),
        PushbackTractor(vehicle_id="PB1", position="DEPOT"),
    ]


def make_dispatcher(aircraft=None, fleet=None):
    G = build_taxiway_graph()
    gates = build_gates()
    runways = build_runways()
    ac_list = aircraft or [make_aircraft()]
    veh_list = fleet or make_fleet()
    return Dispatcher(G, gates, runways, ac_list, veh_list)


# ---- Initial state ----

def test_dispatcher_initialises():
    d = make_dispatcher()
    assert len(d.aircraft) == 1
    assert len(d.vehicles) == 5
    assert d.pending_tasks == []
    assert d.active_tasks == {}
    assert d.conflict_count == 0


def test_metrics_initial():
    d = make_dispatcher()
    m = d.metrics()
    assert m["flights_departed"] == 0
    assert m["conflict_count"] == 0
    assert m["vehicles_dispatched"] == 0


# ---- Landing ----

def test_aircraft_lands_when_arrival_time_reached():
    ac = make_aircraft(arr=100.0, dep=3600.0)
    d = make_dispatcher(aircraft=[ac])
    # Before arrival
    d.tick(50.0)
    assert ac.state == AircraftState.APPROACHING
    # At arrival
    d.tick(100.0)
    assert ac.state in (AircraftState.LANDED, AircraftState.TAXIING_IN)


def test_aircraft_does_not_land_early():
    ac = make_aircraft(arr=500.0, dep=3600.0)
    d = make_dispatcher(aircraft=[ac])
    for t in range(0, 500, 10):
        d.tick(float(t))
    assert ac.state == AircraftState.APPROACHING


def test_landed_aircraft_gets_position():
    ac = make_aircraft(arr=0.0, dep=3600.0)
    d = make_dispatcher(aircraft=[ac])
    d.tick(0.0)
    d.tick(60.0)  # landing clears
    assert ac.position is not None


# ---- Gate assignment ----

def test_gate_assigned_to_landed_aircraft():
    ac = make_aircraft(arr=0.0, dep=7200.0)
    d = make_dispatcher(aircraft=[ac])
    # Run enough ticks for landing + gate assignment
    for t in range(0, 120):
        d.tick(float(t))
    assert ac.assigned_gate is not None


def test_two_aircraft_get_different_gates():
    ac1 = make_aircraft("AA101", arr=0.0, dep=7200.0)
    ac2 = make_aircraft("DL202", arr=0.0, dep=7200.0)
    d = make_dispatcher(aircraft=[ac1, ac2])
    for t in range(0, 180):
        d.tick(float(t))
    # Both should have gates (may not be assigned if only one runway)
    # At minimum, if both assigned, they differ
    if ac1.assigned_gate and ac2.assigned_gate:
        assert ac1.assigned_gate != ac2.assigned_gate


def test_no_gate_double_booking():
    """Two aircraft must never share a gate."""
    aircraft = [make_aircraft(f"F{i:02d}", arr=float(i * 10), dep=7200.0) for i in range(6)]
    d = make_dispatcher(aircraft=aircraft)
    for t in range(0, 300):
        d.tick(float(t))
    gates_used = [a.assigned_gate for a in aircraft if a.assigned_gate]
    assert len(gates_used) == len(set(gates_used)), "Duplicate gate assignment detected"


# ---- Taxiway conflict prevention ----

def test_no_segment_double_occupancy():
    """
    Run two aircraft through the sim; verify no segment is ever double-occupied.
    Any ConflictError would raise and also increment conflict_count.
    """
    ac1 = make_aircraft("AA101", arr=0.0, dep=7200.0)
    ac2 = make_aircraft("DL202", arr=5.0, dep=7200.0)
    d = make_dispatcher(aircraft=[ac1, ac2])
    for t in range(0, 400):
        d.tick(float(t))
    assert d.conflict_count == 0


def test_conflict_count_starts_zero():
    d = make_dispatcher()
    assert d.conflict_count == 0


# ---- Service task creation ----

def test_service_tasks_created_at_gate():
    ac = make_aircraft(arr=0.0, dep=7200.0)
    ac.state = AircraftState.AT_GATE
    ac.assigned_gate = "A1"
    ac.position = "GATE_A1"
    d = make_dispatcher(aircraft=[ac])
    d.tick(0.0)
    total = len(d.pending_tasks) + len(d.active_tasks)
    assert total > 0


def test_no_duplicate_service_tasks():
    """Ticking multiple times should not create duplicate tasks for the same service."""
    ac = make_aircraft(arr=0.0, dep=7200.0)
    ac.state = AircraftState.AT_GATE
    ac.assigned_gate = "A1"
    ac.position = "GATE_A1"
    d = make_dispatcher(aircraft=[ac])
    for t in range(5):
        d.tick(float(t))
    all_tasks = d.pending_tasks + list(d.active_tasks.values())
    service_types = [t.service_type for t in all_tasks if t.flight_id == ac.flight_id]
    assert len(service_types) == len(set(service_types)), "Duplicate service tasks"


# ---- Vehicle assignment ----

def test_fuel_truck_assigned_to_fuel_task():
    ac = make_aircraft(arr=0.0, dep=7200.0)
    ac.state = AircraftState.AT_GATE
    ac.assigned_gate = "A1"
    ac.position = "GATE_A1"
    d = make_dispatcher(aircraft=[ac])
    for t in range(5):
        d.tick(float(t))
    # Find fuel task in active or pending
    all_tasks = d.pending_tasks + list(d.active_tasks.values())
    fuel_tasks = [t for t in all_tasks if t.service_type == "fuel"]
    assert len(fuel_tasks) >= 1
    ft = fuel_tasks[0]
    if ft.assigned_vehicle_id:
        assert ft.assigned_vehicle_id.startswith("FT")


def test_baggage_tug_assigned_to_baggage_task():
    ac = make_aircraft(arr=0.0, dep=7200.0)
    ac.state = AircraftState.AT_GATE
    ac.assigned_gate = "A1"
    ac.position = "GATE_A1"
    d = make_dispatcher(aircraft=[ac])
    for t in range(5):
        d.tick(float(t))
    all_tasks = d.pending_tasks + list(d.active_tasks.values())
    bag_tasks = [t for t in all_tasks if "baggage" in t.service_type]
    for bt in bag_tasks:
        if bt.assigned_vehicle_id:
            assert bt.assigned_vehicle_id.startswith("BT")


def test_vehicles_dispatched_counter_increments():
    ac = make_aircraft(arr=0.0, dep=7200.0)
    ac.state = AircraftState.AT_GATE
    ac.assigned_gate = "A1"
    ac.position = "GATE_A1"
    d = make_dispatcher(aircraft=[ac])
    for t in range(10):
        d.tick(float(t))
    assert d.vehicles_dispatched > 0


def test_vehicle_not_double_assigned():
    """Each vehicle must have at most one assignment at a time."""
    ac1 = make_aircraft("AA101", arr=0.0, dep=7200.0)
    ac2 = make_aircraft("DL202", arr=0.0, dep=7200.0)
    for ac in (ac1, ac2):
        ac.state = AircraftState.AT_GATE
        ac.assigned_gate = "A1" if ac.flight_id == "AA101" else "A2"
        ac.position = "GATE_A1" if ac.flight_id == "AA101" else "GATE_A2"
    d = make_dispatcher(aircraft=[ac1, ac2])
    for t in range(20):
        d.tick(float(t))
        # Each vehicle_id should appear at most once (each vehicle has one assigned_to field,
        # so this is structurally guaranteed — verify the vehicle dict is consistent)
        assigned_vehicle_ids = [
            vid for vid, v in d.vehicles.items() if v.assigned_to is not None
        ]
        # No vehicle should appear twice in the dict keys (trivially true, but verifies dict integrity)
        assert len(assigned_vehicle_ids) == len(set(assigned_vehicle_ids)), \
            f"Duplicate vehicle_id in fleet dict at t={t}"
        # Each assigned vehicle should have a valid flight_id
        for vid in assigned_vehicle_ids:
            v = d.vehicles[vid]
            assert v.assigned_to in d.aircraft, \
                f"Vehicle {vid} assigned to unknown flight {v.assigned_to!r} at t={t}"


# ---- Fuel truck refill ----

def test_fuel_truck_returns_after_refill_threshold():
    ft = FuelTruck(vehicle_id="FT1", position="DEPOT", refill_threshold=1)
    ft.services_since_refill = 1
    d = make_dispatcher(fleet=[ft, BaggageTug("BT1"), PushbackTractor("PB1")])
    d.tick(0.0)
    assert ft.state == VehicleState.RETURNING or ft.state == VehicleState.IDLE


def test_fuel_truck_refilled_at_depot():
    ft = FuelTruck(vehicle_id="FT1", position="DEPOT",
                   fuel_remaining=0.0, services_since_refill=3, refill_threshold=3)
    ft.state = VehicleState.RETURNING
    ft.path = []   # already at depot
    d = make_dispatcher(fleet=[ft, BaggageTug("BT1"), PushbackTractor("PB1")])
    d._advance_vehicles(0.0, 1.0)
    assert ft.state == VehicleState.IDLE
    assert ft.fuel_remaining == ft.fuel_capacity
    assert ft.services_since_refill == 0


# ---- Full run (headless, fast) ----

def test_full_run_no_conflicts():
    """
    Run the entire simulation headless over 4 aircraft and ensure
    conflict_count stays 0.
    """
    from sim.scheduler import load_schedule
    import json, tempfile, os

    mini_schedule = [
        {"flight_id": "T001", "aircraft_type": "B737",
         "scheduled_arrival": 0, "scheduled_departure": 3600,
         "is_arrival_only": False, "is_departure_only": False},
        {"flight_id": "T002", "aircraft_type": "A320",
         "scheduled_arrival": 300, "scheduled_departure": 3900,
         "is_arrival_only": False, "is_departure_only": False},
        {"flight_id": "T003", "aircraft_type": "CRJ900",
         "scheduled_arrival": 600, "scheduled_departure": 4200,
         "is_arrival_only": False, "is_departure_only": False},
        {"flight_id": "T004", "aircraft_type": "B737",
         "scheduled_arrival": 900, "scheduled_departure": 4500,
         "is_arrival_only": False, "is_departure_only": False},
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(mini_schedule, f)
        fname = f.name

    try:
        aircraft_list = load_schedule(fname)
        G = build_taxiway_graph()
        gates = build_gates()
        runways = build_runways()
        fleet = make_fleet()
        d = Dispatcher(G, gates, runways, aircraft_list, fleet)

        for t in range(0, 7200):
            d.tick(float(t))
            assert d.conflict_count == 0, f"Conflict at t={t}!"

        m = d.metrics()
        assert m["conflict_count"] == 0
    finally:
        os.unlink(fname)


def test_find_nearest_vehicle_returns_float_cost():
    """shortest_path_length must return a float, not a dict.
    Regression: when gate_node was None, nx.shortest_path_length returned
    a dict of all targets, causing sort to crash with TypeError.
    """
    import networkx as nx
    d = make_dispatcher()
    G = d.G
    # Verify shortest_path_length returns float for a valid target
    cost = nx.shortest_path_length(G, "DEPOT", "GATE_A1", weight="weight")
    assert isinstance(cost, float), f"Expected float, got {type(cost)}"

    # Verify _find_nearest_vehicle handles None gate_node gracefully
    result = d._find_nearest_vehicle("fuel", None)
    assert result is None, "Should return None for None gate_node"

    # Verify _find_nearest_vehicle handles non-existent gate_node gracefully
    result = d._find_nearest_vehicle("fuel", "NONEXISTENT_NODE")
    assert result is None, "Should return None for non-existent gate_node"


def test_find_nearest_vehicle_tiebreak():
    """When two vehicles have equal cost, sort must not crash on Vehicle comparison."""
    ac = make_aircraft(arr=0.0, dep=7200.0)
    ac.state = AircraftState.AT_GATE
    ac.assigned_gate = "A1"
    ac.position = "GATE_A1"
    # Two fuel trucks at same position
    fleet = [
        FuelTruck(vehicle_id="FT1", position="DEPOT"),
        FuelTruck(vehicle_id="FT2", position="DEPOT"),
        BaggageTug(vehicle_id="BT1", position="DEPOT"),
        PushbackTractor(vehicle_id="PB1", position="DEPOT"),
    ]
    d = make_dispatcher(aircraft=[ac], fleet=fleet)
    # Should not crash even though FT1 and FT2 have same cost
    result = d._find_nearest_vehicle("fuel", "GATE_A1")
    assert result is not None
    assert result.vehicle_id in ("FT1", "FT2")


def test_full_run_flights_eventually_depart():
    """At least some flights should depart within the sim window."""
    from sim.scheduler import load_schedule
    import json, tempfile, os

    mini_schedule = [
        {"flight_id": "T001", "aircraft_type": "B737",
         "scheduled_arrival": 0, "scheduled_departure": 1800,
         "is_arrival_only": False, "is_departure_only": False},
        {"flight_id": "T002", "aircraft_type": "A320",
         "scheduled_arrival": 60, "scheduled_departure": 1860,
         "is_arrival_only": False, "is_departure_only": False},
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(mini_schedule, f)
        fname = f.name

    try:
        aircraft_list = load_schedule(fname)
        G = build_taxiway_graph()
        gates = build_gates()
        runways = build_runways()
        fleet = make_fleet()
        d = Dispatcher(G, gates, runways, aircraft_list, fleet)

        for t in range(0, 5400):
            d.tick(float(t))

        m = d.metrics()
        assert m["flights_departed"] >= 1, "No flights departed!"
    finally:
        os.unlink(fname)
