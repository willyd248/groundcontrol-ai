"""
airport_env.py — Gymnasium environment wrapping the KFIC airport simulator.

Design overview
───────────────
The RL agent replaces the FCFS vehicle-assignment step of the dispatcher.
All other sim logic (taxiing, landings, gate assignment, service durations,
runway rules) runs unmodified inside RLDispatcher, which subclasses Dispatcher
but makes _assign_vehicles() a no-op.

Each env.step(action) does:
  1. Apply one task-assignment action (or hold).
  2. Tick the sim forward until the next decision point:
       "a pending task exists AND a free compatible vehicle exists"
     or the episode ends.
  3. Return (obs, reward, terminated, truncated, info).

Observation space  (flat Box, shape=(OBS_DIM,), dtype=float32, range [-1,1])
─────────────────────────────────────────────────────────────────────────────
Index  Field                        Encoding
─────  ───────────────────────────  ─────────────────────────────────────────
[0]    sim_time_norm                sim_time / SIM_HORIZON  ∈ [0, 1]
[1..160]  aircraft slots (MAX_AIRCRAFT=20, AC_FEATURES=8 each)
  +0   state_norm                  AircraftState ordinal / 7  ∈ [0, 1]
  +1   pos_idx_norm                node index / N_NODES, or -1 if unknown
  +2   time_to_dep_norm            (scheduled_dep - now) / MAX_DEP_WINDOW
                                   clamped to [-1, 1]; +1 = far future
  +3   fuel_done                   1 if "fuel" in services_completed
  +4   baggage_unload_done         1 if "baggage_unload" in services_completed
  +5   baggage_load_done           1 if "baggage_load" in services_completed
  +6   pushback_done               1 if "pushback" in services_completed
  +7   is_active                   1 if slot contains a real aircraft, else 0
[161..180]  vehicle slots (MAX_VEHICLES=4, VEH_FEATURES=5 each)
  +0   state_norm                  VehicleState ordinal / 3  ∈ [0, 1]
  +1   pos_idx_norm                node index / N_NODES  ∈ [0, 1]
  +2   type_norm                   0=fuel_truck, 1=baggage_tug, 2=pushback_tractor
                                   divided by 2  ∈ [0, 1]
  +3   is_free                     1 if vehicle.is_available()
  +4   is_reserved                 1 if vehicle.reserved_for is not None
[181..260]  pending-task slots (MAX_TASKS=16, TASK_FEATURES=5 each)
  +0   svc_type_norm               service type ordinal / 3  ∈ [0, 1]
  +1   gate_idx_norm               gate-node index / N_NODES  ∈ [0, 1]
  +2   age_norm                    (now - created_at) / MAX_DEP_WINDOW  ∈ [0, 1]
  +3   flight_slot_norm            aircraft-slot index / MAX_AIRCRAFT  ∈ [0, 1]
  +4   is_active                   1 if slot contains a real task
[261]  n_pending_norm              len(pending_tasks) / MAX_TASKS  ∈ [0, 1]
[262..333]  anticipated-task slots (MAX_ANTICIPATED=8, ANT_FEATURES=9 each)
  +0   time_until_actionable_norm  time_until_actionable / ANT_HORIZON  ∈ [0, 1]
  +1   svc_fuel                    1 if service_type == "fuel"
  +2   svc_baggage_unload          1 if service_type == "baggage_unload"
  +3   svc_baggage_load            1 if service_type == "baggage_load"
  +4   size_small                  1 if aircraft_size_class == 0 (CRJ900)
  +5   size_medium                 1 if aircraft_size_class == 1 (B737/A320)
  +6   size_heavy                  1 if aircraft_size_class == 2 (B777)
  +7   service_duration_norm       service_duration_estimate / 150  ∈ [0, 1]
  +8   is_active                   1 if slot contains a real anticipated task
[334]  n_anticipated_beyond_norm   flights beyond 600s horizon / 20  ∈ [0, 1]
[335]  earliest_ant_norm           min(time_until_actionable) / 600, or 1.0 if none
[336]  n_reservations_norm         count of reserved vehicles / MAX_VEHICLES
Total: OBS_DIM = 337

Action space  Discrete(MAX_TASKS + MAX_ANTICIPATED + 1 = 25)
─────────────────────────────────────────────────────────────
  action ∈ [0, 15]         → assign pending_tasks[action] to nearest free vehicle
  action ∈ [16, 23]        → reserve free vehicle for anticipated_tasks[action-16]
  action == ACTION_HOLD (24) → do nothing, advance sim

Action masking (MaskablePPO compatible via action_masks())
──────────────────────────────────────────────────────────
  mask[i]  = True  iff pending_tasks[i] exists AND free compatible vehicle exists
  mask[16+j] = True iff anticipated_tasks[j] exists AND free compatible vehicle AND
               time_until_actionable > est_travel_time + 30s AND not already reserved
  mask[ACTION_HOLD] = True ONLY when no assignment AND no reservation action is legal

Reward
──────
  Each sim-tick:
    -1.0 × (new_delay_minutes_accumulated)  [negative for each flight-minute late]
  On successful departure:
    +10  if actual_departure ≤ scheduled_departure + 5 min
    + 2  if late
  Holding when valid assignments exist: -0.1 per step
  Conflict detected: -50 per conflict
  Episode timeout with pending flights: -20 per unresolved flight

Episode termination
───────────────────
  terminated = True   when all flights have departed
  truncated  = True   when sim_time ≥ SIM_HORIZON (4 hours) with flights pending
"""

