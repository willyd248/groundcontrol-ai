"""
main.py — Simulation entry point.

Usage:
    python -m sim.main                        # visual mode (pygame)
    python -m sim.main --headless             # headless, prints final metrics
    python -m sim.main --headless --speed 600 # 10× faster headless
    python -m sim.main --schedule path.json   # custom schedule

Speed is the simulated-seconds-per-wall-second ratio.
Default: 60 (1 sim-minute per real-second).
Headless runs as fast as possible.
"""

from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

from sim.world import build_taxiway_graph, build_gates, build_runways
from sim.scheduler import load_schedule
from sim.entities import (
    FuelTruck, BaggageTug, PushbackTractor, AircraftState,
)
from sim.dispatcher import Dispatcher


# ---- Vehicle fleet ----
def build_fleet():
    return [
        FuelTruck(vehicle_id="FT1", position="DEPOT"),
        FuelTruck(vehicle_id="FT2", position="DEPOT"),
        FuelTruck(vehicle_id="FT3", position="DEPOT"),
        BaggageTug(vehicle_id="BT1", position="DEPOT"),
        BaggageTug(vehicle_id="BT2", position="DEPOT"),
        BaggageTug(vehicle_id="BT3", position="DEPOT"),
        PushbackTractor(vehicle_id="PB1", position="DEPOT"),
        PushbackTractor(vehicle_id="PB2", position="DEPOT"),
    ]


def run(
    schedule_path: str = "schedule.json",
    headless: bool = False,
    speed: int = 60,
    max_sim_seconds: int = 14400,  # 4 hours max
) -> dict:
    """Run the simulation and return final metrics."""

    # Build world
    G       = build_taxiway_graph()
    gates   = build_gates()
    runways = build_runways()
    fleet   = build_fleet()

    # Load schedule
    aircraft_list = load_schedule(schedule_path)

    # Build dispatcher
    dispatcher = Dispatcher(
        graph=G,
        gates=gates,
        runways=runways,
        aircraft=aircraft_list,
        vehicles=fleet,
    )

    # Renderer (only in visual mode)
    renderer = None
    if not headless:
        try:
            from sim.render import Renderer
            renderer = Renderer(G)
        except Exception as e:
            print(f"[warn] Pygame unavailable, falling back to headless: {e}")
            headless = True

    sim_time    = 0.0
    dt          = 1.0          # 1 simulated second per tick
    wall_start  = time.time()

    print(f"[KFIC] Simulation start — {len(aircraft_list)} flights loaded")
    print(f"[KFIC] Mode: {'headless' if headless else 'visual'}  Speed: {speed}×")

    # Determine sim end: all flights departed + 30 min buffer, or hard cap
    def all_done() -> bool:
        return all(
            a.state == AircraftState.DEPARTED
            for a in aircraft_list
        )

    # Determine the latest scheduled departure in the schedule
    latest_dep = max(
        (a.scheduled_departure for a in aircraft_list if a.scheduled_departure < float("inf")),
        default=7200.0,
    )
    sim_end = min(latest_dep + 3600.0, max_sim_seconds)

    fps_cap = 60  # visual FPS

    while sim_time < sim_end:
        if renderer:
            if not renderer.handle_events():
                print("[KFIC] User quit.")
                break
            renderer.draw(
                aircraft=aircraft_list,
                vehicles=fleet,
                sim_time=sim_time,
                metrics=dispatcher.metrics(),
                speed=speed,
            )
            renderer.clock.tick(fps_cap)
            sim_time += speed / fps_cap

        else:
            # Headless: run as fast as possible
            dispatcher.tick(sim_time, dt)
            sim_time += dt
            if all_done():
                print(f"[KFIC] All flights departed at t={sim_time:.0f}s")
                break
            continue

        # Visual mode also ticks
        dispatcher.tick(sim_time, dt * speed / fps_cap)

    final = dispatcher.metrics()
    _print_metrics(final, sim_time)
    return final


def _print_metrics(m: dict, sim_time: float) -> None:
    print()
    print("=" * 44)
    print("  KFIC FINAL METRICS")
    print("=" * 44)
    print(f"  Sim time elapsed   : {_fmt_time(sim_time)}")
    print(f"  Flights departed   : {m['flights_departed']}")
    print(f"  Flights pending    : {m['flights_pending']}")
    print(f"  Total delay        : {m['total_delay_minutes']:.1f} min")
    print(f"  Avg delay/flight   : {m['avg_delay_minutes']:.1f} min")
    print(f"  Max delay/flight   : {m['max_delay_minutes']:.1f} min")
    print(f"  Avg turnaround     : {m['avg_turnaround_minutes']:.1f} min")
    print(f"  Conflict count     : {m['conflict_count']}")
    print(f"  Vehicles dispatched: {m['vehicles_dispatched']}")
    print(f"  Fuel truck refills : {m['fuel_truck_refills']}")
    print("=" * 44)
    if m['conflict_count'] > 0:
        print("  !! CONFLICTS DETECTED — simulator has a bug !!")
    else:
        print("  Zero conflicts. Dispatcher is safe.")
    print()


def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def main() -> None:
    parser = argparse.ArgumentParser(description="KFIC Ground Ops Simulator")
    parser.add_argument("--headless", action="store_true", help="No pygame window")
    parser.add_argument("--speed", type=int, default=60, help="Sim speed multiplier")
    parser.add_argument("--schedule", default="schedule.json", help="Path to schedule JSON")
    args = parser.parse_args()

    result = run(
        schedule_path=args.schedule,
        headless=args.headless,
        speed=args.speed,
    )
    sys.exit(0 if result["conflict_count"] == 0 else 1)


if __name__ == "__main__":
    main()
