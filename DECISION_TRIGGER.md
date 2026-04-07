# DECISION_TRIGGER.md — Diagnosis & Fix Design

## 1. Current Trigger Conditions

The decision-point check lives in `env/airport_env.py`. Two methods are the core:

```python
# airport_env.py:310-315
def _has_decision_point(self) -> bool:
    """Return True if any pending task has a compatible free vehicle."""
    for i in range(len(self.dispatcher.pending_tasks)):
        if self._is_valid_assignment(i):
            return True
    return False
```

```python
# airport_env.py:317-322
def _is_valid_assignment(self, task_idx: int) -> bool:
    """True if pending_tasks[task_idx] exists and has a free vehicle."""
    if task_idx >= len(self.dispatcher.pending_tasks):
        return False
    task = self.dispatcher.pending_tasks[task_idx]
    return self.dispatcher._find_nearest_vehicle(task.service_type, task.gate_node) is not None
```

`_advance_to_decision()` ticks the sim one second at a time and breaks as soon as `_has_decision_point()` is True:

```python
# airport_env.py:348-387
def _advance_to_decision(self) -> float:
    reward = 0.0
    ticks  = 0

    while self._sim_time < SIM_HORIZON:
        self.dispatcher.tick(self._sim_time, dt=1.0)
        self._sim_time += 1.0
        ticks          += 1

        ...

        # Decision point reached?
        if self._has_decision_point():
            break          # <── exits after 1 tick if condition persists

        # Safety cap — return even if no decision point
        if ticks >= MAX_TICKS_PER_STEP:
            break

    return reward
```

`step()` applies exactly one action (assign one task, or HOLD), then calls `_advance_to_decision()`. The agent is queried exactly once per `step()` call.

---

## 2. Why This Produces the ~243:1 Noise Ratio

### The tight-loop mechanism

The condition `pending_task AND free_compatible_vehicle` is **persistent state**, not an event. Once it becomes True it stays True until the agent acts — or the agent HOLDs and the sim ticks forward one second.

After a HOLD action:
1. `step()` applies the HOLD (nothing changes in dispatcher state).
2. `_advance_to_decision()` ticks the sim exactly once (dt=1 s).
3. Nothing changed: the same pending tasks and same free vehicles still exist.
4. `_has_decision_point()` returns True again immediately.
5. Control returns to the agent — 1 second of sim time elapsed, zero progress made.

The agent is now queried again in the exact same configuration it just HOLDed on. If it HOLDs again, the cycle repeats. With `SIM_HORIZON = 14400` seconds and `MAX_TICKS_PER_STEP = 3600`, the only hard stop on this loop is the 4-hour episode limit.

### Why the agent HOLDs

The trained policy has a 99.6% HOLD rate because it learned that holding is never catastrophically wrong (mask[ACTION_HOLD] = True always), while assigning the wrong vehicle might incur penalties. The reward signal for the delay accumulates slowly in the background; the agent can hold thousands of times without a dramatic penalty spike, so the lazy HOLD policy survives training.

### Concrete counting

A typical episode with ~10 aircraft generates approximately:
- 3 service tasks per arrival (fuel, baggage_unload, baggage_load) → each creates a pending task as soon as the aircraft reaches its gate
- 1 pushback task per departure
- → ~37 "real" assignment decisions total (10 × 3 + 7 pushbacks ≈ 37)

Each real assignment takes ~1 tick. But between any two real assignments, **if there is still a pending task with a free vehicle**, the condition fires every single tick. The agent's 99.6% HOLD rate means it holds an average of 243 times before making one assignment.

In numbers:
- 9,000 total queries ÷ 37 real assignments ≈ 243 holds per assignment
- At 1 tick/hold, that's 243 seconds of sim time burned per decision (task completion times: fuel ≈ 50 s, baggage ≈ 60 s, pushback = 120 s)
- Because the sim barely advances, vehicles never finish, tasks never clear, and the same condition re-fires perpetually

### Why the action space makes it worse

The current action space offers 16 task slots + HOLD (17 actions). `step()` assigns at most one task per call. When multiple tasks and multiple free vehicles co-exist (common: 3 tasks appear at once when an aircraft arrives at gate), the agent must make 3 sequential decisions. In FCFS there would be zero decisions — the dispatcher greedily assigns all. With the RL env, those 3 trivially sequential decisions create 3 consecutive decision points spaced 1 tick apart, each of which the HOLD-biased agent can turn into a 243-tick delay.

