"""
eval_health.py — Full policy health diagnostic for POLICY_HEALTH.md.

Usage:
    python -m train.eval_health models/session5_fixed.zip
    python -m train.eval_health models/session5_fixed.zip --n-episodes 10 --seed 42

Outputs (to stdout + POLICY_HEALTH.md at repo root):
    - Total decisions, HOLD rate, action breakdown
    - Entropy distribution (all / HOLD-only / non-HOLD)
    - Services started vs completed (HARD PASS check)
    - Abandonment count (HARD PASS check)
    - Conflict termination rate across N episodes
    - Delay vs FCFS comparison (seed=42 deterministic)
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from datetime import datetime

import numpy as np
import torch
from sb3_contrib import MaskablePPO

from env.airport_env import AirportEnv
from train.callbacks import run_fcfs_episode


# ── Entropy helper ────────────────────────────────────────────────────────────

def _compute_masked_entropy(model: MaskablePPO, obs: np.ndarray, masks: np.ndarray) -> float:
    """
    Compute the entropy of the masked action distribution at a given observation.
    Returns the entropy in nats.
    """
    obs_t = torch.tensor(obs, dtype=torch.float32).unsqueeze(0)
    with torch.no_grad():
        features = model.policy.extract_features(obs_t, model.policy.features_extractor)
        latent_pi, _ = model.policy.mlp_extractor(features)
        logits = model.policy.action_net(latent_pi).squeeze(0)  # shape (n_actions,)

    mask_t = torch.tensor(masks, dtype=torch.bool)
    masked_logits = logits.clone()
    masked_logits[~mask_t] = float("-inf")

    # Softmax over valid actions
    log_probs = torch.nn.functional.log_softmax(masked_logits, dim=0)
    probs = torch.exp(log_probs)
    # Entropy: -sum(p * log p) over valid actions
    valid = mask_t
    entropy = -(probs[valid] * log_probs[valid]).sum().item()
    return float(entropy)


# ── Single episode runner ─────────────────────────────────────────────────────

def run_health_episode(model: MaskablePPO, seed: int = 42, render: bool = False) -> dict:
    """
    Run one deterministic episode and collect full diagnostics.
    Returns a dict with all health metrics.
    """
    env = AirportEnv(randomise=True, seed=seed)
    obs, _ = env.reset(seed=seed)

    hold_action = env.action_space.n - 1  # ACTION_HOLD = MAX_TASKS = 16

    decisions = 0
    hold_count = 0
    action_counts: Counter = Counter()
    entropies_hold: list[float] = []
    entropies_non_hold: list[float] = []

    done = False
    total_reward = 0.0

    while not done:
        masks = env.action_masks()
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)
        action = int(action)

        # Compute entropy BEFORE stepping (so we have the obs that led to this action)
        entropy = _compute_masked_entropy(model, obs, masks)

        decisions += 1
        action_counts[action] += 1
        if action == hold_action:
            hold_count += 1
            entropies_hold.append(entropy)
        else:
            entropies_non_hold.append(entropy)

        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        done = terminated or truncated

        if render:
            label = "HOLD" if action == hold_action else f"task[{action}]"
            print(
                f"  step {decisions:4d} | {label:<12s} | H={entropy:.3f} | "
                f"reward {reward:+7.2f} | pending={info['n_pending_tasks']}"
            )

    env.close()
    info["decisions"] = decisions
    info["hold_count"] = hold_count
    info["action_counts"] = dict(action_counts)
    info["entropies_hold"] = entropies_hold
    info["entropies_non_hold"] = entropies_non_hold
    info["total_reward"] = total_reward
    info["conflict_terminated"] = info.get("conflict_count", 0) > 0
    return info


# ── Entropy stats helper ──────────────────────────────────────────────────────

def _entropy_stats(values: list[float], label: str, n_buckets: int = 10) -> list[str]:
    if not values:
        return [f"  {label}: (no samples)"]

    arr = np.array(values)
    lines = [
        f"  {label} (n={len(arr)})",
        f"    min    = {arr.min():.4f} nats",
        f"    max    = {arr.max():.4f} nats",
        f"    mean   = {arr.mean():.4f} nats",
        f"    median = {np.median(arr):.4f} nats",
        f"    p10    = {np.percentile(arr, 10):.4f} nats",
        f"    p90    = {np.percentile(arr, 90):.4f} nats",
    ]
    # Histogram
    counts, bin_edges = np.histogram(arr, bins=n_buckets)
    lines.append(f"    histogram ({n_buckets} buckets):")
    for i, (lo, hi, ct) in enumerate(zip(bin_edges, bin_edges[1:], counts)):
        bar = "#" * min(40, ct)
        lines.append(f"      [{lo:.3f}, {hi:.3f}) | {bar} {ct}")
    return lines


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Policy health diagnostic")
    parser.add_argument("checkpoint", help="Path to .zip checkpoint")
    parser.add_argument("--n-episodes", type=int, default=10, help="Episodes to run (default 10)")
    parser.add_argument("--seed", type=int, default=42, help="Base seed (episodes use seed+i)")
    parser.add_argument("--render", action="store_true", help="Print per-step output for seed")
    parser.add_argument("--out", type=str, default="POLICY_HEALTH.md", help="Output file")
    args = parser.parse_args()

    print(f"Loading checkpoint: {args.checkpoint}")
    model = MaskablePPO.load(args.checkpoint)
    print(f"Model loaded. Running {args.n_episodes} eval episodes...")

    # Run episodes (seed, seed+1, ..., seed+n-1)
    episodes: list[dict] = []
    for i in range(args.n_episodes):
        ep_seed = args.seed + i
        render = args.render and i == 0
        ep = run_health_episode(model, seed=ep_seed, render=render)
        episodes.append(ep)
        print(
            f"  ep {i+1:2d} (seed={ep_seed}): "
            f"decisions={ep['decisions']} | hold_rate={ep['hold_count']/max(1,ep['decisions']):.1%} | "
            f"delay={ep['total_delay_minutes']:.1f}min | "
            f"conflict={'YES' if ep['conflict_terminated'] else 'no'} | "
            f"reward={ep['total_reward']:+.1f}"
        )

    # Aggregate
    all_decisions    = [ep["decisions"] for ep in episodes]
    all_hold_rates   = [ep["hold_count"] / max(1, ep["decisions"]) for ep in episodes]
    all_delays       = [ep["total_delay_minutes"] for ep in episodes]
    all_conflicts    = [ep["conflict_terminated"] for ep in episodes]
    all_ent_hold     = [e for ep in episodes for e in ep["entropies_hold"]]
    all_ent_non_hold = [e for ep in episodes for e in ep["entropies_non_hold"]]

    # Services hard-pass: sum across all episodes
    services_started   = sum(ep.get("services_started", 0) for ep in episodes)
    services_completed = sum(ep.get("services_completed", 0) for ep in episodes)
    total_abandonments = sum(ep.get("abandonment_count", 0) for ep in episodes)
    conflict_eps       = sum(all_conflicts)

    # FCFS baseline (seed only)
    print("\nRunning FCFS baseline (seed=42)...")
    fcfs = run_fcfs_episode(args.seed)
    delay_improvement = fcfs["total_delay_minutes"] - episodes[0]["total_delay_minutes"]
    fcfs_pct = (delay_improvement / max(1, fcfs["total_delay_minutes"])) * 100

    # ── Health gate checks ────────────────────────────────────────────────────
    avg_decisions = np.mean(all_decisions)
    avg_hold_rate = np.mean(all_hold_rates)

    checks = {
        "decisions_in_range":     30 <= avg_decisions <= 400,
        "hold_rate_acceptable":   avg_hold_rate <= 0.80,
        "hold_rate_target":       0.20 <= avg_hold_rate <= 0.50,
        "services_hard_pass":     services_started == services_completed,
        "abandonment_hard_pass":  total_abandonments == 0,
        "zero_conflicts":         conflict_eps == 0,
        "beats_fcfs_20pct":       fcfs_pct >= 20.0,
    }

    # ── Build report ──────────────────────────────────────────────────────────
    lines: list[str] = []
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines += [
        f"# POLICY_HEALTH.md",
        f"",
        f"Generated: {now}  ",
        f"Checkpoint: `{args.checkpoint}`  ",
        f"Episodes: {args.n_episodes} (seeds {args.seed}–{args.seed + args.n_episodes - 1})",
        f"",
        f"---",
        f"",
        f"## 1. Gate Checks (HARD PASS required)",
        f"",
        f"| Check | Target | Result | Status |",
        f"|-------|--------|--------|--------|",
        f"| Decisions / episode | 30–400 | {avg_decisions:.1f} | {'✅' if checks['decisions_in_range'] else '❌'} |",
        f"| HOLD rate | ≤ 80% | {avg_hold_rate:.1%} | {'✅' if checks['hold_rate_acceptable'] else '❌ FAIL'} |",
        f"| Services started = completed | exact match | {services_started}={services_completed} | {'✅' if checks['services_hard_pass'] else '❌ HARD FAIL'} |",
        f"| Abandonment count | 0 | {total_abandonments} | {'✅' if checks['abandonment_hard_pass'] else '❌ HARD FAIL'} |",
        f"| Conflict episodes | 0 | {conflict_eps}/{args.n_episodes} | {'✅' if checks['zero_conflicts'] else '⚠️ WARNING'} |",
        f"| Delay improvement vs FCFS | ≥ 20% | {fcfs_pct:+.1f}% | {'✅' if checks['beats_fcfs_20pct'] else '⚠️ NOT YET'} |",
        f"",
        f"**HARD PASS status:** {'PASS ✅' if (checks['services_hard_pass'] and checks['abandonment_hard_pass'] and checks['hold_rate_acceptable']) else 'FAIL ❌'}",
        f"",
        f"---",
        f"",
        f"## 2. Decision Statistics ({args.n_episodes} episodes)",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Mean decisions / episode | {avg_decisions:.1f} |",
        f"| Min decisions | {min(all_decisions)} |",
        f"| Max decisions | {max(all_decisions)} |",
        f"| Mean HOLD rate | {avg_hold_rate:.1%} |",
        f"| Min HOLD rate | {min(all_hold_rates):.1%} |",
        f"| Max HOLD rate | {max(all_hold_rates):.1%} |",
        f"",
    ]

    # Action breakdown for ep 0 (seed=42)
    ep0 = episodes[0]
    hold_action = 16
    lines += [
        f"### Action Breakdown (seed={args.seed})",
        f"",
        f"| Action | Count | % |",
        f"|--------|-------|---|",
    ]
    total_acts = ep0["decisions"]
    for act, cnt in sorted(ep0["action_counts"].items()):
        label = "HOLD" if act == hold_action else f"task[{act}]"
        lines.append(f"| {label} | {cnt} | {cnt/max(1,total_acts):.1%} |")
    lines.append("")

    # ── Entropy ───────────────────────────────────────────────────────────────
    lines += [
        f"---",
        f"",
        f"## 3. Entropy Distribution (all {args.n_episodes} episodes pooled)",
        f"",
        f"*(Entropy in nats; higher = more uniform / uncertain policy)*",
        f"",
        "```",
    ]
    lines += _entropy_stats(all_ent_hold, "HOLD decisions")
    lines += [""]
    lines += _entropy_stats(all_ent_non_hold, "Non-HOLD decisions")
    lines += ["```", ""]

    # ── Delay ────────────────────────────────────────────────────────────────
    lines += [
        f"---",
        f"",
        f"## 4. Delay vs FCFS Baseline (seed={args.seed})",
        f"",
        f"| Agent | Total delay (min) | Avg delay (min) | Missed departures |",
        f"|-------|-------------------|-----------------|-------------------|",
        f"| RL (this policy) | {ep0['total_delay_minutes']:.1f} | {ep0['avg_delay_minutes']:.1f} | {ep0['flights_pending']} |",
        f"| FCFS baseline    | {fcfs['total_delay_minutes']:.1f} | {fcfs['avg_delay_minutes']:.1f} | {fcfs['flights_pending']} |",
        f"| **Delta** (RL − FCFS) | **{ep0['total_delay_minutes'] - fcfs['total_delay_minutes']:+.1f}** | — | — |",
        f"",
        f"Improvement over FCFS: **{fcfs_pct:+.1f}%**  ",
        f"Target: ≥ 20% → {'MET ✅' if checks['beats_fcfs_20pct'] else 'NOT YET ⚠️'}",
        f"",
    ]

    # ── Per-episode table ─────────────────────────────────────────────────────
    lines += [
        f"---",
        f"",
        f"## 5. Per-Episode Summary",
        f"",
        f"| Seed | Decisions | HOLD% | Delay(min) | Reward | Conflict |",
        f"|------|-----------|-------|------------|--------|----------|",
    ]
    for i, ep in enumerate(episodes):
        seed_i = args.seed + i
        hr = ep["hold_count"] / max(1, ep["decisions"])
        lines.append(
            f"| {seed_i} | {ep['decisions']} | {hr:.1%} | "
            f"{ep['total_delay_minutes']:.1f} | {ep['total_reward']:+.1f} | "
            f"{'YES ❌' if ep['conflict_terminated'] else 'no ✅'} |"
        )
    lines.append("")

    # ── Write ─────────────────────────────────────────────────────────────────
    report = "\n".join(lines)
    with open(args.out, "w") as f:
        f.write(report)
    print(f"\nReport written to {args.out}")

    # Summary to stdout
    print("\n── Health Summary ────────────────────────────────────────────────")
    print(f"  Avg decisions/ep:  {avg_decisions:.1f}")
    print(f"  Avg HOLD rate:     {avg_hold_rate:.1%}")
    print(f"  Services pass:     {'✅' if checks['services_hard_pass'] else '❌'}")
    print(f"  Abandonment pass:  {'✅' if checks['abandonment_hard_pass'] else '❌'}")
    print(f"  Conflict eps:      {conflict_eps}/{args.n_episodes}")
    print(f"  Delay vs FCFS:     {fcfs_pct:+.1f}%")
    overall = all(checks[k] for k in ["hold_rate_acceptable", "services_hard_pass", "abandonment_hard_pass"])
    print(f"\n  HARD PASS: {'✅ PASS' if overall else '❌ FAIL'}")
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
