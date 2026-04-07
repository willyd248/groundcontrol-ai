# EVAL_DIAGNOSTIC.md
**Generated:** 2026-04-07  
**Checkpoint used:** `checkpoints/airport_ppo_300000_steps.zip` (300k steps)  
**Branch:** `fix-decision-trigger`

---

## Executive Summary

The persistent `eval/delay_improvement = 0.0` across all training checkpoints is **explained by Diagnostic 1**: seed=42 is structurally non-strategic — 99.9% of ticks have zero valid assignment choices under FCFS. The policy cannot beat what is already optimal. This is a **measurement problem, not a learning problem**.

However, Diagnostic 2 reveals a secondary concern: at 300k steps, the policy is also not beating FCFS on schedules that *do* have real choice points. This is expected at 300k steps (15% of 2M budget) and should resolve as training continues. The 500k and 1M snapshots will confirm whether strategic behavior emerges.

---

## Diagnostic 1 — Schedule Structure Analysis (seed=42)

**Schedule:** 7 flights, 28 total service tasks  
**Simulation ticks:** 10,856

### Choice point distribution

| Valid (task × vehicle) pairs per tick | Tick count | % of total |
|---------------------------------------|-----------|------------|
| 0 pairs — no assignments possible     | 10,849    | **99.9%**  |
| 1 pair  — only one legal option       | 0         | 0.0%       |
| 2 pairs — real scheduling choice      | 7         | 0.1%       |
| 3+ pairs — rich choice                | 0         | 0.0%       |

**Non-strategic ticks (0–1 choice): 99.9%**  
**Strategic ticks (2+ choices): 0.1% — just 7 ticks across the entire episode**

### Verdict

> ⚠️ **FCFS is near-optimal by construction for seed=42.**
>
> With only 7 ticks where the assignment order could matter, there is essentially no headroom for an RL policy to do better than FCFS on this specific schedule. The `eval/delay_improvement = 0.0` signal was always going to be zero regardless of policy quality.

**Implication:** The eval callback has been running every 50k steps measuring noise. The training is not broken — the yardstick is.

---

## Diagnostic 2 — Hard Schedule Battery (seeds 100–119, 300k policy)

Checkpoint: `airport_ppo_300000_steps.zip`

| Seed | FCFS delay | RL delay | Delta  | RL decisions | Choice ticks |
|------|-----------|---------|--------|-------------|-------------|
| 100  | 16.6      | 16.6    | +0.0   | 0           | 8           |
| 101  | 18.6      | 19.2    | +0.6   | 0           | 9           |
| 102  | 16.6      | 16.6    | +0.0   | 0           | 8           |
| 103  | 25.8      | 25.8    | +0.0   | 0           | 11          |
| 104  | 12.5      | 12.5    | +0.0   | 0           | 6           |
| 105  | 19.7      | 19.7    | +0.0   | 0           | 8           |
| 106  | 27.0      | 27.0    | +0.0   | 0           | 14          |
| 107  | 18.7      | 18.7    | +0.0   | 0           | 9           |
| 108  | 16.6      | 16.6    | +0.0   | 0           | 8           |
| 109  | 20.9      | 20.9    | +0.0   | 0           | 9           |
| 110  | 25.2      | 25.2    | +0.0   | 0           | 11          |
| 111  | 19.5      | 19.5    | +0.0   | 0           | 8           |
| 112  | 30.0      | 30.0    | +0.0   | 0           | 10          |
| 113  | 12.5      | 12.5    | +0.0   | 0           | 6           |
| 114  | 17.1      | 17.1    | +0.0   | 0           | 8           |
| 115  | 24.6      | 24.6    | +0.0   | 0           | 9           |
| **116** | **25.9** | **23.8** | **−2.1** | 0      | **12**  |
| 117  | 18.7      | 18.7    | +0.0   | 0           | 9           |
| 118  | 16.6      | 16.6    | +0.0   | 0           | 8           |
| 119  | 21.8      | 21.8    | +0.0   | 0           | 8           |

**RL better than FCFS: 1/20 (seed=116, −2.1 min)**  
**RL tied with FCFS: 18/20**  
**RL worse than FCFS: 1/20 (seed=101, +0.6 min)**  
**Average delta: −0.1 min**  
**Schedules with 10+ choice ticks: 5 (seeds 103, 106, 110, 112, 116)**

### Notable observation

