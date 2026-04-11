# Compatibility Report: KAUS Slice vs Simulator

**Date:** 2026-04-08
**Schedule:** data/schedules/kaus_slice_20251210.json (Dec 10, 2025 — sliced)
**Graph:** data/graphs/kaus_slice.json (OSM extraction, pruned to 8 gates)

## Summary: 24 passed, 0 failed

- [PASS] `graph_load`: 119 nodes, 274 edges

- [PASS] `graph_node_types`: Node types: {'intersection': 106, 'gate': 8, 'runway_entry': 4, 'depot': 1}

- [PASS] `graph_depot_to_gates`: DEPOT can reach all 8 gates

- [PASS] `gates_build`: 8 gates: ['30', '32', '35', '36', '37', 'S1', 'S2', 'S3']

- [PASS] `runway_18R36L`: entry=RWY_18R36L_ENTRY, exit=RWY_18R36L_EXIT

- [PASS] `runway_18L36R`: entry=RWY_18L36R_ENTRY, exit=RWY_18L36R_EXIT

- [PASS] `runways_build`: 2 runways

- [PASS] `schedule_load`: 40 flights (32 turnaround, 4 arr-only, 4 dep-only)

- [PASS] `schedule_types`: Types: {'B737': 34, 'CRJ900': 6}

- [PASS] `dep_only_gates`: 4/4 dep-only flights have gate assignments

- [PASS] `dispatcher_init`: Initialized: 40 flights, 8 gates, 2 runways, 7 vehicles

- [PASS] `checkpoint_t1000`: Departed: 0/40, Delay: 0min, Conflicts: 0

- [PASS] `checkpoint_t5000`: Departed: 0/40, Delay: 0min, Conflicts: 0

- [PASS] `checkpoint_t15000`: Departed: 0/40, Delay: 0min, Conflicts: 0

- [PASS] `checkpoint_t30000`: Departed: 5/40, Delay: 12min, Conflicts: 0

- [PASS] `dispatcher_complete`: 36/36 departure-eligible flights departed (4 arrival-only correctly remain at gate)

- [PASS] `fcfs_departed`: 36/40 total (36 eligible)

- [PASS] `fcfs_pending`: 4 pending (4 are arrival-only)

- [PASS] `fcfs_total_delay`: Total delay: 118.4 min

- [PASS] `fcfs_avg_delay`: Avg delay: 3.3 min/flight

- [PASS] `fcfs_max_delay`: Max delay: 14.0 min

- [PASS] `fcfs_turnaround`: Avg turnaround: 53.4 min

- [PASS] `fcfs_conflicts`: Conflicts: 0

- [PASS] `fcfs_vehicles_dispatched`: Vehicle dispatches: 148

## What Was Fixed (Phase 3 Items 1-3)

### 1. dict-vs-float crash in `_find_nearest_vehicle` (sim/dispatcher.py)
- **Root cause:** dep-only flights from JSON schedule had `position=None` and `assigned_gate=None`. When service tasks were created with `gate_node=None`, `nx.shortest_path_length(G, src, None)` returned a dict of all targets instead of a scalar float.
- **Fix:** Guard `_find_nearest_vehicle` to return None when `gate_node is None or gate_node not in G`. Also changed sort tuple from `(cost, vehicle)` to `(cost, vehicle_id, vehicle)` to prevent Vehicle object comparison on tiebreak.
- **Tests:** 2 new tests in `tests/test_dispatcher.py`, all 22 passing.

### 1b. Dep-only gate pre-assignment in `load_schedule` (sim/scheduler.py)
- **Root cause:** `load_schedule()` set dep-only flights to `state=AT_GATE` but never assigned `assigned_gate` or `position`. The dispatcher couldn't create service tasks without a gate node.
- **Fix:** Added optional `gates` parameter to `load_schedule()`. When provided, dep-only flights are pre-assigned to gates round-robin (mirroring `generate_schedule` logic). Falls back to default KFIC 6-gate layout when not provided (backwards compatible).

### 2. JSON graph loader added to `sim/world.py`
- `load_taxiway_graph_from_json(path)` — loads OSM-extracted graph JSON
- `build_gates_from_graph(G)` — builds gate registry from graph gate nodes
- `build_runways_from_graph(G)` — builds runway registry from RWY_*_ENTRY/EXIT nodes
- Validates required entity types (≥1 gate, ≥1 runway entry, ≥1 depot)

### 3. OSM parser node naming normalized (`data/parse_osm_taxiways.py`)
- Runway endpoints: `RWY_18R36L_ENTRY`, `RWY_18R36L_EXIT`, etc.
- Gates: `GATE_1` through `GATE_37`, plus `GATE_S1/S2/S3`
- Depot: `DEPOT`

## What Doesn't Work Yet (Full Scale)

- Full 306-flight KAUS schedule exceeds `MAX_AIRCRAFT=20` in RL observation space
- Full 271-node graph with 40 gates needs scaled vehicle fleet (~50 vehicles)
- `airport_env.py` hardcodes `ALL_NODES` (15 KFIC nodes) — needs dynamic node indexing
- SIM_HORIZON (4h) too short for full KAUS day (24h of operations)

## v1 Deliverable

Phase 3 v1 proves the full real-data pipeline works end-to-end: BTS On-Time Performance CSV from a real day at Austin-Bergstrom (Dec 10, 2025) is converted to the simulator's schedule format, an OSM-extracted taxiway graph is loaded via the new JSON graph loader, and the FCFS dispatcher runs a sliced subset to completion with realistic delay numbers — establishing the foundation for training RL policies on real airport operations instead of synthetic scenarios.

### Pipeline
```
BTS CSV → convert_bts_to_schedule.py → 306-flight full schedule
OSM Overpass → parse_osm_taxiways.py → 271-node full KAUS graph
                    ↓
            build_kaus_slice.py
                    ↓
        40-flight slice + 119-node subgraph
                    ↓
    load_taxiway_graph_from_json() + load_schedule(gates=...)
                    ↓
            Dispatcher FCFS → 36/36 departed, 0 conflicts
```

### Final Numbers

| Metric | Value |
|--------|-------|
| Source | BTS On-Time Performance, December 2025 |
| Airport | KAUS (Austin-Bergstrom International) |
| Day | Wednesday, December 10, 2025 |
| Full schedule | 306 flights (157 turnaround, 76 arr-only, 73 dep-only) |
| Slice | 40 flights (32 turnaround, 4 arr-only, 4 dep-only) |
| Gates (slice) | S1, S2, S3, 30, 32, 35, 36, 37 (8 gates) |
| Graph (slice) | 119 nodes, 274 edges |
| Runways | 18R/36L, 18L/36R |
| FCFS departed | 36/36 departure-eligible |
| FCFS total delay | 118.4 min |
| FCFS avg delay | 3.3 min/flight |
| FCFS max delay | 14.0 min |
| FCFS avg turnaround | 53.4 min |
| Conflicts | 0 |
| Vehicle dispatches | 148 |

### What This Enables

The sliced KAUS data can now serve as an alternative training environment alongside the synthetic KFIC scenarios. Next steps: parameterize `AirportEnv` to accept a graph path + schedule path, scale observation space for larger flight counts, and train RL policies on real operational patterns.
