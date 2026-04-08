"""
smoke_eval_v5.py — Eval a checkpoint against 5 hard seeds from v5 distribution.

Usage:
    python3 -m train.smoke_eval_v5 checkpoints/airport_ppo_final.zip
"""

from __future__ import annotations

import argparse
import sys

from sb3_contrib import MaskablePPO

from train.callbacks import run_fcfs_episode, run_policy_episode


# 5 hard seeds from v5 distribution (high FCFS delay, high suboptimality)
HARD_SEEDS = [6, 19, 42, 10, 40]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", help="Path to .zip checkpoint")
    args = parser.parse_args()

    print(f"Loading {args.checkpoint}...")
    model = MaskablePPO.load(args.checkpoint)

    wins = 0
    total = len(HARD_SEEDS)

    print(f"\nEval on {total} hard seeds from v5 distribution:")
    print(f"{'Seed':>6} | {'FCFS delay':>12} | {'RL delay':>12} | {'Improvement':>12} | {'Winner':>8}")
    print("-" * 68)

    for seed in HARD_SEEDS:
        fcfs = run_fcfs_episode(seed)
        rl = run_policy_episode(model, seed)

        fcfs_d = fcfs["total_delay_minutes"]
        rl_d = rl["total_delay_minutes"]
        imp = fcfs_d - rl_d

        winner = "RL" if imp > 0 else ("TIE" if imp == 0 else "FCFS")
        if imp > 0:
            wins += 1

        print(
            f"{seed:>6} | {fcfs_d:>10.1f} m | {rl_d:>10.1f} m | {imp:>+10.1f} m | {winner:>8}"
        )

        # Also check for problems
        if rl.get("conflict_count", 0) > 0:
            print(f"  !! CONFLICT detected on seed {seed}")
        if rl.get("abandonment_count", 0) > 0:
            print(f"  !! ABANDONMENT detected on seed {seed}")

    print(f"\nRL wins: {wins}/{total} seeds")
    print(f"Smoke pass threshold: ≥1 win")

    if wins >= 1:
        print("SMOKE PASS ✅")
        sys.exit(0)
    else:
        print("SMOKE FAIL ❌ — RL does not beat FCFS on any hard seed")
        sys.exit(1)


if __name__ == "__main__":
    main()
