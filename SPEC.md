# Airport Ground Operations Simulator — Specification

## Overview

A discrete-time, event-driven simulation of airport ground operations. Aircraft arrive, taxi to gates, get serviced by ground vehicles, and depart. A dispatcher coordinates all movement and service. The goal is to minimize delays while ensuring zero conflicts.

---

## Entities

### Aircraft

Represents a single flight (arrival + departure pair or one-way).

**Fields:**
- `flight_id: str` — e.g. "AA101"
- `aircraft_type: str` — e.g. "B737", "A320", "B777"
- `scheduled_arrival: float` — simulation time (seconds)
- `scheduled_departure: float` — simulation time (seconds)
- `actual_arrival: float | None`
- `actual_departure: float | None`
- `state: AircraftState` — see state machine below
- `assigned_gate: Gate | None`
- `position: str` — current taxiway node or gate ID
- `path: list[str]` — remaining waypoints to destination
- `service_requirements: ServiceRequirements`
- `services_completed: set[str]` — which services have finished

**Service Requirements (per aircraft):**
- `needs_fuel: bool`
- `fuel_amount: float` — gallons
- `needs_baggage_unload: bool`
- `needs_baggage_load: bool`
- `baggage_count: int` — number of bags
- `needs_pushback: bool` — always True for departures

---

### Gate

A parking position for an aircraft at a terminal.

**Fields:**
- `gate_id: str` — e.g. "A1", "B3"
- `terminal: str` — "A" or "B"
- `position_node: str` — taxiway graph node ID
- `occupied_by: Aircraft | None`
- `available_at: float` — time gate becomes free

---

### Taxiway

Modeled as a weighted graph (NetworkX). Each edge is a taxiway segment.

**Fields (per node):**
- `node_id: str` — e.g. "TWY_A1", "INTER_1", "RWY_09L_ENTRY"
- `node_type: str` — one of: `gate`, `intersection`, `runway_entry`, `runway_exit`, `depot`, `runway_hold`

**Fields (per edge):**
- `length: float` — meters
- `speed_limit: float` — m/s (default 7 m/s ≈ 14 kts for aircraft, 5 m/s for vehicles)
- `occupied_by: str | None` — `flight_id` or `vehicle_id` currently on segment

---

### Runway

**Fields:**
- `runway_id: str` — e.g. "09L/27R"
- `active_direction: str` — "09L" or "27R"
- `entry_node: str`
- `exit_node: str`
- `state: RunwayState` — `free`, `landing`, `departing`
- `occupied_by: str | None`
- `available_at: float`

---

### FuelTruck

**Fields:**
- `vehicle_id: str`
- `vehicle_type: str` = "fuel_truck"
- `state: VehicleState` — `idle`, `en_route`, `servicing`, `returning`
- `position: str` — current node
- `assigned_to: Aircraft | None`
- `fuel_capacity: float` — gallons
- `fuel_remaining: float`
- `services_since_refill: int`
- `refill_threshold: int` — return to depot after this many services (default: 3)

---

### BaggageTug

**Fields:**
- `vehicle_id: str`
- `vehicle_type: str` = "baggage_tug"
- `state: VehicleState`
- `position: str`
- `assigned_to: Aircraft | None`
- `capacity: int` — bags per trip

---

### PushbackTractor

**Fields:**
- `vehicle_id: str`
- `vehicle_type: str` = "pushback_tractor"
- `state: VehicleState`
- `position: str`
- `assigned_to: Aircraft | None`

---

### Dispatcher

Stateless decision-maker. Called every simulation tick.

**Responsibilities:**
1. Assign free gates to arriving aircraft
2. Route aircraft from runway exit → gate (shortest path)
3. Assign nearest free vehicle to each pending service task
4. Route vehicles from current position → gate (shortest path)
5. Route departing aircraft from gate → runway (shortest path)
6. Enforce segment occupancy: hold aircraft/vehicle if next segment is occupied
7. Send fuel trucks back to depot when below refill threshold

---

## Aircraft State Machine

```
approaching
    │
    ▼ (runway clears, aircraft lands)
landed
    │
    ▼ (assigned gate + path computed)
taxiing_in
    │
    ▼ (reaches gate node)
at_gate
    │
    ▼ (all required services assigned — fuel/baggage/pushback tasks created)
servicing
    │
    ▼ (all services completed AND scheduled_departure time reached)
pushback
    │
    ▼ (pushback tractor moves aircraft to taxiway)
taxiing_out
    │
    ▼ (reaches runway entry, runway is free)
departed
```

**Transitions:**
- `approaching → landed`: triggered when the aircraft's scheduled arrival time is reached AND the landing runway is free
- `landed → taxiing_in`: gate assigned, path computed
- `taxiing_in → at_gate`: aircraft reaches destination gate node
- `at_gate → servicing`: service tasks enqueued in dispatcher
- `servicing → pushback`: all `services_completed` equals required services AND `now >= scheduled_departure`
- `pushback → taxiing_out`: pushback tractor finishes moving aircraft to taxiway hold point
- `taxiing_out → departed`: aircraft clears the runway

