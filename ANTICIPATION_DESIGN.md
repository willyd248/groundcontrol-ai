# ANTICIPATION_DESIGN.md — Anticipation Upgrade

**Date:** 2026-04-08
**Status:** Design review (pre-implementation)
**Branch:** fix-decision-trigger
**Prerequisite:** v5 2M retrain complete (3% win rate, -9.1 min mean delta)

---

## Section 1 — Problem Statement

### The reactive ceiling

The v5 2M retrain conclusively demonstrates that a purely reactive policy cannot meaningfully beat FCFS. Key evidence:

- **3% win rate** on 100-seed battery (vs 0% at 1M)
- **-9.1 min mean delta** vs FCFS — the policy is *worse* on average
- **-7.8 min mean delta on OOD seeds** (FAILURE_DIAGNOSTIC.md, Diagnostic 4: 0/20 wins, -10.1 min mean on seeds 200-219)

The 500k checkpoint analysis (FAILURE_DIAGNOSTIC.md, Diagnostic 2) shows that 100% of divergences from FCFS are task reorderings, zero are HOLD-vs-assign. The policy learned a rigid "baggage-first, fuel-later" heuristic from its training distribution that is uniformly destructive on unseen schedules. This heuristic was the only strategy available given the observation space — without knowledge of upcoming arrivals, the only "signal" the policy can learn is a static task-type preference.

### Why reactive can't solve this

The fundamental problem is stated in DECISION_TRIGGER.md Section 5:

> *"The agent is flying blind during the critical window between an aircraft's scheduled arrival and when it physically reaches its gate (APPROACHING -> LANDED -> TAXIING_IN -> AT_GATE). This can take 60-300+ sim seconds depending on taxi distance."*

Consider this concrete scenario with the v5 fleet (FT x1, BT x2, PB x1):

1. A CRJ900 is at gate A1 needing fuel (20s service time)
2. A B777 is APPROACHING, landing in 90s, will reach gate B1 ~180s from now and need fuel (120s service time)
3. The single fuel truck just became IDLE at DEPOT

The optimal action is to **wait** and reserve the fuel truck for the B777 — its 120s fuel service is the binding constraint on a ~300-bag aircraft with tight slack. Fueling the CRJ900 first means the B777 waits an additional 20s + travel time for the fuel truck, potentially cascading into a late departure.

But today's agent sees: one pending fuel task (CRJ900), one free fuel truck, no upcoming tasks. The mask forces assignment. The agent cannot even represent "save this resource for something more important arriving soon." There is no observation of the B777's impending arrival, no action to reserve the truck, and HOLD is masked when assignments exist.

The reactive policy's ceiling is FCFS with random noise. To beat FCFS, the agent needs **anticipation**: knowledge of future demand and the ability to pre-commit resources.

---

## Section 2 — Conceptual Design

### Anticipated tasks

Add a new data structure `anticipated_tasks` to the dispatcher: a list of scheduled-but-not-yet-actionable service tasks for flights arriving within a **600-second lookahead horizon**.

Each anticipated task represents a service that **will** be needed once the flight reaches its gate, but is not yet actionable because the aircraft hasn't arrived. The structure contains:

| Field | Type | Description |
|-------|------|-------------|
| `flight_id` | str | Which flight this task belongs to |
| `task_type` | str | "fuel", "baggage_unload", "baggage_load" (not pushback — too far in the future) |
| `time_until_actionable` | float | Estimated seconds until the flight reaches its gate and the task becomes a real pending task |
| `aircraft_type` | str | "B737", "A320", "B777", "CRJ900" — determines resource intensity |
| `aircraft_size_class` | int | 0=small (CRJ900), 1=medium (B737/A320), 2=heavy (B777) — for obs encoding |
| `service_duration_estimate` | float | Estimated service time in seconds based on aircraft type defaults |
| `gate_node_estimate` | str | Best-guess gate assignment (nearest free gate from runway exit, or already-assigned gate) |

### How anticipated tasks are generated

Each tick, for every aircraft in state APPROACHING or TAXIING_IN within the 600s horizon:

1. **Estimate time-to-gate**: For APPROACHING aircraft, estimate = (scheduled_arrival - now) + average_taxi_time (~120s). For TAXIING_IN aircraft, estimate = remaining path length / taxi speed.
2. **Project service requirements**: Read `aircraft.service_requirements` to determine which services will be needed (fuel, baggage_unload, baggage_load). Pushback is excluded — it depends on departure time and service completion, making it unpredictable at this stage.
3. **Estimate gate**: If the aircraft already has `assigned_gate`, use that gate's node. Otherwise, estimate using the nearest free gate from the expected arrival node (same logic as `_find_nearest_free_gate`).