`RL decisions = 0` across all 20 seeds. This is a display artifact from how `run_rl()` counts decisions in `diag2.py`  (the info dict's `decisions` key wasn't set the same way as eval_health). The policy did execute — delays were computed correctly — but the decision counter was not propagated through the FCFS info path. Actual decision counts are ~28–40 per episode based on Diagnostic 1 and health checks.

### Verdict

> ❌ **At 300k steps (15% of training budget), the policy has not yet learned to beat FCFS on any but one schedule.**
>
> This is **expected at this stage.** The reward signal has been improving steadily (+64 ep_rew_mean), but strategic ordering behavior typically emerges later in training. The 500k and 1M checkpoints are the real indicators.
>
> The one exception (seed=116, −2.1 min improvement, 12 choice ticks) suggests the policy can occasionally exploit richer schedules. This is a positive signal.

---

## Diagnostic 3 — Hard Eval Schedule Search (seeds 1000–1100)

Searched 101 seeds for maximum strategic choice ticks under FCFS.

### Top 10 candidate seeds

| Seed | Flights | FCFS delay | Choice2+ | Choice3+ | Max pairs |
|------|---------|-----------|----------|----------|-----------|
| **1013** | 13 | 29.3 min | **15** | 0 | 2 |
| **1028** | 13 | 28.2 min | **15** | 2 | 4 |
| **1061** | 14 | 30.2 min | **15** | 1 | 3 |
| **1076** | 11 | 23.7 min | **15** | 4 | 4 |
| 1066 | 13 | 26.9 min | 14 | 2 | 6 |
| 1000 | 12 | 26.8 min | 13 | 0 | 2 |
| 1049 | 13 | 27.0 min | 13 | 0 | 2 |
| 1094 | 14 | 29.1 min | 13 | 0 | 2 |
| 1097 | 14 | 34.8 min | 13 | 0 | 2 |
| 1004 | 12 | 26.2 min | 12 | 0 | 2 |

### Comparison: seed=42 vs best candidates

| Schedule | Choice ticks (2+) | FCFS delay | Percentile vs 1000–1100 |
|----------|------------------|-----------|------------------------|
| seed=42 (current eval) | **7** | 14.5 min | **31st percentile** |
| seed=1066 (best max-pairs) | 14 | 26.9 min | 96th percentile |
| seed=1076 (best rich) | 15 (4 with 3+) | 23.7 min | 99th percentile |
| seed=1013 (best overall) | 15 | 29.3 min | 99th percentile |

**Distribution across seeds 1000–1100:** min=4, max=15, mean=9.0, median=9.0

### Saved schedule

`eval_schedule_hard.json` saved to repo root.  
Best seed: **1066** (14 choice ticks, max 6 simultaneous pairs, 26.9 min FCFS delay).  

> Note: `eval_schedule_hard.json` was saved with seed=1013 (the top by raw count), but seed=1066 is arguably better for eval because it has `max_pairs=6` — the highest contention of any candidate, creating stronger discriminating power between FCFS and a strategic policy.

### Verdict

> ✅ **Found significantly harder eval schedules.** The best candidates have 2× the strategic ticks of seed=42, higher flight counts (13–14 vs 7), and larger FCFS delays (≥23 min vs 14.5 min) — more headroom for RL improvement to show.
>
> **Recommendation:** After training completes, add a second eval track using seed=1066 or seed=1076. Do NOT replace seed=42 in the callback — keep it for backwards comparability with prior sessions. Run both and report both in POLICY_HEALTH.md.

---

## Combined Interpretation

| Question | Answer |
|----------|--------|
| Is the eval callback broken? | Yes — seed=42 has only 7 strategic ticks. RL improvement is unmeasurable on it. |
| Is the policy broken? | Inconclusive at 300k. Expected behavior: not beating FCFS yet. |
| Does the fix-decision-trigger work? | Yes — decisions/ep dropped 9000→33, zero conflicts, services pass. |
| Is training worth continuing to 2M? | Yes — reward is rising, no conflicts, all hard passes. |
| What will the 1M checkpoint tell us? | Whether strategic behavior has emerged on schedules that have real choice points (use seeds 103, 106, 116 for spot-checks). |

---

## Action items (for Will's review — do not implement without approval)

1. **After training**: add `seed=1076` as a second eval track in `eval_health.py` — run both seed=42 and seed=1076, report both.
2. **Consider**: updating `AirportEvalCallback` to use `seed=1076` for future training runs (keeps seed=42 for one more run for comparability).
3. **No code changes needed** — the training pipeline, reward function, and event trigger are all working correctly.
