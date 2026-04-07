"""
Tests for sim/world.py — taxiway graph, paths, conflict detection.
"""

import pytest
import networkx as nx
from sim.world import (
    build_taxiway_graph,
    build_gates,
    build_runways,
    shortest_path,
    path_segments,
    is_segment_free,
    occupy_segment,
    release_segment,
    check_conflicts,
    ConflictError,
    NODE_POSITIONS,
)


@pytest.fixture
def G():
    return build_taxiway_graph()


# ---- Graph structure ----

def test_graph_is_directed(G):
    assert isinstance(G, nx.DiGraph)


def test_all_nodes_present(G):
    expected = {
        "DEPOT", "TWY_SERVICE", "INTER_NW", "TWY_NORTH", "INTER_NE",
        "TWY_A_ENTRY", "TWY_B_ENTRY",
        "GATE_A1", "GATE_A2", "GATE_A3",
        "GATE_B1", "GATE_B2", "GATE_B3",
        "RWY_09L_ENTRY", "RWY_09R_ENTRY",
    }
    assert expected.issubset(set(G.nodes()))


def test_all_gates_reachable_from_inter_nw(G):
    for gate in ["GATE_A1", "GATE_A2", "GATE_A3", "GATE_B1", "GATE_B2", "GATE_B3"]:
        assert nx.has_path(G, "INTER_NW", gate), f"No path INTER_NW → {gate}"


def test_all_gates_reachable_from_inter_ne(G):
    for gate in ["GATE_A1", "GATE_A2", "GATE_A3", "GATE_B1", "GATE_B2", "GATE_B3"]:
        assert nx.has_path(G, "INTER_NE", gate), f"No path INTER_NE → {gate}"


def test_depot_reachable_from_all_gates(G):
    for gate in ["GATE_A1", "GATE_A2", "GATE_A3", "GATE_B1", "GATE_B2", "GATE_B3"]:
        assert nx.has_path(G, gate, "DEPOT"), f"No path {gate} → DEPOT"


def test_runway_entries_reachable_from_gates(G):
    for gate in ["GATE_A1", "GATE_B3"]:
        for rwy in ["RWY_09L_ENTRY", "RWY_09R_ENTRY"]:
            assert nx.has_path(G, gate, rwy), f"No path {gate} → {rwy}"


def test_edges_have_weight(G):
    for u, v, data in G.edges(data=True):
        assert "weight" in data, f"Edge {u}→{v} missing weight"
        assert data["weight"] > 0, f"Edge {u}→{v} has non-positive weight"


def test_edges_have_length(G):
    for u, v, data in G.edges(data=True):
        assert "length" in data, f"Edge {u}→{v} missing length"
        assert data["length"] > 0


def test_edges_occupied_by_none_initially(G):
    for u, v, data in G.edges(data=True):
        assert data["occupied_by"] is None, f"Edge {u}→{v} occupied at init"


def test_node_positions_cover_all_nodes(G):
    for node in G.nodes():
        assert node in NODE_POSITIONS, f"Node {node!r} has no pixel position"


# ---- Shortest path ----

def test_shortest_path_gate_a1_to_depot(G):
    path = shortest_path(G, "GATE_A1", "DEPOT")
    assert path[0] == "GATE_A1"
    assert path[-1] == "DEPOT"
    assert len(path) >= 2


def test_shortest_path_same_node(G):
    path = shortest_path(G, "GATE_A1", "GATE_A1")
    assert path == ["GATE_A1"]


def test_shortest_path_no_duplicate_consecutive(G):
    path = shortest_path(G, "GATE_B3", "RWY_09L_ENTRY")
    for i in range(len(path) - 1):
        assert path[i] != path[i + 1], "Path has consecutive duplicate nodes"


def test_shortest_path_unreachable_raises(G):
    G2 = G.copy()
    # Add isolated node
    G2.add_node("ISOLATED")
    with pytest.raises(ValueError):
        shortest_path(G2, "GATE_A1", "ISOLATED")


def test_path_segments_correct_length(G):
    path = shortest_path(G, "GATE_A1", "DEPOT")
    segs = path_segments(path)
    assert len(segs) == len(path) - 1


