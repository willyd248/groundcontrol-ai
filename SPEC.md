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
| `requirements.txt` | pygame, networkx, pytest, gymnasium, sb3-contrib |

---

## Session 2 — Gymnasium RL Environment

### Overview

The `env/` package wraps the Session 1 simulator in a `gymnasium.Env` subclass
for reinforcement learning. Core sim logic is **not modified**; the env calls
into it via a thin override.

### Architecture

```
AirportEnv
  └── RLDispatcher (subclass of Dispatcher)
        └── _assign_vehicles() → no-op
              (env feeds one action = one vehicle assignment per step)
```

`RLDispatcher` inherits all dispatcher logic (gate assignment, taxiing, runway
rules, service completion) except `_assign_vehicles`, which becomes a no-op.
The env calls `_assign_one_task(action)` to apply the agent's choice, then
advances the sim until the next **decision point**.

### Decision Point

A decision point exists when:
- At least one `ServiceTask` is in `dispatcher.pending_tasks`, AND
- At least one free vehicle of a compatible type exists (checked via
  `_find_nearest_vehicle()`).

The sim ticks (dt=1s each) until a decision point, episode end, or the
`MAX_TICKS_PER_STEP` safety cap (3600 ticks) is hit.

### Observation Space

`Box(low=-1, high=1, shape=(270,), dtype=float32)`

| Slice | Entity | Fields |
|-------|--------|--------|
| [0] | sim | `sim_time / SIM_HORIZON` |
| [1..160] | 20 aircraft slots × 8 features | state_norm, pos_idx_norm, time_to_dep_norm, fuel_done, baggage_unload_done, baggage_load_done, pushback_done, is_active |
| [161..188] | 7 vehicle slots × 4 features | state_norm, pos_idx_norm, type_norm, is_free |
| [189..268] | 16 task slots × 5 features | svc_type_norm, gate_idx_norm, age_norm, flight_slot_norm, is_active |
| [269] | pending queue | `n_pending / MAX_TASKS` |

Position encoding uses a fixed 15-node index (`ALL_NODES` in `airport_env.py`).
All values clamped to [-1, 1].

### Action Space

`Discrete(17)` — actions 0..15 select a pending task to assign; action 16 = HOLD.

Action masking via `action_masks()` returns a `bool[17]` array compatible with
`sb3_contrib.MaskablePPO`. Action `i` is valid iff:
1. `i < len(pending_tasks)`, AND
2. A free compatible vehicle exists for `pending_tasks[i]`.

HOLD (action 16) is always valid.

### Reward

| Event | Reward |
|-------|--------|
| Each sim-tick | `−1.0 × new_delay_minutes` (per overdue flight-minute) |
| On-time departure (≤5 min late) | `+10.0` |
| Late departure (>5 min late) | `+2.0` |
| Hold when valid assignment exists | `−0.1` |
| Conflict detected | `−50.0` |
| Episode truncated — per pending flight | `−20.0` |

### Files Added

| File | Purpose |
|------|---------|
| `env/__init__.py` | Public API: `AirportEnv`, `ACTION_HOLD` |
| `env/airport_env.py` | `gymnasium.Env` subclass + `RLDispatcher` |
| `env/random_schedule.py` | Randomised schedule generator (seed-reproducible) |
| `env/smoke_test.py` | Quick manual sanity check (`python -m env.smoke_test`) |
| `tests/test_env.py` | pytest suite: shapes, bounds, zero-conflict, termination |

---

## Session 3 — PPO Training Infrastructure

### Overview

Adds the full training pipeline on top of the Session 2 Gymnasium environment.
Uses `sb3_contrib.MaskablePPO` so the agent always receives a valid action mask
and cannot select an illegal task or a task with no available vehicle.

### Architecture

```
train/train_ppo.py
  └── SubprocVecEnv(8 × AirportEnv(randomise=True))
        └── MaskablePPO  (policy=MlpPolicy)
              ├── CheckpointCallback  → checkpoints/airport_ppo_{N}_steps.zip
              └── AirportEvalCallback → runs/AirportPPO_*/
                    ├── run_policy_episode(model, seed=42)   (RL)
                    └── run_fcfs_episode(seed=42)            (FCFS baseline, cached)
```

### Hyperparameters

| Parameter | Value |
|-----------|-------|
| `n_envs` | 8 (SubprocVecEnv) |
| `learning_rate` | 3e-4 |
| `batch_size` | 256 |
| `n_steps` | 2048 (per env per rollout) |
| `n_epochs` | 10 |
| `gamma` | 0.99 |
| `clip_range` | 0.2 |
| `ent_coef` | 0.01 |
| `total_timesteps` | 1,000,000 |

### Evaluation Callback

`AirportEvalCallback` fires every 50 k total timesteps and:
1. Runs the current policy deterministically on seed-42 random schedule.
2. Compares against the FCFS baseline (computed once at training start, cached).
3. Logs to TensorBoard: `eval/rl_total_delay_min`, `eval/fcfs_total_delay_min`,
   `eval/delay_improvement`, `eval/rl_conflict_count`, `eval/rl_missed_departures`, etc.

**Debug trigger:** if `delay_improvement < 0` at step ≥ 200 k, the callback prints
a warning to investigate the reward signal or observation space rather than
training longer.