---

## 3. What the Trigger SHOULD Be

The trigger should fire only when **something meaningful just changed** in the assignment problem. Three legitimate trigger conditions:

### (a) Vehicle becomes FREE with work available
A vehicle transitions from `EN_ROUTE / SERVICING / RETURNING → IDLE` AND at least one pending task exists that this vehicle type can service.

This is the core real-time scheduling event: a resource became available. The correct action is to look at the queue and assign it.

Detection: before each tick, snapshot `{v_id: v.state for v in vehicles}`. After the tick, compare — any vehicle that moved to `IDLE` that was not already `IDLE` counts as a trigger if pending_tasks is non-empty for its type.

### (b) New task enters the pending queue AND a free vehicle exists for it
`_create_service_tasks()` adds to `pending_tasks` when an aircraft transitions to `AT_GATE`. `_handle_pushback()` adds a pushback task when departure time arrives and services are done.

Both are genuine "new work arrived" events. If a free vehicle already exists for the new task, the agent should be queried.

Detection: track `len(pending_tasks)` before and after each tick. If it grew AND `_has_decision_point()` is True, trigger.

### (c) Disruption events that change the assignment problem
`sim/disruptions.py` (implemented in the `trusting-albattani` worktree, not yet on main) defines four disruption types. Each has different trigger implications:

**`vehicle_breakdown`** — An IDLE vehicle is made unavailable via sentinel `v.assigned_to = "__BREAKDOWN__"`, causing `is_available()` to return False. This directly shrinks the pool of assignable vehicles.
- **Fires a query when**: the breakdown makes a previously-assignable pending task un-assignable (i.e., the broken vehicle was the last compatible one for some pending task type). The agent needs to know that an assignment it could previously make is now blocked.
- **Expiry** (vehicle returns to IDLE): already covered by **Event A** — the vehicle transitions to IDLE, and if pending tasks exist for its type, Event A fires.
- **Detection**: after each tick, compare active disruptions from `dispatcher.disruption_manager.get_active_events(now)`. If a `vehicle_breakdown` event newly became active this tick, check whether it removed the last compatible vehicle for any pending task; if so, trigger a query.
- **Important caveat**: the current `_apply_event` implementation only sets a breakdown on an IDLE vehicle. If the vehicle is already EN_ROUTE or SERVICING when the breakdown fires, the event silently does nothing (`v.state == VehicleState.IDLE` check in `_apply_event`). No replanning is needed in that case — the vehicle finishes its current job then the expiry restores it to IDLE.

**`gate_fault`** — Pushes `gate.available_at` into the future, preventing new aircraft from being assigned to that gate. Aircraft already AT the faulted gate are unaffected (they stay and continue service).
- **Impact on pending tasks**: near-zero. Service tasks are created with a specific `gate_node` for an aircraft already at the gate; those tasks remain valid. The fault only blocks *new gate assignments* for LANDED aircraft awaiting a gate.
- **Fires a query when**: an aircraft is currently TAXIING_IN toward the faulted gate (its path leads there) and the dispatcher has not yet rerouted it. A query would allow the agent to take any corrective action visible in obs — but the dispatcher currently has no rerouting logic for TAXIING_IN aircraft, so this is a no-op until that is added.
- **Expiry** (gate becomes available again): new gate assignments become possible. No immediate query needed unless a LANDED aircraft is waiting for a gate with no other options — this is handled naturally when the gate opens and a new task can eventually be created.
- **For now**: gate_fault events do NOT need a dedicated trigger. Log the event in `info` so the observation encodes it (future obs extension).

**`runway_closure`** — Pushes `rwy.available_at` into the future if the runway is FREE, blocking departures.
- **Impact on agent**: TAXIING_OUT aircraft queue at the runway entry node; they simply wait. There is no vehicle assignment decision to make. Runway routing is fully deterministic in the dispatcher.
- **Fires a query**: **no**. The agent has no actions that affect runway usage. The closure resolves automatically when `rwy.available_at` is restored at expiry.
- **Expiry**: runway becomes free again; TAXIING_OUT aircraft can depart next tick. No agent query needed.

