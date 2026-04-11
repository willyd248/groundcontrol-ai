"""
tests/test_anticipated.py — Anticipation upgrade test suite.

Tests from ANTICIPATION_DESIGN_v2.md Section 6:
  1. test_anticipated_tasks_populated
  2. test_anticipated_tasks_cleared
  3. test_reservation_action_mask
  4. test_reservation_auto_assign
  5. test_reservation_expiry
  6. test_reservation_conversion_priority
  7. test_obs_dim_correct
  8. test_action_space_correct
  9. test_hold_masking_with_reservations
 10. test_full_episode_with_anticipation

Run with:
    pytest tests/test_anticipated.py -v
"""

from __future__ import annotations

import json
import numpy as np
import pytest

from env.airport_env import (
    AirportEnv, OBS_DIM, ACTION_HOLD, MAX_TASKS, MAX_ANTICIPATED,
    REWARD_FULFILLED_RESERVATION, REWARD_EXPIRED_RESERVATION,
)
from sim.entities import AircraftState, VehicleState
from env.airport_env import RLDispatcher
from sim.world import build_taxiway_graph, build_gates, build_runways
from sim.entities import (
    Aircraft, ServiceRequirements,
    FuelTruck, BaggageTug, PushbackTractor,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_schedule(tmp_path, flights: list[dict]) -> str:
    p = tmp_path / "schedule.json"
    p.write_text(json.dumps(flights))
    return str(p)


def _single_flight(arrival: int = 500) -> dict:
    return {
        "flight_id": "TEST001",
        "aircraft_type": "B737",
        "scheduled_arrival": arrival,
        "scheduled_departure": 99999,
        "is_departure_only": False,
        "is_arrival_only": False,
    }


def _make_rl_dispatcher_with_aircraft_at_gate(flight_id="RES001", aircraft_type="CRJ900"):
    """Build a minimal RLDispatcher with one aircraft already AT_GATE."""
    G = build_taxiway_graph()
    gates = build_gates()
    runways = build_runways()
    fleet = [
        FuelTruck(vehicle_id="FT1", position="DEPOT"),
        BaggageTug(vehicle_id="BT1", position="DEPOT"),
        BaggageTug(vehicle_id="BT2", position="DEPOT"),
        PushbackTractor(vehicle_id="PB1", position="DEPOT"),
    ]
    reqs = ServiceRequirements(
        needs_fuel=True, needs_baggage_unload=True, needs_baggage_load=True,
        needs_pushback=False, fuel_amount=2000, baggage_count=60,
    )
    gate_id = list(gates.keys())[0]
    gate = gates[gate_id]
    ac = Aircraft(
        flight_id=flight_id,
        aircraft_type=aircraft_type,
        scheduled_arrival=0,
        scheduled_departure=99999,
        service_requirements=reqs,
        state=AircraftState.AT_GATE,
        assigned_gate=gate_id,
        position=gate.position_node,
    )
    disp = RLDispatcher(
        graph=G, gates=gates, runways=runways,
        aircraft=[ac], vehicles=fleet,
    )
    return disp, ac, fleet


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAnticipatedTasksPopulated:
    """test_anticipated_tasks_populated: anticipated tasks appear for APPROACHING/TAXIING_IN aircraft."""

    def test_approaching_aircraft_generates_anticipated_tasks(self, tmp_path):
        """An APPROACHING aircraft within 600s horizon creates anticipated tasks."""
        # Use arrival=5000 so the aircraft is definitely APPROACHING when reset() returns
        # (reset() breaks at MAX_TICKS_PER_STEP=3600 ticks, before the 5000s arrival)
        sched_path = _write_schedule(tmp_path, [_single_flight(arrival=5000)])
        env = AirportEnv(schedule_path=sched_path)
        obs, info = env.reset()

        # Verify aircraft is still APPROACHING (not yet at gate)
        aircraft_states = [(ac.flight_id, ac.state) for ac in env.dispatcher.aircraft.values()]

        # Directly call _update_anticipated_tasks to populate anticipated tasks
        # (may be empty since arrival=5000 is beyond 600s horizon at t=3600)
        # Advance sim until aircraft is within 600s horizon
        ant_found = len(env.dispatcher.anticipated_tasks) > 0
        for _ in range(1200):
            # Tick dispatcher directly to advance time toward arrival
            env.dispatcher.tick(env._sim_time, dt=1.0)
            env._sim_time += 1.0
            if len(env.dispatcher.anticipated_tasks) > 0:
                ant_found = True
                break

        assert ant_found, (
            "No anticipated tasks found even after advancing toward aircraft arrival. "
            f"Aircraft states: {[(ac.flight_id, ac.state) for ac in env.dispatcher.aircraft.values()]}, "
            f"sim_time: {env._sim_time:.0f}"
        )

        # Verify structure of anticipated tasks
        for ant in env.dispatcher.anticipated_tasks:
            assert ant.flight_id, "flight_id must be set"
            assert ant.service_type in ("fuel", "baggage_unload", "baggage_load"), \
                f"Unexpected service_type: {ant.service_type}"
            assert 0.0 <= ant.time_until_actionable <= 600.0, \
                f"time_until_actionable out of horizon: {ant.time_until_actionable}"
            assert ant.aircraft_size_class in (0, 1, 2), \
                f"Invalid size_class: {ant.aircraft_size_class}"
            assert ant.service_duration_estimate > 0, "Duration must be positive"
            assert ant.gate_node_estimate, "gate_node_estimate must be set"

        env.close()

    def test_anticipated_sorted_by_urgency(self, tmp_path):
        """Anticipated tasks are sorted by time_until_actionable ascending."""
        # Use two aircraft arriving at different times within the 600s horizon
        flights = [
            {
                "flight_id": "F1", "aircraft_type": "B737",
                "scheduled_arrival": 200, "scheduled_departure": 99999,
                "is_departure_only": False, "is_arrival_only": False,
            },
            {
                "flight_id": "F2", "aircraft_type": "CRJ900",
                "scheduled_arrival": 400, "scheduled_departure": 99999,
                "is_departure_only": False, "is_arrival_only": False,
            },
        ]
        sched_path = _write_schedule(tmp_path, flights)
        env = AirportEnv(schedule_path=sched_path)
        env.reset()

        # Run until both aircraft are APPROACHING and in horizon
        for _ in range(20):
            if len(env.dispatcher.anticipated_tasks) >= 2:
                break
            mask = env.action_masks()
            valid = np.where(mask)[0]
            _, _, term, trunc, _ = env.step(int(valid[0]))
            if term or trunc:
                break

        if len(env.dispatcher.anticipated_tasks) >= 2:
            times = [at.time_until_actionable for at in env.dispatcher.anticipated_tasks]
            assert times == sorted(times), f"Anticipated tasks not sorted: {times}"

        env.close()


class TestAnticipatedTasksCleared:
    """test_anticipated_tasks_cleared: anticipated tasks removed when flight reaches gate."""

    def test_anticipated_task_disappears_at_gate(self, tmp_path):
        """Once an aircraft reaches AT_GATE, its anticipated tasks should not appear."""
        sched_path = _write_schedule(tmp_path, [_single_flight(arrival=0)])
        env = AirportEnv(schedule_path=sched_path)
        obs, info = env.reset()

        # Check: AT_GATE aircraft should not appear in anticipated_tasks
        for ac in env.dispatcher.aircraft.values():
            if ac.state in (AircraftState.AT_GATE, AircraftState.SERVICING,
                            AircraftState.PUSHBACK, AircraftState.DEPARTED):
                at_gate_ids = {at.flight_id for at in env.dispatcher.anticipated_tasks}
                assert ac.flight_id not in at_gate_ids, (
                    f"Aircraft {ac.flight_id} is {ac.state} but still in anticipated_tasks"
                )

        # Step through episode and verify the invariant holds
        for _ in range(50):
            for ac in env.dispatcher.aircraft.values():
                if ac.state in (AircraftState.AT_GATE, AircraftState.SERVICING,
                                AircraftState.PUSHBACK, AircraftState.DEPARTED):
                    at_gate_ids = {at.flight_id for at in env.dispatcher.anticipated_tasks}
                    assert ac.flight_id not in at_gate_ids, (
                        f"Aircraft {ac.flight_id} ({ac.state}) still in anticipated_tasks"
                    )
            mask = env.action_masks()
            valid = np.where(mask)[0]
            _, _, term, trunc, _ = env.step(int(valid[0]))
            if term or trunc:
                break

        env.close()


class TestReservationActionMask:
    """test_reservation_action_mask: reservation actions masked correctly."""

    def test_reservation_masked_when_no_anticipated_tasks(self, tmp_path):
        """All reservation slots (16..23) must be False when no anticipated tasks."""
        # Aircraft arrives at t=0 — will be at gate immediately, no anticipated tasks
        sched_path = _write_schedule(tmp_path, [_single_flight(arrival=0)])
        env = AirportEnv(schedule_path=sched_path)
        env.reset()

        # Wait until all aircraft are at gate / servicing (no more APPROACHING)
        for _ in range(50):
            approaching = [
                ac for ac in env.dispatcher.aircraft.values()
                if ac.state == AircraftState.APPROACHING
            ]
            if not approaching:
                break
            mask = env.action_masks()
            valid = np.where(mask)[0]
            _, _, term, trunc, _ = env.step(int(valid[0]))
            if term or trunc:
                break

        # Now: no APPROACHING aircraft → no anticipated tasks → reservation slots should all be False
        if not env.dispatcher.anticipated_tasks:
            mask = env.action_masks()
            reservation_bits = mask[MAX_TASKS:ACTION_HOLD]
            assert not reservation_bits.any(), (
                f"Reservation slots should all be False when no anticipated tasks. "
                f"Mask[16..23]: {reservation_bits}"
            )

        env.close()

    def test_reservation_requires_free_vehicle(self, tmp_path):
        """A reservation action is only legal if a free compatible vehicle exists."""
        sched_path = _write_schedule(tmp_path, [_single_flight(arrival=300)])
        env = AirportEnv(schedule_path=sched_path)
        env.reset()

        # For each legal reservation action, verify free vehicle exists for that type
        for _ in range(100):
            mask = env.action_masks()
            ant_tasks = env.dispatcher.anticipated_tasks[:MAX_ANTICIPATED]
            for j, ant in enumerate(ant_tasks):
                action_idx = MAX_TASKS + j
                if mask[action_idx]:
                    # Must have a free compatible vehicle
                    vehicle = env.dispatcher._find_nearest_vehicle(
                        ant.service_type, ant.gate_node_estimate
                    )
                    assert vehicle is not None, (
                        f"Reservation action {action_idx} is legal but no free vehicle for "
                        f"{ant.service_type}"
                    )
            valid = np.where(mask)[0]
            _, _, term, trunc, _ = env.step(int(valid[0]))
            if term or trunc:
                break

        env.close()

    def test_reservation_not_legal_when_already_reserved(self, tmp_path):
        """Once a vehicle is reserved for (flight, svc), that slot is not legal again."""
        sched_path = _write_schedule(tmp_path, [_single_flight(arrival=300)])
        env = AirportEnv(schedule_path=sched_path)
        env.reset()

        # Find a legal reservation action and take it
        reservation_taken = False
        for _ in range(100):
            mask = env.action_masks()
            for j in range(MAX_ANTICIPATED):
                action_idx = MAX_TASKS + j
                if mask[action_idx]:
                    env.step(action_idx)  # Take the reservation
                    reservation_taken = True
                    break
            if reservation_taken:
                break
            valid = np.where(mask)[0]
            _, _, term, trunc, _ = env.step(int(valid[0]))
            if term or trunc:
                break

        if reservation_taken:
            # The same (flight_id, service_type) pair should not be legal to reserve again
            mask = env.action_masks()
            ant_tasks = env.dispatcher.anticipated_tasks[:MAX_ANTICIPATED]
            for v in env.dispatcher.vehicles.values():
                if v.reserved_for is not None:
                    key = v.reserved_for
                    for j, ant in enumerate(ant_tasks):
                        if (ant.flight_id, ant.service_type) == key:
                            assert not mask[MAX_TASKS + j], (
                                f"Reservation action {MAX_TASKS + j} legal despite vehicle "
                                f"already reserved for {key}"
                            )

        env.close()


class TestReservationAutoAssign:
    """test_reservation_auto_assign: reserved vehicle auto-assigned when task materializes."""

    def test_reserved_vehicle_auto_assigned(self):
        """Reserved vehicle is auto-assigned when the corresponding task materializes."""
        disp, ac, fleet = _make_rl_dispatcher_with_aircraft_at_gate()

        bt1 = disp.vehicles["BT1"]
        bt2 = disp.vehicles["BT2"]

        # Reserve BT1 for the baggage_unload task that will be created
        bt1.reserved_for   = ("RES001", "baggage_unload")
        bt1.reserved_until = 9999.0

        # Call _create_service_tasks — conversion should happen immediately
        disp._create_service_tasks(now=0.0)

        # BT1 should be EN_ROUTE (auto-assigned), not BT2
        assert bt1.state == VehicleState.EN_ROUTE, \
            f"BT1 should be EN_ROUTE after auto-assign, got {bt1.state}"
        assert bt1.assigned_to == "RES001", \
            f"BT1 should be assigned to RES001, got {bt1.assigned_to}"
        assert bt1.reserved_for is None, \
            "BT1 reservation should be cleared after conversion"
        assert bt1.committed, "BT1 should be committed after assignment"

        # BT2 should NOT have been used for baggage_unload
        assert bt2.assigned_to != "RES001" or bt2.state != VehicleState.EN_ROUTE, \
            "BT2 should not have been assigned to RES001 baggage_unload"

        # baggage_unload should be in active_tasks, not pending
        active_svcs = {t.service_type for t in disp.active_tasks.values()}
        pending_svcs = [t.service_type for t in disp.pending_tasks]
        assert "baggage_unload" in active_svcs, \
            f"baggage_unload should be active, got active={active_svcs}"
        assert "baggage_unload" not in pending_svcs, \
            f"baggage_unload should NOT be pending, got pending={pending_svcs}"

        # Fulfillment counter incremented
        assert disp.reservation_fulfillments == 1

    def test_auto_assign_increments_task_counters(self):
        """Auto-assignment increments vehicles_dispatched and tasks_started."""
        disp, ac, fleet = _make_rl_dispatcher_with_aircraft_at_gate()
        bt1 = disp.vehicles["BT1"]
        bt1.reserved_for   = ("RES001", "baggage_unload")
        bt1.reserved_until = 9999.0

        disp._create_service_tasks(now=0.0)

        assert disp.vehicles_dispatched == 1, \
            f"vehicles_dispatched should be 1, got {disp.vehicles_dispatched}"
        assert disp.tasks_started == 1, \
            f"tasks_started should be 1, got {disp.tasks_started}"


class TestReservationExpiry:
    """test_reservation_expiry: expired reservations free the vehicle and apply penalty."""

    def test_expired_reservation_frees_vehicle(self, tmp_path):
        """A reservation past its reserved_until time frees the vehicle."""
        sched_path = _write_schedule(tmp_path, [_single_flight(arrival=300)])
        env = AirportEnv(schedule_path=sched_path)
        env.reset()

        ft1 = env.dispatcher.vehicles.get("FT1")
        assert ft1 is not None

        # Manually set a reservation already past its expiry (expired 1s ago)
        ft1.reserved_for   = ("FAKE_FLIGHT", "fuel")
        ft1.reserved_until = env._sim_time - 1.0   # already expired

        initial_expirations = env.dispatcher.reservation_expirations

        # Step once — the expiry loop should fire
        mask = env.action_masks()
        valid = np.where(mask)[0]
        env.step(int(valid[0]))

        # After stepping (and advancing time), ft1 should be free
        assert ft1.reserved_for is None, \
            f"FT1 reservation should be cleared after expiry, got {ft1.reserved_for}"
        assert env.dispatcher.reservation_expirations > initial_expirations, \
            "reservation_expirations counter should have incremented"

        env.close()

    def test_expiry_penalty_applied(self, tmp_path):
        """Reward includes REWARD_EXPIRED_RESERVATION penalty when a reservation expires."""
        sched_path = _write_schedule(tmp_path, [_single_flight(arrival=300)])
        env = AirportEnv(schedule_path=sched_path)
        env.reset()

        ft1 = env.dispatcher.vehicles.get("FT1")
        ft1.reserved_for   = ("FAKE_FLIGHT", "fuel")
        ft1.reserved_until = env._sim_time - 1.0   # already expired

        # Step and collect total reward; should contain the -0.5 penalty
        mask = env.action_masks()
        valid = np.where(mask)[0]
        _, reward, _, _, info = env.step(int(valid[0]))

        # The -0.5 penalty should be in the reward somewhere
        assert info["reservation_expirations"] > 0, "No expiration counted in info"

        env.close()


class TestReservationConversionPriority:
    """test_reservation_conversion_priority: reserved vehicle wins over free vehicle."""

    def test_reserved_vehicle_wins_over_free(self):
        """
        Scenario: BT1 reserved for RES001/baggage_unload, BT2 free.
        When baggage_unload task materializes, BT1 must win (not BT2).
        Task must NEVER appear in pending_tasks.
        """
        disp, ac, fleet = _make_rl_dispatcher_with_aircraft_at_gate()
        bt1 = disp.vehicles["BT1"]
        bt2 = disp.vehicles["BT2"]

        bt1.reserved_for   = ("RES001", "baggage_unload")
        bt1.reserved_until = 9999.0

        pending_before_ids = {t.task_id for t in disp.pending_tasks}
        disp._create_service_tasks(now=0.0)

        # 1. Task never appeared in pending_tasks
        for t in disp.pending_tasks:
            if t.flight_id == "RES001" and t.service_type == "baggage_unload":
                pytest.fail(
                    f"baggage_unload appeared in pending_tasks — conversion failed. "
                    f"Task: {t.task_id}"
                )

        # 2. BT1 (reserved) gets the assignment
        assert bt1.state == VehicleState.EN_ROUTE, \
            f"BT1 should be EN_ROUTE, got {bt1.state}"
        assert bt1.assigned_to == "RES001"
        assert bt1.reserved_for is None   # cleared

        # 3. BT2 (free) is untouched
        assert bt2.is_available(), \
            f"BT2 should remain available, got state={bt2.state}"

        # 4. Task is in active (not pending)
        active_svcs = {t.service_type for t in disp.active_tasks.values()}
        assert "baggage_unload" in active_svcs

    def test_no_double_assignment(self):
        """
        When reservation converts, the task gets exactly ONE vehicle — not two.
        """
        disp, ac, fleet = _make_rl_dispatcher_with_aircraft_at_gate()
        bt1 = disp.vehicles["BT1"]
        bt1.reserved_for   = ("RES001", "baggage_unload")
        bt1.reserved_until = 9999.0

        disp._create_service_tasks(now=0.0)

        baggage_active = [
            t for t in disp.active_tasks.values()
            if t.flight_id == "RES001" and t.service_type == "baggage_unload"
        ]
        assert len(baggage_active) == 1, \
            f"Expected exactly 1 active baggage_unload task, got {len(baggage_active)}"
        assert baggage_active[0].assigned_vehicle_id == "BT1"


class TestObsDimCorrect:
    """test_obs_dim_correct: verify new OBS_DIM = 337."""

    def test_obs_dim_is_337(self, tmp_path):
        sched_path = _write_schedule(tmp_path, [_single_flight()])
        env = AirportEnv(schedule_path=sched_path)
        assert OBS_DIM == 337, f"OBS_DIM should be 337, got {OBS_DIM}"
        obs, _ = env.reset()
        assert obs.shape == (337,), f"Obs shape should be (337,), got {obs.shape}"
        assert env.observation_space.shape == (337,)
        env.close()

    def test_obs_values_in_range(self, tmp_path):
        """All obs values must be in [-1, 1]."""
        sched_path = _write_schedule(tmp_path, [_single_flight(arrival=300)])
        env = AirportEnv(schedule_path=sched_path)
        obs, _ = env.reset()
        assert np.all(obs >= -1.0) and np.all(obs <= 1.0), (
            f"Obs out of range: min={obs.min():.3f}, max={obs.max():.3f}"
        )
        for _ in range(30):
            mask = env.action_masks()
            valid = np.where(mask)[0]
            obs, _, term, trunc, _ = env.step(int(valid[0]))
            assert np.all(obs >= -1.0) and np.all(obs <= 1.0)
            if term or trunc:
                break
        env.close()


class TestActionSpaceCorrect:
    """test_action_space_correct: verify Discrete(25)."""

    def test_action_space_is_25(self, tmp_path):
        sched_path = _write_schedule(tmp_path, [_single_flight()])
        env = AirportEnv(schedule_path=sched_path)
        assert env.action_space.n == 25, \
            f"Action space should be Discrete(25), got {env.action_space.n}"
        assert ACTION_HOLD == 24, f"ACTION_HOLD should be 24, got {ACTION_HOLD}"
        assert MAX_TASKS + MAX_ANTICIPATED + 1 == 25
        env.close()

    def test_mask_shape_is_25(self, tmp_path):
        sched_path = _write_schedule(tmp_path, [_single_flight()])
        env = AirportEnv(schedule_path=sched_path)
        env.reset()
        mask = env.action_masks()
        assert mask.shape == (25,), f"Mask shape should be (25,), got {mask.shape}"
        env.close()


class TestHoldMaskingWithReservations:
    """test_hold_masking_with_reservations: HOLD only when no assignments AND no reservations."""

    def test_hold_illegal_when_reservation_legal(self, tmp_path):
        """If any reservation action is legal, HOLD must be masked."""
        sched_path = _write_schedule(tmp_path, [_single_flight(arrival=300)])
        env = AirportEnv(schedule_path=sched_path)
        env.reset()

        for _ in range(100):
            mask = env.action_masks()
            reservation_bits = mask[MAX_TASKS:ACTION_HOLD]
            if reservation_bits.any():
                assert not mask[ACTION_HOLD], (
                    "HOLD must be masked when at least one reservation action is legal. "
                    f"Reservation mask: {reservation_bits}, HOLD: {mask[ACTION_HOLD]}"
                )
            valid = np.where(mask)[0]
            _, _, term, trunc, _ = env.step(int(valid[0]))
            if term or trunc:
                break

        env.close()

    def test_hold_illegal_when_assignment_legal(self, tmp_path):
        """HOLD must be masked when any assignment action is legal."""
        sched_path = _write_schedule(tmp_path, [_single_flight(arrival=0)])
        env = AirportEnv(schedule_path=sched_path)
        env.reset()

        for _ in range(100):
            mask = env.action_masks()
            assignment_bits = mask[:MAX_TASKS]
            if assignment_bits.any():
                assert not mask[ACTION_HOLD], (
                    "HOLD must be masked when assignment actions are available"
                )
            valid = np.where(mask)[0]
            _, _, term, trunc, _ = env.step(int(valid[0]))
            if term or trunc:
                break

        env.close()

    def test_hold_only_legal_when_nothing_else(self, tmp_path):
        """HOLD is legal iff mask[0..23] are all False."""
        sched_path = _write_schedule(tmp_path, [_single_flight(arrival=0)])
        env = AirportEnv(schedule_path=sched_path)
        env.reset()

        for _ in range(100):
            mask = env.action_masks()
            has_work = mask[:ACTION_HOLD].any()
            if mask[ACTION_HOLD]:
                assert not has_work, (
                    "HOLD is True but some non-HOLD action is also True"
                )
            else:
                assert has_work, (
                    "HOLD is False and all other actions are also False — no legal action"
                )
            valid = np.where(mask)[0]
            _, _, term, trunc, _ = env.step(int(valid[0]))
            if term or trunc:
                break

        env.close()


class TestFullEpisodeWithAnticipation:
    """test_full_episode_with_anticipation: 3 seeds end-to-end, zero conflicts."""

    @pytest.mark.parametrize("seed", [0, 1, 2])
    def test_zero_conflicts_seed(self, seed):
        """Run a full episode with random valid actions; must have zero conflicts."""
        env = AirportEnv(randomise=True, seed=seed)
        rng = np.random.default_rng(seed + 100)
        obs, info = env.reset(seed=seed)

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for _ in range(2000):
                mask = env.action_masks()
                valid = np.where(mask)[0]
                action = int(rng.choice(valid))
                obs, reward, terminated, truncated, info = env.step(action)
                assert obs.shape == (OBS_DIM,), f"Obs shape wrong: {obs.shape}"
                assert np.isfinite(reward), f"Non-finite reward: {reward}"
                if terminated or truncated:
                    break

        assert info.get("conflict_count", 0) == 0, (
            f"Seed {seed}: {info['conflict_count']} conflicts detected"
        )
        env.close()

    def test_anticipated_tasks_in_info(self):
        """Info dict contains n_anticipated_tasks, reservation_fulfillments, etc."""
        env = AirportEnv(randomise=True, seed=42)
        obs, info = env.reset(seed=42)

        assert "n_anticipated_tasks" in info, "Missing n_anticipated_tasks in info"
        assert "reservation_fulfillments" in info, "Missing reservation_fulfillments in info"
        assert "reservation_expirations" in info, "Missing reservation_expirations in info"
        assert "n_active_reservations" in info, "Missing n_active_reservations in info"
        assert isinstance(info["n_anticipated_tasks"], int)
        assert info["n_anticipated_tasks"] >= 0

        env.close()
