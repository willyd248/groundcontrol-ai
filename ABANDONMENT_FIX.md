# ABANDONMENT_FIX.md — Abandonment Bug Investigation & Fix Design

## Findings

### 1. Is there a reward penalty for abandoning a service in progress?

**No.** The reward function has no abandonment penalty. The penalty set
`REWARD_HOLD_WITH_WORK = -0.1` penalises holding when work is available,
`REWARD_CONFLICT = -50.0` penalises taxiway conflicts, and
`REWARD_PENDING_AT_TIMEOUT = -20.0` penalises unfinished flights at episode end.
None of these apply to mid-service abandonment.

### 2. Can a vehicle be reassigned mid-service in the current code?

**No — but only via an implicit, fragile guard.**

The sole protection is `Vehicle.is_available()` in `sim/entities.py:169`:

```python
def is_available(self) -> bool:
    return self.state == VehicleState.IDLE and self.assigned_to is None
```

`Dispatcher._find_nearest_vehicle()` (dispatcher.py:314–333) only considers
vehicles where `v.is_available()` returns True. A vehicle in `EN_ROUTE` or
`SERVICING` fails this check and cannot be selected by the agent.

There is **no explicit `committed` flag**. The protection is a side-effect of
the state machine: once dispatched, the vehicle is never IDLE until
`_complete_services()` at dispatcher.py:399–433 explicitly frees it:

```python
# dispatcher.py:422-425
vehicle.state = VehicleState.IDLE
vehicle.assigned_to = None
vehicle.service_end_time = 0.0
```

This means:
- Under the current dispatcher, reassignment mid-service is impossible.
- If any future code changes the state machine (e.g., preemption, disruption
  force-release), nothing blocks the action mask from offering a busy vehicle.
- The protection is invisible and can be accidentally broken.

### 3. What state transition allowed the previous policy to "abandon" B6111?

**There is no code-level abandonment.** B6111 was not reassigned mid-service.

The observed abandonment in the demo was a **policy failure caused by the old
trigger's 99.6% HOLD rate**, not a vehicle reassignment bug:

1. B6111 arrives at gate → 3 service tasks created (fuel, baggage_unload,
   baggage_load).
2. Old trigger fires every tick while `pending_task AND free_vehicle` is True.
3. The HOLD-biased policy holds ~243 times per assignment decision.
4. While the policy sits on decisions for 243+ seconds of sim time, B6111's
   `scheduled_departure` passes and delay accumulates.
5. Eventually the episode times out (truncated) with B6111's services incomplete
   — or the policy finally assigns vehicles but too late to prevent the delay.
6. From an observer's perspective this looks like "abandonment" but is really
   "failure to dispatch promptly."

The Step 2 event-based trigger fix reduces decisions from ~9000 to ~40 per
episode, eliminating this pathological slow-dispatch behaviour. After Step 2,
each decision point corresponds to a real assignment opportunity and the policy
cannot sit idle for 243 seconds between assignments.

### 4. Why add the committed flag despite no current abandonment path?

Two forward-looking risks justify the defensive measure:

**Risk A — Disruption force-release (Session 5 feature).**
`sim/disruptions.py` (in the `trusting-albattani` worktree) implements
`vehicle_breakdown` by setting `v.state = VehicleState.RETURNING, path = []`.
On the next tick, `_advance_vehicles()` sees `RETURNING + empty path` →
`v.state = IDLE`. If the vehicle was SERVICING at the time of breakdown, it
would become IDLE without completing the task. The task would remain in
`active_tasks` with no vehicle actively working on it (orphaned task). Currently
the breakdown code guards against this by only applying to IDLE vehicles, but
this guard is in the disruption code, not in the dispatcher.

**Risk B — Preemption extension.**
If a future policy design allows the agent to preempt a running task (e.g.,
redirect a vehicle to a higher-priority departure), the action mask would need to
expose non-IDLE vehicles. Without an explicit committed flag, there is nothing in
the mask-generation code that would know which vehicles are mid-task.

---

## Implementation Plan

### Part 1: `committed` flag on Vehicle

Add to `Vehicle` dataclass in `sim/entities.py`:

```python
committed: bool = False   # True while assigned to an active (in-progress) task
```

Set it in `env/airport_env.py:_assign_one_task()`:
```python
vehicle.committed = True
```

Clear it in `sim/dispatcher.py:_complete_services()` when task completes:
```python
vehicle.committed = False
```

Add an extra guard in `Dispatcher._find_nearest_vehicle()`:
```python
if v.committed:
    continue
```

This makes the protection explicit, visible, and independent of the state
machine, so future changes to `is_available()` or vehicle states cannot
accidentally expose mid-service vehicles.

### Part 2: Abandonment detection and penalty

Define "abandonment" as: a task is in `active_tasks`, its assigned vehicle is
NOT in `{EN_ROUTE, SERVICING}` (e.g., it was force-released by a disruption),
AND the task has not been completed (`task.completed_at is None`).

**Penalty magnitude:** `-1.0 × (time_already_spent_on_task / 60.0)` reward
units (minutes of wasted service time).

**Reasoning:** The delay penalty is `-1.0` per flight-minute of accumulated
departure delay. If we spend T minutes servicing then abandon, we have wasted
T minutes and still need to re-service. The penalty equalling the wasted time
makes abandonment strictly worse than completion: completing takes T more
minutes at zero penalty (or a small delay penalty), while abandoning costs T
minutes now AND still requires a future T-minute service.

**Detection location:** `_compute_tick_reward()` in `env/airport_env.py`.
After each tick, scan `active_tasks` for orphaned tasks. Track which tasks
have been penalised (via a set `_abandoned_task_ids`) to avoid double-counting.

**Implementation sketch:**

```python
# In AirportEnv.__init__:
self._abandoned_task_ids: set[str] = set()

# In reset():
self._abandoned_task_ids = set()

# In _compute_tick_reward() — new section after departure reward:
abandonment_reward = 0.0
now = self._sim_time
for task_id, task in list(self.dispatcher.active_tasks.items()):
    if task_id in self._abandoned_task_ids:
        continue
    vehicle = self.dispatcher.vehicles.get(task.assigned_vehicle_id)
    if vehicle is None:
        continue
    if vehicle.state not in (VehicleState.EN_ROUTE, VehicleState.SERVICING):
        # Vehicle is no longer working on this task (force-released)
        time_spent = (now - task.started_at) / 60.0 if task.started_at else 0.0
        abandonment_reward += REWARD_ABANDONMENT * time_spent
        self._abandoned_task_ids.add(task_id)
return delay_reward, dep_reward, abandonment_reward
```

**Penalty constant:**
```python
REWARD_ABANDONMENT = -1.0   # per minute of service time wasted
```

This is proportional to delay impact (same scale as `REWARD_PER_DELAY_MINUTE`),
making the abandonment penalty interpretable and comparable to other penalties.
Default is conservative (-1.0/min); can be increased if the policy learns to
exploit force-releases.

---

## What Does NOT Change

- Action space: Discrete(17), unchanged.
- Mask generation: unchanged. The `committed` flag adds a guard in
  `_find_nearest_vehicle()`, not in the mask loop — the mask loop already relies
  on `_is_valid_assignment()` which calls `_find_nearest_vehicle()`.
- Reward constants for delay, departure, conflict, hold, and timeout: unchanged.
- Step 2 event-based trigger: unchanged.
