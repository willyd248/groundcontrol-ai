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

### (c) Disruption event (future extension)
Vehicle breakdown, gate closure, runway closure would require replanning. Not currently modelled in the sim but the trigger framework should accommodate them.

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