**`late_arrival`** — Applied at `trigger_time=0.0` (episode start, before the first `_advance_to_decision()` call). It simply shifts `ac.scheduled_arrival` forward.
- **Fires a query**: **no**. Applied before the episode loop begins; there are no prior assignments to invalidate.

**Summary table**:

| Disruption type    | Query on apply? | Query on expiry? | Reason |
|--------------------|-----------------|------------------|--------|
| `late_arrival`     | No              | No               | Applied at t=0 before any assignments |
| `vehicle_breakdown`| Yes (conditional) | No (Event A covers it) | Removes resource; Event A fires on expiry |
| `gate_fault`       | No              | No               | No current assignment invalidated; no agent action available |
| `runway_closure`   | No              | No               | Agent has no runway-related actions |

The conditional vehicle_breakdown trigger is: query only if the breakdown eliminates the last compatible free vehicle for at least one pending task (i.e., `_has_decision_point()` was True before the breakdown and is now False). Otherwise the assignment pool is unchanged and no query is needed.

### What should NOT trigger a query
- The agent just HOLDed and nothing changed — do not re-query.
- A free vehicle exists but no legal tasks for it — auto-hold internally, keep ticking.
- Multiple tasks pending but no vehicles free — sim should keep running; no agent choice is available.

In other words: **only trigger on state transitions, not on persistent state**.

---

## 4. Proposed Implementation Approach

### Core change: event-driven `_advance_to_decision()`

Replace the condition `_has_decision_point()` with two event detectors inside the tick loop:

```python
def _advance_to_decision(self) -> float:
    reward = 0.0
    ticks  = 0

    # Snapshot state before ticking
    prev_vehicle_states = {
        vid: v.state for vid, v in self.dispatcher.vehicles.items()
    }
    prev_pending_count = len(self.dispatcher.pending_tasks)

    while self._sim_time < SIM_HORIZON:
        self.dispatcher.tick(self._sim_time, dt=1.0)
        self._sim_time += 1.0
        ticks += 1

        reward += self._compute_tick_rewards()  # delay + departure + conflict

        if all(a.state == AircraftState.DEPARTED
               for a in self.dispatcher.aircraft.values()):
            break

        # --- Event detection ---

        # Event A: a vehicle just became free
        vehicle_freed = False
        for vid, v in self.dispatcher.vehicles.items():
            if (prev_vehicle_states.get(vid) != VehicleState.IDLE
                    and v.state == VehicleState.IDLE):
                vehicle_freed = True
                break

        # Event B: new task(s) entered the pending queue
        new_tasks_arrived = len(self.dispatcher.pending_tasks) > prev_pending_count

        # Update snapshots for next tick
        prev_vehicle_states = {
            vid: v.state for vid, v in self.dispatcher.vehicles.items()
        }
        prev_pending_count = len(self.dispatcher.pending_tasks)

        # Only trigger if something changed AND there is actionable work
        if (vehicle_freed or new_tasks_arrived) and self._has_decision_point():
            break

        if ticks >= MAX_TICKS_PER_STEP:
            break

    return reward
```

### Event C: vehicle_breakdown fires and eliminates the last compatible vehicle

Add a third event detector in the tick loop, after the disruption manager's `apply_tick` has run:

```python
# Event C: vehicle_breakdown just fired and made a pending task un-assignable
breakdown_fired = False
if hasattr(self.dispatcher, 'disruption_manager') and self.dispatcher.disruption_manager:
    for ev in self.dispatcher.disruption_manager._events:
        if (ev.event_type == "vehicle_breakdown"
                and ev._applied
                and not ev._active   # just applied this tick
                # "just applied" = applied flag flipped this tick; use a prev snapshot
        ):
            breakdown_fired = True
            break
```

> **Note**: the exact "just applied this tick" detection requires tracking `prev_applied_set` (set of applied event IDs from the previous tick) alongside `prev_vehicle_states`. This is a small additional snapshot. Only trigger if `breakdown_fired AND NOT _has_decision_point()` (i.e., the breakdown removed the last compatible vehicle; if assignable work still exists, Event A or B will catch the relevant moment).

### Safety valve for degenerate HOLD loops (GAP 2)

