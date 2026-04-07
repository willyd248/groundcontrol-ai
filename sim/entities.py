"""
Entities: Aircraft, Gate, Vehicle subclasses, and related enums/dataclasses.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AircraftState(Enum):
    APPROACHING   = "approaching"
    LANDED        = "landed"
    TAXIING_IN    = "taxiing_in"
    AT_GATE       = "at_gate"
    SERVICING     = "servicing"
    PUSHBACK      = "pushback"
    TAXIING_OUT   = "taxiing_out"
    DEPARTED      = "departed"


class VehicleState(Enum):
    IDLE       = "idle"
    EN_ROUTE   = "en_route"
    SERVICING  = "servicing"
    RETURNING  = "returning"


class RunwayState(Enum):
    FREE       = "free"
    LANDING    = "landing"
    DEPARTING  = "departing"


# ---------------------------------------------------------------------------
# Service requirements
# ---------------------------------------------------------------------------

@dataclass
class ServiceRequirements:
    needs_fuel: bool = True
    fuel_amount: float = 5000.0          # gallons
    needs_baggage_unload: bool = True
    needs_baggage_load: bool = True
    baggage_count: int = 120
    needs_pushback: bool = True

    def required_services(self) -> list[str]:
        """Return list of service type names that must complete."""
        svcs = []
        if self.needs_fuel:
            svcs.append("fuel")
        if self.needs_baggage_unload:
            svcs.append("baggage_unload")
        if self.needs_baggage_load:
            svcs.append("baggage_load")
        if self.needs_pushback:
            svcs.append("pushback")
        return svcs


# ---------------------------------------------------------------------------
# Per-aircraft-type defaults
# ---------------------------------------------------------------------------

AIRCRAFT_TYPE_DEFAULTS: dict[str, dict] = {
    "B737":   {"fuel_amount": 5000,  "baggage_count": 120},
    "A320":   {"fuel_amount": 4500,  "baggage_count": 110},
    "B777":   {"fuel_amount": 12000, "baggage_count": 300},
    "CRJ900": {"fuel_amount": 2000,  "baggage_count": 60},
}


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

@dataclass
class Gate:
    gate_id: str
    terminal: str
    position_node: str
    occupied_by: Optional[str] = None   # flight_id
    available_at: float = 0.0

    def is_free(self, now: float) -> bool:
        return self.occupied_by is None and now >= self.available_at


# ---------------------------------------------------------------------------
# Runway
# ---------------------------------------------------------------------------

@dataclass
class Runway:
    runway_id: str
    active_direction: str
    entry_node: str
    exit_node: str
    state: RunwayState = RunwayState.FREE
    occupied_by: Optional[str] = None
    available_at: float = 0.0

    def is_free(self, now: float) -> bool:
        return self.state == RunwayState.FREE and now >= self.available_at


# ---------------------------------------------------------------------------
# Aircraft
# ---------------------------------------------------------------------------

@dataclass
class Aircraft:
    flight_id: str
    aircraft_type: str
    scheduled_arrival: float            # sim-seconds; None for dep-only
    scheduled_departure: float          # sim-seconds
    service_requirements: ServiceRequirements

    # Runtime state
    state: AircraftState = AircraftState.APPROACHING
    assigned_gate: Optional[str] = None   # gate_id
    position: Optional[str] = None        # current node
    path: list[str] = field(default_factory=list)
    segment_entered_at: float = 0.0       # time we entered current segment
    services_completed: set[str] = field(default_factory=set)

    # Timing
    actual_arrival: Optional[float] = None
    actual_departure: Optional[float] = None

    # Visual (set by renderer)
    pixel_x: float = 0.0
    pixel_y: float = 0.0
    pixel_heading: float = 0.0

    def all_services_done(self) -> bool:
        required = set(self.service_requirements.required_services())
        # pushback is handled separately via state transition
        required.discard("pushback")
        return required.issubset(self.services_completed)

    def __repr__(self) -> str:
        return f"<Aircraft {self.flight_id} {self.state.value} @{self.position}>"


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------

@dataclass
class Vehicle:
    vehicle_id: str
    vehicle_type: str
    state: VehicleState = VehicleState.IDLE
    position: str = "DEPOT"
    assigned_to: Optional[str] = None    # flight_id
    path: list[str] = field(default_factory=list)
    service_end_time: float = 0.0

    # Visual
    pixel_x: float = 0.0
    pixel_y: float = 0.0

    def is_available(self) -> bool:
        return self.state == VehicleState.IDLE and self.assigned_to is None

    def __repr__(self) -> str:
        return f"<{self.vehicle_type} {self.vehicle_id} {self.state.value}>"


@dataclass
class FuelTruck(Vehicle):
    vehicle_type: str = "fuel_truck"
    fuel_capacity: float = 20000.0       # gallons
    fuel_remaining: float = 20000.0
    services_since_refill: int = 0
    refill_threshold: int = 3


@dataclass
class BaggageTug(Vehicle):
    vehicle_type: str = "baggage_tug"
    capacity: int = 150                  # bags per trip


@dataclass
class PushbackTractor(Vehicle):
    vehicle_type: str = "pushback_tractor"


# ---------------------------------------------------------------------------
# Service task (used by dispatcher queue)
# ---------------------------------------------------------------------------

@dataclass
class ServiceTask:
    task_id: str
    flight_id: str
    service_type: str           # "fuel", "baggage_unload", "baggage_load", "pushback"
    gate_node: str
    created_at: float
    assigned_vehicle_id: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def duration(self, aircraft: Aircraft) -> float:
        """Return how many sim-seconds this service takes."""
        reqs = aircraft.service_requirements
        if self.service_type == "fuel":
            # 1 gallon/second
            return reqs.fuel_amount / 100.0
        elif self.service_type == "baggage_unload":
            return reqs.baggage_count * 0.5   # 0.5 sec per bag
        elif self.service_type == "baggage_load":
            return reqs.baggage_count * 0.5
        elif self.service_type == "pushback":
            return 120.0                       # 2 minutes flat
        return 60.0
