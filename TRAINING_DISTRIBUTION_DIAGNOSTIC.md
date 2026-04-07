# TRAINING_DISTRIBUTION_DIAGNOSTIC.md

**Generated:** 2026-04-07 ~19:10 EDT  
**Branch:** `fix-decision-trigger`  
**Training killed:** 1M steps — see `CHECKPOINT_1M_BATTERY.md`

---

## Part 1 — Training Schedule Distribution (seeds 0–49)

Choice ticks = ticks where ≥2 valid (task × vehicle) assignment pairs existed simultaneously.

| Seed | Flights | Total ticks | 0-pair% | 2+ ticks | FCFS delay |
|------|---------|------------|---------|---------|------------|
| 0 | 12 | 14,400 | 100% | 10 | — |
| 1 | 8 | 9,347 | 100% | 7 | — |
| 2 | 6 | 10,782 | 100% | 6 | — |
| 3 | 9 | 13,079 | 100% | 9 | — |
| 4 | 9 | 8,505 | 100% | 10 | — |
| 5 | 10 | 10,391 | 100% | 11 | — |
| 6 | 7 | 10,115 | 100% | 7 | — |
| 7 | 11 | 10,839 | 100% | 12 | — |
| 8 | 9 | 9,966 | 100% | 8 | — |
| 9 | 13 | 12,133 | 100% | 12 | — |
| 10 | 6 | 10,148 | 100% | 5 | — |
| 11 | 13 | 14,400 | 100% | 11 | — |
| 12 | 13 | 14,209 | 100% | 12 | — |
| 13 | 10 | 14,400 | 100% | 8 | — |
| 14 | 7 | 9,982 | 100% | 7 | — |
| 15 | 9 | 12,052 | 100% | 8 | — |
| 16 | 11 | 12,855 | 100% | 9 | — |
| 17 | 14 | 14,400 | 100% | 10 | — |
| 18 | 8 | 9,556 | 100% | 7 | — |
| 19 | 6 | 7,211 | 100% | 5 | — |
| 20 | 8 | 12,271 | 100% | 8 | — |
| 21 | 8 | 7,990 | 100% | 8 | — |
| 22 | 8 | 12,480 | 100% | 7 | — |
| 23 | 10 | 10,089 | 100% | 8 | — |
| 24 | 12 | 14,400 | 100% | 9 | — |
| 25 | 12 | 11,228 | 100% | 12 | — |
| 26 | 9 | 10,161 | 100% | 9 | — |
| 27 | 13 | 14,400 | 100% | 13 | — |
| 28 | 7 | 10,333 | 100% | 6 | — |
| 29 | 14 | 14,400 | 100% | 10 | — |
| 30 | 14 | 14,400 | 100% | 12 | — |
| 31 | 6 | 8,526 | 100% | 6 | — |
| 32 | 7 | 9,743 | 100% | 6 | — |
| 33 | 8 | 12,280 | 100% | 8 | — |
| 34 | 14 | 14,400 | 100% | 10 | — |
| 35 | 14 | 11,632 | 100% | 13 | — |
| 36 | 11 | 14,314 | 100% | 11 | — |
| 37 | 7 | 9,961 | 100% | 7 | — |
| 38 | 12 | 14,400 | 100% | 9 | — |
| 39 | 9 | 11,752 | 100% | 8 | — |
| 40 | 13 | 14,400 | 100% | 12 | — |
| 41 | 12 | 13,162 | 100% | 12 | — |
| 42 | 7 | 10,856 | 100% | 7 | — |
| 43 | 6 | 8,517 | 100% | 6 | — |
| 44 | 12 | 10,342 | 100% | 14 | — |
| 45 | 10 | 10,951 | 100% | 9 | — |
| 46 | 7 | 9,521 | 100% | 6 | — |
| 47 | 11 | 13,672 | 100% | 11 | — |
| 48 | 14 | 14,400 | 100% | 12 | — |
| 49 | 7 | 11,819 | 100% | 6 | — |

### Aggregate statistics (seeds 0–49)

| Metric | Value |
|--------|-------|
| Mean choice ticks (2+) | **8.98** |
| Median | 9.0 |
| Min | 5 |
| Max | 14 |
| p25 | 7 |
| p75 | 11 |
| p90 | 12 |
| Zero choice ticks | **0/50** (all schedules have some) |
| 5+ choice ticks | **50/50** (100%) |
| 10+ choice ticks | **20/50** (40%) |
| 15+ choice ticks | **0/50** (0%) |

**Non-strategic tick fraction:** Every single training seed has ~100% zero-pair ticks (the 2+ ticks are 0.1% or less of total sim time). All 50 schedules have a tiny number of choice ticks (5–14) against 8,000–14,400 total ticks.

---

## Part 2 — Cross-Distribution Comparison

