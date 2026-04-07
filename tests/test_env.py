"""
tests/test_env.py — Gymnasium env correctness suite.

Run with:
    pytest tests/test_env.py -v

Tests:
  1. Observation and mask shapes are consistent across resets and steps.
  2. Obs values stay within declared bounds [-1, 1].
  3. Hold action is always in the mask.
  4. Only valid actions are in the mask (no vehicle = not maskable).
  5. Zero conflicts across 1000 random steps over 10 random schedules.
  6. Episode terminates within SIM_HORIZON.
  7. Reward is finite (no NaN/Inf).
  8. Mask and action_space.n agree.
  9. (event-trigger) decisions per episode within sane range after fix.
  10. (event-trigger) mask consistency: non-HOLD actions ↔ _has_decision_point().
  11. (event-trigger) each step advances sim time; batching confirmed.
  12. (event-trigger) safety valve emits RuntimeWarning after 600 idle ticks.
  13. (event-trigger) Event C fires when all compatible vehicles break mid-advance.
"""

from __future__ import annotations

import json
import warnings

import numpy as np
import pytest

from env.airport_env import (
    AirportEnv, OBS_DIM, ACTION_HOLD, MAX_TASKS,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _write_schedule(tmp_path, flights: list[dict]) -> str:
    """Write a schedule JSON to a temp file and return the path."""
    p = tmp_path / "schedule.json"
    p.write_text(json.dumps(flights))
    return str(p)


# ── Helpers ───────────────────────────────────────────────────────────────────

def random_valid_action(env: AirportEnv, rng: np.random.Generator) -> int:
    mask  = env.action_masks()
    valid = np.where(mask)[0]
    return int(rng.choice(valid))


def run_episode(env: AirportEnv, rng: np.random.Generator, max_steps: int = 1000):
    """
    Run one full episode with random valid actions.
    Returns (total_reward, final_info, steps_taken, conflict_count).
    """
    obs, info = env.reset()

    assert obs.shape == (OBS_DIM,),    f"reset() obs shape: {obs.shape}"
    assert obs.dtype == np.float32,     "obs must be float32"

    total_reward  = 0.0
    steps         = 0
    conflict_count = 0

    for _ in range(max_steps):
        mask = env.action_masks()

        # Shape and hold-always-valid invariant
        assert mask.shape == (env.action_space.n,), f"mask shape: {mask.shape}"
        assert mask[ACTION_HOLD], "Hold must always be masked True"

        action = random_valid_action(env, rng)
        assert 0 <= action < env.action_space.n, f"action out of range: {action}"
        assert mask[action], f"Chose action {action} but mask[action]=False"

        obs, reward, terminated, truncated, info = env.step(action)

        assert obs.shape == (OBS_DIM,),    f"step obs shape: {obs.shape}"
        assert obs.dtype == np.float32
        assert np.isfinite(reward),         f"reward is not finite: {reward}"
        assert np.all(np.isfinite(obs)),    "obs contains NaN or Inf"
        assert np.all(obs >= -1.0) and np.all(obs <= 1.0), (
            f"obs out of bounds: min={obs.min():.4f} max={obs.max():.4f}"
        )

        total_reward   += reward
        conflict_count  = info.get("conflict_count", 0)
        steps          += 1

        if terminated or truncated:
            break

    return total_reward, info, steps, conflict_count


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestObsAndMaskShapes:
    """Obs and mask shapes stay consistent."""

    def test_obs_shape_after_reset(self):
        env = AirportEnv(schedule_path="schedule.json")
        obs, _ = env.reset()
        assert obs.shape == (OBS_DIM,)
        env.close()

    def test_obs_shape_after_step(self):
        env = AirportEnv(schedule_path="schedule.json")
        env.reset()
        mask   = env.action_masks()
        valid  = np.where(mask)[0]
        obs, *_ = env.step(int(valid[0]))
        assert obs.shape == (OBS_DIM,)
        env.close()

    def test_mask_shape(self):
        env = AirportEnv(schedule_path="schedule.json")
        env.reset()
        mask = env.action_masks()
        assert mask.shape == (MAX_TASKS + 1,)
        assert mask.dtype == bool
        env.close()

    def test_action_space_matches_mask(self):
        env = AirportEnv(schedule_path="schedule.json")
        env.reset()
        mask = env.action_masks()
        assert len(mask) == env.action_space.n
        env.close()

    def test_hold_always_valid(self):
        env = AirportEnv(schedule_path="schedule.json")
        rng = np.random.default_rng(0)
        env.reset()
        for _ in range(50):
            mask = env.action_masks()
            assert mask[ACTION_HOLD], "Hold must always be valid"
            action = random_valid_action(env, rng)
            _, _, terminated, truncated, _ = env.step(action)
            if terminated or truncated:
                env.reset()
        env.close()


class TestObsValues:
    """Obs values stay within [-1, 1] for the entire episode."""

    def test_obs_bounds_fixed_schedule(self):
        env = AirportEnv(schedule_path="schedule.json")
        rng = np.random.default_rng(1)
        _, info, _, _ = run_episode(env, rng, max_steps=2000)
        env.close()

    def test_obs_bounds_random_schedule(self):
        env = AirportEnv(randomise=True, seed=7)
        rng = np.random.default_rng(7)
        _, info, _, _ = run_episode(env, rng, max_steps=2000)
        env.close()


class TestNoConflicts:
    """Zero conflicts across 1000 random steps × 10 random seeds."""

    @pytest.mark.parametrize("seed", list(range(10)))
    def test_no_conflicts_random_schedule(self, seed: int):
        env = AirportEnv(randomise=True, seed=seed)
        rng = np.random.default_rng(seed + 100)

        total_steps      = 0
        total_conflicts  = 0

        while total_steps < 1000:
            remaining = 1000 - total_steps
            _, info, steps, conflicts = run_episode(env, rng, max_steps=remaining)
            total_steps     += steps
            total_conflicts += conflicts

            if total_steps < 1000:
                env.reset()

        env.close()
        assert total_conflicts == 0, (
            f"seed={seed}: {total_conflicts} conflict(s) in {total_steps} steps"
        )


class TestEpisodeTermination:
    """Episodes terminate (done or truncated) within SIM_HORIZON."""

    def test_terminates_fixed(self):
        env = AirportEnv(schedule_path="schedule.json")
        rng = np.random.default_rng(42)
        _, info, _, _ = run_episode(env, rng, max_steps=100_000)
        assert info["sim_time"] <= 14401.0, "sim_time exceeded SIM_HORIZON"
        env.close()

    @pytest.mark.parametrize("seed", [0, 3, 9])
    def test_terminates_random(self, seed):
        env = AirportEnv(randomise=True, seed=seed)
        rng = np.random.default_rng(seed)
        _, info, _, _ = run_episode(env, rng, max_steps=100_000)
        assert info["sim_time"] <= 14401.0
        env.close()


class TestRewardFinite:
    """Reward is always finite."""

    @pytest.mark.parametrize("seed", [0, 5])
    def test_reward_finite(self, seed):
        env = AirportEnv(randomise=True, seed=seed)
        rng = np.random.default_rng(seed + 200)
        total, _, _, _ = run_episode(env, rng, max_steps=500)
        assert np.isfinite(total), f"Total reward not finite: {total}"
        env.close()


class TestMaskValidity:
    """Masked actions always have a compatible vehicle."""

    def test_masked_actions_have_vehicles(self):
        env = AirportEnv(schedule_path="schedule.json")
        rng = np.random.default_rng(99)
        obs, _ = env.reset()

        for _ in range(200):
            mask  = env.action_masks()
            # Every non-hold masked action must have a vehicle available
            for i, valid in enumerate(mask[:-1]):   # exclude hold
                if valid:
                    assert env._is_valid_assignment(i), (
                        f"Mask says action {i} is valid but no vehicle available"
                    )

            action = random_valid_action(env, rng)
            _, _, terminated, truncated, _ = env.step(action)
            if terminated or truncated:
                env.reset()

        env.close()


# ── Abandonment tests (Step 3) ────────────────────────────────────────────────

class TestAbandonmentProtection:
    """
    Verify the committed flag prevents mid-service reassignment.
    """

    def test_no_mid_service_reassignment(self):
        """
        Once a vehicle is dispatched (committed=True), it must not be selected
        for a new assignment until its current task completes (committed=False).
        """
        import warnings
        from sim.entities import VehicleState

        env = AirportEnv(schedule_path="schedule.json")
        rng = np.random.default_rng(0)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            env.reset()

            for _ in range(300):
                committed_ids = {
                    vid for vid, v in env.dispatcher.vehicles.items()
                    if v.committed
                }

                mask = env.action_masks()

                # No committed vehicle should appear as the assignment target
                for i in range(len(env.dispatcher.pending_tasks)):
                    if i >= MAX_TASKS or not mask[i]:
                        continue
                    task = env.dispatcher.pending_tasks[i]
                    vehicle = env.dispatcher._find_nearest_vehicle(
                        task.service_type, task.gate_node
                    )
                    assert vehicle is not None, (
                        f"Mask says action {i} is valid but no vehicle found"
                    )
                    assert vehicle.vehicle_id not in committed_ids, (
                        f"Vehicle {vehicle.vehicle_id} is committed (mid-task) "
                        f"but appeared as assignment candidate for action {i}"
                    )

                action = random_valid_action(env, rng)
                _, _, terminated, truncated, _ = env.step(action)
                if terminated or truncated:
                    break

        env.close()

    def test_committed_flag_lifecycle(self):
        """
        committed=False before dispatch; True immediately after _assign_one_task();
        False again once service completes (vehicle back to IDLE).
        step() advances the sim to the next event, so by the time step() returns
        the vehicle may have already finished — test handles both cases.
        """
        import warnings
        from sim.entities import VehicleState

        env = AirportEnv(schedule_path="schedule.json")
        rng = np.random.default_rng(5)

        dispatched_vehicles: set[str] = set()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            env.reset()

            for _ in range(400):
                mask     = env.action_masks()
                non_hold = [i for i in range(MAX_TASKS) if mask[i]]

                if non_hold:
                    action = non_hold[0]
                    task   = env.dispatcher.pending_tasks[action]
                    veh    = env.dispatcher._find_nearest_vehicle(
                        task.service_type, task.gate_node
                    )
                    assert veh is not None
                    assert not veh.committed, (
                        f"{veh.vehicle_id} should not be committed before assignment"
                    )

                    # Call internal assignment directly to check committed=True
                    # before the sim ticks forward
                    env._assign_one_task(action)
                    assert veh.committed, (
                        f"{veh.vehicle_id} should be committed immediately after dispatch"
                    )
                    dispatched_vehicles.add(veh.vehicle_id)

                    # Advance sim; reward doesn't matter for this test
                    env._advance_to_decision()
                else:
                    _, _, terminated, truncated, _ = env.step(ACTION_HOLD)
                    if terminated or truncated:
                        break

        # IDLE vehicles must have committed=False (cleared on service completion)
        for vid in dispatched_vehicles:
            v = env.dispatcher.vehicles.get(vid)
            if v is not None and v.state == VehicleState.IDLE:
                assert not v.committed, (
                    f"{vid} is IDLE but committed=True — not cleared on completion"
                )

        env.close()


# ── Event-trigger tests (Step 2) ──────────────────────────────────────────────

class TestEventTrigger:
    """
    Verify the event-based decision trigger introduced in Step 2.

    The old trigger fired on every tick where pending_task + free_vehicle existed,
    producing ~9000 queries per episode.  The new trigger fires only when something
    meaningfully changes (Event A/B/C), reducing queries to O(tasks-per-episode).
    """

    def test_decisions_per_episode_in_sane_range(self):
        """Full episode with random valid policy: 30–400 total decisions (not ~9000)."""
        env = AirportEnv(randomise=True, seed=0)
        rng = np.random.default_rng(0)

        obs, info = env.reset(seed=0)
        steps = 0

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            for _ in range(600):          # hard cap well above expected
                mask   = env.action_masks()
                action = int(rng.choice(np.where(mask)[0]))
                _, _, terminated, truncated, _ = env.step(action)
                steps += 1
                if terminated or truncated:
                    break

        env.close()
        assert 30 <= steps <= 400, (
            f"Expected 30–400 decisions per episode, got {steps}. "
            f"Old trigger produced ~9000; if this is high the trigger is still broken."
        )

    def test_no_query_without_legal_action(self):
        """
        Mask consistency: non-HOLD slots are True iff _has_decision_point() is True.
        Ensures the env never presents misleading mask state to the agent.
        """
        env = AirportEnv(schedule_path="schedule.json")
        rng = np.random.default_rng(42)
        env.reset()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            for _ in range(200):
                mask     = env.action_masks()
                has_work = mask[:ACTION_HOLD].any()
                # Mask must agree with _has_decision_point()
                assert has_work == env._has_decision_point(), (
                    f"Mask says has_work={has_work} but "
                    f"_has_decision_point()={env._has_decision_point()}"
                )
                action = random_valid_action(env, rng)
                _, _, terminated, truncated, _ = env.step(action)
                if terminated or truncated:
                    break

        env.close()

    def test_event_batching(self, tmp_path):
        """
        Each step() advances sim time by ≥1 tick.
        Total sim advance >> step count confirms events are batched, not one-tick-per-query.
        """
        env = AirportEnv(schedule_path="schedule.json")
        rng = np.random.default_rng(1)
        env.reset()

        sim_times = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            for _ in range(80):
                prev_t = env._sim_time
                mask   = env.action_masks()
                action = int(rng.choice(np.where(mask)[0]))
                _, _, terminated, truncated, _ = env.step(action)
                sim_times.append(env._sim_time - prev_t)
                if terminated or truncated:
                    break

        env.close()

        # Every step must advance time by at least 1 sim-second
        assert all(dt >= 1.0 for dt in sim_times), (
            "A step advanced 0 sim-seconds — event-based loop is not ticking."
        )

        # Average advance per step should be well above 1 s
        # (old trigger: ~1 s/step because it re-queried every tick)
        avg_advance = float(np.mean(sim_times)) if sim_times else 0.0
        assert avg_advance >= 10.0, (
            f"Average sim advance per step: {avg_advance:.1f}s "
            f"(expected ≥10s with event-based trigger; ~1s indicates regression to old trigger)"
        )

    def test_safety_valve_fires(self, tmp_path):
        """
        Holding with pending tasks + free vehicles for 600 ticks emits RuntimeWarning.
        Uses a single-aircraft schedule so no second arrival event can fire
        during the 600-tick window after the first decision point.
        """
        # Single arriving aircraft: lands at t=0, gets gate, creates service tasks.
        # After reset() returns (first decision point), a HOLD leaves tasks + free
        # vehicles unchanged for 600 ticks — no Event A, B, or C fires.
        sched_path = _write_schedule(tmp_path, [{
            "flight_id": "VALVE001",
            "aircraft_type": "CRJ900",
            "scheduled_arrival": 0,
            "scheduled_departure": 99999,   # far future — no pushback trigger
            "is_departure_only": False,
            "is_arrival_only": False,
        }])

        env = AirportEnv(schedule_path=sched_path)
        env.reset()

        assert env._has_decision_point(), (
            "Expected pending service tasks after single-aircraft reset."
        )

        # HOLD: same tasks + free vehicles, nothing changes for 600 ticks → valve fires
        with pytest.warns(RuntimeWarning, match="No decision event in 600 ticks"):
            env.step(ACTION_HOLD)

        env.close()

    def test_disruption_event_c(self, tmp_path, monkeypatch):
        """
        When all compatible vehicles become unavailable mid-advance (Event C),
        the env queries the agent after exactly 1 tick (not after 600 ticks).
        After the query, only HOLD is valid.
        """
        from sim.entities import VehicleState

        sched_path = _write_schedule(tmp_path, [{
            "flight_id": "EVT001",
            "aircraft_type": "CRJ900",
            "scheduled_arrival": 0,
            "scheduled_departure": 99999,
            "is_departure_only": False,
            "is_arrival_only": False,
        }])

        env = AirportEnv(schedule_path=sched_path)
        env.reset()

        assert env._has_decision_point(), (
            "Need a decision point before testing Event C."
        )

        # Wrap dispatcher.tick() to break ALL available vehicles on the first tick
        tick_count = [0]
        original_tick = env.dispatcher.tick

        def injecting_tick(now, dt=1.0):
            tick_count[0] += 1
            original_tick(now, dt)
            if tick_count[0] == 1:
                # Simulate: all free vehicles suddenly unavailable (breakdown)
                for v in env.dispatcher.vehicles.values():
                    if v.is_available():
                        v.state       = VehicleState.RETURNING
                        v.assigned_to = "__BREAKDOWN__"

        monkeypatch.setattr(env.dispatcher, "tick", injecting_tick)

        # HOLD: _advance_to_decision() must detect Event C and return after 1 tick
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            env.step(ACTION_HOLD)

        assert tick_count[0] == 1, (
            f"Event C should fire after exactly 1 tick; ran {tick_count[0]} ticks. "
            f"If this is 600, Event C detection is not working."
        )

        # After Event C: no legal non-HOLD actions (no compatible vehicles)
        assert not env.action_masks()[:ACTION_HOLD].any(), (
            "Expected all non-HOLD actions masked out after all vehicles broken."
        )

        env.close()
