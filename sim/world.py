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