def test_path_segments_empty_on_single_node():
    assert path_segments(["A"]) == []


def test_path_segments_values(G):
    path = ["GATE_A1", "TWY_A_ENTRY", "INTER_NW"]
    segs = path_segments(path)
    assert segs == [("GATE_A1", "TWY_A_ENTRY"), ("TWY_A_ENTRY", "INTER_NW")]


# ---- Segment occupancy ----

def test_segment_free_initially(G):
    assert is_segment_free(G, "GATE_A1", "TWY_A_ENTRY")


def test_occupy_segment(G):
    occupy_segment(G, "GATE_A1", "TWY_A_ENTRY", "AA101")
    assert not is_segment_free(G, "GATE_A1", "TWY_A_ENTRY")
    assert G["GATE_A1"]["TWY_A_ENTRY"]["occupied_by"] == "AA101"


def test_release_segment(G):
    occupy_segment(G, "GATE_A1", "TWY_A_ENTRY", "AA101")
    release_segment(G, "GATE_A1", "TWY_A_ENTRY", "AA101")
    assert is_segment_free(G, "GATE_A1", "TWY_A_ENTRY")


def test_double_occupy_raises_conflict_error(G):
    occupy_segment(G, "GATE_A1", "TWY_A_ENTRY", "AA101")
    with pytest.raises(ConflictError):
        occupy_segment(G, "GATE_A1", "TWY_A_ENTRY", "DL202")


def test_release_wrong_occupant_is_noop(G):
    occupy_segment(G, "GATE_A1", "TWY_A_ENTRY", "AA101")
    release_segment(G, "GATE_A1", "TWY_A_ENTRY", "OTHER")
    # Should still be occupied by AA101
    assert not is_segment_free(G, "GATE_A1", "TWY_A_ENTRY")


def test_occupy_different_segments_independently(G):
    occupy_segment(G, "GATE_A1", "TWY_A_ENTRY", "AA101")
    occupy_segment(G, "GATE_B1", "TWY_B_ENTRY", "DL202")
    assert not is_segment_free(G, "GATE_A1", "TWY_A_ENTRY")
    assert not is_segment_free(G, "GATE_B1", "TWY_B_ENTRY")
    release_segment(G, "GATE_A1", "TWY_A_ENTRY", "AA101")
    assert is_segment_free(G, "GATE_A1", "TWY_A_ENTRY")
    assert not is_segment_free(G, "GATE_B1", "TWY_B_ENTRY")


# ---- check_conflicts ----

def test_check_conflicts_none_initially(G):
    assert check_conflicts(G) == []


# ---- Gates ----

def test_gates_registry():
    gates = build_gates()
    assert set(gates.keys()) == {"A1", "A2", "A3", "B1", "B2", "B3"}
    for gid, gate in gates.items():
        assert gate.gate_id == gid
        assert gate.terminal in ("A", "B")
        assert gate.position_node.startswith("GATE_")
        assert gate.occupied_by is None


def test_gate_is_free(G):
    gates = build_gates()
    for gate in gates.values():
        assert gate.is_free(0.0)


def test_gate_not_free_when_occupied():
    gates = build_gates()
    g = gates["A1"]
    g.occupied_by = "AA101"
    assert not g.is_free(0.0)
    g.occupied_by = None
    assert g.is_free(0.0)


def test_gate_not_free_before_available_at():
    gates = build_gates()
    g = gates["B2"]
    g.available_at = 500.0
    assert not g.is_free(400.0)
    assert g.is_free(500.0)
    assert g.is_free(600.0)


# ---- Runways ----

def test_runways_registry():
    runways = build_runways()
    assert "09L/27R" in runways
    assert "09R/27L" in runways


def test_runway_free_initially():
    runways = build_runways()
    for rwy in runways.values():
        assert rwy.is_free(0.0)


def test_runway_nodes_in_graph(G):
    runways = build_runways()
    for rwy in runways.values():
        assert G.has_node(rwy.entry_node), f"Entry node {rwy.entry_node} not in graph"
        assert G.has_node(rwy.exit_node), f"Exit node {rwy.exit_node} not in graph"