With event-based triggering it is possible — due to bugs or edge-case scheduling — for the sim to advance an arbitrarily long time without any event firing. The current `MAX_TICKS_PER_STEP = 3600` safety cap exists in `_advance_to_decision()` but it only fires a return; there is no explicit warning.

The updated approach must add a **secondary inactivity cap** with a warning:

```python
# Inside _advance_to_decision(), at the end of each tick iteration:
INACTIVITY_WARN_TICKS = 600   # 10 sim-minutes with no event = likely a bug

if ticks % INACTIVITY_WARN_TICKS == 0 and ticks > 0:
    import warnings
    warnings.warn(
        f"[AirportEnv] No decision event in {ticks} ticks "
        f"(sim_time={self._sim_time:.0f}s). "
        f"Pending tasks: {len(self.dispatcher.pending_tasks)}, "
        f"free vehicles: {sum(1 for v in self.dispatcher.vehicles.values() if v.is_available())}. "
        f"Forcing query.",
        RuntimeWarning,
        stacklevel=2,
    )
    if self._has_decision_point():
        break   # Force query with normal mask
    # If no decision point exists either, continue running — this is normal
    # (e.g., all vehicles busy, no tasks pending, waiting for next arrival)
```

Key design decisions:
- **600-tick threshold, not MAX_TICKS_PER_STEP**: 10 minutes of sim time with pending work and available vehicles is abnormal; the current 1-hour cap is too loose to surface bugs quickly.
- **Warning, not exception**: the episode continues uninterrupted; the warning surfaces in training logs for debugging.
- **Only force-query if `_has_decision_point()` is True**: if no actionable work exists, the inactivity is expected (waiting for an aircraft to land, for a service to complete, etc.) and the sim continues silently.
- **Normal operation**: this valve should never fire in a correct implementation. If it fires repeatedly during training, it signals a missed event type in the detector.

### Event batching: query exactly once per tick (GAP 3)

If multiple events fire within the same sim tick — e.g., two vehicles simultaneously complete service (both transition to IDLE) and a new task is also added — the env must query the agent **exactly once**, not once per event.

This is guaranteed by the current implementation plan because:
1. `_advance_to_decision()` calls `dispatcher.tick()` once per loop iteration.
2. All event detection happens after `tick()` returns, reading the post-tick state.
3. The `break` fires at most once per loop iteration regardless of how many events were detected.

```python
# The check is a single OR across all event flags:
if (vehicle_freed or new_tasks_arrived or breakdown_fired) and self._has_decision_point():
    break   # exits once, even if all three flags are True
```

The agent then receives a single observation that reflects the full post-tick state: all newly-freed vehicles, all new tasks, all active disruptions. It makes one decision and returns. There is no risk of querying twice in one tick.

**Implication for the observation**: the obs `_build_obs()` already encodes all vehicle states and pending tasks in a single flat vector. No change needed — the existing obs naturally batches all simultaneous state changes.

### Action space implications

No change to `Discrete(17)`. Action masking remains unchanged. The key difference is that when the agent HOLDs, `_advance_to_decision()` will **not** return on the next tick — it will keep running until something genuinely changes (a vehicle finishes, a new task arrives). This means:

- A HOLD is now meaningful: "I don't want to assign right now; come back when the situation changes."
- A HOLD in a state with all vehicles busy and no pending tasks already never triggers (correct).
- A HOLD when tasks exist but vehicles are all busy: sim advances until a vehicle frees up.
- A HOLD when tasks AND free vehicles exist: this is still a valid hold (maybe saving vehicle for higher-priority upcoming task), but the agent should NOT be re-queried 1 tick later for the same frozen state.

The remaining question is whether we should auto-assign when only ONE legal assignment exists (no real choice). That would further reduce noise but changes the action space semantics. Recommend keeping it as is for now and letting action masking handle it — the agent will learn quickly when there's only one legal action.

### Interaction with the hold penalty

The existing `REWARD_HOLD_WITH_WORK = -0.1` penalty applies when the agent holds while a valid assignment exists. With the new trigger, this penalty fires legitimately: the agent is only queried when there IS a valid assignment, and holding now has real cost because the sim won't return to the agent until something changes. The -0.1 becomes a meaningful signal rather than noise accumulated 9000×.

### Expected episode query count after fix