from __future__ import annotations

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from typing import Optional

from sim.world import build_taxiway_graph, build_gates, build_runways, shortest_path
from sim.scheduler import load_schedule
from sim.entities import (
    AircraftState, VehicleState,
    FuelTruck, BaggageTug, PushbackTractor,
    AnticipatedTask,
)
from sim.dispatcher import Dispatcher

# ── Observation-space constants ───────────────────────────────────────────────

MAX_AIRCRAFT   = 20    # upper bound on flights per episode
MAX_VEHICLES   = 4     # fixed fleet (FT×1, BT×2, PB×1)
MAX_TASKS      = 16    # pending-task slots visible in obs
MAX_ANTICIPATED = 8    # anticipated-task slots visible in obs
SIM_HORIZON    = 14400.0   # 4 hours; hard episode time limit (seconds)
MAX_DEP_WINDOW = 3600.0    # normalisation window for time-to-departure

# Anticipation horizon (must match dispatcher.ANTICIPATION_HORIZON)
ANT_HORIZON = 600.0    # seconds

# Action sentinels
ACTION_HOLD = MAX_TASKS + MAX_ANTICIPATED   # = 24

# Deterministic node index for position encoding (must stay stable)
ALL_NODES = [
    "DEPOT", "TWY_SERVICE", "INTER_NW", "TWY_NORTH", "INTER_NE",
    "TWY_A_ENTRY", "TWY_B_ENTRY",
    "GATE_A1", "GATE_A2", "GATE_A3",
    "GATE_B1", "GATE_B2", "GATE_B3",
    "RWY_09L_ENTRY", "RWY_09R_ENTRY",
]
N_NODES  = len(ALL_NODES)   # 15
NODE_IDX = {n: i for i, n in enumerate(ALL_NODES)}

# Stable ordinal for AircraftState (matches state machine order)
_AC_STATE_LIST = list(AircraftState)          # 8 entries
AC_STATE_IDX   = {s: i for i, s in enumerate(_AC_STATE_LIST)}

# Stable ordinal for VehicleState
_VEH_STATE_LIST = list(VehicleState)          # 4 entries
VEH_STATE_IDX   = {s: i for i, s in enumerate(_VEH_STATE_LIST)}

# Service type index
SVC_TYPES = ["fuel", "baggage_unload", "baggage_load", "pushback"]
SVC_IDX   = {s: i for i, s in enumerate(SVC_TYPES)}

# Vehicle type index
VEH_TYPE_IDX = {"fuel_truck": 0, "baggage_tug": 1, "pushback_tractor": 2}

# Per-entity feature counts (must match docstring table)
AC_FEATURES   = 8
VEH_FEATURES  = 5    # was 4; +1 for is_reserved
TASK_FEATURES = 5
ANT_FEATURES  = 9    # per anticipated-task slot

# Service type onehot index for anticipated tasks (no pushback)
ANT_SVC_TYPES = ["fuel", "baggage_unload", "baggage_load"]

OBS_DIM = (
    1                                  # sim_time_norm
    + MAX_AIRCRAFT  * AC_FEATURES      # 160
    + MAX_VEHICLES  * VEH_FEATURES     # 20  (was 16; +4 from is_reserved)
    + MAX_TASKS     * TASK_FEATURES    # 80
    + 1                                # n_pending_norm
    + MAX_ANTICIPATED * ANT_FEATURES   # 72  (NEW)
    + 3                                # global anticipation features (NEW)
)  # = 337

# ── Reward constants ──────────────────────────────────────────────────────────

REWARD_PER_DELAY_MINUTE        = -1.0   # per flight-minute of new delay this tick
REWARD_ONTIME_DEPARTURE        = +10.0  # departed ≤ 5 min late
REWARD_LATE_DEPARTURE          = +2.0   # departed > 5 min late
REWARD_HOLD_WITH_WORK          = -0.1   # held when valid assignment existed
REWARD_CONFLICT                = -50.0  # per additional conflict in the same tick (rarely > 1)
REWARD_CONFLICT_TERMINAL       = -200.0 # lump-sum on the tick that produces the first conflict
REWARD_PENDING_AT_TIMEOUT      = -20.0  # per flight still pending at truncation
REWARD_ABANDONMENT             = -1.0   # per minute of service time wasted on an abandoned task
REWARD_FULFILLED_RESERVATION   = +1.0   # Signal 7: reservation auto-assigned successfully
REWARD_EXPIRED_RESERVATION     = -1.0   # Signal 8: reservation expired unused (tuned from -0.5, Phase 2, HEALTHY verdict)

