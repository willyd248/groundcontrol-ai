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
"""

from __future__ import annotations

import numpy as np
import pytest

from env.airport_env import (
    AirportEnv, OBS_DIM, ACTION_HOLD, MAX_TASKS,
)


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
