"""
smoke_test.py — Quick sanity check for AirportEnv.

Run with:
    python -m env.smoke_test

Steps the env with random valid actions for up to N_STEPS steps,
printing reward, action, and key info each step.
Exits 0 on success, 1 if any assertion fails.
"""

from __future__ import annotations

import sys
import numpy as np

from env.airport_env import AirportEnv, OBS_DIM, ACTION_HOLD, MAX_TASKS, MAX_ANTICIPATED


N_STEPS    = 200
N_EPISODES = 2

# Action index ranges
ASSIGN_START     = 0
ASSIGN_END       = MAX_TASKS          # exclusive
RESERVE_START    = MAX_TASKS
RESERVE_END      = MAX_TASKS + MAX_ANTICIPATED  # exclusive = ACTION_HOLD


def _label(action: int) -> str:
    if action == ACTION_HOLD:
        return "HOLD"
    if RESERVE_START <= action < RESERVE_END:
        return f"reserve ant[{action - RESERVE_START}]"
    return f"assign task[{action}]"


def main() -> None:
    print("=" * 60)
    print("  AirportEnv smoke test (anticipation-aware)")
    print("=" * 60)
    print(f"  OBS_DIM      : {OBS_DIM}")
    print(f"  action_space : Discrete({ACTION_HOLD + 1})")
    print(f"  assign range : 0–{ASSIGN_END - 1}")
    print(f"  reserve range: {RESERVE_START}–{RESERVE_END - 1}")
    print(f"  HOLD         : {ACTION_HOLD}")

    total_ok       = True
    reserve_seen   = 0

    for ep in range(N_EPISODES):
        print(f"\n── Episode {ep + 1} (randomise={ep > 0}) ──")
        env = AirportEnv(
            schedule_path="schedule.json",
            randomise=(ep > 0),
            seed=ep * 42,
        )
        obs, info = env.reset(seed=ep)

        # Shape checks
        assert obs.shape == (OBS_DIM,), f"Bad obs shape: {obs.shape}"
        assert obs.dtype == np.float32,  "Obs dtype must be float32"
        assert env.action_space.n == ACTION_HOLD + 1, \
            f"action_space.n should be {ACTION_HOLD + 1}, got {env.action_space.n}"

        ep_reward = 0.0
        for step in range(N_STEPS):
            mask = env.action_masks()
            assert mask.shape == (env.action_space.n,), f"Bad mask shape: {mask.shape}"
            assert mask.any(), "At least one action must be valid (HOLD when no work, assign/reserve otherwise)"

            # Pick a random valid action
            valid_actions = np.where(mask)[0]
            action = int(np.random.choice(valid_actions))

            if RESERVE_START <= action < RESERVE_END:
                reserve_seen += 1

            obs, reward, terminated, truncated, info = env.step(action)

            assert obs.shape == (OBS_DIM,), f"Step {step}: bad obs shape"
            assert np.all(obs >= -1.0) and np.all(obs <= 1.0), (
                f"Step {step}: obs out of [-1,1]: min={obs.min():.3f} max={obs.max():.3f}"
            )

            ep_reward += reward
            n_ant = info.get("n_anticipated_tasks", "?")
            print(
                f"  step {step:4d} | {_label(action):<22s} | "
                f"reward {reward:+7.2f} | pending={info['n_pending_tasks']} "
                f"| ant={n_ant} | departed={info['flights_departed']} "
                f"| sim_t={info['sim_time']:.0f}s"
            )

            if terminated or truncated:
                reason = "DONE" if terminated else "TRUNCATED"
                print(f"  → Episode ended ({reason}) at step {step}")
                break
        else:
            print(f"  → Reached max steps ({N_STEPS})")

        print(f"  Episode reward: {ep_reward:+.2f}")
        if info.get("conflict_count", 0) > 0:
            print(f"  !! {info['conflict_count']} CONFLICTS DETECTED")
            total_ok = False

    env.close()

    print()
    print(f"  Reservation actions taken across all episodes: {reserve_seen}")
    if reserve_seen == 0:
        print("  NOTE: no reservation actions were exercised (may be expected with small schedule)")

    print()
    if total_ok:
        print("smoke_test: ALL PASSED")
        sys.exit(0)
    else:
        print("smoke_test: FAILED (see conflicts above)")
        sys.exit(1)


if __name__ == "__main__":
    main()
