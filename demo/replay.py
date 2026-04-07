"""
replay.py — Frame-by-frame replay system for the side-by-side demo.

During a live run, ReplayRecorder snapshots both sim states every sim-second
into a compact dict representation. After the episode ends, ReplayController
lets the user step backward/forward through those snapshots.

Snapshot schema (per side, per tick):
  {
    "sim_time": float,
    "aircraft": [
      {"flight_id": str, "state": str, "position": str | None,
       "path": list[str], "services_completed": list[str],
       "scheduled_departure": float, "actual_departure": float | None},
      ...
    ],
    "vehicles": [
      {"vehicle_id": str, "vehicle_type": str, "state": str,
       "position": str},
      ...
    ],
    "metrics": dict,   # from dispatcher.metrics()
  }
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FrameSnapshot:
    """One complete snapshot of both sides at a given sim-second."""
    sim_time: float
    fcfs: dict[str, Any]
    agent: dict[str, Any]


def _snapshot_side(dispatcher, sim_time: float) -> dict[str, Any]:
    """Compact snapshot of one dispatcher's current state."""
    aircraft_snap = []
    for ac in dispatcher.aircraft.values():
        aircraft_snap.append({
            "flight_id":          ac.flight_id,
            "state":              ac.state.value,
            "position":           ac.position,
            "path":               list(ac.path),
            "services_completed": list(ac.services_completed),
            "scheduled_departure": ac.scheduled_departure,
            "actual_departure":   ac.actual_departure,
        })

    vehicles_snap = []
    for v in dispatcher.vehicles.values():
        vehicles_snap.append({
            "vehicle_id":   v.vehicle_id,
            "vehicle_type": v.vehicle_type,
            "state":        v.state.value,
            "position":     v.position,
        })

    return {
        "sim_time": sim_time,
        "aircraft": aircraft_snap,
        "vehicles": vehicles_snap,
        "metrics":  dispatcher.metrics(),
    }


class ReplayRecorder:
    """
    Records snapshots during a live run.
    Call record() every sim-second for both dispatchers.
    """

    def __init__(self) -> None:
        self._frames: list[FrameSnapshot] = []

    def record(
        self,
        sim_time: float,
        fcfs_dispatcher,
        agent_dispatcher,
    ) -> None:
        frame = FrameSnapshot(
            sim_time=sim_time,
            fcfs=_snapshot_side(fcfs_dispatcher, sim_time),
            agent=_snapshot_side(agent_dispatcher, sim_time),
        )
        self._frames.append(frame)

    @property
    def frames(self) -> list[FrameSnapshot]:
        return self._frames

    def __len__(self) -> int:
        return len(self._frames)


class ReplayController:
    """
    Navigates through recorded frames after an episode ends.

    Usage:
        ctrl = ReplayController(recorder.frames)
        ctrl.current_frame  → FrameSnapshot at current position
        ctrl.step_forward() / ctrl.step_backward()
        ctrl.jump_to(index)
    """

    def __init__(self, frames: list[FrameSnapshot]) -> None:
        if not frames:
            raise ValueError("Cannot replay an empty recording.")
        self._frames = frames
        self._idx = len(frames) - 1   # start at end of episode

    @property
    def current_frame(self) -> FrameSnapshot:
        return self._frames[self._idx]

    @property
    def index(self) -> int:
        return self._idx

    @property
    def total(self) -> int:
        return len(self._frames)

    def step_forward(self, n: int = 1) -> None:
        self._idx = min(self._idx + n, len(self._frames) - 1)

    def step_backward(self, n: int = 1) -> None:
        self._idx = max(self._idx - n, 0)

    def jump_to(self, index: int) -> None:
        self._idx = max(0, min(index, len(self._frames) - 1))

    def at_start(self) -> bool:
        return self._idx == 0

    def at_end(self) -> bool:
        return self._idx == len(self._frames) - 1


# ---------------------------------------------------------------------------
# Lightweight proxy objects for the panel renderer
# ---------------------------------------------------------------------------
# The panel renderer calls ac.state.value, ac.position, ac.path, etc.
# These proxies let us render from snapshot dicts without touching real entities.

class _AircraftProxy:
    """Read-only proxy that looks like an Aircraft to the panel renderer."""

    __slots__ = (
        "flight_id", "state", "position", "path",
        "services_completed", "scheduled_departure", "actual_departure",
        "pixel_x", "pixel_y",
    )

    def __init__(self, snap: dict) -> None:
        from sim.entities import AircraftState
        self.flight_id           = snap["flight_id"]
        self.state               = AircraftState(snap["state"])
        self.position            = snap["position"]
        self.path                = snap["path"]
        self.services_completed  = set(snap["services_completed"])
        self.scheduled_departure = snap["scheduled_departure"]
        self.actual_departure    = snap["actual_departure"]
        self.pixel_x = 0.0
        self.pixel_y = 0.0


class _VehicleProxy:
    """Read-only proxy that looks like a Vehicle to the panel renderer."""

    __slots__ = ("vehicle_id", "vehicle_type", "state", "position", "pixel_x", "pixel_y")

    def __init__(self, snap: dict) -> None:
        from sim.entities import VehicleState, FuelTruck, BaggageTug, PushbackTractor
        self.vehicle_id   = snap["vehicle_id"]
        self.vehicle_type = snap["vehicle_type"]
        self.state        = VehicleState(snap["state"])
        self.position     = snap["position"]
        self.pixel_x = 0.0
        self.pixel_y = 0.0

    # Make isinstance checks work for color-coding in panel renderer
    def _is_fuel_truck(self) -> bool:
        return self.vehicle_type == "fuel_truck"

    def _is_baggage_tug(self) -> bool:
        return self.vehicle_type == "baggage_tug"


def proxies_from_snapshot(snap: dict) -> tuple[list, list]:
    """Return (aircraft_list, vehicle_list) proxy objects from a side snapshot."""
    aircraft = [_AircraftProxy(a) for a in snap["aircraft"]]
    vehicles  = [_VehicleProxy(v) for v in snap["vehicles"]]
    return aircraft, vehicles