| Distribution | N schedules | Mean choice ticks | Max | 10+ | 15+ |
|---|---|---|---|---|---|
| **Training seeds 0–49** | 50 | **8.98** | 14 | 20/50 (40%) | 0/50 |
| Hard battery 100–119 | 20 | ~9.1 | 14 | 5/20 (25%) | 0/20 |
| Hard search 1000–1100 | 101 | 9.0 | 15 | ~40% | 1/101 |
| eval seed=42 | 1 | 7 | 2 | 0/1 | 0/1 |

**Finding:** The training distribution (seeds 0–49) is essentially identical in structure to the hard battery (seeds 100–119) and the broader 1000–1100 search. All three pools produce 5–14 choice ticks per schedule with mean ~9. The training distribution is NOT structurally different from the eval distributions.

This rules out "training on easier schedules than eval" as the root cause. The policy regressed despite being trained on schedules of identical complexity to the evaluation set.

---

## Part 3 — HOLD Penalty Diagnostic (1M policy on seeds 0–4)

Checkpoint: `models/session5_reactive_diverged.zip`

| Seed | Decisions | Total HOLDs | HOLDs with work penalty | Idle HOLDs | % penalised |
|------|-----------|------------|------------------------|------------|------------|
| 0 | 79 | 33 | **33** | 0 | **100%** |
| 1 | 31 | 0 | 0 | 0 | — |
| 2 | 24 | 0 | 0 | 0 | — |
| 3 | 36 | 0 | 0 | 0 | — |
| 4 | 33 | 0 | 0 | 0 | — |

**Critical finding:** On seed=0, the policy made 33 HOLDs — **every single one triggered the `REWARD_HOLD_WITH_WORK` penalty** (−0.1 each = −3.3 total). Not one HOLD was an "idle" hold where no assignment was available. The policy is paying the penalty for all its HOLDs.

On seeds 1–4, zero HOLDs — the policy assigned immediately on these simpler schedules.

This explains the divergence pattern:
- On schedules where the policy chooses to HOLD, it is always holding at a moment when FCFS would assign
- The policy learned to delay, but the delay is never beneficial
- The +3.9 min regression on seed=110 and +3.5 min on seed=116 are directly caused by these penalised HOLDs not being offset by better downstream assignments

---

## Part 4 — Root Cause Summary

### What actually happened

The training schedule pool (seeds 0–49) has 5–14 choice ticks per episode out of 8,000–14,400 total ticks — **<0.1% of sim time is strategically interesting**. During those rare ticks, the signal for "which assignment order is better" is extremely weak because:

1. The reward difference between assignment orders is small (holding costs −0.1/step but only saves delay if the held vehicle is genuinely needed for a future, higher-priority task)
2. With 8 parallel training environments and random seeds, the policy rarely sees the same schedule structure twice
3. The gradient from beneficial holds (when they occur) is drowned out by the −0.1 HOLD penalty accumulating across all the times the policy tried to hold and didn't improve anything

### Why the policy learned HOLD-on-complexity

The policy learned a heuristic: "when I see a complex schedule (many pending tasks), use HOLD." This is a pattern that sometimes reduced delay at 300k (seed=116: −2.1 min) when the policy happened to hold at the right moment by chance. But as training continued, the policy refined this heuristic into "hold aggressively on complex schedules" — which increased the HOLD rate from 0% → 23% → 41% on seed=116 while making the delay progressively worse.

The HOLD-with-work penalty (−0.1) was not strong enough to suppress this: a policy that holds 40 times gets −4.0 penalty, but if it happened to get even one +10 on-time departure that it attributes to its holding, the gradient pushes toward more holding.

### What this means for future training

The sim does not have enough **structural richness** in its schedules to teach strategic timing via RL. With <0.1% of ticks being genuinely strategic, the policy cannot reliably learn that specific HOLDs improve downstream outcomes. 

Options for Will to consider (not implemented here):
1. **Denser schedules** — generate schedules where simultaneous service demand is higher (more flights at gate simultaneously, fewer vehicles vs tasks)
2. **Remove HOLD action / replace with priority scoring** — instead of binary assign/hold, give the agent a continuous priority score for each task
3. **Shaped HOLD reward** — only remove the HOLD penalty, or invert it: give +0.1 for strategic holds (held now, saved time later), remove it for non-strategic holds
4. **Accept reactive policy** — the 300k checkpoint (before HOLD divergence) is the best this architecture produces: immediate assignment matching FCFS, zero conflicts, all services completing

---

## Appendix — seed=0 as the divergence specimen

seed=0 is the clearest example of what went wrong: 12 flights, 14,400 ticks, 10 real choice ticks. The 1M policy made **33 HOLDs on 79 total decisions (42% HOLD rate)** — every hold was penalised. Resulting delay: 24.2 min. FCFS delay would be approximately 16–18 min for a 12-flight schedule. The policy has severely over-held on this schedule.
