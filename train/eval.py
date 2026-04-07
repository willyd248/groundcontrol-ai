"""
eval.py — Load a checkpoint and evaluate it on a given schedule.

Usage:
    python -m train.eval checkpoints/airport_ppo_final.zip
    python -m train.eval checkpoints/airport_ppo_50000_steps.zip --seed 7
    python -m train.eval checkpoints/airport_ppo_final.zip --schedule schedule.json
    python -m train.eval checkpoints/airport_ppo_final.zip --render

Flags:
    path            Path to the .zip checkpoint (positional, required).
    --seed INT      Random schedule seed (default: 42). Ignored if --schedule set.
    --schedule PATH Use a fixed schedule.json instead of a random schedule.
    --render        Print per-step logs to stdout (verbose mode).
    --compare-fcfs  Also run FCFS on the same schedule and print comparison.

Prints final metrics: total_delay, avg_delay, max_delay, conflicts, departed/pending.
Exit code 0 on success, 1 if conflicts > 0.
"""

from __future__ import annotations

import argparse
import sys

from sb3_contrib import MaskablePPO

from env.airport_env import AirportEnv
from train.callbacks import run_fcfs_episode


def run_eval(
    checkpoint: str,
    seed: int = 42,
    schedule_path: str | None = None,
    render: bool = False,
    compare_fcfs: bool = False,
) -> dict:
    """
    Run a single episode with the loaded policy. Returns the final info dict.
    """
    model = MaskablePPO.load(checkpoint)

    if schedule_path:
        env = AirportEnv(schedule_path=schedule_path, randomise=False)
    else:
        env = AirportEnv(randomise=True, seed=seed)

    obs, info = env.reset(seed=seed)
    done  = False
    step  = 0
    total_reward = 0.0

    while not done:
        masks = env.action_masks()
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(int(action))
        total_reward += reward
        done = terminated or truncated
        step += 1

        if render:
            action_label = "HOLD" if action == env.action_space.n - 1 else f"task[{action}]"
            print(
                f"  step {step:4d} | {action_label:<12s} | "
                f"reward {reward:+7.2f} | "
                f"pending={info['n_pending_tasks']} | "
                f"departed={info['flights_departed']} | "
                f"sim_t={info['sim_time']:.0f}s"
            )

    env.close()

    # ── Print results ─────────────────────────────────────────────────────────
    print("\n── RL Agent Results ──────────────────────────────────────────────")
    print(f"  Total reward:       {total_reward:+.2f}")
    print(f"  Steps taken:        {step}")
    print(f"  Flights departed:   {info['flights_departed']}")
    print(f"  Flights pending:    {info['flights_pending']}")
    print(f"  Total delay:        {info['total_delay_minutes']:.1f} min")
    print(f"  Avg delay:          {info['avg_delay_minutes']:.1f} min")
    print(f"  Max delay:          {info['max_delay_minutes']:.1f} min")
    print(f"  Conflict count:     {info['conflict_count']}")

    if compare_fcfs:
        print("\n── FCFS Baseline ─────────────────────────────────────────────────")
        if schedule_path:
            # Fixed schedule: we can't reproduce FCFS on same fixed schedule easily,
            # so we skip and note it
            print("  (FCFS comparison not available for fixed --schedule, use --seed instead)")
        else:
            fc = run_fcfs_episode(seed)
            print(f"  Flights departed:   {fc['flights_departed']}")
            print(f"  Flights pending:    {fc['flights_pending']}")
            print(f"  Total delay:        {fc['total_delay_minutes']:.1f} min")
            print(f"  Avg delay:          {fc['avg_delay_minutes']:.1f} min")
            print(f"  Max delay:          {fc['max_delay_minutes']:.1f} min")
            print(f"  Conflict count:     {fc['conflict_count']}")

            delay_delta  = fc["total_delay_minutes"] - info["total_delay_minutes"]
            missed_delta = fc["flights_pending"]      - info["flights_pending"]
            sign_d = "+" if delay_delta >= 0 else ""
            sign_m = "+" if missed_delta >= 0 else ""
            print(
                f"\n── Delta (positive = RL better) ──────────────────────────────────"
            )
            print(f"  Delay improvement:  {sign_d}{delay_delta:.1f} min")
            print(f"  Missed improvement: {sign_m}{missed_delta} flights")

    return info


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained AirportPPO checkpoint")
    parser.add_argument("path", help="Path to checkpoint .zip")
    parser.add_argument("--seed", type=int, default=42, help="Schedule seed (default 42)")
    parser.add_argument("--schedule", type=str, default=None, help="Fixed schedule.json path")
    parser.add_argument("--render", action="store_true", help="Print per-step output")
    parser.add_argument("--compare-fcfs", action="store_true", help="Compare against FCFS baseline")
    args = parser.parse_args()

    info = run_eval(
        checkpoint=args.path,
        seed=args.seed,
        schedule_path=args.schedule,
        render=args.render,
        compare_fcfs=args.compare_fcfs,
    )

    sys.exit(1 if info.get("conflict_count", 0) > 0 else 0)


if __name__ == "__main__":
    main()
