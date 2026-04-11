# KAUS Slice Rationale

## Gate Selection

Picked 8 gates closest to DEPOT by shortest-path travel time:

| Gate | Travel Time | Distance | Location |
|------|------------|----------|----------|
| GATE_S1 | 94.9s | 664m | South Terminal |
| GATE_S2 | 98.3s | 688m | South Terminal |
| GATE_S3 | 115.1s | 806m | South Terminal |
| GATE_36 | 122.7s | 859m | Barbara Jordan Terminal |
| GATE_37 | 123.8s | 867m | Barbara Jordan Terminal |
| GATE_35 | 126.4s | 885m | Barbara Jordan Terminal |
| GATE_30 | 149.3s | 1045m | Barbara Jordan Terminal |
| GATE_32 | 151.2s | 1058m | Barbara Jordan Terminal |

Gates span two terminal areas (South Terminal S-gates + BJT 30s block), providing variety while keeping service vehicle travel times reasonable for the 7-vehicle fleet.

## Graph Pruning

Full KAUS graph: 271 nodes, 793 edges
Sliced graph: 119 nodes, 274 edges (~44% of original)

Kept: all nodes on shortest paths between the 8 chosen gates, 2 runways (18R/36L, 18L/36R), and DEPOT. Graph is weakly connected — all gates, runways, and depot are mutually reachable.

## Schedule Filtering

From the full 306-flight Dec 10, 2025 schedule:
- **40 flights selected** (target: 30-50)
  - 32 turnarounds (full arrival → service → departure cycle)
  - 4 arrival-only (positioning flights)
  - 4 departure-only (pre-positioned overnight aircraft)
- Aircraft types: 34 B737, 6 CRJ900
- Time window: first arrival at 180s (0:03), last departure at 44040s (12:14)

## FCFS Baseline Results

| Metric | Value |
|--------|-------|
| Flights departed | 32/36 eligible (4 arr-only never depart by design) |
| Total delay | 155.5 min |
| Avg delay | 4.9 min/flight |
| Max delay | 17.0 min |
| Avg turnaround | 54.9 min |
| Conflicts | 0 |
| Vehicle dispatches | 136 |

**Note:** 4 departure-only flights stuck in `servicing` state with no gate assignment. This is a known gap — `load_schedule()` doesn't pre-assign gates to dep-only flights (unlike `generate_schedule()`). These flights are excluded from delay calculations. All 32 turnaround flights completed successfully.

## Comparison to Synthetic Data

The synthetic schedule (`generate_schedule`) uses 6-14 flights with 6 gates. This slice is a 3-5x scale increase:
- 40 flights vs 6-14 (3-7x)
- 8 gates vs 6 (1.3x)
- 119-node graph vs 15-node (8x)
- Real BTS timing patterns vs uniform random arrivals

The FCFS baseline shows the system handles the scale increase without conflicts, validating the path to full KAUS (306 flights, 40 gates, 271 nodes).
