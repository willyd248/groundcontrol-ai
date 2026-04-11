"""
eval_phase2.py — Phase 2 post-retrain evaluation of v5_anticipation_v2_final.zip
Produces POLICY_HEALTH_ANTICIPATION_V2_FINAL.md and PHASE_2_VERDICT.txt

Usage:
    python -m train.eval_phase2
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime

import numpy as np
from sb3_contrib import MaskablePPO

from env.airport_env import AirportEnv, ACTION_HOLD, MAX_TASKS, MAX_ANTICIPATED
from train.callbacks import run_fcfs_episode

HARD_SEEDS = list(range(0, 50))
OOD_SEEDS  = list(range(200, 250))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

V1_HARD_WINS = 12
V1_OOD_WINS = 9
V1_COMBINED_WINS = 21
V1_MEAN_DELTA = -0.4
V1_HARD_MEAN = -0.3
V1_OOD_MEAN = -0.5


def run_policy_detailed(model, seed: int) -> dict:
    """Run model on seed, return metrics."""
    env = AirportEnv(randomise=True, seed=seed)
    obs, info = env.reset(seed=seed)

    total_decisions = 0
    hold_count = 0
    reservation_count = 0
    done = False

    while not done:
        masks = env.action_masks()
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)
        action = int(action)

        if action == ACTION_HOLD:
            hold_count += 1
        elif action >= MAX_TASKS and action < ACTION_HOLD:
            reservation_count += 1

        obs, reward, terminated, truncated, info = env.step(action)
        total_decisions += 1
        done = terminated or truncated

    env.close()
    info["decisions"] = total_decisions
    info["hold_count"] = hold_count
    info["reservation_count"] = reservation_count
    info["hold_rate"] = hold_count / max(1, total_decisions)
    info["reservation_rate"] = reservation_count / max(1, total_decisions)
    return info


def run_battery(model, seeds: list[int], label: str, verbose: bool = True) -> dict:
    """Run model vs FCFS on given seeds."""
    results = []
    wins = 0
    losses = 0
    ties = 0
    best_seed, best_delta = None, -9999
    worst_seed, worst_delta = None, 9999

    if verbose:
        print(f"  Running {label} battery ({len(seeds)} seeds)...")

    for i, seed in enumerate(seeds):
        fcfs = run_fcfs_episode(seed)
        rl = run_policy_detailed(model, seed)
        fcfs_d = fcfs["total_delay_minutes"]
        rl_d = rl["total_delay_minutes"]
        delta = fcfs_d - rl_d  # positive = RL better
        res_rate = rl["reservation_rate"]

        row = {
            "seed": seed,
            "fcfs_delay": fcfs_d,
            "rl_delay": rl_d,
            "delta": delta,
            "gap": rl_d - fcfs_d,
            "res_rate": res_rate,
            "conflicts": rl.get("conflict_count", 0),
            "abandonments": rl.get("abandonment_count", 0),
            "hold_rate": rl["hold_rate"],
        }
        results.append(row)

        if delta > 0.5:
            wins += 1
        elif delta < -0.5:
            losses += 1
        else:
            ties += 1

        if delta > best_delta:
            best_delta = delta
            best_seed = seed
        if delta < worst_delta:
            worst_delta = delta
            worst_seed = seed

        if verbose and (i % 10 == 0 or len(seeds) <= 10):
            print(f"    seed {seed:3d}: FCFS={fcfs_d:.1f}m  RL={rl_d:.1f}m  delta={delta:+.1f}m  res={res_rate:.1%}")

    deltas = [r["delta"] for r in results]
    return {
        "results": results,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "mean_delta": float(np.mean(deltas)),
        "median_delta": float(np.median(deltas)),
        "best_seed": best_seed,
        "best_delta": best_delta,
        "worst_seed": worst_seed,
        "worst_delta": worst_delta,
        "total_conflicts": sum(r["conflicts"] for r in results),
        "total_abandonments": sum(r["abandonments"] for r in results),
        "mean_hold_rate": float(np.mean([r["hold_rate"] for r in results])),
        "mean_res_rate": float(np.mean([r["res_rate"] for r in results])),
    }


def main():
    start_time = time.time()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*60}")
    print(f"PHASE 2 — v5_anticipation_v2_final evaluation")
    print(f"Started: {now_str}")
    print(f"{'='*60}\n")

    os.chdir(REPO_ROOT)

    # Load model
    print(f"Loading models/v5_anticipation_v2_final.zip...")
    try:
        model = MaskablePPO.load("models/v5_anticipation_v2_final.zip")
        print("  Model loaded OK")
    except Exception as e:
        print(f"  ERROR: {e}")
        with open("PHASE_2_VERDICT.txt", "w") as f:
            f.write("WORSE")
        sys.exit(1)

    # 50-seed hard battery
    print(f"\n(a) 50-seed hard battery (seeds 0-49)...")
    hard = run_battery(model, HARD_SEEDS, "hard-50", verbose=True)
    print(f"  Hard battery: {hard['wins']}/50 wins, mean {hard['mean_delta']:+.1f}m")

    # 50-seed OOD battery
    print(f"\n(b) 50-seed OOD battery (seeds 200-249)...")
    ood = run_battery(model, OOD_SEEDS, "ood-50", verbose=True)
    print(f"  OOD battery: {ood['wins']}/50 wins, mean {ood['mean_delta']:+.1f}m")

    # Combined
    combined_wins = hard["wins"] + ood["wins"]
    all_deltas = [r["delta"] for r in hard["results"]] + [r["delta"] for r in ood["results"]]
    combined_mean = float(np.mean(all_deltas))
    combined_median = float(np.median(all_deltas))

    print(f"\n(c) Combined 100-seed results:")
    print(f"  V2: wins={combined_wins}/100, mean={combined_mean:+.1f}m")
    print(f"  V1: wins={V1_COMBINED_WINS}/100, mean={V1_MEAN_DELTA:+.1f}m")

    # Determine verdict
    if combined_wins > V1_COMBINED_WINS + 5 or combined_mean > V1_MEAN_DELTA + 2.0:
        verdict = "BETTER"
    elif combined_wins < V1_COMBINED_WINS - 5 or combined_mean < V1_MEAN_DELTA - 2.0:
        verdict = "WORSE"
    else:
        verdict = "SAME"

    print(f"\nVERDICT: {verdict}")

    with open("PHASE_2_VERDICT.txt", "w") as f:
        f.write(verdict)
    print(f"PHASE_2_VERDICT.txt written: {verdict}")

    # Produce health report
    elapsed = time.time() - start_time
    produce_v2_report(hard, ood, combined_wins, combined_mean, combined_median, verdict, elapsed, now_str)

    print(f"\nPhase 2 evaluation complete in {elapsed/60:.1f} min")


def produce_v2_report(hard, ood, combined_wins, combined_mean, combined_median, verdict, elapsed, now_str):
    lines = []
    lines.append("# POLICY_HEALTH_ANTICIPATION_V2_FINAL.md\n")
    lines.append(f"**Generated:** {now_str}  ")
    lines.append(f"**Model:** models/v5_anticipation_v2_final.zip  ")
    lines.append(f"**Reward tuning:** REWARD_EXPIRED_RESERVATION = -1.0 (from -0.5)  ")
    lines.append(f"**Phase 2 verdict:** {verdict}\n")
    lines.append("---\n")

    # Side-by-side comparison
    lines.append("## 1. Side-by-Side Comparison: V1 vs V2\n")
    lines.append("| Metric | V1 (v5_anticipation) | V2 (v5_anticipation_v2) | Change |")
    lines.append("|--------|---------------------|------------------------|--------|")
    lines.append(f"| Hard wins (50 seeds) | {V1_HARD_WINS}/50 | {hard['wins']}/50 | {hard['wins']-V1_HARD_WINS:+d} |")
    lines.append(f"| OOD wins (50 seeds) | {V1_OOD_WINS}/50 | {ood['wins']}/50 | {ood['wins']-V1_OOD_WINS:+d} |")
    lines.append(f"| Combined wins | {V1_COMBINED_WINS}/100 | {combined_wins}/100 | {combined_wins-V1_COMBINED_WINS:+d} |")
    lines.append(f"| Hard mean delta | {V1_HARD_MEAN:+.1f}m | {hard['mean_delta']:+.1f}m | {hard['mean_delta']-V1_HARD_MEAN:+.1f}m |")
    lines.append(f"| OOD mean delta | {V1_OOD_MEAN:+.1f}m | {ood['mean_delta']:+.1f}m | {ood['mean_delta']-V1_OOD_MEAN:+.1f}m |")
    lines.append(f"| Combined mean delta | {V1_MEAN_DELTA:+.1f}m | {combined_mean:+.1f}m | {combined_mean-V1_MEAN_DELTA:+.1f}m |")
    lines.append(f"| Conflicts | 0 | {hard['total_conflicts']+ood['total_conflicts']} | — |")
    lines.append(f"| Abandonments | 0 | {hard['total_abandonments']+ood['total_abandonments']} | — |")
    lines.append(f"| Hard mean res rate | ~0.0% | {hard['mean_res_rate']:.1%} | — |")
    lines.append(f"| OOD mean res rate | ~0.0% | {ood['mean_res_rate']:.1%} | — |\n")

    lines.append(f"**VERDICT: {verdict}**\n")
    lines.append("Verdict criteria: BETTER if +5 wins or +2m delta, WORSE if -5 wins or -2m delta, else SAME.\n")

    # Hard battery detail
    lines.append("## 2. 50-seed Hard Battery\n")
    lines.append("| Seed | FCFS | RL | Delta | Res rate |")
    lines.append("|------|------|-----|-------|----------|")
    for row in hard["results"]:
        sign = "WIN" if row["delta"] > 0.5 else ("LOSS" if row["delta"] < -0.5 else "TIE")
        lines.append(f"| {row['seed']} | {row['fcfs_delay']:.1f} | {row['rl_delay']:.1f} | {row['delta']:+.1f} ({sign}) | {row['res_rate']:.1%} |")
    lines.append(f"\n**Wins:** {hard['wins']}/50  **Mean:** {hard['mean_delta']:+.1f}m  **Median:** {hard['median_delta']:+.1f}m\n")

    # OOD battery detail
    lines.append("## 3. 50-seed OOD Battery\n")
    lines.append("| Seed | FCFS | RL | Delta | Res rate |")
    lines.append("|------|------|-----|-------|----------|")
    for row in ood["results"]:
        sign = "WIN" if row["delta"] > 0.5 else ("LOSS" if row["delta"] < -0.5 else "TIE")
        lines.append(f"| {row['seed']} | {row['fcfs_delay']:.1f} | {row['rl_delay']:.1f} | {row['delta']:+.1f} ({sign}) | {row['res_rate']:.1%} |")
    lines.append(f"\n**Wins:** {ood['wins']}/50  **Mean:** {ood['mean_delta']:+.1f}m  **Median:** {ood['median_delta']:+.1f}m\n")

    report_path = "POLICY_HEALTH_ANTICIPATION_V2_FINAL.md"
    with open(report_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Written to {report_path}")


if __name__ == "__main__":
    main()