### FCFS Baseline (seed=42)

Measured at training start:
- Total delay: **14.5 min**
- Missed departures: **0**
- Conflicts: **0**

The RL agent should beat or match this by step 200 k. If not, debug reward shaping
before extending training.

### Usage

```bash
# Full 1M-step training
python -m train.train_ppo

# Short sanity check
python -m train.train_ppo --timesteps 10000 --n-envs 2

# Resume from checkpoint
python -m train.train_ppo --resume checkpoints/airport_ppo_500000_steps

# Evaluate a checkpoint
python -m train.eval checkpoints/airport_ppo_final.zip --compare-fcfs
python -m train.eval checkpoints/airport_ppo_final.zip --render --seed 99

# TensorBoard
tensorboard --logdir runs/
```

### Files Added

| File | Purpose |
|------|---------|
| `train/__init__.py` | Package init |
| `train/train_ppo.py` | MaskablePPO training entry point |
| `train/callbacks.py` | `AirportEvalCallback` + FCFS/policy episode runners |
| `train/eval.py` | Standalone checkpoint evaluation script |
| `checkpoints/` | Saved model checkpoints (every 50 k steps) |

---

## Session 4 — Split-Screen Demo

### Overview

A pygame split-screen demo that runs two simulator instances in lockstep on the
same schedule, with the same fleet starting at t=0.  Left panel: FCFS dispatcher.
Right panel: trained MaskablePPO agent.  A live scoreboard at the top shows the
real-time delta.

### Architecture

```
demo/side_by_side.py
  ├── FCFSRunner       — thin wrapper around sim/dispatcher.py
  ├── RLRunner         — wraps env/airport_env.py + MaskablePPO checkpoint
  │     └── _DemoAirportEnv(AirportEnv)  — reset() without auto-advance
  ├── PanelRenderer    — scaled (0.65×) pygame panel drawer
  ├── ReplayRecorder   — snapshots every sim-second into memory
  └── ReplayController — step backward/forward after episode ends
demo/scoreboard.py     — live scoreboard surface renderer
demo/replay.py         — FrameSnapshot, ReplayRecorder, ReplayController,
                         _AircraftProxy / _VehicleProxy for rendering snapshots
demo/recorder.py       — optional imageio-ffmpeg mp4 writer
demo/scenarios/
  easy.json            — 4 flights, well-spaced (agent wins by a little)
  medium.json          — 8 flights, two B777s hog fuel trucks; B737/A320 starved
  stress.json          — 12 flights, three simultaneous B777s + tight-window flights
```

### Determinism Guarantee

Both runners are initialised from the **same JSON schedule file** with the
**same fleet** (FT×2, BT×3, PB×2) at **t=0**.  `_DemoAirportEnv.reset()`
skips the auto-advance-to-decision-point so both sides truly start at tick 0.
There is no RNG in the FCFS dispatcher or the static schedule loader — all
nondeterminism was removed at the schedule level.

### Safety Checks

- After every RL action: assert `_is_valid_assignment(action)` → halt on illegal action
- After every tick (both sides): assert `conflict_count` didn't increase → halt on conflict
- Both asserts print a loud `FATAL:` message and raise `RuntimeError`

### Window Layout

```
┌──────────────────────────────────────────────────────────────┐  ← 190px scoreboard
│ FCFS Baseline │  00:04:10  │ Trained Agent                   │
│ delay, etc.   │  delta msg │ delay, etc.                     │
├───────────────────────────────────┬──────────────────────────┤  ← 520px panels
│  Left panel: FCFS  (scaled 0.65×) │ Right panel: Agent       │
└───────────────────────────────────┴──────────────────────────┘
  1560 px total
```

### Controls

| Key | Action |
|-----|--------|
| SPACE | Pause / resume live run |
| ← / → | Step one display-frame backward / forward (while paused or in replay) |
| ESC | Quit |

### Usage

```bash
# Live demo (medium scenario, default 60× speed)
python -m demo.side_by_side \
    --checkpoint checkpoints/latest.zip \
    --scenario   demo/scenarios/medium.json

# Record to mp4
python -m demo.side_by_side \
    --checkpoint checkpoints/latest.zip \
    --scenario   demo/scenarios/stress.json \
    --record     stress_demo.mp4

# Slower speed for recording clarity
python -m demo.side_by_side \
    --checkpoint checkpoints/latest.zip \
    --scenario   demo/scenarios/stress.json \
    --speed 30 --record stress_demo.mp4
```

### Files Added

| File | Purpose |
|------|---------|
| `demo/__init__.py` | Package init |
| `demo/side_by_side.py` | Main entry point, runners, panel renderer |
| `demo/scoreboard.py` | Live scoreboard surface renderer |
| `demo/replay.py` | Snapshot system + replay controller + proxy objects |
| `demo/recorder.py` | Optional imageio-ffmpeg mp4 writer |
| `demo/scenarios/easy.json` | 4-flight benchmark (light traffic) |
| `demo/scenarios/medium.json` | 8-flight benchmark (B777 fuel-truck contention) |
| `demo/scenarios/stress.json` | 12-flight benchmark (3 B777s + tight windows) |
