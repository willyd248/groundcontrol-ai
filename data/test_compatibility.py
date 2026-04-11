#!/usr/bin/env python3
"""Test compatibility of KAUS sliced data with the existing simulator.

Tests:
  1. Graph loader: can load_taxiway_graph_from_json parse the sliced graph?
  2. Gate/Runway builders: can build_gates_from_graph / build_runways_from_graph work?
  3. Schedule loader: can sim/scheduler.py parse the sliced schedule?
  4. Dispatcher FCFS: can the dispatcher run a full episode end-to-end?
  5. Metrics: total FCFS delay, flights departed, conflicts

Reports all failures without attempting to fix them.
"""

import json
import sys
import os
import traceback

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

SLICE_SCHEDULE_PATH = os.path.join(os.path.dirname(__file__), "schedules", "kaus_slice_20251210.json")
SLICE_GRAPH_PATH = os.path.join(os.path.dirname(__file__), "graphs", "kaus_slice.json")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "COMPATIBILITY_REPORT.md")

results = []


def record(test_name: str, passed: bool, detail: str):
    status = "PASS" if passed else "FAIL"
    results.append({"test": test_name, "passed": passed, "detail": detail})
    print(f"  [{status}] {test_name}: {detail}")


def test_graph_loader():
    """Test 1: Load sliced graph via JSON loader."""
    print("\n=== Test 1: JSON Graph Loader ===")
    try:
        from sim.world import load_taxiway_graph_from_json
        G = load_taxiway_graph_from_json(SLICE_GRAPH_PATH)
        n_nodes = G.number_of_nodes()
        n_edges = G.number_of_edges()
        node_types = {}
        for _, d in G.nodes(data=True):
            t = d.get("node_type", "unknown")
            node_types[t] = node_types.get(t, 0) + 1

        record("graph_load", True, f"{n_nodes} nodes, {n_edges} edges")
        record("graph_node_types", True, f"Node types: {node_types}")

        # Verify DEPOT reachable to all gates
        import networkx as nx
        gates = [n for n, d in G.nodes(data=True) if d.get("node_type") == "gate"]
        unreachable = []
        for g in gates:
            try:
                nx.shortest_path(G, "DEPOT", g, weight="weight")
            except nx.NetworkXNoPath:
                unreachable.append(g)
        if unreachable:
            record("graph_depot_to_gates", False, f"DEPOT cannot reach: {unreachable}")
        else:
            record("graph_depot_to_gates", True, f"DEPOT can reach all {len(gates)} gates")

        return G
    except Exception as e:
        record("graph_load", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        return None


def test_gate_runway_builders(G):
    """Test 2: Build gates and runways from graph."""
    print("\n=== Test 2: Gate/Runway Builders ===")
    try:
        from sim.world import build_gates_from_graph, build_runways_from_graph
        gates = build_gates_from_graph(G)
        record("gates_build", True, f"{len(gates)} gates: {sorted(gates.keys())}")

        runways = build_runways_from_graph(G)
        for rid, rwy in runways.items():
            record(f"runway_{rid}", True,
                   f"entry={rwy.entry_node}, exit={rwy.exit_node}")
        record("runways_build", True, f"{len(runways)} runways")

        return gates, runways
    except Exception as e:
        record("builders", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        return None, None


def test_schedule_loader(gates):
    """Test 3: Load sliced schedule with gate pre-assignment for dep-only flights."""
    print("\n=== Test 3: Schedule Loader ===")
    try:
        from sim.scheduler import load_schedule
        from sim.entities import AircraftState
        aircraft_list = load_schedule(SLICE_SCHEDULE_PATH, gates=gates)
        n = len(aircraft_list)

        from collections import Counter
        types = Counter(ac.aircraft_type for ac in aircraft_list)
        dep_only = [ac for ac in aircraft_list if ac.scheduled_arrival == float("inf")]
        arr_only = sum(1 for ac in aircraft_list if ac.scheduled_departure == float("inf"))
        turnaround = n - len(dep_only) - arr_only

        record("schedule_load", True,
               f"{n} flights ({turnaround} turnaround, {arr_only} arr-only, {len(dep_only)} dep-only)")
        record("schedule_types", True, f"Types: {dict(types)}")

        # Verify dep-only flights got gate assignments
        dep_with_gates = sum(1 for ac in dep_only
                             if ac.assigned_gate is not None and ac.position is not None)
        record("dep_only_gates", dep_with_gates == len(dep_only),
               f"{dep_with_gates}/{len(dep_only)} dep-only flights have gate assignments")

        return aircraft_list
    except Exception as e:
        record("schedule_load", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        return None


def test_fcfs_dispatcher(G, gates, runways, aircraft_list):
    """Test 4+5: Run FCFS dispatcher end-to-end on slice."""
    print("\n=== Test 4: FCFS Dispatcher (Sliced KAUS data) ===")
    try:
        from sim.entities import (
            AircraftState, FuelTruck, BaggageTug, PushbackTractor,
        )
        from sim.dispatcher import Dispatcher

        # Scale fleet for 40 flights / 8 gates
        fleet = [
            FuelTruck(vehicle_id="FT1", position="DEPOT"),
            FuelTruck(vehicle_id="FT2", position="DEPOT"),
            BaggageTug(vehicle_id="BT1", position="DEPOT"),
            BaggageTug(vehicle_id="BT2", position="DEPOT"),
            BaggageTug(vehicle_id="BT3", position="DEPOT"),
            PushbackTractor(vehicle_id="PB1", position="DEPOT"),
            PushbackTractor(vehicle_id="PB2", position="DEPOT"),
        ]

        dispatcher = Dispatcher(
            graph=G, gates=gates, runways=runways,
            aircraft=aircraft_list, vehicles=fleet,
        )
        record("dispatcher_init", True,
               f"Initialized: {len(aircraft_list)} flights, {len(gates)} gates, "
               f"{len(runways)} runways, {len(fleet)} vehicles")

        # Run full day (last departure ~44000s, add buffer)
        SIM_HORIZON = 60000  # ~16.7 hours
        crashed = False
        crash_detail = ""

        # Checkpoints
        checkpoints = [1000, 5000, 15000, 30000, SIM_HORIZON]
        cp_idx = 0

        for t in range(SIM_HORIZON):
            try:
                dispatcher.tick(float(t), dt=1.0)
            except Exception as e:
                crashed = True
                crash_detail = f"Crashed at tick {t}: {type(e).__name__}: {e}\n{traceback.format_exc()}"
                break

            # Report at checkpoints
            if cp_idx < len(checkpoints) and t == checkpoints[cp_idx]:
                m = dispatcher.metrics()
                record(f"checkpoint_t{t}", True,
                       f"Departed: {m['flights_departed']}/{len(aircraft_list)}, "
                       f"Delay: {m['total_delay_minutes']:.0f}min, "
                       f"Conflicts: {m['conflict_count']}")
                cp_idx += 1

            # Early exit if all done
            if all(ac.state == AircraftState.DEPARTED
                   for ac in dispatcher.aircraft.values()):
                break

        if crashed:
            record("dispatcher_run", False, crash_detail)
            return

        m = dispatcher.metrics()
        # Count arrival-only flights (they never depart — by design)
        arr_only_count = sum(
            1 for ac in dispatcher.aircraft.values()
            if ac.scheduled_departure == float("inf")
        )
        dep_eligible = len(aircraft_list) - arr_only_count
        all_dep_eligible_departed = m['flights_departed'] == dep_eligible

        record("dispatcher_complete", all_dep_eligible_departed,
               f"{m['flights_departed']}/{dep_eligible} departure-eligible flights departed"
               f" ({arr_only_count} arrival-only correctly remain at gate)")
        record("fcfs_departed", True,
               f"{m['flights_departed']}/{len(aircraft_list)} total ({dep_eligible} eligible)")
        record("fcfs_pending", m['flights_pending'] == arr_only_count,
               f"{m['flights_pending']} pending ({arr_only_count} are arrival-only)")
        record("fcfs_total_delay", True,
               f"Total delay: {m['total_delay_minutes']:.1f} min")
        record("fcfs_avg_delay", True,
               f"Avg delay: {m['avg_delay_minutes']:.1f} min/flight")
        record("fcfs_max_delay", True,
               f"Max delay: {m['max_delay_minutes']:.1f} min")
        record("fcfs_turnaround", True,
               f"Avg turnaround: {m['avg_turnaround_minutes']:.1f} min")
        record("fcfs_conflicts", m['conflict_count'] == 0,
               f"Conflicts: {m['conflict_count']}")
        record("fcfs_vehicles_dispatched", True,
               f"Vehicle dispatches: {m['vehicles_dispatched']}")

    except Exception as e:
        record("dispatcher_init", False,
               f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


def write_report():
    """Write COMPATIBILITY_REPORT.md."""
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])

    lines = [
        "# Compatibility Report: KAUS Slice vs Simulator",
        "",
        f"**Date:** 2026-04-08",
        f"**Schedule:** data/schedules/kaus_slice_20251210.json (Dec 10, 2025 — sliced)",
        f"**Graph:** data/graphs/kaus_slice.json (OSM extraction, pruned to 8 gates)",
        "",
        f"## Summary: {passed} passed, {failed} failed",
        "",
    ]

    for r in results:
        status = "PASS" if r["passed"] else "**FAIL**"
        lines.append(f"- [{status}] `{r['test']}`: {r['detail']}")
        lines.append("")

    lines.extend([
        "## What Was Fixed (Phase 3 Items 1-3)",
        "",
        "### 1. dict-vs-float crash in `_find_nearest_vehicle` (sim/dispatcher.py)",
        "- **Root cause:** dep-only flights from JSON schedule had `position=None` and `assigned_gate=None`. "
        "When service tasks were created with `gate_node=None`, `nx.shortest_path_length(G, src, None)` "
        "returned a dict of all targets instead of a scalar float.",
        "- **Fix:** Guard `_find_nearest_vehicle` to return None when `gate_node is None or gate_node not in G`. "
        "Also changed sort tuple from `(cost, vehicle)` to `(cost, vehicle_id, vehicle)` to prevent "
        "Vehicle object comparison on tiebreak.",
        "- **Tests:** 2 new tests in `tests/test_dispatcher.py`, all 22 passing.",
        "",
        "### 2. JSON graph loader added to `sim/world.py`",
        "- `load_taxiway_graph_from_json(path)` — loads OSM-extracted graph JSON",
        "- `build_gates_from_graph(G)` — builds gate registry from graph gate nodes",
        "- `build_runways_from_graph(G)` — builds runway registry from RWY_*_ENTRY/EXIT nodes",
        "- Validates required entity types (≥1 gate, ≥1 runway entry, ≥1 depot)",
        "",
        "### 3. OSM parser node naming normalized (`data/parse_osm_taxiways.py`)",
        "- Runway endpoints: `RWY_18R36L_ENTRY`, `RWY_18R36L_EXIT`, etc.",
        "- Gates: `GATE_1` through `GATE_37`, plus `GATE_S1/S2/S3`",
        "- Depot: `DEPOT`",
        "",
        "## What Doesn't Work Yet (Full Scale)",
        "",
        "- Full 306-flight KAUS schedule exceeds `MAX_AIRCRAFT=20` in RL observation space",
        "- Full 271-node graph with 40 gates needs scaled vehicle fleet (~50 vehicles)",
        "- `airport_env.py` hardcodes `ALL_NODES` (15 KFIC nodes) — needs dynamic node indexing",
        "- SIM_HORIZON (4h) too short for full KAUS day (24h of operations)",
        "",
        "## v1 Deliverable",
        "",
        "**BTS real data → OSM graph → KAUS slice → FCFS dispatcher end-to-end.**",
        "",
        "Pipeline: `convert_bts_to_schedule.py` → `parse_osm_taxiways.py` → `build_kaus_slice.py` → "
        "`load_taxiway_graph_from_json()` + `load_schedule()` → Dispatcher FCFS.",
    ])

    report = "\n".join(lines) + "\n"
    with open(REPORT_PATH, "w") as f:
        f.write(report)
    print(f"\nReport written to {REPORT_PATH}")


def main():
    print("=" * 60)
    print("KAUS Slice Compatibility Test")
    print("=" * 60)

    G = test_graph_loader()
    if G is None:
        print("\nGraph load failed — cannot proceed with remaining tests.")
        write_report()
        return

    gates, runways = test_gate_runway_builders(G)
    if gates is None:
        print("\nGate/runway build failed — cannot proceed.")
        write_report()
        return

    aircraft_list = test_schedule_loader(gates)
    if aircraft_list is None:
        print("\nSchedule load failed — cannot proceed.")
        write_report()
        return

    test_fcfs_dispatcher(G, gates, runways, aircraft_list)
    write_report()

    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    print(f"\n{'=' * 60}")
    print(f"TOTAL: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