### What the agent can do with anticipated tasks

The agent **cannot assign** a vehicle to an anticipated task (the aircraft isn't at the gate yet — there's nothing to service). Instead, the agent can **reserve** a vehicle for an anticipated task. This is a new action type described in Section 3.

A reservation means: "Vehicle X is committed to anticipated task Y. Vehicle X is unavailable for other assignments until Y becomes actionable (auto-assigned) or the reservation expires."

When the anticipated task's flight reaches its gate and the task materializes as a real pending task, the reserved vehicle is **automatically assigned** — no agent decision needed. If the reservation expires (flight diverts, aircraft cancelled, or time exceeds 2x the estimated time-to-actionable), the vehicle is released back to the free pool and a small penalty is applied.

---

## Section 3 — Action Space Changes

### New action: "reserve vehicle X for anticipated task Y"

The current action space is `Discrete(17)`: 16 pending-task assignment slots + 1 HOLD.

The new action space adds reservation actions:

| Action range | Meaning |
|-------------|---------|
| 0..15 | Assign pending_tasks[i] to nearest free compatible vehicle (unchanged) |
| 16..23 | Reserve a free compatible vehicle for anticipated_tasks[i-16] (NEW) |
| 24 | HOLD (shifted from 16) |

**New action space: `Discrete(25)`** — 16 assignment slots + 8 reservation slots + 1 HOLD.

MAX_ANTICIPATED = 8 is chosen because:
- 600s horizon x typical tight-schedule arrival rate (~1 flight per 60-120s) = 5-10 flights
- Each flight generates 3 anticipated tasks (fuel, baggage_unload, baggage_load)
- But the agent only needs to reserve for the most impactful — 8 slots covers the top priorities
- The anticipated task list is sorted by urgency (lowest time_until_actionable first)

### Reservation mechanics

When the agent selects action `i` in [16..23]:
1. Identify `anticipated_tasks[i - 16]`
2. Find the nearest free compatible vehicle (same logic as `_find_nearest_vehicle`)
3. Set `vehicle.reserved_for = anticipated_task_id`
4. Set `vehicle.reserved_until = now + 2 * time_until_actionable` (expiry)
5. Vehicle is now **unavailable** for regular assignment (but not physically moving yet)

When the anticipated task becomes a real pending task (aircraft reaches gate):
1. If the reserved vehicle is still free and reserved for this task → auto-assign, clear reservation
2. If the reserved vehicle was released (reservation expired) → task enters normal pending queue

### Action mask logic

**Assignment actions (0..15):** Unchanged — `mask[i] = True` iff `pending_tasks[i]` exists AND a free compatible vehicle exists.

**Reservation actions (16..23):** `mask[i] = True` iff:
1. `anticipated_tasks[i - 16]` exists, AND
2. A free compatible vehicle exists for this task type, AND
3. `time_until_actionable > estimated_travel_time + 30s buffer` (no point reserving if the task will be actionable before the vehicle could arrive — just wait for the normal assignment), AND
4. No vehicle is already reserved for this specific anticipated task

**HOLD (24):** Legal ONLY when no assignment actions AND no reservation actions are legal. Same mutual-exclusion rule as current HOLD masking.

### Action space size summary

| Component | Current | New |
|-----------|---------|-----|
| Assignment slots | 16 | 16 |
| Reservation slots | 0 | 8 |
| HOLD | 1 | 1 |
| **Total** | **17** | **25** |

---

## Section 4 — Observation Space Changes

### New observation features for anticipated tasks

Add per-anticipated-task features (MAX_ANTICIPATED = 8 slots):

| Feature | Encoding | Range |
|---------|----------|-------|
| `time_until_actionable` | seconds / 600 (horizon) | [0, 1] |
| `task_type_onehot` | 3 dims: fuel, baggage_unload, baggage_load | {0, 1} |
| `aircraft_size_onehot` | 3 dims: small, medium, heavy | {0, 1} |
| `service_duration_norm` | duration / 150 (max = B777 baggage) | [0, 1] |
| `is_active` | 1 if slot is populated | {0, 1} |

Features per anticipated task: **9**
Total for 8 slots: **72**

### Additional global features

