"""
Tests for sim/entities.py — state machine, service requirements, vehicle logic.
"""

import pytest
from sim.entities import (
    Aircraft, AircraftState, Gate, Runway, RunwayState,
    Vehicle, VehicleState, FuelTruck, BaggageTug, PushbackTractor,
    ServiceRequirements, ServiceTask, AIRCRAFT_TYPE_DEFAULTS,
)


# ---- ServiceRequirements ----

def test_service_requirements_defaults():
    reqs = ServiceRequirements()
    assert reqs.needs_fuel
    assert reqs.needs_baggage_unload
    assert reqs.needs_baggage_load
    assert reqs.needs_pushback


def test_required_services_all():
    reqs = ServiceRequirements()
    svcs = reqs.required_services()
    assert "fuel" in svcs
    assert "baggage_unload" in svcs
    assert "baggage_load" in svcs
    assert "pushback" in svcs


def test_required_services_no_pushback():
    reqs = ServiceRequirements(needs_pushback=False)
    svcs = reqs.required_services()
    assert "pushback" not in svcs
    assert "fuel" in svcs


def test_required_services_departure_only():
    reqs = ServiceRequirements(needs_baggage_unload=False)
    svcs = reqs.required_services()
    assert "baggage_unload" not in svcs
    assert "baggage_load" in svcs
    assert "fuel" in svcs
    assert "pushback" in svcs


def test_aircraft_type_defaults_present():
    for atype in ("B737", "A320", "B777", "CRJ900"):
        assert atype in AIRCRAFT_TYPE_DEFAULTS
        d = AIRCRAFT_TYPE_DEFAULTS[atype]
        assert "fuel_amount" in d
        assert "baggage_count" in d
        assert d["fuel_amount"] > 0
        assert d["baggage_count"] > 0


# ---- Aircraft ----

def test_aircraft_initial_state():
    reqs = ServiceRequirements()
    ac = Aircraft("AA101", "B737", 0.0, 3600.0, reqs)
    assert ac.state == AircraftState.APPROACHING
    assert ac.assigned_gate is None
    assert ac.position is None
    assert ac.path == []
    assert ac.services_completed == set()


def test_aircraft_all_services_done_initially_false():
    reqs = ServiceRequirements()
    ac = Aircraft("AA101", "B737", 0.0, 3600.0, reqs)
    assert not ac.all_services_done()


def test_aircraft_all_services_done_after_completing():
    reqs = ServiceRequirements(needs_pushback=True)
    ac = Aircraft("AA101", "B737", 0.0, 3600.0, reqs)
    # pushback excluded from all_services_done check
    ac.services_completed = {"fuel", "baggage_unload", "baggage_load"}
    assert ac.all_services_done()


def test_aircraft_all_services_done_partial():
    reqs = ServiceRequirements()
    ac = Aircraft("AA101", "B737", 0.0, 3600.0, reqs)
    ac.services_completed = {"fuel"}
    assert not ac.all_services_done()


def test_aircraft_repr():
    reqs = ServiceRequirements()
    ac = Aircraft("AA101", "B737", 0.0, 3600.0, reqs)
    r = repr(ac)
    assert "AA101" in r
    assert "approaching" in r


# ---- Aircraft state machine transitions (manual) ----

def test_state_progression_manual():
    """Manually walk through all valid state transitions."""
    reqs = ServiceRequirements()
    ac = Aircraft("AA101", "B737", 0.0, 3600.0, reqs)

    transitions = [
        AircraftState.APPROACHING,
        AircraftState.LANDED,
        AircraftState.TAXIING_IN,
        AircraftState.AT_GATE,
        AircraftState.SERVICING,
        AircraftState.AT_GATE,   # back after service
        AircraftState.PUSHBACK,
        AircraftState.TAXIING_OUT,
        AircraftState.DEPARTED,
    ]
    for state in transitions:
        ac.state = state
        assert ac.state == state


# ---- Gate ----

def test_gate_free_no_occupant():
    g = Gate("A1", "A", "GATE_A1")
    assert g.is_free(0.0)
    assert g.is_free(9999.0)


