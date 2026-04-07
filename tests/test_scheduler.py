"""
Tests for sim/scheduler.py — JSON loading, flight parsing.
"""

import json
import tempfile
import os
import pytest
from sim.scheduler import load_schedule
from sim.entities import AircraftState


def write_schedule(data):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return f.name


# ---- Basic loading ----

def test_load_single_flight():
    data = [{
        "flight_id": "AA101",
        "aircraft_type": "B737",
        "scheduled_arrival": 0,
        "scheduled_departure": 3600,
        "is_arrival_only": False,
        "is_departure_only": False,
    }]
    path = write_schedule(data)
    try:
        flights = load_schedule(path)
        assert len(flights) == 1
        ac = flights[0]
        assert ac.flight_id == "AA101"
        assert ac.aircraft_type == "B737"
        assert ac.scheduled_arrival == 0.0
        assert ac.scheduled_departure == 3600.0
    finally:
        os.unlink(path)


def test_load_twelve_flights():
    path = "schedule.json"
    flights = load_schedule(path)
    assert len(flights) == 12


def test_flights_sorted_by_arrival():
    data = [
        {"flight_id": "C", "aircraft_type": "B737", "scheduled_arrival": 900,
         "scheduled_departure": 4500, "is_arrival_only": False, "is_departure_only": False},
        {"flight_id": "A", "aircraft_type": "B737", "scheduled_arrival": 0,
         "scheduled_departure": 3600, "is_arrival_only": False, "is_departure_only": False},
        {"flight_id": "B", "aircraft_type": "B737", "scheduled_arrival": 300,
         "scheduled_departure": 3900, "is_arrival_only": False, "is_departure_only": False},
    ]
    path = write_schedule(data)
    try:
        flights = load_schedule(path)
        arrivals = [f.scheduled_arrival for f in flights]
        assert arrivals == sorted(arrivals)
    finally:
        os.unlink(path)


def test_departure_only_flag():
    data = [{
        "flight_id": "DEP1",
        "aircraft_type": "A320",
        "scheduled_arrival": None,
        "scheduled_departure": 3600,
        "is_arrival_only": False,
        "is_departure_only": True,
    }]
    path = write_schedule(data)
    try:
        flights = load_schedule(path)
        ac = flights[0]
        assert ac.state == AircraftState.AT_GATE
        assert not ac.service_requirements.needs_baggage_unload
        assert ac.service_requirements.needs_baggage_load
        assert ac.service_requirements.needs_pushback
    finally:
        os.unlink(path)


def test_arrival_only_flag():
    data = [{
        "flight_id": "ARR1",
        "aircraft_type": "B737",
        "scheduled_arrival": 600,
        "scheduled_departure": 9999999,
        "is_arrival_only": True,
        "is_departure_only": False,
    }]
    path = write_schedule(data)
    try:
        flights = load_schedule(path)
        ac = flights[0]
        assert not ac.service_requirements.needs_baggage_load
        assert not ac.service_requirements.needs_pushback
        assert ac.service_requirements.needs_baggage_unload
    finally:
        os.unlink(path)


def test_aircraft_type_defaults_applied():
    for atype, expected_fuel in [("B737", 5000), ("B777", 12000), ("CRJ900", 2000)]:
        data = [{
            "flight_id": f"X{atype}",
            "aircraft_type": atype,
            "scheduled_arrival": 0,
            "scheduled_departure": 3600,
            "is_arrival_only": False,
            "is_departure_only": False,
        }]
        path = write_schedule(data)
        try:
            flights = load_schedule(path)
            ac = flights[0]
            assert ac.service_requirements.fuel_amount == expected_fuel, \
                f"{atype}: expected {expected_fuel} got {ac.service_requirements.fuel_amount}"
        finally:
            os.unlink(path)


def test_all_flights_have_service_requirements():
    flights = load_schedule("schedule.json")
    for ac in flights:
        assert ac.service_requirements is not None
        assert len(ac.service_requirements.required_services()) > 0


def test_no_flight_has_zero_scheduled_departure():
    flights = load_schedule("schedule.json")
    for ac in flights:
        assert ac.scheduled_departure > 0
