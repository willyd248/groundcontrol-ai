"""
dispatcher.py — First-Come-First-Served (FCFS) baseline dispatcher.

Responsibilities each tick:
  1. Assign a free runway to approaching aircraft (landing)
  2. Assign a free gate to newly-landed aircraft
  3. Route taxiing aircraft one step forward if next segment is free
  4. Create service tasks for aircraft at gate
  5. Assign nearest free vehicle to oldest pending service task
  6. Advance vehicles one step toward their destination
  7. Complete in-progress service tasks
  8. Handle pushback → taxiing_out transition
  9. Route taxiing_out aircraft to runway
  10. Send fuel trucks back to depot when needed
"""

from __future__ import annotations
import math
import networkx as nx
from sim.entities import (
    Aircraft, AircraftState, Gate, Runway, RunwayState,
    Vehicle, VehicleState, FuelTruck, BaggageTug, PushbackTractor,
    ServiceTask, AnticipatedTask, AIRCRAFT_SIZE_CLASS, AIRCRAFT_TYPE_DEFAULTS,
)
from sim.world import (
    shortest_path, is_segment_free, occupy_segment, release_segment,
    ConflictError, AIRCRAFT_SPEED, VEHICLE_SPEED, SEPARATION_TIME,
)

# How long an aircraft spends traversing a segment (computed per edge)
# Vehicles move independently; we track positions by node advancement each tick.

LANDING_CLEARANCE  = 60.0   # seconds after landing before next runway op
DEPARTURE_CLEARANCE = 30.0  # seconds of runway clear before departure allowed

# Anticipation constants
ANTICIPATION_HORIZON = 600.0   # seconds of lookahead for anticipated tasks
AVG_TAXI_TIME        = 120.0   # estimated gate-transit time for APPROACHING aircraft (seconds)
ANT_SVC_TYPES = ["fuel", "baggage_unload", "baggage_load"]  # pushback excluded