# Safety limit: max sim-ticks between decision points before we force a return
MAX_TICKS_PER_STEP = 3600          # 1 sim-hour


# ── RLDispatcher ─────────────────────────────────────────────────────────────

class RLDispatcher(Dispatcher):
    """
    Dispatcher with vehicle assignment disabled.
    The RL environment feeds one action at a time instead.
    All other dispatcher logic (gates, taxiing, runways, services) runs normally.

    Also overrides _create_service_tasks() to implement reservation conversion ordering
    (ANTICIPATION_DESIGN_v2 Section 3): when a new pending task is created, check for a
    matching vehicle reservation BEFORE returning control to the env. If a reservation
    matches, auto-assign the reserved vehicle immediately. The task never appears in
    pending_tasks from the env's perspective.
    """

    def _assign_vehicles(self, now: float) -> None:  # noqa: ARG002
        # Deliberately a no-op — env controls vehicle assignment.
        pass

    def _create_service_tasks(self, now: float) -> None:
        """
        Override of Dispatcher._create_service_tasks with reservation conversion.

        Ordering guarantee (per design doc Section 3):
          1. Call super() to create tasks and append to pending_tasks.
          2. For each newly appended task, check if any vehicle has reserved_for
             matching (flight_id, service_type).
          3. If match found: auto-assign the reserved vehicle, move task to
             active_tasks, remove from pending_tasks. Task never surfaces to agent.
          4. Only after all conversions resolved does control return to env.
        """
        pending_ids_before: set[str] = {t.task_id for t in self.pending_tasks}
        super()._create_service_tasks(now)

        # Reservation conversion: check tasks added by super()
        for task in list(self.pending_tasks):
            if task.task_id in pending_ids_before:
                continue  # not newly added

            key = (task.flight_id, task.service_type)
            matched_vehicle = None
            for v in self.vehicles.values():
                if v.reserved_for == key and now <= v.reserved_until:
                    matched_vehicle = v
                    break

            if matched_vehicle is None:
                continue  # no reservation — stays in pending_tasks for agent

            # Auto-assign the reserved vehicle to this task
            matched_vehicle.assigned_to   = task.flight_id
            matched_vehicle.committed     = True
            matched_vehicle.state         = VehicleState.EN_ROUTE
            matched_vehicle.reserved_for  = None
            matched_vehicle.reserved_until = 0.0
            try:
                path = shortest_path(self.G, matched_vehicle.position, task.gate_node)
                matched_vehicle.path = path[1:]
            except ValueError:
                matched_vehicle.path = []

            task.assigned_vehicle_id = matched_vehicle.vehicle_id
            task.started_at          = now
            self.active_tasks[task.task_id] = task
            self.pending_tasks.remove(task)
            self.vehicles_dispatched    += 1
            self.tasks_started          += 1
            self.reservation_fulfillments += 1


# ── Fleet factory ─────────────────────────────────────────────────────────────

def _build_fleet():
    return [
        FuelTruck(vehicle_id="FT1", position="DEPOT"),
        BaggageTug(vehicle_id="BT1", position="DEPOT"),
        BaggageTug(vehicle_id="BT2", position="DEPOT"),
        PushbackTractor(vehicle_id="PB1", position="DEPOT"),
    ]


# ── AirportEnv ────────────────────────────────────────────────────────────────

