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

from env.airport_env import AirportEnv, OBS_DIM, ACTION_HOLD


N_STEPS    = 200
N_EPISODES = 2


def main() -> None:
    print("=" * 60)
    print("  AirportEnv smoke test")
    print("=" * 60)

    total_ok = True

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

        ep_reward = 0.0
        for step in range(N_STEPS):
            mask = env.action_masks()
            assert mask.shape == (env.action_space.n,), f"Bad mask shape: {mask.shape}"
            assert mask[ACTION_HOLD], "Hold action must always be valid"

            # Pick a random valid action
            valid_actions = np.where(mask)[0]
            action = int(np.random.choice(valid_actions))

            obs, reward, terminated, truncated, info = env.step(action)

            assert obs.shape == (OBS_DIM,), f"Step {step}: bad obs shape"
            assert np.all(obs >= -1.0) and np.all(obs <= 1.0), (
                f"Step {step}: obs out of [-1,1]: min={obs.min():.3f} max={obs.max():.3f}"
            )

            ep_reward += reward
            action_label = "HOLD" if action == ACTION_HOLD else f"assign task[{action}]"
            print(
                f"  step {step:4d} | {action_label:<18s} | "
                f"reward {reward:+7.2f} | pending={info['n_pending_tasks']} | "
                f"departed={info['flights_departed']} | "
                f"sim_t={info['sim_time']:.0f}s"
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
    if total_ok:
        print("smoke_test: ALL PASSED")
        sys.exit(0)
    else:
        print("smoke_test: FAILED (see conflicts above)")
        sys.exit(1)


if __name__ == "__main__":
    main()