| Feature | Encoding | Range |
|---------|----------|-------|
| `n_anticipated_beyond_window` | count of flights beyond 600s horizon that have scheduled arrivals within SIM_HORIZON, / 20 | [0, 1] |
| `earliest_time_until_actionable` | min time_until_actionable across all anticipated tasks, / 600 | [0, 1], or 1.0 if none |
| `n_active_reservations` | count of vehicles currently reserved, / MAX_VEHICLES | [0, 1] |

Additional global dims: **3**

### New observation dimension

| Component | Current dims | New dims |
|-----------|-------------|----------|
| sim_time | 1 | 1 |
| Aircraft slots (20 x 8) | 160 | 160 |
| Vehicle slots (4 x 4) | 16 | 16 |
| Pending task slots (16 x 5) | 80 | 80 |
| n_pending_norm | 1 | 1 |
| **Anticipated task slots (8 x 9)** | **0** | **72** |
| **Global anticipation features** | **0** | **3** |
| **Total OBS_DIM** | **258** | **333** |

### Vehicle slot update

Add one feature to each vehicle slot to encode reservation status:

| Feature | Encoding | Range |
|---------|----------|-------|
| `is_reserved` | 1 if vehicle has an active reservation | {0, 1} |

This changes VEH_FEATURES from 4 to 5, adding 4 dims (4 vehicles x 1 feature).

**Revised total: OBS_DIM = 258 + 72 + 3 + 4 = 337**

### Architecture incompatibility

The observation space changes from shape `(258,)` to shape `(337,)`. This is a **breaking change** — the MlpPolicy input layer has a fixed width. The v5 2M checkpoint cannot be loaded or fine-tuned. **Training must start from scratch.**

This is acceptable because:
1. The v5 policy has no useful knowledge to transfer (3% win rate, reactive heuristic)
2. The new observation features are the entire point — without them the policy cannot learn anticipation
3. The action space also changed (17 -> 25), which independently requires retraining

---

## Section 5 — Reward Shaping

### Principle: minimal changes

The current reward function (REWARD_FUNCTION.md) is well-calibrated and tested. The anticipation upgrade should add the minimum reward signal needed to learn reservation behavior without destabilizing existing signals.

### New reward signals

**Signal 7 — Reservation auto-assignment bonus** (fires once per successful reservation fulfillment)

When a reserved vehicle is auto-assigned to the materialized task:
```
+1.0  (flat bonus, same scale as REWARD_PER_DELAY_MINUTE)
```

**Why +1.0:** Small enough to not dominate delay penalties (-1.0/min), but provides a positive gradient for learning that reservations lead to assignments. The real payoff of good reservations shows up in the existing delay reduction signals.

**Signal 8 — Reservation expiry penalty** (fires once per expired unused reservation)

When a reservation expires without being fulfilled:
```
-0.5  (flat penalty)
```

**Why -0.5:** Half the magnitude of the bonus. Expired reservations waste a vehicle's availability window, but the cost is opportunity cost (other tasks that could have used the vehicle), not direct delay. This penalty is smaller than `REWARD_PER_DELAY_MINUTE` to avoid making the agent overly cautious about reserving.

### Signals NOT added

- No bonus for "correct" reservation timing — too hard to define, let delay signals handle it
- No penalty for failing to reserve — absence of reservation is not an error, FCFS-like reactive play should remain viable
- No reservation-count reward — would incentivize over-reserving

### Updated reward table

| Signal | Value | Fires |
|--------|-------|-------|
| Delay accumulation | -1.0/min | Every tick |
| On-time departure | +10.0 | Once per departure |
| Late departure | +2.0 | Once per departure |
| Hold with work | -0.1 | Once per step |
| Conflict (terminal) | -200.0 | Once, episode ends |
| Conflict (extra) | -50.0 | Per extra same-tick conflict |
| Pending at timeout | -20.0 | Per flight at truncation |
| Abandonment | -1.0/min | Per orphaned task |
| **Reservation fulfilled** | **+1.0** | **Once per auto-assignment** |
| **Reservation expired** | **-0.5** | **Once per expiry** |

---

## Section 6 — Implementation Plan

### Step 1: Anticipated tasks in dispatcher (complexity: medium, ~2 hours)

Add to `Dispatcher`:
- `anticipated_tasks: list[AnticipatedTask]` — new dataclass
- `_update_anticipated_tasks(now)` method called each tick in `tick()`
- Logic: scan aircraft in APPROACHING/TAXIING_IN states, estimate time-to-gate, project service requirements
- 600s lookahead horizon constant
- Sort by urgency (lowest time_until_actionable first)
- Remove anticipated tasks when the flight reaches AT_GATE (they become real pending tasks)

