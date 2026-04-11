"""
world.py — Taxiway graph for fictional airport KFIC.

Layout (schematic):

  DEPOT ── TWY_SERVICE ─────────────────────────────────────────────────────┐
                │                                                            │
  RWY_09L_EXIT──INTER_NW──TWY_NORTH──INTER_NE──RWY_09R_EXIT                 │
                │               │         │                                  │
          RWY_09L_ENTRY   TWY_A_ENTRY  TWY_B_ENTRY                          │
                │               │         │                                  │
          RWY_09R_ENTRY    GATE_A1,A2,A3  GATE_B1,B2,B3 ◄──────────────────┘
                                                          (service road loop)

Runways:
  09L/27R: aircraft enter at RWY_09L_ENTRY for departure, exit at INTER_NW after landing
  09R/27L: aircraft enter at RWY_09R_ENTRY for departure, exit at INTER_NE after landing
"""

from __future__ import annotations
import networkx as nx
from pathlib import Path
from sim.entities import Gate, Runway, RunwayState

# ---------------------------------------------------------------------------
# Node positions for rendering (pixel coords, 1200×700 canvas)
# ---------------------------------------------------------------------------

NODE_POSITIONS: dict[str, tuple[float, float]] = {
    "DEPOT":          (80,  350),
    "TWY_SERVICE":    (200, 350),
    "INTER_NW":       (320, 200),
    "TWY_NORTH":      (600, 200),
    "INTER_NE":       (880, 200),
    "TWY_A_ENTRY":    (400, 350),
    "TWY_B_ENTRY":    (760, 350),
    "GATE_A1":        (300, 500),
    "GATE_A2":        (450, 500),
    "GATE_A3":        (560, 500),
    "GATE_B1":        (680, 500),
    "GATE_B2":        (790, 500),
    "GATE_B3":        (900, 500),
    "RWY_09L_ENTRY":  (320,  80),
    "RWY_09R_ENTRY":  (880,  80),
    "RWY_09L_EXIT":   (320, 200),   # same as INTER_NW (landing exits here)
    "RWY_09R_EXIT":   (880, 200),   # same as INTER_NE
}

# Alias: runway exits merge with intersections
RWY_09L_LAND_EXIT = "INTER_NW"
RWY_09R_LAND_EXIT = "INTER_NE"

AIRCRAFT_SPEED  = 7.0   # m/s on taxiways (~14 kts)
VEHICLE_SPEED   = 5.0   # m/s for service vehicles

SEPARATION_TIME = 15.0  # seconds — minimum gap before entering a segment


def build_taxiway_graph() -> nx.DiGraph:
    """
    Build and return the directed taxiway graph for KFIC.
    Each edge has:
      - weight: travel time in seconds (length / speed)
      - length: metres
      - occupied_by: None initially
    """
    G = nx.DiGraph()

    # Add all nodes with type metadata
    node_types = {
        "DEPOT":          "depot",
        "TWY_SERVICE":    "intersection",
        "INTER_NW":       "intersection",
        "TWY_NORTH":      "intersection",
        "INTER_NE":       "intersection",
        "TWY_A_ENTRY":    "intersection",
        "TWY_B_ENTRY":    "intersection",
        "GATE_A1":        "gate",
        "GATE_A2":        "gate",
        "GATE_A3":        "gate",
        "GATE_B1":        "gate",
        "GATE_B2":        "gate",
        "GATE_B3":        "gate",
        "RWY_09L_ENTRY":  "runway_entry",
        "RWY_09R_ENTRY":  "runway_entry",
    }
    for node, ntype in node_types.items():
        G.add_node(node, node_type=ntype, pos=NODE_POSITIONS.get(node, (0, 0)))

    def add_edge(u: str, v: str, length: float, bidirectional: bool = True) -> None:
        travel_time = length / AIRCRAFT_SPEED
        G.add_edge(u, v, length=length, weight=travel_time, occupied_by=None)
        if bidirectional:
            G.add_edge(v, u, length=length, weight=travel_time, occupied_by=None)

    # ---- Depot / service road ----
    add_edge("DEPOT",       "TWY_SERVICE",  120)
    add_edge("TWY_SERVICE", "INTER_NW",     200)
    add_edge("TWY_SERVICE", "TWY_A_ENTRY",  150)
    add_edge("TWY_SERVICE", "TWY_B_ENTRY",  150)

    # ---- North taxiway spine ----
    add_edge("INTER_NW",    "TWY_NORTH",    280)
    add_edge("TWY_NORTH",   "INTER_NE",     280)

    # ---- Terminal A spur ----
    add_edge("TWY_A_ENTRY", "INTER_NW",     180)
    add_edge("TWY_A_ENTRY", "GATE_A1",      100)
    add_edge("TWY_A_ENTRY", "GATE_A2",       60)
    add_edge("TWY_A_ENTRY", "GATE_A3",      100)

    # ---- Terminal B spur ----
    add_edge("TWY_B_ENTRY", "INTER_NE",     180)
    add_edge("TWY_B_ENTRY", "GATE_B1",      100)
    add_edge("TWY_B_ENTRY", "GATE_B2",       60)
    add_edge("TWY_B_ENTRY", "GATE_B3",      100)

    # ---- Runway connections (departure entries) ----
    add_edge("INTER_NW",    "RWY_09L_ENTRY", 120)
    add_edge("INTER_NE",    "RWY_09R_ENTRY", 120)

    return G