class AirportEnv(gym.Env):
    """KFIC airport ground-ops Gymnasium environment. See module docstring."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        schedule_path: str = "schedule.json",
        randomise: bool = False,
        seed: Optional[int] = None,
        density: str = "tight",
    ) -> None:
        super().__init__()
        self.schedule_path = schedule_path
        self.randomise     = randomise
        self._init_seed    = seed
        self.density       = density

        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(OBS_DIM,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(MAX_TASKS + MAX_ANTICIPATED + 1)  # = 25

        # Populated by reset()
        self.dispatcher:       Optional[RLDispatcher] = None
        self._sim_time:        float = 0.0
        self._aircraft_order:  list[str] = []   # stable flight_id order for obs slots
        self._vehicle_order:   list[str] = []   # stable vehicle_id order for obs slots
        self._prev_delay_total:   float = 0.0
        self._prev_conflict_count: int  = 0
        self._departed_ids:    set[str] = set()
        self._conflict_terminated: bool = False
        self._prev_reservation_fulfillments: int = 0
        self._prev_reservation_expirations:  int = 0
        # RNG for generating unique schedule seeds on each reset.
        # Worker rank (self._init_seed) controls the sequence, but each
        # episode draws a fresh seed so the agent sees diverse schedules.
        self._rng = np.random.default_rng(self._init_seed)

    # ── Public Gymnasium API ──────────────────────────────────────────────────

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[dict] = None,
    ):
        super().reset(seed=seed)

        G       = build_taxiway_graph()
        gates   = build_gates()
        runways = build_runways()
        fleet   = _build_fleet()

        if self.randomise:
            from env.random_schedule import generate_schedule
            if seed is not None:
                effective_seed = seed
            else:
                # CRITICAL: each reset must produce a different schedule.
                # self._rng is seeded by worker rank so sequences are
                # reproducible per-worker but non-trivial across episodes.
                effective_seed = int(self._rng.integers(0, 2**31 - 1))
            aircraft_list  = generate_schedule(seed=effective_seed, density=self.density)
            ft = sum(1 for v in fleet if v.vehicle_type == "fuel_truck")
            bt = sum(1 for v in fleet if v.vehicle_type == "baggage_tug")
            pb = sum(1 for v in fleet if v.vehicle_type == "pushback_tractor")
            print(f"SCHEDULE_DENSITY: {self.density}, FLEET: FT={ft} BT={bt} PB={pb}, flights={len(aircraft_list)}")
        else:
            schedule_file = (options or {}).get("schedule", self.schedule_path)
            aircraft_list = load_schedule(schedule_file)

        self.dispatcher = RLDispatcher(
            graph=G, gates=gates, runways=runways,
            aircraft=aircraft_list, vehicles=fleet,
        )

        # Pre-mark gates occupied by departure-only aircraft (already at gate)
        for ac in aircraft_list:
            if ac.state == AircraftState.AT_GATE and ac.assigned_gate is not None:
                gate = self.dispatcher.gates.get(ac.assigned_gate)
                if gate is not None:
                    gate.occupied_by = ac.flight_id

        self._sim_time              = 0.0
        self._aircraft_order        = [a.flight_id for a in aircraft_list]
        self._vehicle_order         = [v.vehicle_id for v in fleet]
        self._prev_delay_total      = 0.0
        self._prev_conflict_count   = 0
        self._departed_ids          = set()
        self._abandoned_task_ids    = set()
        self._conflict_terminated   = False
        self._abandoned_task_ids:  set[str] = set()
        self._prev_reservation_fulfillments = 0
        self._prev_reservation_expirations  = 0

        # Run to the first decision point
        self._advance_to_decision()

        return self._build_obs(), self._build_info()

    def step(self, action: int):
        reward = 0.0

        # --- Apply the action ------------------------------------------------
        is_hold    = (action == ACTION_HOLD)
        is_reserve = MAX_TASKS <= action < ACTION_HOLD
        can_assign = (not is_hold and not is_reserve) and self._is_valid_assignment(action)
        _ant_idx   = action - MAX_TASKS
        can_reserve = (
            is_reserve
            and _ant_idx < len(self.dispatcher.anticipated_tasks)
            and self._is_valid_reservation(
                _ant_idx, self.dispatcher.anticipated_tasks[_ant_idx]
            )
        )

        action_taken = False
        if can_assign:
            self._assign_one_task(action)
            action_taken = True
        elif can_reserve:
            self._assign_reservation(action)
            action_taken = True
        else:
            # Penalise if the agent held/chose invalid action when work existed
            if self._has_decision_point():
                reward += REWARD_HOLD_WITH_WORK

        # --- Advance sim to next decision point ------------------------------
        reward += self._advance_to_decision(action_taken=action_taken)

        # --- Termination -----------------------------------------------------
        all_done  = all(
            a.state == AircraftState.DEPARTED
            for a in self.dispatcher.aircraft.values()
        )
        timed_out = self._sim_time >= SIM_HORIZON

        terminated = all_done or self._conflict_terminated
        truncated  = (not terminated) and timed_out

        if truncated:
            n_pending = sum(
                1 for a in self.dispatcher.aircraft.values()
                if a.state != AircraftState.DEPARTED
            )
            reward += REWARD_PENDING_AT_TIMEOUT * n_pending

        return self._build_obs(), reward, terminated, truncated, self._build_info()

    def action_masks(self) -> np.ndarray:
        """
        Boolean mask of shape (25,) for use with sb3-contrib MaskablePPO.
        True = the action is legal this step.

        Action layout:
          0..15  — assign pending_tasks[i] to nearest free vehicle
          16..23 — reserve free vehicle for anticipated_tasks[i-16]
          24     — HOLD (ACTION_HOLD)

        HOLD masking rule: HOLD is legal ONLY when zero assignment AND zero
        reservation actions are legal.  This enforces the event-based trigger
        contract: the trigger only fires when something actionable exists.
        """
        mask = np.zeros(MAX_TASKS + MAX_ANTICIPATED + 1, dtype=bool)
        any_actionable = False

        # Assignment actions (0..15)
        for i in range(min(len(self.dispatcher.pending_tasks), MAX_TASKS)):
            if self._is_valid_assignment(i):
                mask[i] = True
                any_actionable = True

        # Reservation actions (16..23)
        ant_tasks = self.dispatcher.anticipated_tasks[:MAX_ANTICIPATED]
        for j, ant in enumerate(ant_tasks):
            if self._is_valid_reservation(j, ant):
                mask[MAX_TASKS + j] = True
                any_actionable = True

        # HOLD only when nothing else is actionable
        mask[ACTION_HOLD] = not any_actionable
        return mask

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _has_assignment_point(self) -> bool:
        """Return True if any pending task has a compatible free vehicle (assignment only).
        Used for event detection (Events A/B/C) and safety valve — does NOT include
        reservation actions, since reservations do not add new query triggers per design."""
        for i in range(len(self.dispatcher.pending_tasks)):
            if self._is_valid_assignment(i):
                return True
        return False

    def _has_decision_point(self) -> bool:
        """Return True if any assignment OR reservation action is currently legal.
        Used for HOLD masking / hold penalty — covers the full action space."""
        if self._has_assignment_point():
            return True
        for j, ant in enumerate(self.dispatcher.anticipated_tasks[:MAX_ANTICIPATED]):
            if self._is_valid_reservation(j, ant):
                return True
        return False

    def _is_valid_assignment(self, task_idx: int) -> bool:
        """True if pending_tasks[task_idx] exists and has a free vehicle."""
        if task_idx >= len(self.dispatcher.pending_tasks):
            return False
        task = self.dispatcher.pending_tasks[task_idx]
        return self.dispatcher._find_nearest_vehicle(task.service_type, task.gate_node) is not None

    def _is_valid_reservation(self, ant_idx: int, ant: "AnticipatedTask") -> bool:
        """
        True iff:
          1. A free compatible vehicle exists for this service type.
          2. time_until_actionable > estimated travel time + 30s buffer.
          3. No vehicle is already reserved for this (flight_id, service_type).
        """
        import networkx as nx

        # Condition 3: already reserved?
        key = (ant.flight_id, ant.service_type)
        if any(v.reserved_for == key for v in self.dispatcher.vehicles.values()):
            return False

        # Condition 1: free compatible vehicle exists?
        vehicle = self.dispatcher._find_nearest_vehicle(
            ant.service_type, ant.gate_node_estimate
        )
        if vehicle is None:
            return False

        # Condition 2: enough time to be useful?
        try:
            travel_time = nx.shortest_path_length(
                self.dispatcher.G, vehicle.position, ant.gate_node_estimate,
                weight="weight"
            )
        except Exception:
            travel_time = 60.0  # conservative fallback
        return ant.time_until_actionable > travel_time + 30.0

    def _assign_reservation(self, action: int) -> None:
        """
        Reserve the nearest free compatible vehicle for anticipated_tasks[action - MAX_TASKS].
        Sets vehicle.reserved_for = (flight_id, service_type) and reserved_until.
        """
        ant_idx = action - MAX_TASKS
        if ant_idx >= len(self.dispatcher.anticipated_tasks):
            return
        ant = self.dispatcher.anticipated_tasks[ant_idx]
        vehicle = self.dispatcher._find_nearest_vehicle(
            ant.service_type, ant.gate_node_estimate
        )
        if vehicle is None:
            return
        vehicle.reserved_for  = (ant.flight_id, ant.service_type)
        vehicle.reserved_until = self._sim_time + 2.0 * ant.time_until_actionable

    def _assign_one_task(self, task_idx: int) -> None:
        """
        Assign pending_tasks[task_idx] to the nearest compatible free vehicle.
        Mirrors the single-task branch of Dispatcher._assign_vehicles().
        """
        task    = self.dispatcher.pending_tasks[task_idx]
        vehicle = self.dispatcher._find_nearest_vehicle(task.service_type, task.gate_node)
        if vehicle is None:
            return   # guard — should not happen with proper masking

        vehicle.assigned_to = task.flight_id
        vehicle.committed   = True
        vehicle.state       = VehicleState.EN_ROUTE
        try:
            path = shortest_path(self.dispatcher.G, vehicle.position, task.gate_node)
            vehicle.path = path[1:]
        except ValueError:
            vehicle.path = []

        task.assigned_vehicle_id = vehicle.vehicle_id
        task.started_at          = self._sim_time
        self.dispatcher.active_tasks[task.task_id] = task
        self.dispatcher.pending_tasks.remove(task)
        self.dispatcher.vehicles_dispatched += 1
        self.dispatcher.tasks_started += 1

    def _advance_to_decision(self, action_taken: bool = False) -> float:
        """
        Tick the sim (dt=1 each tick) until a genuine scheduling event fires,
        then return exactly one query to the agent.

        Event-based trigger (fires only when something meaningfully changed):
          Event A — a vehicle transitions to IDLE this tick AND at least one
                    pending task has a compatible free vehicle.
          Event B — new task(s) entered pending_tasks this tick AND a compatible
                    free vehicle exists.
          Event C — assignment was possible before this tick but is not after
                    (captures vehicle breakdowns and any other resource removal).
          Safety valve — 600 ticks with no event and _has_decision_point() True:
                    emit RuntimeWarning and force a query to prevent silent hangs.

        All events that fire in the same tick collapse into exactly one query;
        the observation returned already reflects all simultaneous state changes.

        Also handles:
          • all flights departed — break normally.
          • sim_time ≥ SIM_HORIZON — break (truncation handled in step()).
          • MAX_TICKS_PER_STEP ticks — hard safety cap.

        Returns total reward accumulated during these ticks.
        """
        import warnings

        reward = 0.0
        ticks  = 0

        # ── Snapshots for event detection ─────────────────────────────────────
        prev_vehicle_states: dict[str, VehicleState] = {
            vid: v.state for vid, v in self.dispatcher.vehicles.items()
        }
        prev_reserved: set[str] = {
            vid for vid, v in self.dispatcher.vehicles.items()
            if v.reserved_for is not None
        }
        prev_pending_count: int = len(self.dispatcher.pending_tasks)
        # Event C: was a legal ASSIGNMENT possible before this tick?
        # Uses _has_assignment_point() — reservations do NOT add query triggers.
        had_assignment_before: bool = self._has_assignment_point()
        # Burst mode: after any action (assign or reserve), remaining pending tasks
        # should be offered to the agent after 1 tick without a 600-tick wait. ONLY
        # fires when a non-HOLD action was taken — preserving safety-valve behavior
        # for pure HOLD scenarios where nothing changes.
        burst_work_at_entry: bool = action_taken and had_assignment_before

        while self._sim_time < SIM_HORIZON:
            self.dispatcher.tick(self._sim_time, dt=1.0)
            self._sim_time += 1.0
            ticks          += 1

            # Expire stale reservations (reservation expiry reward wired in Step 5)
            for v in self.dispatcher.vehicles.values():
                if v.reserved_for is not None and self._sim_time > v.reserved_until:
                    v.reserved_for  = None
                    v.reserved_until = 0.0
                    self.dispatcher.reservation_expirations += 1

            delay_r, dep_r = self._compute_tick_reward()
            reward += delay_r + dep_r

            # Conflict penalty — first conflict terminates the episode (Option B).
            # Any additional simultaneous conflicts in the same tick get -50 each.
            new_conflicts = self.dispatcher.conflict_count - self._prev_conflict_count
            if new_conflicts > 0:
                reward += REWARD_CONFLICT_TERMINAL          # -200 flat on first hit
                reward += REWARD_CONFLICT * (new_conflicts - 1)   # -50 per extra
                self._prev_conflict_count  = self.dispatcher.conflict_count
                self._conflict_terminated  = True
                break   # end advance loop; step() will terminate the episode

            # All done?
            if all(a.state == AircraftState.DEPARTED
                   for a in self.dispatcher.aircraft.values()):
                break

            # ── Event detection ────────────────────────────────────────────────

            # Event A: any vehicle transitioned to IDLE this tick
            vehicle_freed: bool = any(
                prev_vehicle_states.get(vid) != VehicleState.IDLE
                and v.state == VehicleState.IDLE
                for vid, v in self.dispatcher.vehicles.items()
            )

            # Event A': a reservation expired this tick (vehicle became re-available)
            now_reserved: set[str] = {
                vid for vid, v in self.dispatcher.vehicles.items()
                if v.reserved_for is not None
            }
            reservation_expired: bool = bool(prev_reserved - now_reserved)

            # Event B: new tasks arrived in pending queue this tick
            new_tasks_arrived: bool = (
                len(self.dispatcher.pending_tasks) > prev_pending_count
            )

            # Event C: assignment was possible before tick, impossible after
            # Uses assignment-only check — reservations don't trigger Event C.
            now_has_assignment: bool = self._has_assignment_point()
            resources_reduced: bool  = had_assignment_before and not now_has_assignment

            # Update snapshots for next tick
            prev_vehicle_states  = {
                vid: v.state for vid, v in self.dispatcher.vehicles.items()
            }
            prev_reserved        = now_reserved
            prev_pending_count   = len(self.dispatcher.pending_tasks)
            had_assignment_before = now_has_assignment

            # ── Trigger query ──────────────────────────────────────────────────
            # Event C: assignment opportunity disappeared — query so agent observes
            # the change. Mask may show only HOLD or show reservation actions.
            if resources_reduced:
                break

            # Events A / A' / B: something new became assignable
            if (vehicle_freed or reservation_expired or new_tasks_arrived) and now_has_assignment:
                break

            # Burst event: work existed at advance-entry (e.g. tasks remain after
            # a burst arrival or reservation conversion). Return after first tick so
            # the agent can assign remaining tasks without a 600-tick wait.
            if burst_work_at_entry and now_has_assignment:
                burst_work_at_entry = False   # clear so it fires only once
                break

            # ── Safety valve: 600-tick inactivity guard ────────────────────────
            # Fires only when pending assignments are stuck. Reservation-only states
            # intentionally do not trigger here — they wait for Events A/B/C.
            if ticks == 600 and now_has_assignment:
                warnings.warn(
                    f"[AirportEnv] No decision event in {ticks} ticks "
                    f"(sim_time={self._sim_time:.0f}s). "
                    f"Pending: {len(self.dispatcher.pending_tasks)} task(s), "
                    f"free vehicles: "
                    f"{sum(1 for v in self.dispatcher.vehicles.values() if v.is_available())}. "
                    f"Forcing query to prevent hang.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                break

            # Hard safety cap — return even with no decision point
            if ticks >= MAX_TICKS_PER_STEP:
                break

        return reward

    def _compute_tick_reward(self) -> tuple[float, float]:
        """
        Compute (delay_reward, departure_reward) for the most recent sim tick.
        Also applies abandonment penalty when a vehicle is detected mid-task
        without actively working (e.g. after a force-release disruption).
        Updates internal state trackers.
        """
        now = self._sim_time

        # Accumulate delay for flights that are overdue and not yet departed
        current_delay = 0.0
        for ac in self.dispatcher.aircraft.values():
            if ac.state == AircraftState.DEPARTED:
                continue
            if ac.scheduled_departure < float("inf") and now > ac.scheduled_departure:
                current_delay += (now - ac.scheduled_departure) / 60.0  # minutes

        delay_reward = REWARD_PER_DELAY_MINUTE * max(0.0, current_delay - self._prev_delay_total)
        self._prev_delay_total = current_delay

        # Bonus for newly departed flights
        dep_reward = 0.0
        for ac in self.dispatcher.aircraft.values():
            if ac.state == AircraftState.DEPARTED and ac.flight_id not in self._departed_ids:
                self._departed_ids.add(ac.flight_id)
                if (ac.actual_departure is not None
                        and ac.scheduled_departure < float("inf")):
                    delay_min = (ac.actual_departure - ac.scheduled_departure) / 60.0
                    dep_reward += (
                        REWARD_ONTIME_DEPARTURE if delay_min <= 5.0
                        else REWARD_LATE_DEPARTURE
                    )

        # Abandonment penalty: active task whose vehicle is no longer EN_ROUTE/SERVICING.
        # Fires only when a disruption force-releases a committed vehicle mid-task.
        # In normal operation (no disruptions) this loop costs nothing — no orphaned tasks.
        for task_id, task in self.dispatcher.active_tasks.items():
            if task_id in self._abandoned_task_ids:
                continue
            vehicle = self.dispatcher.vehicles.get(task.assigned_vehicle_id)
            if vehicle is None:
                continue
            if vehicle.state not in (VehicleState.EN_ROUTE, VehicleState.SERVICING):
                # Vehicle was freed without completing this task
                time_spent = (
                    (now - task.started_at) / 60.0
                    if task.started_at is not None else 0.0
                )
                dep_reward += REWARD_ABANDONMENT * max(0.0, time_spent)
                self._abandoned_task_ids.add(task_id)

        # Signal 7: reservation fulfillment bonus (+1.0 per auto-assignment)
        new_fulfillments = (
            self.dispatcher.reservation_fulfillments - self._prev_reservation_fulfillments
        )
        if new_fulfillments > 0:
            dep_reward += REWARD_FULFILLED_RESERVATION * new_fulfillments
            self._prev_reservation_fulfillments = self.dispatcher.reservation_fulfillments

        # Signal 8: reservation expiry penalty (-0.5 per expired reservation)
        new_expirations = (
            self.dispatcher.reservation_expirations - self._prev_reservation_expirations
        )
        if new_expirations > 0:
            dep_reward += REWARD_EXPIRED_RESERVATION * new_expirations
            self._prev_reservation_expirations = self.dispatcher.reservation_expirations

        return delay_reward, dep_reward

    # ── Observation builder ───────────────────────────────────────────────────

    def _build_obs(self) -> np.ndarray:
        obs    = np.zeros(OBS_DIM, dtype=np.float32)
        now    = self._sim_time
        cursor = 0

        # [0] sim_time_norm
        obs[cursor] = float(np.clip(now / SIM_HORIZON, 0.0, 1.0))
        cursor += 1

        # Aircraft slots
        for i in range(MAX_AIRCRAFT):
            if i < len(self._aircraft_order):
                ac = self.dispatcher.aircraft.get(self._aircraft_order[i])
                if ac is not None:
                    svc = ac.services_completed
                    obs[cursor + 0] = AC_STATE_IDX[ac.state] / 7.0
                    pidx = NODE_IDX.get(ac.position, -1)
                    obs[cursor + 1] = (pidx / N_NODES) if pidx >= 0 else -1.0
                    if ac.scheduled_departure < float("inf"):
                        ttd = (ac.scheduled_departure - now) / MAX_DEP_WINDOW
                    else:
                        ttd = 1.0
                    obs[cursor + 2] = float(np.clip(ttd, -1.0, 1.0))
                    obs[cursor + 3] = 1.0 if "fuel"           in svc else 0.0
                    obs[cursor + 4] = 1.0 if "baggage_unload" in svc else 0.0
                    obs[cursor + 5] = 1.0 if "baggage_load"   in svc else 0.0
                    obs[cursor + 6] = 1.0 if "pushback"       in svc else 0.0
                    obs[cursor + 7] = 1.0   # is_active
            # else: slot stays zero-padded
            cursor += AC_FEATURES

        # Vehicle slots (VEH_FEATURES=5: state, pos, type, is_free, is_reserved)
        veh_list = list(self.dispatcher.vehicles.values())
        for i in range(MAX_VEHICLES):
            if i < len(veh_list):
                v = veh_list[i]
                obs[cursor + 0] = VEH_STATE_IDX[v.state] / 3.0
                obs[cursor + 1] = NODE_IDX.get(v.position, 0) / N_NODES
                obs[cursor + 2] = VEH_TYPE_IDX.get(v.vehicle_type, 0) / 2.0
                obs[cursor + 3] = 1.0 if v.is_available() else 0.0
                obs[cursor + 4] = 1.0 if v.reserved_for is not None else 0.0
            cursor += VEH_FEATURES

        # Pending-task slots
        tasks = self.dispatcher.pending_tasks[:MAX_TASKS]
        for i in range(MAX_TASKS):
            if i < len(tasks):
                t = tasks[i]
                obs[cursor + 0] = SVC_IDX.get(t.service_type, 0) / 3.0
                obs[cursor + 1] = NODE_IDX.get(t.gate_node, 0) / N_NODES
                obs[cursor + 2] = float(np.clip(
                    (now - t.created_at) / MAX_DEP_WINDOW, 0.0, 1.0
                ))
                fslot = (
                    self._aircraft_order.index(t.flight_id)
                    if t.flight_id in self._aircraft_order else 0
                )
                obs[cursor + 3] = fslot / MAX_AIRCRAFT
                obs[cursor + 4] = 1.0   # is_active
            cursor += TASK_FEATURES

        # n_pending_norm
        obs[cursor] = min(len(self.dispatcher.pending_tasks), MAX_TASKS) / MAX_TASKS
        cursor += 1

        # Anticipated-task slots (ANT_FEATURES=9 each)
        ant_tasks = self.dispatcher.anticipated_tasks[:MAX_ANTICIPATED]
        for i in range(MAX_ANTICIPATED):
            if i < len(ant_tasks):
                at = ant_tasks[i]
                obs[cursor + 0] = float(np.clip(at.time_until_actionable / ANT_HORIZON, 0.0, 1.0))
                obs[cursor + 1] = 1.0 if at.service_type == "fuel"           else 0.0
                obs[cursor + 2] = 1.0 if at.service_type == "baggage_unload" else 0.0
                obs[cursor + 3] = 1.0 if at.service_type == "baggage_load"   else 0.0
                obs[cursor + 4] = 1.0 if at.aircraft_size_class == 0         else 0.0
                obs[cursor + 5] = 1.0 if at.aircraft_size_class == 1         else 0.0
                obs[cursor + 6] = 1.0 if at.aircraft_size_class == 2         else 0.0
                obs[cursor + 7] = float(np.clip(at.service_duration_estimate / 150.0, 0.0, 1.0))
                obs[cursor + 8] = 1.0   # is_active
            cursor += ANT_FEATURES

        # Global anticipation features (3)
        # n_anticipated_beyond_norm: flights approaching but beyond 600s horizon
        n_beyond = sum(
            1 for ac in self.dispatcher.aircraft.values()
            if ac.state == AircraftState.APPROACHING
            and ac.scheduled_arrival - now > ANT_HORIZON
        )
        obs[cursor] = float(np.clip(n_beyond / 20.0, 0.0, 1.0))
        cursor += 1

        # earliest_ant_norm: most urgent anticipated task (or 1.0 if none)
        if self.dispatcher.anticipated_tasks:
            earliest = self.dispatcher.anticipated_tasks[0].time_until_actionable
            obs[cursor] = float(np.clip(earliest / ANT_HORIZON, 0.0, 1.0))
        else:
            obs[cursor] = 1.0
        cursor += 1

        # n_reservations_norm: fraction of vehicles currently reserved
        n_reserved = sum(
            1 for v in self.dispatcher.vehicles.values()
            if v.reserved_for is not None
        )
        obs[cursor] = float(np.clip(n_reserved / MAX_VEHICLES, 0.0, 1.0))
        cursor += 1

        assert cursor == OBS_DIM, f"Obs cursor mismatch: {cursor} != {OBS_DIM}"
        return obs

    def _build_info(self) -> dict:
        m = self.dispatcher.metrics()
        m["sim_time"]                 = self._sim_time
        m["n_pending_tasks"]          = len(self.dispatcher.pending_tasks)
        m["conflict_terminated"]      = self._conflict_terminated
        m["abandonment_count"]        = len(self._abandoned_task_ids)
        m["n_anticipated_tasks"]      = len(self.dispatcher.anticipated_tasks)
        m["reservation_fulfillments"] = self.dispatcher.reservation_fulfillments
        m["reservation_expirations"]  = self.dispatcher.reservation_expirations
        m["n_active_reservations"]    = sum(
            1 for v in self.dispatcher.vehicles.values()
            if v.reserved_for is not None
        )
        return m
