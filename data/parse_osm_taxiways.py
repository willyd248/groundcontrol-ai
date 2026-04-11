#!/usr/bin/env python3
"""Parse KAUS taxiway data from OpenStreetMap into a networkx-compatible graph.

Fetches taxiway, runway, and gate data from OSM Overpass API and produces
a graph JSON compatible with sim/world.py's networkx DiGraph format.

Usage:
    python data/parse_osm_taxiways.py data/graphs/kaus_taxiways.json
"""

import json
import math
import sys
from urllib.request import urlopen, Request
from urllib.parse import quote


# KAUS bounding box (slightly padded)
BBOX = "30.18,-97.69,30.21,-97.65"

OVERPASS_QUERY = f"""
[out:json][timeout:30];
(
  way["aeroway"="taxiway"]({BBOX});
  way["aeroway"="runway"]({BBOX});
  node["aeroway"="gate"]({BBOX});
);
out body;
>;
out skel qt;
"""

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Speeds matching sim/world.py
AIRCRAFT_SPEED = 7.0  # m/s


def fetch_osm_data(cache_path: str = None) -> dict:
    """Fetch KAUS aeroway data from Overpass API, or load from cache."""
    if cache_path:
        import os
        if os.path.exists(cache_path):
            print(f"Loading cached OSM data from {cache_path}...")
            with open(cache_path) as f:
                data = json.load(f)
            print(f"  Loaded {len(data['elements'])} elements")
            return data

    print("Fetching OSM data for KAUS via POST...")
    from urllib.parse import urlencode
    post_data = urlencode({"data": OVERPASS_QUERY}).encode("utf-8")
    req = Request(OVERPASS_URL, data=post_data, headers={"User-Agent": "AirportSim/1.0"})
    with urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    print(f"  Received {len(data['elements'])} elements")

    # Cache for future runs
    if cache_path:
        with open(cache_path, "w") as f:
            json.dump(data, f)

    return data


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters between two lat/lon points."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_graph(osm_data: dict) -> dict:
    """Build a graph from OSM data.

    Returns a dict with:
    - nodes: list of {id, node_type, pos, label}
    - edges: list of {source, target, length, weight}

    Compatible with sim/world.py's graph structure.
    """
    # Parse elements
    nodes_by_id = {}  # OSM node id → {lat, lon}
    ways = []         # taxiway/runway ways
    gates = []        # gate nodes

    for el in osm_data["elements"]:
        if el["type"] == "node":
            nodes_by_id[el["id"]] = {"lat": el["lat"], "lon": el["lon"]}
            if el.get("tags", {}).get("aeroway") == "gate":
                gates.append({
                    "id": el["id"],
                    "lat": el["lat"],
                    "lon": el["lon"],
                    "ref": el.get("tags", {}).get("ref", ""),
                })
        elif el["type"] == "way":
            tags = el.get("tags", {})
            aeroway = tags.get("aeroway", "")
            if aeroway in ("taxiway", "runway"):
                ways.append({
                    "id": el["id"],
                    "aeroway": aeroway,
                    "ref": tags.get("ref", tags.get("name", "")),
                    "nodes": el.get("nodes", []),
                })

    print(f"  Taxiways: {sum(1 for w in ways if w['aeroway'] == 'taxiway')}")
    print(f"  Runways: {sum(1 for w in ways if w['aeroway'] == 'runway')}")
    print(f"  Gates: {len(gates)}")

    # Build graph nodes and edges from ways
    # Strategy: each OSM node that appears in 2+ ways is an intersection
    # We simplify: keep intersection nodes + endpoints, collapse intermediate nodes into edge lengths

    node_usage = {}  # osm_node_id → count of ways using it
    for way in ways:
        for nid in way["nodes"]:
            node_usage[nid] = node_usage.get(nid, 0) + 1

    # Identify key nodes: endpoints of ways + intersections (used by 2+ ways)
    key_nodes = set()
    for way in ways:
        if way["nodes"]:
            key_nodes.add(way["nodes"][0])   # start
            key_nodes.add(way["nodes"][-1])  # end
        for nid in way["nodes"]:
            if node_usage.get(nid, 0) >= 2:
                key_nodes.add(nid)

    # Build graph edges by walking each way and creating edges between consecutive key nodes
    graph_nodes = {}  # node_id_str → {node_type, pos, label}
    graph_edges = []  # {source, target, length, weight}

    # Pre-build runway endpoint name mapping:
    # Each runway way's start → RWY_<ref>_ENTRY, end → RWY_<ref>_EXIT
    rwy_node_names = {}  # osm_node_id → named string
    rwy_counter = 0
    for way in ways:
        if way["aeroway"] != "runway" or len(way["nodes"]) < 2:
            continue
        ref = way["ref"].replace("/", "") if way["ref"] else f"UNK{rwy_counter}"
        rwy_counter += 1
        start_id = way["nodes"][0]
        end_id = way["nodes"][-1]
        rwy_node_names[start_id] = f"RWY_{ref}_ENTRY"
        rwy_node_names[end_id] = f"RWY_{ref}_EXIT"

    def node_id_str(osm_id: int) -> str:
        if osm_id in rwy_node_names:
            return rwy_node_names[osm_id]
        return f"N{osm_id}"

    def add_graph_node(osm_id: int, node_type: str = "intersection", label: str = ""):
        nid = node_id_str(osm_id)
        if nid not in graph_nodes and osm_id in nodes_by_id:
            nd = nodes_by_id[osm_id]
            graph_nodes[nid] = {
                "id": nid,
                "node_type": node_type,
                "pos": [nd["lon"], nd["lat"]],  # [lon, lat] for geospatial
                "label": label,
            }

    for way in ways:
        way_nodes = way["nodes"]
        if len(way_nodes) < 2:
            continue

        is_runway = way["aeroway"] == "runway"

        # Walk through way, accumulate distance between key nodes
        prev_key = None
        accumulated_dist = 0.0

        for i, nid in enumerate(way_nodes):
            if i > 0:
                prev_nid = way_nodes[i - 1]
                if prev_nid in nodes_by_id and nid in nodes_by_id:
                    n1, n2 = nodes_by_id[prev_nid], nodes_by_id[nid]
                    accumulated_dist += haversine(n1["lat"], n1["lon"], n2["lat"], n2["lon"])

            if nid in key_nodes:
                # Determine node type
                if is_runway and (i == 0 or i == len(way_nodes) - 1):
                    ntype = "runway_entry"
                else:
                    ntype = "intersection"
                label = way["ref"] if nid == way_nodes[0] else ""
                add_graph_node(nid, ntype, label)

                if prev_key is not None and accumulated_dist > 0:
                    src = node_id_str(prev_key)
                    tgt = node_id_str(nid)
                    weight = accumulated_dist / AIRCRAFT_SPEED

                    # Add bidirectional edges
                    graph_edges.append({
                        "source": src,
                        "target": tgt,
                        "length": round(accumulated_dist, 1),
                        "weight": round(weight, 1),
                    })
                    graph_edges.append({
                        "source": tgt,
                        "target": src,
                        "length": round(accumulated_dist, 1),
                        "weight": round(weight, 1),
                    })

                prev_key = nid
                accumulated_dist = 0.0

    # Add gate nodes and connect to nearest taxiway node
    for gate in gates:
        gid = f"GATE_{gate['ref']}" if gate["ref"] else f"GATE_{gate['id']}"
        graph_nodes[gid] = {
            "id": gid,
            "node_type": "gate",
            "pos": [gate["lon"], gate["lat"]],
            "label": gate["ref"],
        }

        # Find nearest graph node (not a gate) to connect to
        min_dist = float("inf")
        nearest = None
        for nid, nd in graph_nodes.items():
            if nd["node_type"] == "gate":
                continue
            dist = haversine(gate["lat"], gate["lon"], nd["pos"][1], nd["pos"][0])
            if dist < min_dist:
                min_dist = dist
                nearest = nid

        if nearest and min_dist < 500:  # max 500m connection
            weight = min_dist / AIRCRAFT_SPEED
            graph_edges.append({
                "source": gid,
                "target": nearest,
                "length": round(min_dist, 1),
                "weight": round(weight, 1),
            })
            graph_edges.append({
                "source": nearest,
                "target": gid,
                "length": round(min_dist, 1),
                "weight": round(weight, 1),
            })

    # Add a DEPOT node (roughly at the maintenance area, west side of airport)
    depot_lat, depot_lon = 30.1960, -97.6750
    graph_nodes["DEPOT"] = {
        "id": "DEPOT",
        "node_type": "depot",
        "pos": [depot_lon, depot_lat],
        "label": "DEPOT",
    }

    # Connect depot to nearest intersection
    min_dist = float("inf")
    nearest = None
    for nid, nd in graph_nodes.items():
        if nd["node_type"] != "intersection":
            continue
        dist = haversine(depot_lat, depot_lon, nd["pos"][1], nd["pos"][0])
        if dist < min_dist:
            min_dist = dist
            nearest = nid

    if nearest:
        weight = min_dist / AIRCRAFT_SPEED
        graph_edges.append({"source": "DEPOT", "target": nearest, "length": round(min_dist, 1), "weight": round(weight, 1)})
        graph_edges.append({"source": nearest, "target": "DEPOT", "length": round(min_dist, 1), "weight": round(weight, 1)})

    return {
        "nodes": list(graph_nodes.values()),
        "edges": graph_edges,
    }


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <output.json>")
        sys.exit(1)

    output_path = sys.argv[1]

    cache_path = output_path.replace("graphs/", "raw/").replace("taxiways.json", "osm.json")
    osm_data = fetch_osm_data(cache_path=cache_path)
    graph = build_graph(osm_data)

    with open(output_path, "w") as f:
        json.dump(graph, f, indent=2)

    print(f"\nGraph written to {output_path}")
    print(f"  Nodes: {len(graph['nodes'])}")
    print(f"  Edges: {len(graph['edges'])}")

    # Breakdown
    from collections import Counter
    types = Counter(n["node_type"] for n in graph["nodes"])
    print(f"  Node types: {dict(types)}")


if __name__ == "__main__":
    main()