# ---------------------------------------------------------------------------
# Gates registry
# ---------------------------------------------------------------------------

def build_gates() -> dict[str, Gate]:
    return {
        "A1": Gate("A1", "A", "GATE_A1"),
        "A2": Gate("A2", "A", "GATE_A2"),
        "A3": Gate("A3", "A", "GATE_A3"),
        "B1": Gate("B1", "B", "GATE_B1"),
        "B2": Gate("B2", "B", "GATE_B2"),
        "B3": Gate("B3", "B", "GATE_B3"),
    }


# ---------------------------------------------------------------------------
# Runways registry
# ---------------------------------------------------------------------------

def build_runways() -> dict[str, Runway]:
    return {
        "09L/27R": Runway(
            runway_id="09L/27R",
            active_direction="09L",
            entry_node="RWY_09L_ENTRY",
            exit_node=RWY_09L_LAND_EXIT,
        ),
        "09R/27L": Runway(
            runway_id="09R/27L",
            active_direction="09R",
            entry_node="RWY_09R_ENTRY",
            exit_node=RWY_09R_LAND_EXIT,
        ),
    }


# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------

def shortest_path(G: nx.DiGraph, source: str, target: str) -> list[str]:
    """Return shortest-path node list (source included). Raises if unreachable."""
    try:
        return nx.shortest_path(G, source, target, weight="weight")
    except nx.NetworkXNoPath:
        raise ValueError(f"No path from {source!r} to {target!r}")


def path_segments(path: list[str]) -> list[tuple[str, str]]:
    """Convert node list to edge list."""
    return [(path[i], path[i + 1]) for i in range(len(path) - 1)]


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def check_conflicts(G: nx.DiGraph) -> list[tuple[str, str, str]]:
    """
    Return list of (u, v, occupant) triples where an edge is occupied
    by more than one entity (should never happen).
    Currently we just check for edges that carry multiple occupants.
    The dispatcher prevents this; this is a safety assertion.
    """
    conflicts = []
    for u, v, data in G.edges(data=True):
        occ = data.get("occupied_by")
        if occ is not None and isinstance(occ, list) and len(occ) > 1:
            conflicts.append((u, v, str(occ)))
    return conflicts


def occupy_segment(G: nx.DiGraph, u: str, v: str, entity_id: str) -> None:
    """Mark edge (u,v) as occupied. Raises if already occupied."""
    data = G[u][v]
    current = data.get("occupied_by")
    if current is not None:
        raise ConflictError(f"Segment {u}→{v} already occupied by {current!r}, "
                            f"cannot assign to {entity_id!r}")
    data["occupied_by"] = entity_id


def release_segment(G: nx.DiGraph, u: str, v: str, entity_id: str) -> None:
    """Release edge (u,v). No-op if already free."""
    data = G[u][v]
    if data.get("occupied_by") == entity_id:
        data["occupied_by"] = None


def is_segment_free(G: nx.DiGraph, u: str, v: str) -> bool:
    return G[u][v].get("occupied_by") is None