---

## Service Requirements by Aircraft Type

| Aircraft Type | Fuel (gal) | Bags | Pushback |
|--------------|-----------|------|----------|
| B737         | 5,000     | 120  | Yes      |
| A320         | 4,500     | 110  | Yes      |
| B777         | 12,000    | 300  | Yes      |
| CRJ900       | 2,000     | 60   | Yes      |

All arriving aircraft need: fuel + baggage unload + baggage load
Departures-only: fuel + baggage load + pushback (no unload)

---

## World Rules

### Taxiway Segment Occupancy
- At most **one** aircraft per taxiway segment (edge) at a time
- Vehicles occupy their own slot — aircraft and vehicles share nodes but not simultaneously on the same edge in opposite directions
- An aircraft must **hold** (stop advancing) if the next segment on its path is occupied
- Vehicles follow the same rule but yield to aircraft

### Separation Buffer
- Aircraft must maintain a minimum **15-second gap** when following another aircraft on the same taxiway sequence
- Implemented as: aircraft cannot enter a segment until the previous occupant has been on it for at least 15 simulated seconds

### Gate Occupancy
- Only one aircraft per gate at a time
- A gate is unavailable while `occupied_by` is set

### Vehicle Assignment
- Each vehicle can service only one aircraft at a time (`assigned_to` must be `None`)
- Fuel trucks must return to depot to refill after `refill_threshold` services (default: 3)
- Vehicles move on the taxiway graph at `speed_limit` and can occupy segments (but at lower priority than aircraft)

### Runway Rules
- Only one aircraft on a runway at a time
- Landing aircraft have priority over departing aircraft
- After landing, a 60-second clearance gap before the next operation
- Departure clearance: runway must be free for at least 30 seconds

### Scheduling
- Aircraft appear at `scheduled_arrival` time in state `approaching`
- Departure-only flights appear at `scheduled_departure - 30min` in state `at_gate` with full service requirements

---

## World Layout — Fictional Airport "KFIC"

```
Depot ──── TWY_SERVICE
              │
RWY_09L ──── INTER_NW ──── TWY_NORTH ──── INTER_NE ──── RWY_09R
              │                                │
           TWY_A_ENTRY                    TWY_B_ENTRY
              │                                │
    ┌─────────┴─────────┐            ┌─────────┴─────────┐
   A1       A2         A3           B1        B2         B3
```

**Nodes (14):**
`DEPOT, TWY_SERVICE, INTER_NW, TWY_NORTH, INTER_NE, TWY_A_ENTRY, TWY_B_ENTRY, GATE_A1, GATE_A2, GATE_A3, GATE_B1, GATE_B2, GATE_B3, RWY_09L_ENTRY, RWY_09R_ENTRY, RWY_09L_EXIT, RWY_09R_EXIT`

**Runways:**
- `09L/27R`: entry at `RWY_09L_ENTRY`, exit (after landing) at `INTER_NW`
- `09R/27L`: entry at `RWY_09R_ENTRY`, exit (after landing) at `INTER_NE`

---

## Metrics

Collected and printed at simulation end:

| Metric | Description |
|--------|-------------|
| `total_delay_minutes` | Sum of `actual_departure - scheduled_departure` for all departed flights (positive = late) |
| `avg_turnaround_minutes` | Mean of `actual_departure - actual_arrival` for turn flights |
| `max_delay_minutes` | Worst single-flight delay |
| `conflict_count` | Times two aircraft were assigned to the same taxiway segment simultaneously — **must always be 0** |
| `vehicles_dispatched` | Total vehicle assignments made |
| `fuel_truck_refills` | Number of depot refill trips |
| `flights_departed` | Count of aircraft that reached `departed` state |
| `flights_pending` | Count of aircraft that did not depart within simulation window |

---

## Simulation Loop

```
tick_rate: 1 simulated second per loop iteration
speed_multiplier: configurable (default 60 = 1 sim-minute per wall-second)

each tick:
  1. Spawn aircraft that have reached scheduled_arrival
  2. Update aircraft positions (advance along path if next segment free)
  3. Update vehicle positions (advance along path if next segment free)
  4. Check state machine transitions for all aircraft
  5. Dispatcher: assign gates, vehicles, paths for any pending tasks
  6. Check for conflicts (assertion: none should occur)
  7. Render (if not headless)
  8. Collect metrics
```

---

## Files

| File | Purpose |
|------|---------|
| `sim/world.py` | Taxiway graph, layout constants, conflict detection |
| `sim/entities.py` | Aircraft, Vehicle subclasses, Gate, enums |
| `sim/scheduler.py` | Load/parse schedule.json, manage flight queue |
| `sim/dispatcher.py` | FCFS gate assignment, vehicle dispatch, path routing |
| `sim/render.py` | Pygame visualization |
| `sim/main.py` | Entry point, simulation loop |
| `tests/` | pytest tests |
| `schedule.json` | Sample 12-flight 2-hour schedule |
| `requirements.txt` | pygame, networkx, pytest |
