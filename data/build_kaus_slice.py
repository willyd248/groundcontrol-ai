#!/usr/bin/env python3
"""Build a KAUS slice: 6-8 gates closest to depot, filtered schedule, pruned graph.

Usage:
    python data/build_kaus_slice.py
"""

import json
import sys
import os
import networkx as nx

# Paths
GRAPH_PATH = os.path.join(os.path.dirname(__file__), "graphs", "kaus_taxiways.json")
SCHEDULE_PATH = os.path.join(os.path.dirname(__file__), "schedules", "kaus_20251210.json")
SLICE_GRAPH_PATH = os.path.join(os.path.dirname(__file__), "graphs", "kaus_slice.json")
SLICE_SCHEDULE_PATH = os.path.join(os.path.dirname(__file__), "schedules", "kaus_slice_20251210.json")

# Slice parameters
NUM_GATES = 8
TARGET_FLIGHTS_MIN = 30
TARGET_FLIGHTS_MAX = 50


def load_graph(path: str) -> nx.DiGraph:
    with open(path) as f:
        data = json.load(f)
    G = nx.DiGraph()
    for node in data["nodes"]:
        G.add_node(node["id"], node_type=node["node_type"],
                   pos=node["pos"], label=node.get("label", ""))
    for edge in data["edges"]:
        G.add_edge(edge["source"], edge["target"],
                   length=edge["length"], weight=edge["weight"])
    return G


def find_closest_gates(G: nx.DiGraph, depot: str, n: int) -> list[str]:
    """Find n gates closest to depot by travel time."""
    gates = [node for node, d in G.nodes(data=True) if d.get("node_type") == "gate"]
    dists = []
    for g in gates:
        try:
            dist = nx.shortest_path_length(G, depot, g, weight="weight")
            dists.append((dist, g))
        except nx.NetworkXNoPath:
            continue
    dists.sort()
    return [g for _, g in dists[:n]]


def extract_subgraph(G: nx.DiGraph, chosen_gates: list[str]) -> nx.DiGraph:
    """Extract minimal connected subgraph containing chosen gates, runways, and depot.

    Strategy: for each gate, find shortest path to each runway entry and to depot.
    Union of all path nodes = the subgraph.
    """
    # Key nodes we must include
    rwy_entries = [n for n, d in G.nodes(data=True) if d.get("node_type") == "runway_entry"]
    depots = [n for n, d in G.nodes(data=True) if d.get("node_type") == "depot"]
    must_include = set(chosen_gates + rwy_entries + depots)

    # Find all nodes on shortest paths between key node pairs
    path_nodes = set()
    endpoints = list(must_include)

    for src in chosen_gates:
        for tgt in rwy_entries + depots:
            try:
                path = nx.shortest_path(G, src, tgt, weight="weight")
                path_nodes.update(path)
            except nx.NetworkXNoPath:
                pass
            # Also reverse direction
            try:
                path = nx.shortest_path(G, tgt, src, weight="weight")
                path_nodes.update(path)
            except nx.NetworkXNoPath:
                pass

    # Also ensure depot ↔ runway connectivity
    for depot in depots:
        for rwy in rwy_entries:
            try:
                path = nx.shortest_path(G, depot, rwy, weight="weight")
                path_nodes.update(path)
            except nx.NetworkXNoPath:
                pass
            try:
                path = nx.shortest_path(G, rwy, depot, weight="weight")
                path_nodes.update(path)
            except nx.NetworkXNoPath:
                pass

    # Build subgraph
    sub = G.subgraph(path_nodes).copy()
    return sub


def graph_to_json(G: nx.DiGraph) -> dict:
    """Convert networkx graph to JSON format."""
    nodes = []
    for n, d in G.nodes(data=True):
        nodes.append({
            "id": n,
            "node_type": d.get("node_type", "intersection"),
            "pos": list(d.get("pos", [0, 0])),
            "label": d.get("label", ""),
        })
    edges = []
    for u, v, d in G.edges(data=True):
        edges.append({
            "source": u,
            "target": v,
            "length": d.get("length", 0),
            "weight": d.get("weight", 0),
        })
    return {"nodes": nodes, "edges": edges}


