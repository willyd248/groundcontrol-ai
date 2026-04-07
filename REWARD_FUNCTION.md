# REWARD_FUNCTION.md — Full Reward Function Reference

This document lists every reward signal in `env/airport_env.py` with the
constant values, firing conditions, and design rationale. Do not change any
reward magnitude without updating this file and getting explicit approval.

---

## Constants (airport_env.py:141–148)

| Constant | Value | Description |
|---|---|---|
| `REWARD_PER_DELAY_MINUTE` | −1.0 | Per flight-minute of new departure delay this tick |
| `REWARD_ONTIME_DEPARTURE` | +10.0 | Bonus when a flight departs ≤ 5 min late |
| `REWARD_LATE_DEPARTURE` | +2.0 | Consolation bonus when a flight departs > 5 min late |
| `REWARD_HOLD_WITH_WORK` | −0.1 | Agent held when a legal assignment existed |
| `REWARD_CONFLICT` | −50.0 | Per new taxiway/runway conflict detected |
| `REWARD_PENDING_AT_TIMEOUT` | −20.0 | Per flight still active when sim_time ≥ SIM_HORIZON |
| `REWARD_ABANDONMENT` | −1.0 | Per minute of service time wasted on an abandoned task |

---

## Signal 1 — Delay accumulation (fires every tick)

**Location:** `_compute_tick_reward()` → `delay_reward`

```python
# airport_env.py
current_delay = 0.0
for ac in self.dispatcher.aircraft.values():
    if ac.state == AircraftState.DEPARTED:
        continue
    if ac.scheduled_departure < float("inf") and now > ac.scheduled_departure:
        current_delay += (now - ac.scheduled_departure) / 60.0  # minutes

delay_reward = REWARD_PER_DELAY_MINUTE * max(0.0, current_delay - self._prev_delay_total)
self._prev_delay_total = current_delay
```

**What it does:** Accumulates departure delay in minutes across all undeparted
flights. Each tick, the reward is the incremental new delay since last tick
(delta, not cumulative). `_prev_delay_total` resets at the start of each episode.

**Intent:** Urgent, continuous pressure to get aircraft out on time.
Scale: an aircraft 1 minute late costs −1.0; 10 minutes late costs −10.0
(cumulatively across those 10 minutes).

**Edge case:** Only fires once the flight is past `scheduled_departure`. Pre-
departure ticks cost nothing.

---

## Signal 2 — On-time departure bonus (fires once per departure)

**Location:** `_compute_tick_reward()` → `dep_reward`

```python
for ac in self.dispatcher.aircraft.values():
    if ac.state == AircraftState.DEPARTED and ac.flight_id not in self._departed_ids:
        self._departed_ids.add(ac.flight_id)
        if ac.actual_departure is not None and ac.scheduled_departure < float("inf"):
            delay_min = (ac.actual_departure - ac.scheduled_departure) / 60.0
            dep_reward += (
                REWARD_ONTIME_DEPARTURE if delay_min <= 5.0
                else REWARD_LATE_DEPARTURE
            )
```

**What it does:** One-shot bonus when a flight departs. +10.0 if ≤ 5 minutes
late; +2.0 if late. Never fires twice for the same flight (`_departed_ids` set).
Does not fire for arrival-only flights (they have `scheduled_departure = inf`).

**Intent:** Strong positive signal for on-time performance. The +10/+2 ratio
makes on-time departures 5× more valuable than late ones, creating urgency to
complete services before departure time.

---

## Signal 3 — Hold penalty (fires once per step, not per tick)

**Location:** `step()` before `_advance_to_decision()`

```python
if can_assign:
    self._assign_one_task(action)
else:
    if self._has_decision_point():
        reward += REWARD_HOLD_WITH_WORK   # −0.1
```

**What it does:** Applies −0.1 once per `step()` call when the agent chooses
HOLD (or an invalid action) and a valid assignment existed at that moment.

**Intent:** Small, persistent pressure to assign rather than wait. Intentionally
small (−0.1 vs −1.0/min delay) so it doesn't dominate — delay is the primary
signal, hold penalty is a tiebreaker.

**After Step 2 change:** With event-based triggering, this penalty fires at most
once per genuine scheduling event (not 9000×/episode). It is now a meaningful
signal rather than noise.

---

## Signal 4 — Conflict penalty (fires per tick, per new conflict)

**Location:** `_advance_to_decision()` tick loop