class ConflictError(Exception):
    pass


# ---------------------------------------------------------------------------
# JSON graph loader (for real airport data, e.g. OSM-extracted KAUS)
# ---------------------------------------------------------------------------

def load_taxiway_graph_from_json(path: str | Path) -> nx.DiGraph:
    """
    Load a taxiway graph from a JSON file produced by data/parse_osm_taxiways.py.

    JSON schema:
    {
        "nodes": [{"id": str, "node_type": str, "pos": [lon, lat], "label": str}, ...],
        "edges": [{"source": str, "target": str, "length": float, "weight": float}, ...]
    }

    Returns a networkx DiGraph compatible with the dispatcher:
      - Each node has: node_type, pos, label
      - Each edge has: length, weight, occupied_by (initialized to None)

    Raises ValueError if the graph lacks required entity types.
    """
    import json
    data = json.loads(Path(path).read_text())

    G = nx.DiGraph()

    for node in data["nodes"]:
        G.add_node(
            node["id"],
            node_type=node["node_type"],
            pos=tuple(node["pos"]),
            label=node.get("label", ""),
        )

    for edge in data["edges"]:
        G.add_edge(
            edge["source"],
            edge["target"],
            length=edge["length"],
            weight=edge["weight"],
            occupied_by=None,
        )

    # Validate required entity types
    node_types = {d.get("node_type") for _, d in G.nodes(data=True)}
    gates = [n for n, d in G.nodes(data=True) if d.get("node_type") == "gate"]
    rwy_entries = [n for n, d in G.nodes(data=True) if d.get("node_type") == "runway_entry"]
    depots = [n for n, d in G.nodes(data=True) if d.get("node_type") == "depot"]

    if not gates:
        raise ValueError(f"Graph at {path} has no gate nodes (node_type='gate')")
    if not rwy_entries:
        raise ValueError(f"Graph at {path} has no runway entry nodes (node_type='runway_entry')")
    if not depots:
        raise ValueError(f"Graph at {path} has no depot nodes (node_type='depot')")

    return G


def build_gates_from_graph(G: nx.DiGraph) -> dict[str, Gate]:
    """Build a gate registry from gate nodes in a loaded graph."""
    gates = {}
    for node, data in G.nodes(data=True):
        if data.get("node_type") != "gate":
            continue
        label = data.get("label", "")
        # Derive gate_id and terminal from node name
        # Expected format: GATE_<terminal><number> or GATE_<number>
        gate_id = node.replace("GATE_", "")
        # Infer terminal from first character if it's a letter
        if gate_id and gate_id[0].isalpha():
            terminal = gate_id[0]
        else:
            terminal = "T"  # default terminal
        gates[gate_id] = Gate(gate_id, terminal, node)
    return gates


def build_runways_from_graph(G: nx.DiGraph) -> dict[str, Runway]:
    """Build a runway registry from runway_entry nodes in a loaded graph.

    Expects nodes named RWY_<id>_ENTRY with corresponding RWY_<id>_EXIT nodes
    or nearest intersection as exit.
    """
    entries = {}
    exits = {}
    for node, data in G.nodes(data=True):
        if data.get("node_type") == "runway_entry":
            if "_ENTRY" in node:
                rwy_id = node.replace("RWY_", "").replace("_ENTRY", "")
                entries[rwy_id] = node
            elif "_EXIT" in node:
                rwy_id = node.replace("RWY_", "").replace("_EXIT", "")
                exits[rwy_id] = node

    runways = {}
    for rwy_id, entry_node in entries.items():
        exit_node = exits.get(rwy_id)
        if exit_node is None:
            # Find nearest intersection as exit
            best_node = None
            best_cost = float("inf")
            for n, d in G.nodes(data=True):
                if d.get("node_type") == "intersection" and G.has_edge(n, entry_node):
                    cost = G[n][entry_node].get("weight", float("inf"))
                    if cost < best_cost:
                        best_cost = cost
                        best_node = n
            exit_node = best_node or entry_node

        runways[rwy_id] = Runway(
            runway_id=rwy_id,
            active_direction=rwy_id,
            entry_node=entry_node,
            exit_node=exit_node,
        )

    return runways