Files: `sim/entities.py` (new `AnticipatedTask` dataclass), `sim/dispatcher.py` (new method + call in `tick()`)

### Step 2: Observation space update (complexity: medium, ~2 hours)

- Update OBS_DIM constant: 258 -> 337
- Add anticipated task encoding in `_build_obs()`
- Add vehicle `is_reserved` feature
- Add global anticipation features (n_anticipated_beyond_window, earliest_time, n_reservations)
- Update obs space docstring

Files: `env/airport_env.py`

### Step 3: Action mask update (complexity: medium, ~2 hours)

- Expand action space: Discrete(17) -> Discrete(25)
- Update `action_masks()` for reservation actions (16..23)
- Reservation mask logic: anticipated task exists + free compatible vehicle + time > travel + buffer
- HOLD shifted to action 24
- Update ACTION_HOLD constant

Files: `env/airport_env.py`

### Step 4: Reservation state on vehicles (complexity: medium, ~2 hours)

- Add `reserved_for: Optional[str]` and `reserved_until: float` to `Vehicle`
- Update `Vehicle.is_available()` to return False when reserved
- Add `_assign_reservation(action)` method in AirportEnv
- Add reservation expiry check in `_advance_to_decision()` tick loop
- Add auto-assignment logic: when anticipated task materializes, check for reserved vehicle

Files: `sim/entities.py`, `env/airport_env.py`

### Step 5: FCFS baseline — leave naive (complexity: zero)

The FCFS baseline dispatcher does not need updating. FCFS is by definition reactive — it never anticipates. The value of the anticipation upgrade is measured against this naive baseline. Changing FCFS to also anticipate would move the goalposts and eliminate the advantage we're trying to create.

Justification: The 14.1% greedy-suboptimality measured in v5 (SPEC.md, Session 5) represents the theoretical headroom with the current fleet and schedule distribution. Anticipation should capture a significant portion of this headroom. If FCFS were upgraded to anticipate, the remaining headroom would shrink and require more sophisticated policy learning.

### Step 6: Tests (complexity: medium, ~3 hours)

New test cases:
- `test_anticipated_tasks_populated`: verify anticipated tasks appear for APPROACHING/TAXIING_IN aircraft within 600s
- `test_anticipated_tasks_cleared`: verify anticipated tasks removed when flight reaches gate
- `test_reservation_action_mask`: verify reservation actions masked correctly
- `test_reservation_auto_assign`: verify reserved vehicle auto-assigned when task materializes
- `test_reservation_expiry`: verify expired reservations free the vehicle and apply penalty
- `test_obs_dim_correct`: verify new OBS_DIM = 337
- `test_action_space_correct`: verify Discrete(25)
- `test_hold_masking_with_reservations`: verify HOLD only legal when no assignments AND no reservations legal
- `test_full_episode_with_anticipation`: run 3 seeds end-to-end, verify zero conflicts

Files: `tests/test_env.py`, `tests/test_anticipated.py` (new)

### Step 7: Smoke test environment (complexity: low, ~30 min)

- Run `python -m env.smoke_test` with updated env
- Verify: episodes complete, no crashes, obs shape correct, action masks valid
- Verify: anticipated tasks appear in info dict
- Spot-check: reservation actions are selected by random policy

Files: `env/smoke_test.py` (update)

### Step 8: 100k training run (complexity: low compute, ~1 hour wall time)

- `python -m train.train_ppo --timesteps 100000 --n-envs 8`
- Verify: training doesn't crash, reward is non-degenerate
- Check: reservation rate > 0% (agent is exploring reservations)
- Check: no conflicts
- Compare 100k delay vs FCFS — don't expect wins yet, just stability

### Step 9: Full 2M training run (complexity: high compute, ~6-8 hours wall time)

- `python -m train.train_ppo --timesteps 2000000 --n-envs 8`
- Full eval at 250k, 500k, 1M, 1.5M, 2M checkpoints
- 100-seed battery at final checkpoint
- Compare against v5 results (3% win rate baseline)

---

## Section 7 — Verification Plan

### Success criteria

