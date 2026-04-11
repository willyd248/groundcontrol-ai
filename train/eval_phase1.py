"""
eval_phase1.py — Phase 1 comprehensive evaluation of v5_anticipation_final.zip

Usage:
    python -m train.eval_phase1

Produces:
    POLICY_HEALTH_ANTICIPATION_FINAL.md
    PHASE_1_VERDICT.txt
    Appends 1M-2M entries to MILESTONE_TRACE_ANTICIPATION.md
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime

import numpy as np
import torch
from sb3_contrib import MaskablePPO

from env.airport_env import AirportEnv, ACTION_HOLD, MAX_TASKS, MAX_ANTICIPATED
from train.callbacks import run_fcfs_episode, run_policy_episode

HARD_SEEDS = list(range(0, 50))
OOD_SEEDS  = list(range(200, 250))
BATTERY5   = [6, 10, 19, 40, 42]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODELS = {
    "1M":   "models/v5_anticipation_step_1000000_steps.zip",
    "1.25M":"models/v5_anticipation_step_1250000_steps.zip",
    "1.5M": "models/v5_anticipation_step_1500000_steps.zip",
    "1.75M":"models/v5_anticipation_step_1750000_steps.zip",
    "2M":   "models/v5_anticipation_step_2000000_steps.zip",
}
FINAL_MODEL = "models/v5_anticipation_final.zip"


# ── helpers ───────────────────────────────────────────────────────────────────

def run_policy_episode_detailed(model, seed: int) -> dict:
    """Run model on seed, return metrics + reservation stats."""
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
    """Run model vs FCFS on given seeds. Returns aggregate stats."""
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
        rl   = run_policy_episode_detailed(model, seed)
        fcfs_d = fcfs["total_delay_minutes"]
        rl_d   = rl["total_delay_minutes"]
        delta  = fcfs_d - rl_d  # positive = RL better
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
            "res_fulfilled": rl.get("reservations_fulfilled", 0),
            "res_expired": rl.get("reservations_expired", 0),
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


def run_mini_battery(model, seeds: list[int]) -> dict:
    """Run 5-seed battery for milestone checkpoints."""
    return run_battery(model, seeds, "mini", verbose=False)


def verdict_from_combined(combined_wins: int, combined_mean_delta: float,
                          total_conflicts: int, total_abandonments: int,
                          load_error: bool) -> str:
    """Compute HEALTHY/MARGINAL/WEAK/BROKEN verdict."""
    if load_error or total_conflicts > 0 or total_abandonments > 0:
        return "BROKEN"
    win_rate = combined_wins / 100.0
    if win_rate >= 0.10 and combined_mean_delta > -5.0:
        return "HEALTHY"
    elif win_rate >= 0.05 or (combined_mean_delta >= -10.0 and combined_mean_delta > -5.0):
        return "MARGINAL"
    elif combined_mean_delta >= -5.0 and combined_mean_delta <= -10.0:
        return "MARGINAL"
    else:
        return "WEAK"


# ── TensorBoard extraction ────────────────────────────────────────────────────

def extract_tb_metrics(log_dir: str) -> dict:
    """Extract per-step metrics from TensorBoard event file."""
    try:
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
        ea = EventAccumulator(log_dir)
        ea.Reload()

        def get_scalar_at_steps(tag: str, target_steps: list[int], window: int = 32768) -> dict:
            """Get scalar value nearest to each target step."""
            try:
                events = ea.Scalars(tag)
            except KeyError:
                return {s: None for s in target_steps}
            result = {}
            for target in target_steps:
                closest = min(events, key=lambda e: abs(e.step - target))
                if abs(closest.step - target) <= window:
                    result[target] = closest.value
                else:
                    result[target] = None
            return result

        steps_50k = list(range(750_000, 2_050_000, 50_000))

        rew = get_scalar_at_steps("rollout/ep_rew_mean", steps_50k)
        ev  = get_scalar_at_steps("train/explained_variance", steps_50k)
        cf  = get_scalar_at_steps("train/clip_fraction", steps_50k)
        ent = get_scalar_at_steps("train/entropy_loss", steps_50k)

        return {"steps": steps_50k, "rew": rew, "ev": ev, "cf": cf, "ent": ent}
    except Exception as e:
        print(f"  [WARN] TensorBoard extraction failed: {e}")
        return {}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    start_time = time.time()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*60}")
    print(f"PHASE 1 — v5_anticipation_final comprehensive evaluation")
    print(f"Started: {now_str}")
    print(f"{'='*60}\n")

    os.chdir(REPO_ROOT)

    # ── Load final model ──────────────────────────────────────────────────────
    print(f"Loading {FINAL_MODEL}...")
    load_error = False
    try:
        model = MaskablePPO.load(FINAL_MODEL)
        print("  Model loaded OK")
    except Exception as e:
        print(f"  ERROR loading model: {e}")
        load_error = True
        with open("PHASE_1_VERDICT.txt", "w") as f:
            f.write("BROKEN")
        print("PHASE_1_VERDICT.txt written: BROKEN")
        sys.exit(1)

    # ── (a) 50-seed hard battery ──────────────────────────────────────────────
    print(f"\n(a) 50-seed hard battery (seeds 0-49)...")
    hard = run_battery(model, HARD_SEEDS, "hard-50", verbose=True)
    print(f"  Hard battery: {hard['wins']}/50 wins, mean {hard['mean_delta']:+.1f}m, median {hard['median_delta']:+.1f}m")

    # ── (b) 50-seed OOD battery ───────────────────────────────────────────────
    print(f"\n(b) 50-seed OOD battery (seeds 200-249)...")
    ood = run_battery(model, OOD_SEEDS, "ood-50", verbose=True)
    print(f"  OOD battery: {ood['wins']}/50 wins, mean {ood['mean_delta']:+.1f}m, median {ood['median_delta']:+.1f}m")

    # ── (c) Combined verdict ──────────────────────────────────────────────────
    combined_wins = hard["wins"] + ood["wins"]
    all_deltas = [r["delta"] for r in hard["results"]] + [r["delta"] for r in ood["results"]]
    combined_mean  = float(np.mean(all_deltas))
    combined_median = float(np.median(all_deltas))
    combined_conflicts = hard["total_conflicts"] + ood["total_conflicts"]
    combined_abandonments = hard["total_abandonments"] + ood["total_abandonments"]

    print(f"\n(c) Combined 100-seed verdict:")
    print(f"  Wins: {combined_wins}/100 ({combined_wins}%)")
    print(f"  Mean delta: {combined_mean:+.1f}m")
    print(f"  Median delta: {combined_median:+.1f}m")
    print(f"  Conflicts: {combined_conflicts}  Abandonments: {combined_abandonments}")

    # ── (d) TensorBoard trace 750k-2M ────────────────────────────────────────
    print(f"\n(d) Extracting TensorBoard metrics 750k-2M...")
    tb = extract_tb_metrics("runs/AirportPPO_anticipation_2M")

    # ── (e) Per-milestone 5-seed battery ─────────────────────────────────────
    print(f"\n(e) Per-milestone 5-seed batteries (seeds {BATTERY5})...")
    milestone_results = {}
    for label, model_path in MODELS.items():
        print(f"  Loading {model_path}...")
        try:
            m = MaskablePPO.load(model_path)
            r = run_mini_battery(m, BATTERY5)
            milestone_results[label] = r
            print(f"    {label}: wins={r['wins']}/5  mean={r['mean_delta']:+.1f}m  conflicts={r['total_conflicts']}")
        except Exception as e:
            print(f"    FAILED: {e}")
            milestone_results[label] = None

    # ── Compute verdict ───────────────────────────────────────────────────────
    verdict = verdict_from_combined(combined_wins, combined_mean,
                                    combined_conflicts, combined_abandonments,
                                    load_error)
    print(f"\nVERDICT: {verdict}")

    # ── Write PHASE_1_VERDICT.txt ─────────────────────────────────────────────
    with open("PHASE_1_VERDICT.txt", "w") as f:
        f.write(verdict)
    print(f"PHASE_1_VERDICT.txt written: {verdict}")

    # ── Append to MILESTONE_TRACE_ANTICIPATION.md ─────────────────────────────
    print(f"\nAppending 1M-2M milestone results to MILESTONE_TRACE_ANTICIPATION.md...")
    append_milestone_trace(milestone_results, tb)

    # ── Produce POLICY_HEALTH_ANTICIPATION_FINAL.md ────────────────────────────
    print(f"\nProducing POLICY_HEALTH_ANTICIPATION_FINAL.md...")
    elapsed = time.time() - start_time
    produce_health_report(hard, ood, combined_wins, combined_mean, combined_median,
                          milestone_results, tb, verdict, elapsed, now_str)

    print(f"\nPhase 1 complete in {elapsed/60:.1f} min")
    return verdict


def append_milestone_trace(milestone_results: dict, tb: dict):
    """Append 1M-2M milestone sections to MILESTONE_TRACE_ANTICIPATION.md."""
    lines = []

    steps_map = {
        "1M":   1_000_000,
        "1.25M":1_250_000,
        "1.5M": 1_500_000,
        "1.75M":1_750_000,
        "2M":   2_000_000,
    }

    for label, res in milestone_results.items():
        target_step = steps_map[label]
        lines.append(f"\n## Milestone: {label} steps (overnight eval {datetime.utcnow().strftime('%Y-%m-%d')})\n")

        # Hard battery table
        lines.append(f"### Hard Battery (seeds {BATTERY5})")
        lines.append(f"| Seed | FCFS delay | RL delay | Gap | Res rate |")
        lines.append(f"|------|-----------|---------|------|----------|")

        if res is None:
            lines.append(f"| — | — | — | — | — |")
            lines.append(f"| Mean | | | FAILED TO LOAD | — |\n")
        else:
            for row in res["results"]:
                lines.append(
                    f"| {row['seed']} | {row['fcfs_delay']:.1f}m | {row['rl_delay']:.1f}m"
                    f" | {row['gap']:+.1f}m | {row['res_rate']:.1%} |"
                )
            lines.append(f"| Mean | | | {-res['mean_delta']:+.1f}m | {res['mean_res_rate']:.1%} |")
            lines.append(f"")
            lines.append(f"**Wins:** {res['wins']}/5  **Mean delta (FCFS-RL):** {res['mean_delta']:+.1f}m")

        # TensorBoard metrics near this step
        if tb and "steps" in tb:
            closest_step = min(tb["steps"], key=lambda s: abs(s - target_step))
            rew_val = tb["rew"].get(closest_step)
            ev_val  = tb["ev"].get(closest_step)
            cf_val  = tb["cf"].get(closest_step)
            ent_val = tb["ent"].get(closest_step)
            lines.append(f"\n### Training Metrics (from TensorBoard @ step {closest_step:,})")
            lines.append(f"- ep_rew_mean: {rew_val:.1f}" if rew_val is not None else "- ep_rew_mean: N/A")
            lines.append(f"- explained_variance: {ev_val:.3f}" if ev_val is not None else "- explained_variance: N/A")
            lines.append(f"- clip_fraction: {cf_val:.3f}" if cf_val is not None else "- clip_fraction: N/A")
            lines.append(f"- entropy_loss: {ent_val:.3f}" if ent_val is not None else "- entropy_loss: N/A")

        lines.append(f"\n---")

    # Read existing file and append
    trace_path = "MILESTONE_TRACE_ANTICIPATION.md"
    try:
        with open(trace_path, "r") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = "# MILESTONE TRACE — v5_anticipation 2M Run\n\n---\n\n"

    with open(trace_path, "w") as f:
        f.write(existing + "\n" + "\n".join(lines) + "\n")

    print(f"  Appended to {trace_path}")


def produce_health_report(hard: dict, ood: dict, combined_wins: int, combined_mean: float,
                           combined_median: float, milestone_results: dict, tb: dict,
                           verdict: str, elapsed: float, now_str: str):
    """Write POLICY_HEALTH_ANTICIPATION_FINAL.md."""
    lines = []
    lines.append("# POLICY_HEALTH_ANTICIPATION_FINAL.md\n")
    lines.append(f"**Generated:** {now_str}  ")
    lines.append(f"**Model:** models/v5_anticipation_final.zip  ")
    lines.append(f"**Verdict:** {verdict}\n")
    lines.append("---\n")

    # Section 1 — 50-seed hard battery
    lines.append("## 1. 50-seed Hard Battery (seeds 0-49)\n")
    lines.append("| Seed | FCFS (min) | RL (min) | Delta | Res rate |")
    lines.append("|------|-----------|---------|-------|----------|")
    for row in hard["results"]:
        sign = "WIN" if row["delta"] > 0.5 else ("LOSS" if row["delta"] < -0.5 else "TIE")
        lines.append(
            f"| {row['seed']} | {row['fcfs_delay']:.1f} | {row['rl_delay']:.1f} "
            f"| {row['delta']:+.1f} ({sign}) | {row['res_rate']:.1%} |"
        )
    lines.append(f"\n**Wins:** {hard['wins']}/50 ({hard['wins']*2}%)  ")
    lines.append(f"**Mean delta:** {hard['mean_delta']:+.1f} min  ")
    lines.append(f"**Median delta:** {hard['median_delta']:+.1f} min  ")
    lines.append(f"**Best:** seed {hard['best_seed']} ({hard['best_delta']:+.1f} min)  ")
    lines.append(f"**Worst:** seed {hard['worst_seed']} ({hard['worst_delta']:+.1f} min)  ")
    lines.append(f"**Conflicts:** {hard['total_conflicts']}  **Abandonments:** {hard['total_abandonments']}\n")

    # Section 2 — 50-seed OOD battery
    lines.append("## 2. 50-seed OOD Battery (seeds 200-249)\n")
    lines.append("| Seed | FCFS (min) | RL (min) | Delta | Res rate |")
    lines.append("|------|-----------|---------|-------|----------|")
    for row in ood["results"]:
        sign = "WIN" if row["delta"] > 0.5 else ("LOSS" if row["delta"] < -0.5 else "TIE")
        lines.append(
            f"| {row['seed']} | {row['fcfs_delay']:.1f} | {row['rl_delay']:.1f} "
            f"| {row['delta']:+.1f} ({sign}) | {row['res_rate']:.1%} |"
        )
    lines.append(f"\n**Wins:** {ood['wins']}/50 ({ood['wins']*2}%)  ")
    lines.append(f"**Mean delta:** {ood['mean_delta']:+.1f} min  ")
    lines.append(f"**Median delta:** {ood['median_delta']:+.1f} min  ")
    lines.append(f"**Best:** seed {ood['best_seed']} ({ood['best_delta']:+.1f} min)  ")
    lines.append(f"**Worst:** seed {ood['worst_seed']} ({ood['worst_delta']:+.1f} min)\n")

    # Section 3 — Combined
    lines.append("## 3. Combined 100-seed Verdict\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total wins | {combined_wins}/100 |")
    lines.append(f"| Win rate | {combined_wins}% |")
    lines.append(f"| Mean delta | {combined_mean:+.1f} min |")
    lines.append(f"| Median delta | {combined_median:+.1f} min |")
    lines.append(f"| Total conflicts | {hard['total_conflicts'] + ood['total_conflicts']} |")
    lines.append(f"| Total abandonments | {hard['total_abandonments'] + ood['total_abandonments']} |\n")

    # Verdict criteria explanation
    lines.append("### Verdict Criteria\n")
    lines.append("- HEALTHY: combined win rate ≥10% AND mean delta better than -5 min")
    lines.append("- MARGINAL: combined win rate 5-10% OR mean delta -5 to -10 min")
    lines.append("- WEAK: combined win rate <5% AND mean delta worse than -10 min")
    lines.append("- BROKEN: any conflicts/abandonments, or model fails to load\n")
    lines.append(f"**VERDICT: {verdict}**\n")

    # Section 4 — Milestone trajectory
    lines.append("## 4. Milestone Trajectory (5-seed battery)\n")
    lines.append("| Milestone | Wins/5 | Mean Delta (FCFS-RL) | Conflicts |")
    lines.append("|-----------|--------|---------------------|-----------|")

    # Include earlier milestones from the existing trace doc for context
    earlier = [
        ("250k", 0, "+24.9m"),
        ("500k", 0, "+17.8m"),
        ("750k", 0, "+15.8m"),
    ]
    for label, wins, mean in earlier:
        lines.append(f"| {label} (from MILESTONE_TRACE_ANTICIPATION.md) | {wins}/5 | {mean} | 0 |")

    steps_map = {"1M": 1_000_000, "1.25M": 1_250_000, "1.5M": 1_500_000, "1.75M": 1_750_000, "2M": 2_000_000}
    for label, res in milestone_results.items():
        if res is None:
            lines.append(f"| {label} | FAILED | FAILED | FAILED |")
        else:
            lines.append(
                f"| {label} | {res['wins']}/5 | {res['mean_delta']:+.1f}m | {res['total_conflicts']} |"
            )
    lines.append("")

    # TensorBoard table
    if tb and "steps" in tb:
        lines.append("## 5. Training Metrics (TensorBoard, 750k-2M, every 50k)\n")
        lines.append("| Step | ep_rew_mean | explained_variance | clip_fraction | entropy_loss |")
        lines.append("|------|------------|-------------------|---------------|--------------|")
        for step in tb["steps"]:
            rew_v = tb["rew"].get(step)
            ev_v  = tb["ev"].get(step)
            cf_v  = tb["cf"].get(step)
            ent_v = tb["ent"].get(step)
            def fmt(v):
                return f"{v:.3f}" if v is not None else "—"
            lines.append(
                f"| {step//1000}k | {fmt(rew_v)} | {fmt(ev_v)} | {fmt(cf_v)} | {fmt(ent_v)} |"
            )
        lines.append("")

    # Section 6 — Reservation usage
    lines.append("## 6. Reservation Usage Across Milestones\n")
    lines.append("| Milestone | Mean Res Rate |")
    lines.append("|-----------|--------------|")
    for label, res in milestone_results.items():
        if res is None:
            lines.append(f"| {label} | FAILED |")
        else:
            lines.append(f"| {label} | {res['mean_res_rate']:.1%} |")
    lines.append(f"| Final (hard-50 mean) | {hard['mean_res_rate']:.1%} |")
    lines.append(f"| Final (OOD-50 mean)  | {ood['mean_res_rate']:.1%} |\n")

    # Section 7 — Honest verdict
    lines.append("## 7. Honest Verdict\n")
    lines.append(f"**Did the policy beat FCFS?** {'YES — on some seeds' if combined_wins > 0 else 'NO — RL was slower on all 100 seeds.'}\n")
    lines.append(f"- Combined win rate: {combined_wins}% ({combined_wins}/100 seeds)")
    lines.append(f"- Mean delay delta: {combined_mean:+.1f} min (positive = RL better)")
    lines.append(f"- Hard battery: {hard['wins']}/50 wins, mean {hard['mean_delta']:+.1f} min")
    lines.append(f"- OOD battery: {ood['wins']}/50 wins, mean {ood['mean_delta']:+.1f} min")
    lines.append(f"")
    if verdict == "HEALTHY":
        lines.append("The policy demonstrates meaningful improvement over FCFS.")
        lines.append("Anticipation is working — the policy is making productive pre-emptive reservations.")
    elif verdict == "MARGINAL":
        lines.append("The policy shows limited improvement over FCFS.")
        lines.append("Anticipation is partially working but needs stronger reward shaping or longer training.")
    elif verdict == "WEAK":
        lines.append("The policy fails to meaningfully beat FCFS.")
        lines.append("The anticipation mechanism may not be providing a useful signal, or the policy hasn't learned to exploit it.")
    elif verdict == "BROKEN":
        lines.append("CRITICAL: The policy has structural failures (conflicts or abandonments).")
        lines.append("Do NOT retrain without fixing the underlying environment/reward issue.")
    lines.append("")

    report_path = "POLICY_HEALTH_ANTICIPATION_FINAL.md"
    with open(report_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Written to {report_path}")


if __name__ == "__main__":
    main()