def test_gate_occupied():
    g = Gate("A1", "A", "GATE_A1", occupied_by="AA101")
    assert not g.is_free(0.0)


def test_gate_available_at_future():
    g = Gate("A1", "A", "GATE_A1", available_at=1000.0)
    assert not g.is_free(999.0)
    assert g.is_free(1000.0)


def test_gate_both_constraints():
    g = Gate("A1", "A", "GATE_A1", occupied_by="AA101", available_at=1000.0)
    g.occupied_by = None
    assert not g.is_free(500.0)  # not available yet
    assert g.is_free(1000.0)


# ---- Runway ----

def test_runway_free_initially():
    rwy = Runway("09L/27R", "09L", "RWY_09L_ENTRY", "INTER_NW")
    assert rwy.is_free(0.0)


def test_runway_not_free_when_occupied():
    rwy = Runway("09L/27R", "09L", "RWY_09L_ENTRY", "INTER_NW",
                 state=RunwayState.LANDING, occupied_by="AA101", available_at=60.0)
    assert not rwy.is_free(0.0)
    assert not rwy.is_free(30.0)


def test_runway_free_after_clearance():
    rwy = Runway("09L/27R", "09L", "RWY_09L_ENTRY", "INTER_NW",
                 state=RunwayState.FREE, available_at=60.0)
    assert not rwy.is_free(59.9)
    assert rwy.is_free(60.0)


# ---- Vehicles ----

def test_vehicle_available_when_idle():
    v = FuelTruck("FT1")
    assert v.is_available()


def test_vehicle_not_available_when_en_route():
    v = FuelTruck("FT1")
    v.state = VehicleState.EN_ROUTE
    assert not v.is_available()


def test_vehicle_not_available_when_assigned():
    v = FuelTruck("FT1")
    v.assigned_to = "AA101"
    assert not v.is_available()


def test_fuel_truck_defaults():
    ft = FuelTruck("FT1")
    assert ft.vehicle_type == "fuel_truck"
    assert ft.fuel_remaining == ft.fuel_capacity
    assert ft.services_since_refill == 0
    assert ft.refill_threshold == 3


def test_baggage_tug_defaults():
    bt = BaggageTug("BT1")
    assert bt.vehicle_type == "baggage_tug"
    assert bt.capacity > 0


def test_pushback_tractor_defaults():
    pb = PushbackTractor("PB1")
    assert pb.vehicle_type == "pushback_tractor"


def test_vehicle_repr():
    v = FuelTruck("FT1")
    r = repr(v)
    assert "FT1" in r
    assert "idle" in r


# ---- ServiceTask ----

def test_service_task_duration_fuel():
    reqs = ServiceRequirements(fuel_amount=5000.0)
    ac = Aircraft("AA101", "B737", 0.0, 3600.0, reqs)
    task = ServiceTask("T0001", "AA101", "fuel", "GATE_A1", 0.0)
    assert task.duration(ac) == 5000.0 / 100.0  # 50 seconds


def test_service_task_duration_baggage():
    reqs = ServiceRequirements(baggage_count=120)
    ac = Aircraft("AA101", "B737", 0.0, 3600.0, reqs)
    task = ServiceTask("T0002", "AA101", "baggage_unload", "GATE_A1", 0.0)
    assert task.duration(ac) == 120 * 0.5  # 60 seconds


def test_service_task_duration_pushback():
    reqs = ServiceRequirements()
    ac = Aircraft("AA101", "B737", 0.0, 3600.0, reqs)
    task = ServiceTask("T0003", "AA101", "pushback", "GATE_A1", 0.0)
    assert task.duration(ac) == 120.0


def test_service_task_duration_load():
    reqs = ServiceRequirements(baggage_count=60)
    ac = Aircraft("NK606", "CRJ900", 0.0, 3600.0, reqs)
    task = ServiceTask("T0004", "NK606", "baggage_load", "GATE_B1", 0.0)
    assert task.duration(ac) == 60 * 0.5