class Dispatcher:
    def __init__(
        self,
        graph: nx.DiGraph,
        gates: dict[str, Gate],
        runways: dict[str, Runway],
        aircraft: list[Aircraft],
        vehicles: list[Vehicle],
    ) -> None:
        self.G = graph
        self.gates = gates
        self.runways = runways
        self.aircraft: dict[str, Aircraft] = {a.flight_id: a for a in aircraft}
        self.vehicles: dict[str, Vehicle] = {v.vehicle_id: v for v in vehicles}

        # Pending service tasks (not yet assigned)
        self.pending_tasks: list[ServiceTask] = []
        # Active tasks (assigned, vehicle en route or servicing)
        self.active_tasks: dict[str, ServiceTask] = {}  # task_id → task
        self._task_counter = 0

        # Anticipated tasks (lookahead for APPROACHING/TAXIING_IN aircraft)
        self.anticipated_tasks: list[AnticipatedTask] = []

        # Reservation metrics (incremented by RLDispatcher overrides)
        self.reservation_fulfillments = 0   # successful reservation auto-assignments
        self.reservation_expirations  = 0   # reservations that expired unused

        # Metrics
        self.conflict_count = 0
        self.vehicles_dispatched = 0
        self.fuel_truck_refills = 0
        self.tasks_started = 0    # incremented when a task is dispatched to a vehicle
        self.tasks_completed = 0  # incremented when a task finishes normally

        # Track segment entry times for separation enforcement
        # key: (flight_id_or_vehicle_id, u, v) → time entered
        self._segment_entry: dict[tuple, float] = {}

        # Track which aircraft are waiting for runway clearance
        self._runway_queue: list[str] = []  # flight_ids in order

    # -----------------------------------------------------------------------
    # Main tick
    # -----------------------------------------------------------------------

    def tick(self, now: float, dt: float = 1.0) -> None:
        self._spawn_approaching(now)
        self._assign_landing_runways(now)
        self._complete_landings(now)
        self._assign_gates(now)
        self._advance_aircraft(now, dt)
        self._update_anticipated_tasks(now)   # rebuild after aircraft state changes
        self._create_service_tasks(now)
        self._assign_vehicles(now)
        self._advance_vehicles(now, dt)
        self._complete_services(now)
        self._handle_pushback(now)
        self._assign_departure_runways(now)
        self._advance_departing(now, dt)
        self._complete_departures(now)
        self._return_fuel_trucks(now)

    # -----------------------------------------------------------------------
    # 1. Spawn: mark aircraft as LANDED when their arrival time is reached
    #    (they appear at the runway exit node)
    # -----------------------------------------------------------------------

    def _spawn_approaching(self, now: float) -> None:
        for ac in self.aircraft.values():
            if ac.state == AircraftState.APPROACHING and now >= ac.scheduled_arrival:
                # Will be handled by _assign_landing_runways
                pass

    # -----------------------------------------------------------------------
    # 2. Assign a free runway to the next approaching aircraft
    # -----------------------------------------------------------------------

    def _assign_landing_runways(self, now: float) -> None:
        approaching = [
            a for a in self.aircraft.values()
            if a.state == AircraftState.APPROACHING and now >= a.scheduled_arrival
        ]
        # FCFS: sort by scheduled_arrival
        approaching.sort(key=lambda a: a.scheduled_arrival)

        for ac in approaching:
            for rwy in self.runways.values():
                if rwy.is_free(now):
                    rwy.state = RunwayState.LANDING
                    rwy.occupied_by = ac.flight_id
                    rwy.available_at = now + 60.0   # time on runway
                    ac.state = AircraftState.LANDED
                    ac.actual_arrival = now
                    ac.position = rwy.runway_id      # "on runway"
                    # Store which runway for later
                    ac.path = [rwy.exit_node]        # will taxi to exit node
                    break

    # -----------------------------------------------------------------------
    # 3. Complete landings: move aircraft from runway to exit node
    # -----------------------------------------------------------------------

    def _complete_landings(self, now: float) -> None:
        for rwy in self.runways.values():
            if rwy.state == RunwayState.LANDING and now >= rwy.available_at:
                ac = self.aircraft.get(rwy.occupied_by)
                if ac and ac.state == AircraftState.LANDED:
                    ac.position = rwy.exit_node
                    ac.path = []
                    rwy.state = RunwayState.FREE
                    rwy.occupied_by = None
                    rwy.available_at = now + LANDING_CLEARANCE

    # -----------------------------------------------------------------------
    # 4. Assign free gates to landed aircraft
    # -----------------------------------------------------------------------

    def _assign_gates(self, now: float) -> None:
        needs_gate = [
            a for a in self.aircraft.values()
            if a.state == AircraftState.LANDED and a.assigned_gate is None
            and a.position is not None
            and a.position not in {rwy.runway_id for rwy in self.runways.values()}
        ]
        for ac in needs_gate:
            gate = self._find_nearest_free_gate(ac.position, now)
            if gate:
                gate.occupied_by = ac.flight_id
                ac.assigned_gate = gate.gate_id
                try:
                    ac.path = shortest_path(self.G, ac.position, gate.position_node)
                    ac.path = ac.path[1:]   # remove current position
                    ac.state = AircraftState.TAXIING_IN
                except ValueError:
                    pass  # no path — try again next tick

    def _find_nearest_free_gate(self, from_node: str, now: float) -> Gate | None:
        best_gate = None
        best_cost = float("inf")
        for gate in self.gates.values():
            if not gate.is_free(now):
                continue
            try:
                cost = nx.shortest_path_length(
                    self.G, from_node, gate.position_node, weight="weight"
                )
                if cost < best_cost:
                    best_cost = cost
                    best_gate = gate
            except nx.NetworkXNoPath:
                continue
        return best_gate

    # -----------------------------------------------------------------------
    # 5. Advance taxiing_in aircraft one segment per tick
    # -----------------------------------------------------------------------

    def _advance_aircraft(self, now: float, dt: float) -> None:
        for ac in self.aircraft.values():
            if ac.state != AircraftState.TAXIING_IN:
                continue
            if not ac.path:
                # Reached gate
                gate = self.gates.get(ac.assigned_gate)
                if gate:
                    ac.state = AircraftState.AT_GATE
                continue

            next_node = ac.path[0]
            current_node = ac.position

            if not self.G.has_edge(current_node, next_node):
                # Recompute path
                try:
                    new_path = shortest_path(self.G, current_node, next_node)
                    ac.path = new_path[1:] + ac.path[1:]
                    next_node = ac.path[0]
                except ValueError:
                    continue

            edge_data = self.G[current_node][next_node]
            travel_time = edge_data["weight"]

            # Check if we've been waiting long enough to move
            seg_key = (ac.flight_id, current_node, next_node)
            entered = self._segment_entry.get(seg_key, 0)

            if not is_segment_free(self.G, current_node, next_node):
                continue  # hold — segment occupied

            # Separation check: don't enter if another aircraft entered recently
            if not self._separation_ok(current_node, next_node, now):
                continue

            # Advance
            try:
                occupy_segment(self.G, current_node, next_node, ac.flight_id)
            except ConflictError:
                self.conflict_count += 1
                continue

            # Release previous segment if any
            self._release_aircraft_prev_segment(ac, current_node)

            ac.position = next_node
            ac.path.pop(0)
            self._segment_entry[(ac.flight_id, current_node, next_node)] = now

            # Schedule release after travel time
            # (simplified: we release immediately since we advance node-by-node each tick)
            # Release happens next tick after advancement
            release_segment(self.G, current_node, next_node, ac.flight_id)

    def _separation_ok(self, u: str, v: str, now: float) -> bool:
        """Check 15-second separation: no other aircraft entered this segment recently."""
        for key, t in self._segment_entry.items():
            if key[1] == u and key[2] == v:
                if (now - t) < SEPARATION_TIME:
                    return False
        return True

    def _release_aircraft_prev_segment(self, ac: Aircraft, current_pos: str) -> None:
        """Release any segment that ends at current_pos for this aircraft."""
        for (eid, u, v), _ in list(self._segment_entry.items()):
            if eid == ac.flight_id and v == current_pos:
                if self.G.has_edge(u, v) and self.G[u][v].get("occupied_by") == ac.flight_id:
                    release_segment(self.G, u, v, ac.flight_id)

    # -----------------------------------------------------------------------
    # 5b. Update anticipated tasks (lookahead for APPROACHING/TAXIING_IN)
    # -----------------------------------------------------------------------

    def _update_anticipated_tasks(self, now: float) -> None:
        """
        Rebuild anticipated_tasks each tick.

        For each aircraft in APPROACHING or TAXIING_IN state within the 600s
        lookahead horizon, project the services that will be needed once the
        aircraft reaches its gate. Pushback is excluded (too far in future).
        Sort ascending by time_until_actionable (most urgent first).
        """
        # Index existing task service types per flight (pending + active)
        # so we don't duplicate anticipated tasks for services already queued.
        existing: dict[str, set[str]] = {}
        for t in self.pending_tasks:
            existing.setdefault(t.flight_id, set()).add(t.service_type)
        for t in self.active_tasks.values():
            existing.setdefault(t.flight_id, set()).add(t.service_type)

        new_anticipated: list[AnticipatedTask] = []

        for ac in self.aircraft.values():
            if ac.state == AircraftState.APPROACHING:
                # Time until gate = time until landing + average taxi time
                time_to_gate = max(0.0, ac.scheduled_arrival - now) + AVG_TAXI_TIME
            elif ac.state == AircraftState.TAXIING_IN:
                # Each path step ≈ 1 sim-second (aircraft advances one node/tick)
                time_to_gate = float(len(ac.path))
            else:
                continue  # AT_GATE, SERVICING, etc. — already actionable or done

            if time_to_gate > ANTICIPATION_HORIZON:
                continue  # beyond lookahead window

            # Gate node estimate
            if ac.assigned_gate and ac.assigned_gate in self.gates:
                gate_node = self.gates[ac.assigned_gate].position_node
            else:
                gate_node = self._estimate_gate_node(now)

            size_class = AIRCRAFT_SIZE_CLASS.get(ac.aircraft_type, 1)
            defaults   = AIRCRAFT_TYPE_DEFAULTS.get(ac.aircraft_type, {})
            done       = ac.services_completed | existing.get(ac.flight_id, set())

            for svc in ANT_SVC_TYPES:
                # Only anticipate services this aircraft actually needs
                if svc == "fuel" and not ac.service_requirements.needs_fuel:
                    continue
                if svc == "baggage_unload" and not ac.service_requirements.needs_baggage_unload:
                    continue
                if svc == "baggage_load" and not ac.service_requirements.needs_baggage_load:
                    continue
                if svc in done:
                    continue

                # Duration estimate from aircraft-type defaults
                if svc == "fuel":
                    fuel_amount  = defaults.get("fuel_amount", 5000)
                    duration_est = fuel_amount / 100.0
                else:
                    bag_count    = defaults.get("baggage_count", 120)
                    duration_est = bag_count * 0.5

                new_anticipated.append(AnticipatedTask(
                    flight_id=ac.flight_id,
                    service_type=svc,
                    time_until_actionable=time_to_gate,
                    aircraft_type=ac.aircraft_type,
                    aircraft_size_class=size_class,
                    service_duration_estimate=duration_est,
                    gate_node_estimate=gate_node,
                ))

        # Sort by urgency (lowest time_until_actionable first)
        new_anticipated.sort(key=lambda t: t.time_until_actionable)
        self.anticipated_tasks = new_anticipated

    def _estimate_gate_node(self, now: float) -> str:
        """Return a gate node estimate when no gate has been assigned yet."""
        for gate in self.gates.values():
            if gate.is_free(now):
                return gate.position_node
        gates = list(self.gates.values())
        return gates[0].position_node if gates else "DEPOT"

    # -----------------------------------------------------------------------
    # 6. Create service tasks when aircraft reaches gate
    # -----------------------------------------------------------------------

    def _create_service_tasks(self, now: float) -> None:
        for ac in self.aircraft.values():
            if ac.state != AircraftState.AT_GATE:
                continue
            existing = {
                t.service_type
                for t in self.pending_tasks + list(self.active_tasks.values())
                if t.flight_id == ac.flight_id
            } | ac.services_completed

            for svc in ac.service_requirements.required_services():
                if svc == "pushback":
                    continue   # pushback handled separately at departure
                if svc not in existing:
                    gate = self.gates.get(ac.assigned_gate)
                    task = ServiceTask(
                        task_id=f"T{self._task_counter:04d}",
                        flight_id=ac.flight_id,
                        service_type=svc,
                        gate_node=gate.position_node if gate else ac.position,
                        created_at=now,
                    )
                    self._task_counter += 1
                    self.pending_tasks.append(task)
                    # Transition to SERVICING state
                    ac.state = AircraftState.SERVICING

    # -----------------------------------------------------------------------
    # 7. Assign nearest free vehicle to oldest pending task (FCFS)
    # -----------------------------------------------------------------------

    def _assign_vehicles(self, now: float) -> None:
        # Sort tasks oldest first
        self.pending_tasks.sort(key=lambda t: t.created_at)

        for task in list(self.pending_tasks):
            vehicle = self._find_nearest_vehicle(task.service_type, task.gate_node)
            if vehicle is None:
                continue

            vehicle.assigned_to = task.flight_id
            vehicle.state = VehicleState.EN_ROUTE
            try:
                path = shortest_path(self.G, vehicle.position, task.gate_node)
                vehicle.path = path[1:]
            except ValueError:
                vehicle.path = []

            task.assigned_vehicle_id = vehicle.vehicle_id
            task.started_at = now
            self.active_tasks[task.task_id] = task
            self.pending_tasks.remove(task)
            self.vehicles_dispatched += 1
            self.tasks_started += 1

    def _find_nearest_vehicle(self, service_type: str, gate_node: str) -> Vehicle | None:
        if gate_node is None or gate_node not in self.G:
            return None
        candidates = []
        for v in self.vehicles.values():
            if not v.is_available():
                continue
            if v.committed:          # defensive: is_available() also checks this
                continue
            if service_type == "fuel" and not isinstance(v, FuelTruck):
                continue
            if service_type in ("baggage_unload", "baggage_load") and not isinstance(v, BaggageTug):
                continue
            if service_type == "pushback" and not isinstance(v, PushbackTractor):
                continue
            try:
                cost = nx.shortest_path_length(self.G, v.position, gate_node, weight="weight")
                candidates.append((cost, v.vehicle_id, v))
            except nx.NetworkXNoPath:
                continue
        if not candidates:
            return None
        candidates.sort(key=lambda x: (x[0], x[1]))
        return candidates[0][2]

    # -----------------------------------------------------------------------
    # 8. Advance vehicles one node per tick toward destination
    # -----------------------------------------------------------------------

    def _advance_vehicles(self, now: float, dt: float) -> None:
        for v in self.vehicles.values():
            if v.state not in (VehicleState.EN_ROUTE, VehicleState.RETURNING):
                continue
            if not v.path:
                if v.state == VehicleState.EN_ROUTE:
                    v.state = VehicleState.SERVICING
                elif v.state == VehicleState.RETURNING:
                    v.state = VehicleState.IDLE
                    if isinstance(v, FuelTruck):
                        v.fuel_remaining = v.fuel_capacity
                        v.services_since_refill = 0
                continue

            next_node = v.path[0]
            current_node = v.position

            if not self.G.has_edge(current_node, next_node):
                # Recompute
                try:
                    dest = v.path[-1]
                    new_path = shortest_path(self.G, current_node, dest)
                    v.path = new_path[1:]
                    next_node = v.path[0]
                except (ValueError, IndexError):
                    continue

            if not is_segment_free(self.G, current_node, next_node):
                continue  # wait

            try:
                occupy_segment(self.G, current_node, next_node, v.vehicle_id)
            except ConflictError:
                self.conflict_count += 1
                continue

            self._release_vehicle_prev_segment(v, current_node)
            v.position = next_node
            v.path.pop(0)
            release_segment(self.G, current_node, next_node, v.vehicle_id)

            if not v.path:
                if v.state == VehicleState.EN_ROUTE:
                    v.state = VehicleState.SERVICING
                elif v.state == VehicleState.RETURNING:
                    v.state = VehicleState.IDLE
                    if isinstance(v, FuelTruck):
                        v.fuel_remaining = v.fuel_capacity
                        v.services_since_refill = 0

    def _release_vehicle_prev_segment(self, v: Vehicle, current_pos: str) -> None:
        for (eid, u, vv), _ in list(self._segment_entry.items()):
            if eid == v.vehicle_id and vv == current_pos:
                if self.G.has_edge(u, vv) and self.G[u][vv].get("occupied_by") == v.vehicle_id:
                    release_segment(self.G, u, vv, v.vehicle_id)

    # -----------------------------------------------------------------------
    # 9. Complete services (vehicle is SERVICING at gate)
    # -----------------------------------------------------------------------

    def _complete_services(self, now: float) -> None:
        for task_id, task in list(self.active_tasks.items()):
            vehicle = self.vehicles.get(task.assigned_vehicle_id)
            if vehicle is None:
                continue
            if vehicle.state != VehicleState.SERVICING:
                continue

            ac = self.aircraft.get(task.flight_id)
            if ac is None:
                continue

            # Set service_end_time on first tick in SERVICING state
            if vehicle.service_end_time == 0.0 or vehicle.service_end_time < now:
                duration = task.duration(ac)
                vehicle.service_end_time = now + duration

            if now >= vehicle.service_end_time:
                # Service complete
                task.completed_at = now
                ac.services_completed.add(task.service_type)
                del self.active_tasks[task_id]
                self.tasks_completed += 1

                # Free vehicle
                vehicle.state = VehicleState.IDLE
                vehicle.assigned_to = None
                vehicle.service_end_time = 0.0
                vehicle.committed = False

                if isinstance(vehicle, FuelTruck):
                    vehicle.fuel_remaining -= ac.service_requirements.fuel_amount
                    vehicle.services_since_refill += 1

                # Check if all ground services done
                if ac.state == AircraftState.SERVICING and ac.all_services_done():
                    ac.state = AircraftState.AT_GATE  # wait for scheduled departure

    # -----------------------------------------------------------------------
    # 10. Handle pushback when departure time reached
    # -----------------------------------------------------------------------

    def _handle_pushback(self, now: float) -> None:
        for ac in self.aircraft.values():
            if ac.state != AircraftState.AT_GATE:
                continue
            if not ac.all_services_done():
                continue
            if now < ac.scheduled_departure:
                continue

            reqs = ac.service_requirements
            if not reqs.needs_pushback:
                # Skip pushback, go straight to taxiing out
                ac.state = AircraftState.TAXIING_OUT
                self._setup_departure_path(ac)
                continue

            # Check if pushback task already pending/active
            existing = {
                t.service_type
                for t in self.pending_tasks + list(self.active_tasks.values())
                if t.flight_id == ac.flight_id
            }
            if "pushback" in existing or "pushback" in ac.services_completed:
                continue

            # Create pushback task
            gate = self.gates.get(ac.assigned_gate)
            task = ServiceTask(
                task_id=f"T{self._task_counter:04d}",
                flight_id=ac.flight_id,
                service_type="pushback",
                gate_node=gate.position_node if gate else ac.position,
                created_at=now,
            )
            self._task_counter += 1
            self.pending_tasks.append(task)
            ac.state = AircraftState.PUSHBACK

    # -----------------------------------------------------------------------
    # Handle pushback completion → transition to TAXIING_OUT
    # -----------------------------------------------------------------------

    def _assign_departure_runways(self, now: float) -> None:
        # Check if any pushback tasks completed → move to taxiing_out
        for ac in self.aircraft.values():
            if ac.state == AircraftState.PUSHBACK:
                if "pushback" in ac.services_completed:
                    ac.state = AircraftState.TAXIING_OUT
                    self._setup_departure_path(ac)

    def _setup_departure_path(self, ac: Aircraft) -> None:
        """Assign departure runway and compute path."""
        gate = self.gates.get(ac.assigned_gate)
        start_node = gate.position_node if gate else ac.position
        if start_node is None:
            return

        # Pick a free runway (or least busy)
        target_rwy = None
        for rwy in self.runways.values():
            if rwy.is_free(0):  # will check properly when we reach entry
                target_rwy = rwy
                break
        if target_rwy is None:
            target_rwy = list(self.runways.values())[0]

        try:
            path = shortest_path(self.G, start_node, target_rwy.entry_node)
            ac.path = path[1:]
            ac.position = start_node
        except ValueError:
            pass

    # -----------------------------------------------------------------------
    # 11. Advance departing aircraft toward runway
    # -----------------------------------------------------------------------

    def _advance_departing(self, now: float, dt: float) -> None:
        for ac in self.aircraft.values():
            if ac.state != AircraftState.TAXIING_OUT:
                continue
            if not ac.path:
                continue

            next_node = ac.path[0]
            current_node = ac.position

            if not self.G.has_edge(current_node, next_node):
                try:
                    dest = ac.path[-1]
                    new_path = shortest_path(self.G, current_node, dest)
                    ac.path = new_path[1:]
                    next_node = ac.path[0]
                except ValueError:
                    continue

            if not is_segment_free(self.G, current_node, next_node):
                continue

            if not self._separation_ok(current_node, next_node, now):
                continue

            try:
                occupy_segment(self.G, current_node, next_node, ac.flight_id)
            except ConflictError:
                self.conflict_count += 1
                continue

            self._release_aircraft_prev_segment(ac, current_node)
            ac.position = next_node
            ac.path.pop(0)
            self._segment_entry[(ac.flight_id, current_node, next_node)] = now
            release_segment(self.G, current_node, next_node, ac.flight_id)

    # -----------------------------------------------------------------------
    # 12. Complete departures at runway entry
    # -----------------------------------------------------------------------

    def _complete_departures(self, now: float) -> None:
        for ac in self.aircraft.values():
            if ac.state != AircraftState.TAXIING_OUT:
                continue
            if ac.path:
                continue  # Not yet at runway entry

            # At runway entry — check runway is free
            for rwy in self.runways.values():
                if ac.position == rwy.entry_node and rwy.is_free(now):
                    rwy.state = RunwayState.DEPARTING
                    rwy.occupied_by = ac.flight_id
                    rwy.available_at = now + 60.0
                    ac.state = AircraftState.DEPARTED
                    ac.actual_departure = now

                    # Free gate
                    gate = self.gates.get(ac.assigned_gate)
                    if gate:
                        gate.occupied_by = None
                        gate.available_at = now + 300.0   # 5-min buffer

                    # Clear runway after use
                    break

        # Free runways after departure
        for rwy in self.runways.values():
            if rwy.state == RunwayState.DEPARTING and now >= rwy.available_at:
                rwy.state = RunwayState.FREE
                rwy.occupied_by = None

    # -----------------------------------------------------------------------
    # 13. Return fuel trucks to depot when low
    # -----------------------------------------------------------------------

    def _return_fuel_trucks(self, now: float) -> None:
        for v in self.vehicles.values():
            if not isinstance(v, FuelTruck):
                continue
            if v.state != VehicleState.IDLE:
                continue
            if v.services_since_refill >= v.refill_threshold:
                v.state = VehicleState.RETURNING
                try:
                    path = shortest_path(self.G, v.position, "DEPOT")
                    v.path = path[1:]
                    self.fuel_truck_refills += 1
                except ValueError:
                    v.state = VehicleState.IDLE

    # -----------------------------------------------------------------------
    # Metrics snapshot
    # -----------------------------------------------------------------------

    def metrics(self) -> dict:
        departed = [a for a in self.aircraft.values() if a.state == AircraftState.DEPARTED]
        pending  = [a for a in self.aircraft.values() if a.state != AircraftState.DEPARTED]

        delays = []
        turnarounds = []
        for ac in departed:
            if ac.actual_departure is not None and ac.scheduled_departure < float("inf"):
                delays.append((ac.actual_departure - ac.scheduled_departure) / 60.0)
            if (ac.actual_arrival is not None and ac.actual_departure is not None
                    and ac.scheduled_arrival < float("inf")):
                turnarounds.append((ac.actual_departure - ac.actual_arrival) / 60.0)

        return {
            "flights_departed":        len(departed),
            "flights_pending":         len(pending),
            "total_delay_minutes":     round(sum(delays), 1),
            "avg_delay_minutes":       round(sum(delays) / len(delays), 1) if delays else 0.0,
            "max_delay_minutes":       round(max(delays), 1) if delays else 0.0,
            "avg_turnaround_minutes":  round(sum(turnarounds) / len(turnarounds), 1) if turnarounds else 0.0,
            "conflict_count":          self.conflict_count,
            "vehicles_dispatched":     self.vehicles_dispatched,
            "fuel_truck_refills":      self.fuel_truck_refills,
            "tasks_started":           self.tasks_started,
            "tasks_completed":         self.tasks_completed,
        }