```python
new_conflicts = self.dispatcher.conflict_count - self._prev_conflict_count
if new_conflicts > 0:
    reward += REWARD_CONFLICT * new_conflicts   # −50.0 each
    self._prev_conflict_count = self.dispatcher.conflict_count
```

**What it does:** Penalises each new taxiway segment conflict detected by the
world graph (two aircraft/vehicles attempt to occupy the same segment). Counted
via `dispatcher.conflict_count` which increments in `_advance_aircraft()` and
`_advance_vehicles()` when `ConflictError` is raised.

**Intent:** Hard deterrent. −50.0 per conflict is large relative to the delay
signal, making conflict avoidance a near-absolute constraint. In practice,
conflicts are rare under normal operation (separation logic prevents most).

---

## Signal 5 — Pending-at-timeout penalty (fires once at truncation)

**Location:** `step()` on truncation

```python
if truncated:
    n_pending = sum(
        1 for a in self.dispatcher.aircraft.values()
        if a.state != AircraftState.DEPARTED
    )
    reward += REWARD_PENDING_AT_TIMEOUT * n_pending   # −20.0 per flight
```

**What it does:** One-shot penalty when the episode is truncated (`sim_time ≥
SIM_HORIZON = 4 hours`) with flights still active. −20.0 per unfinished flight.

**Intent:** Ensures the policy cannot exploit the timeout by holding until
truncation to avoid delay penalties. −20.0 per flight exceeds the typical maximum
delay penalty for a single flight (most flights depart within 60–90 minutes of
scheduled time, so maximum delay is ~30–90 min → −30 to −90). This means it is
always better to depart late than to not depart at all.

---

## Signal 6 — Abandonment penalty (fires per orphaned task, added Step 3)

**Location:** `_compute_tick_reward()` after departure bonus

```python
for task_id, task in self.dispatcher.active_tasks.items():
    if task_id in self._abandoned_task_ids:
        continue
    vehicle = self.dispatcher.vehicles.get(task.assigned_vehicle_id)
    if vehicle is None:
        continue
    if vehicle.state not in (VehicleState.EN_ROUTE, VehicleState.SERVICING):
        time_spent = (now - task.started_at) / 60.0 if task.started_at else 0.0
        dep_reward += REWARD_ABANDONMENT * max(0.0, time_spent)   # −1.0/min
        self._abandoned_task_ids.add(task_id)
```

**What it does:** Detects tasks in `active_tasks` whose assigned vehicle is no
longer EN_ROUTE or SERVICING (vehicle was force-released mid-task). Applies a
one-shot penalty of −1.0 per minute of service time already spent.

**Intent:** Makes abandonment strictly worse than completion. If a vehicle spent
T minutes on a task and then abandons, the −T reward for wasted work plus the
cost of re-servicing exceeds the cost of completing the original service.

**In normal operation (no disruptions):** This loop iterates over an empty or
static `active_tasks` and never fires. Zero performance overhead.

**Fires when:** Future disruption code force-releases a committed vehicle mid-
task (e.g., a breakdown that hits an EN_ROUTE vehicle). Does not fire for normal
service completion.

---

## Total reward decomposition (typical 10-flight episode)

| Signal | Typical range | Notes |
|--------|---------------|-------|
| Delay accumulation | −0 to −200 | Depends heavily on dispatch speed |
| Departure bonuses | +10 to +100 | +10 per on-time flight |
| Hold penalty | −0.1 to −5.0 | With Step 2 fix: ~40 steps × −0.1 = −4 max |
| Conflict penalty | 0 (rarely fires) | Separation logic prevents most |
| Pending at timeout | 0 or −20 to −240 | 0 if all flights depart before 4 hours |
| Abandonment | 0 (normal ops) | Fires only on disruption force-release |

**On-time, no-conflict, no-timeout episode:** approximately +60 to +100.
**Chaotic episode (all late, some abandoned):** approximately −100 to −300.

---

## What requires Will's approval before changing

1. Any change to `REWARD_ONTIME_DEPARTURE` / `REWARD_LATE_DEPARTURE` ratio
   (changes the relative value of on-time vs late departures).
2. Any change to `REWARD_CONFLICT` (touching the conflict deterrent).
3. Any change to `REWARD_PENDING_AT_TIMEOUT` (affects the timeout exploitation
   boundary — must remain > max possible delay per flight).
4. Introducing a new reward signal (update this document first).