With event-driven triggers:
- Queries per aircraft: roughly (num_service_tasks + 1 pushback) = 4 per aircraft
- For 10-aircraft episode: ~40 queries
- Possible extras from multi-task bundles (when 3 tasks appear at once and 1 assignment frees up another vehicle): still O(tasks), not O(ticks)
- Expected ratio: < 2:1 (maybe 1.1:1 if tasks always clear in one shot)

This eliminates the 243:1 noise and forces the policy to learn from real scheduling decisions.

---

## 5. Scope of `pending_tasks`: Currently-Actionable Only (GAP 4)

### What the code actually does

`pending_tasks` is **currently-actionable only**. Tasks are never pre-populated for future arrivals. The two places that create tasks:

**`dispatcher._create_service_tasks()` (dispatcher.py:260-285)**:
```python
def _create_service_tasks(self, now: float) -> None:
    for ac in self.aircraft.values():
        if ac.state != AircraftState.AT_GATE:
            continue
        ...
        for svc in ac.service_requirements.required_services():
            if svc == "pushback":
                continue
            if svc not in existing:
                task = ServiceTask(...)
                self.pending_tasks.append(task)
```
Guard: `ac.state != AircraftState.AT_GATE` — tasks are created only after the aircraft physically arrives at the gate. An aircraft still APPROACHING, LANDED, or TAXIING_IN has no pending tasks yet.

**`dispatcher._handle_pushback()` (dispatcher.py:439-475)**:
```python
def _handle_pushback(self, now: float) -> None:
    for ac in self.aircraft.values():
        if ac.state != AircraftState.AT_GATE:
            continue
        if not ac.all_services_done():
            continue
        if now < ac.scheduled_departure:
            continue
        ...
        task = ServiceTask(..., service_type="pushback", ...)
        self.pending_tasks.append(task)
```
Guards: aircraft must be AT_GATE, all other services done, AND `now >= scheduled_departure`. Pushback tasks are created at the latest possible moment.

**`sim/scheduler.py`**: `load_schedule()` only creates `Aircraft` objects; it never touches `pending_tasks`. No future task pre-population happens at schedule load time.

### Consequence for the agent

The agent is flying blind during the critical window between an aircraft's scheduled arrival and when it physically reaches its gate (APPROACHING → LANDED → TAXIING_IN → AT_GATE). This can take 60–300+ sim seconds depending on taxi distance. During this time:
- The agent sees in obs that an aircraft exists (`is_active=1`) with a state less than AT_GATE
- But no tasks appear in the pending-task slots
- The agent cannot pre-position vehicles toward the gate in anticipation

A human dispatcher would know "AA101 lands in 4 minutes at gate A2 — send the fuel truck now so it arrives concurrently." The current design forces the agent to react after the fact.

### Proposed expansion: "anticipated task" slots with actionability flag

**Do not implement yet — document only.**

Add a flag `is_actionable: bool` to `ServiceTask` (default `True` for all currently-created tasks). Populate "anticipated tasks" in the observation by reading the schedule for aircraft that are APPROACHING or TAXIING_IN, projecting their service requirements, and materialising `ServiceTask` objects with `is_actionable=False`.

```python
# Sketch — not for implementation now
class ServiceTask:
    ...
    is_actionable: bool = True   # False = task exists but no vehicle assignment yet allowed

# In _create_anticipated_tasks(now):
#   for ac in aircraft with state in {APPROACHING, TAXIING_IN}:
#       project gate (from ac.assigned_gate or nearest free gate estimate)
#       for svc in ac.service_requirements.required_services():
#           if no existing task for this (flight_id, svc_type):
#               push ServiceTask(..., is_actionable=False) into a separate anticipated_tasks list
```

The action mask would only expose `is_actionable=True` tasks for assignment, so the agent cannot prematurely assign a vehicle that can't service a not-yet-arrived aircraft. But the observation would encode anticipated tasks in the task slots (using `is_active=1, is_actionable=0` encoding), giving the agent the lookahead it needs to pre-position vehicles.

**Why this matters**: with the event-driven trigger fix, the agent will be queried ~40 times per episode instead of ~9000. Each query is now a real scheduling decision. Lookahead lets the agent make the optimal pre-positioning choice at those 40 moments rather than always reacting. This is the difference between a reactive dispatcher and a proactive one.