def filter_schedule(schedule: list[dict], num_flights: int) -> list[dict]:
    """Select a contiguous window of flights from the schedule.

    Since the schedule is sorted by time, take a morning window to get
    a natural burst of arrivals and departures.
    """
    # Start with turnaround flights (they exercise the full pipeline)
    turnarounds = [f for f in schedule
                   if not f.get("is_arrival_only") and not f.get("is_departure_only")]
    arr_only = [f for f in schedule if f.get("is_arrival_only")]
    dep_only = [f for f in schedule if f.get("is_departure_only")]

    # Take first N turnarounds + proportional arr/dep only
    n_turn = min(num_flights - 8, len(turnarounds))  # leave room for arr/dep only
    n_arr = min(4, len(arr_only))
    n_dep = min(4, len(dep_only))

    selected = turnarounds[:n_turn] + arr_only[:n_arr] + dep_only[:n_dep]

    # Sort by time
    def sort_key(e):
        arr = e["scheduled_arrival"] if e["scheduled_arrival"] is not None else float("inf")
        dep = e["scheduled_departure"] if e["scheduled_departure"] is not None else float("inf")
        return (arr, dep)

    selected.sort(key=sort_key)

    # Re-number flight IDs to avoid collisions
    for i, entry in enumerate(selected):
        entry["flight_id"] = f"KAUS{i+1:03d}"

    return selected


def main():
    print("Loading full KAUS graph...")
    G = load_graph(GRAPH_PATH)
    print(f"  {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    print(f"\nFinding {NUM_GATES} closest gates to DEPOT...")
    chosen_gates = find_closest_gates(G, "DEPOT", NUM_GATES)
    for g in chosen_gates:
        dist = nx.shortest_path_length(G, "DEPOT", g, weight="weight")
        print(f"  {g}: {dist:.1f}s from DEPOT")

    print("\nExtracting subgraph...")
    sub = extract_subgraph(G, chosen_gates)
    sub_types = {}
    for _, d in sub.nodes(data=True):
        t = d.get("node_type", "unknown")
        sub_types[t] = sub_types.get(t, 0) + 1
    print(f"  {sub.number_of_nodes()} nodes, {sub.number_of_edges()} edges")
    print(f"  Node types: {sub_types}")

    # Verify connectivity
    if nx.is_weakly_connected(sub):
        print("  Graph is weakly connected: OK")
    else:
        comps = list(nx.weakly_connected_components(sub))
        print(f"  WARNING: {len(comps)} components")

    # Save sliced graph
    graph_json = graph_to_json(sub)
    with open(SLICE_GRAPH_PATH, "w") as f:
        json.dump(graph_json, f, indent=2)
    print(f"\nSliced graph saved to {SLICE_GRAPH_PATH}")

    # Load and filter schedule
    print("\nFiltering schedule...")
    with open(SCHEDULE_PATH) as f:
        full_schedule = json.load(f)

    target = (TARGET_FLIGHTS_MIN + TARGET_FLIGHTS_MAX) // 2
    sliced = filter_schedule(full_schedule, target)
    print(f"  {len(sliced)} flights selected")

    turnarounds = sum(1 for f in sliced
                      if not f.get("is_arrival_only") and not f.get("is_departure_only"))
    arr_only = sum(1 for f in sliced if f.get("is_arrival_only"))
    dep_only = sum(1 for f in sliced if f.get("is_departure_only"))
    print(f"  Turnarounds: {turnarounds}, Arrival-only: {arr_only}, Departure-only: {dep_only}")

    from collections import Counter
    types = Counter(f["aircraft_type"] for f in sliced)
    print(f"  Aircraft types: {dict(types)}")

    # Time window
    arrivals = [f["scheduled_arrival"] for f in sliced if f["scheduled_arrival"] is not None]
    departures = [f["scheduled_departure"] for f in sliced if f["scheduled_departure"] is not None]
    if arrivals:
        print(f"  First arrival: {min(arrivals)}s ({min(arrivals)/3600:.1f}h)")
        print(f"  Last arrival: {max(arrivals)}s ({max(arrivals)/3600:.1f}h)")
    if departures:
        print(f"  Last departure: {max(departures)}s ({max(departures)/3600:.1f}h)")

    with open(SLICE_SCHEDULE_PATH, "w") as f:
        json.dump(sliced, f, indent=2)
    print(f"\nSliced schedule saved to {SLICE_SCHEDULE_PATH}")


if __name__ == "__main__":
    main()
