"""
milestone_diagnostic.py — Comprehensive milestone diagnostic for MILESTONE_TRACE.md.

Usage:
    python3 -m train.milestone_diagnostic <checkpoint> <step_label>

Appends a full diagnostic section to MILESTONE_TRACE.md.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime

import numpy as np
import torch
from sb3_contrib import MaskablePPO

from env.airport_env import AirportEnv, ACTION_HOLD
from train.callbacks import run_fcfs_episode, run_policy_episode


HARD_SEEDS = [6, 10, 19, 40, 42]
OOD_SEEDS = list(range(200, 220))
TRACE_SEED = 19  # strategy emergence tracking


def compute_masked_entropy(model, obs, masks):
    obs_t = torch.tensor(obs, dtype=torch.float32).unsqueeze(0)
    with torch.no_grad():
        features = model.policy.extract_features(obs_t, model.policy.features_extractor)
        latent_pi, _ = model.policy.mlp_extractor(features)
        logits = model.policy.action_net(latent_pi).squeeze(0)
    mask_t = torch.tensor(masks, dtype=torch.bool)
    masked_logits = logits.clone()
    masked_logits[~mask_t] = float("-inf")
    log_probs = torch.nn.functional.log_softmax(masked_logits, dim=0)
    probs = torch.exp(log_probs)
    valid = mask_t
    entropy = -(probs[valid] * log_probs[valid]).sum().item()
    return float(entropy)


def run_detailed_episode(model, seed):
    """Run episode capturing divergence data, entropy, and health metrics."""
    env = AirportEnv(randomise=True, seed=seed, density="tight")
    obs, info = env.reset(seed=seed)

    decisions = []
    hold_count = 0
    entropies = []
    done = False
    step = 0

    while not done:
        masks = env.action_masks()
        legal = [i for i in range(len(masks)) if masks[i]]
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)
        action = int(action)

        entropy = compute_masked_entropy(model, obs, masks)
        entropies.append(entropy)

        pending = env.dispatcher.pending_tasks
        if action < len(pending):
            task = pending[action]
            action_desc = f"{task.service_type}:{task.flight_id}"
        else:
            action_desc = "HOLD"
            hold_count += 1

        fcfs_action = None
        for i in range(len(masks) - 1):
            if masks[i]:
                fcfs_action = i
                break
        if fcfs_action is not None and fcfs_action < len(pending):
            fcfs_desc = f"{pending[fcfs_action].service_type}:{pending[fcfs_action].flight_id}"
        else:
            fcfs_desc = "HOLD"

        diverged = (action != fcfs_action) if fcfs_action is not None else False

        decisions.append({
            "step": step,
            "sim_time": env._sim_time,
            "action": action,
            "action_desc": action_desc,
            "fcfs_action": fcfs_action,
            "fcfs_desc": fcfs_desc,
            "diverged": diverged,
            "legal_count": sum(masks),
            "entropy": entropy,
        })

        obs, reward, terminated, truncated, info = env.step(action)
        step += 1
        done = terminated or truncated

    env.close()

    ent_arr = np.array(entropies)
    return {
        "decisions": decisions,
        "total_decisions": len(decisions),
        "hold_count": hold_count,
        "hold_rate": hold_count / max(1, len(decisions)),
        "mean_entropy": float(ent_arr.mean()) if len(ent_arr) else 0.0,
        "info": info,
        "divergence_count": sum(1 for d in decisions if d["diverged"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", help="Path to .zip checkpoint")
    parser.add_argument("step_label", help="e.g. '250k', '500k', '2M'")
    args = parser.parse_args()

    print(f"Loading {args.checkpoint}...")
    model = MaskablePPO.load(args.checkpoint)

    lines = []
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines.append(f"## Milestone: {args.step_label}")
    lines.append(f"")
    lines.append(f"**Checkpoint:** `{args.checkpoint}`  ")
    lines.append(f"**Time:** {now}")
    lines.append(f"")

    # ── (a) HARD BATTERY ─────────────────────────────────────────────────────
    lines.append(f"### (a) Hard Battery (seeds {HARD_SEEDS})")
    lines.append(f"")
    lines.append(f"| Seed | FCFS (min) | RL (min) | Gap (min) | Divergence % |")
    lines.append(f"|------|-----------|---------|----------|-------------|")

    hard_deltas = []
    hard_wins = 0
    for seed in HARD_SEEDS:
        fcfs = run_fcfs_episode(seed)
        ep = run_detailed_episode(model, seed)
        fcfs_d = fcfs["total_delay_minutes"]
        rl_d = ep["info"]["total_delay_minutes"]
        gap = rl_d - fcfs_d
        hard_deltas.append(-gap)  # positive = RL better
        if gap < 0:
            hard_wins += 1
        div_pct = ep["divergence_count"] / max(1, ep["total_decisions"]) * 100
        lines.append(f"| {seed} | {fcfs_d:.1f} | {rl_d:.1f} | {gap:+.1f} | {div_pct:.0f}% |")

    mean_hard = np.mean(hard_deltas)
    lines.append(f"")
    lines.append(f"**Mean delta (FCFS−RL):** {mean_hard:+.1f} min | **Wins:** {hard_wins}/5")
    lines.append(f"")

    # ── (b) OOD BATTERY ──────────────────────────────────────────────────────
    lines.append(f"### (b) OOD Battery (seeds 200-219)")
    lines.append(f"")

    ood_deltas = []
    ood_wins = 0
    ood_losses = 0
    ood_ties = 0
    best_seed, best_gap = None, -999
    worst_seed, worst_gap = None, 999

    for seed in OOD_SEEDS:
        fcfs = run_fcfs_episode(seed)
        rl = run_policy_episode(model, seed)
        fcfs_d = fcfs["total_delay_minutes"]
        rl_d = rl["total_delay_minutes"]
        delta = fcfs_d - rl_d  # positive = RL better
        ood_deltas.append(delta)
        if delta > 0.5:
            ood_wins += 1
        elif delta < -0.5:
            ood_losses += 1
        else:
            ood_ties += 1
        if delta > best_gap:
            best_gap = delta
            best_seed = seed
        if delta < worst_gap:
            worst_gap = delta
            worst_seed = seed

    ood_mean = np.mean(ood_deltas)
    lines.append(f"**Mean delta:** {ood_mean:+.1f} min | **W/L/T:** {ood_wins}/{ood_losses}/{ood_ties}")
    lines.append(f"**Best:** seed {best_seed} ({best_gap:+.1f} min) | **Worst:** seed {worst_seed} ({worst_gap:+.1f} min)")
    lines.append(f"")

    # ── (c) STRATEGY EMERGENCE — seed 19 ─────────────────────────────────────
    lines.append(f"### (c) Strategy Emergence (seed {TRACE_SEED})")
    lines.append(f"")

    trace = run_detailed_episode(model, TRACE_SEED)
    divergences = [d for d in trace["decisions"] if d["diverged"]]

    lines.append(f"Total decisions: {trace['total_decisions']} | Divergences from FCFS: {trace['divergence_count']} ({trace['divergence_count']/max(1,trace['total_decisions'])*100:.0f}%)")
    lines.append(f"")

    if divergences:
        lines.append(f"First 5 divergence points:")
        lines.append(f"")
        lines.append(f"| # | Time | Legal | RL chose | FCFS would |")
        lines.append(f"|---|------|-------|----------|------------|")
        for i, d in enumerate(divergences[:5]):
            lines.append(f"| {i+1} | {d['sim_time']:.0f}s | {d['legal_count']} | {d['action_desc']} | {d['fcfs_desc']} |")
        lines.append(f"")

    # ── (d) POLICY HEALTH ─────────────────────────────────────────────────────
    lines.append(f"### (d) Policy Health")
    lines.append(f"")

    # Run 5 episodes for health stats
    health_episodes = []
    for s in [6, 10, 19, 40, 42]:
        ep = run_detailed_episode(model, s)
        health_episodes.append(ep)

    avg_hold = np.mean([ep["hold_rate"] for ep in health_episodes])
    avg_entropy = np.mean([ep["mean_entropy"] for ep in health_episodes])
    avg_decisions = np.mean([ep["total_decisions"] for ep in health_episodes])
    total_conflicts = sum(ep["info"].get("conflict_count", 0) for ep in health_episodes)
    total_abandonments = sum(ep["info"].get("abandonment_count", 0) for ep in health_episodes)

    # Max entropy for normalization (log of typical legal actions ~2-3)
    max_ent = np.log(4)  # ~1.386 for 4 legal actions
    confidence = max(0, 1 - avg_entropy / max_ent)

    lines.append(f"| Metric | Value | Status |")
    lines.append(f"|--------|-------|--------|")
    lines.append(f"| HOLD rate | {avg_hold:.1%} | {'STOP' if avg_hold > 0.01 else 'OK'} |")
    lines.append(f"| Mean entropy | {avg_entropy:.3f} nats | — |")
    lines.append(f"| Mean confidence | {confidence:.1%} | — |")
    lines.append(f"| Avg decisions/ep | {avg_decisions:.0f} | — |")
    lines.append(f"| Conflicts | {total_conflicts} | {'STOP' if total_conflicts > 0 else 'OK'} |")
    lines.append(f"| Abandonments | {total_abandonments} | {'STOP' if total_abandonments > 0 else 'OK'} |")
    lines.append(f"")

    # Check structural stops
    stop = False
    if avg_hold > 0.01:
        lines.append(f"**STRUCTURAL STOP: HOLD rate {avg_hold:.1%} > 1%**")
        stop = True
    if total_conflicts > 0:
        lines.append(f"**STRUCTURAL STOP: {total_conflicts} conflicts detected**")
        stop = True
    if total_abandonments > 0:
        lines.append(f"**STRUCTURAL STOP: {total_abandonments} abandonments detected**")
        stop = True

    # ── (e) Training Metrics placeholder ──────────────────────────────────────
    lines.append(f"### (e) Training Metrics")
    lines.append(f"")
    lines.append(f"*(Captured from training log at checkpoint time)*")
    lines.append(f"")

    # ── Interpretation ────────────────────────────────────────────────────────
    # Determine trend
    if hard_wins >= 2 or ood_wins >= 5:
        interp = "Improving"
    elif hard_wins >= 1 or ood_wins >= 1:
        interp = "Emerging"
    elif mean_hard > -15:
        interp = "Approaching"
    elif mean_hard > -25:
        interp = "Stable"
    else:
        interp = "Stuck"

    lines.append(f"**Interpretation: {interp}**")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # ── Append to MILESTONE_TRACE.md ──────────────────────────────────────────
    section = "\n".join(lines)

    trace_path = "MILESTONE_TRACE.md"
    try:
        with open(trace_path, "r") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = "# MILESTONE_TRACE.md\n\nAccumulated milestone diagnostics for v5 2M retrain (fixed seeding).\n\n---\n\n"

    with open(trace_path, "w") as f:
        f.write(existing + section)

    print(f"\nAppended {args.step_label} milestone to {trace_path}")
    print(f"Hard battery: {hard_wins}/5 wins, mean {mean_hard:+.1f} min")
    print(f"OOD battery: {ood_wins}/20 wins, mean {ood_mean:+.1f} min")
    print(f"HOLD rate: {avg_hold:.1%} | Conflicts: {total_conflicts} | Abandonments: {total_abandonments}")
    print(f"Interpretation: {interp}")

    if stop:
        print("\n** STRUCTURAL STOP TRIGGERED **")
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