| Metric | Target | v5 baseline | Why this target |
|--------|--------|-------------|-----------------|
| Win rate (100 seeds) | >= 30% | 3% | 10x improvement; demonstrates anticipation provides real advantage |
| Mean delta vs FCFS | > -3.0 min | -9.1 min | Cuts deficit by 2/3; closer to parity or better |
| OOD mean delta (seeds 200-219) | > -5.0 min | -10.1 min (FAILURE_DIAGNOSTIC.md) | 50% improvement on unseen schedules |
| Reservation rate | > 5% of decisions | 0% (no reservations exist) | Agent actively using the new capability |
| Seed 40 delta | < +15 min | +27.6 min (estimated from FAILURE_DIAGNOSTIC.md pattern) | Seed 40 is worst-case B777 contention; should benefit most from anticipation |
| Conflict rate | 0% | 0% | No regression on safety |
| Reservation expiry rate | < 50% of reservations | N/A | Agent not over-reserving |

### Checkpoint milestones

| Checkpoint | Expected signal |
|------------|----------------|
| 100k | Reservation rate > 0%; agent exploring; reward non-degenerate |
| 250k | Win rate > 5%; mean delta improving trend |
| 500k | Win rate > 15%; reservation rate stabilizing |
| 1M | Win rate > 25%; OOD performance improving |
| 2M | Target metrics met or clear trajectory toward them |

### Kill criteria

**Stop training and reassess if any of these hold at 500k steps:**

1. **Reservation rate near 0%** — agent is not using the new capability at all. Indicates obs encoding is broken, mask logic prevents reservation exploration, or reward signal is too weak.
2. **Win rate < 5% at 1M** — no improvement over v5 despite new capability. Indicates the anticipation mechanism isn't providing useful signal, or the policy can't learn to exploit it.
3. **Conflict rate > 0** — safety regression. Indicates reservation/auto-assignment logic has a bug that creates invalid states.
4. **Reservation expiry rate > 90%** — agent is reserving indiscriminately. Reward shaping needs adjustment (increase expiry penalty or decrease fulfillment bonus).

---

## Section 8 — Open Questions for Will's Review

1. **Lookahead horizon: 600s (10 min) — right length?** This covers the typical APPROACHING -> AT_GATE transit time (60-300s) plus buffer. Shorter (300s) means less anticipation but simpler learning. Longer (900s) means more anticipated tasks but noisier predictions. Recommendation: start with 600s, tune later if needed.

2. **MAX_ANTICIPATED = 8 slots — enough?** With 10-20 flights and 3 services each, the anticipated queue could theoretically hold 30+ tasks. But 8 slots (sorted by urgency) captures the most impactful decisions. More slots = larger obs space = harder to learn. Recommendation: 8 is fine for v1.

3. **Should reservation prevent vehicle movement, or allow pre-positioning?** Current design: reserved vehicle stays in place until the task materializes. Alternative: reserved vehicle starts moving toward the estimated gate immediately. Pre-positioning is more realistic and powerful, but adds complexity (what happens if the gate estimate is wrong? vehicle has to reroute). Recommendation: start with stationary reservation, add pre-positioning in v2 if results are promising.

4. **Pushback in anticipated tasks — include or exclude?** Current design excludes pushback from anticipated tasks because pushback timing depends on service completion + departure time, making it unpredictable. But for B777s with 120s pushback, reserving the single PB1 early could matter. Recommendation: exclude for v1, revisit after seeing reservation patterns.

5. **Should we increase fleet size alongside anticipation?** The v5 fleet (FT x1, BT x2, PB x1) was chosen to maximize contention. With anticipation, some of that contention becomes manageable, potentially reducing the headroom. Counter-argument: keeping the fleet tight is exactly why anticipation matters — it's about using scarce resources smarter. Recommendation: keep fleet unchanged; if win rate exceeds 60%, consider tightening further.

6. **Reservation expiry multiplier (2x time_until_actionable) — too generous?** If a flight is 300s away, the reservation lasts 600s. This is generous but simple. A tighter expiry (1.5x) forces more precise reservations. Recommendation: start with 2x; if expiry rate is very low, tighten to 1.5x.

7. **Event-based trigger update needed?** The current trigger fires on Event A (vehicle freed) and Event B (new task). Reservation creation doesn't fit either — it's triggered by anticipated task appearing. Need a new **Event D: new anticipated task enters the queue AND a free compatible vehicle exists.** Without this, the agent won't be queried when reservation opportunities arise. Recommendation: implement Event D.

8. **OBS_DIM 337 vs 258 — should we also increase network width?** MlpPolicy default is [64, 64]. With 337 inputs (vs 258), the first hidden layer might be undersized. Consider [128, 128] or [256, 128]. Recommendation: test with [128, 128] first; if results are poor, try larger.
