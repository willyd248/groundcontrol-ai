# POLICY_HEALTH_V5_FINAL.md

**v5 2M Retrain — Final Policy Health Report**  
**Date:** 2026-04-08  
**Checkpoint:** `models/v5_2m_final.zip` (2,000,000 steps)  
**Config:** tight schedules, FT×1/BT×2/PB×1, HOLD masking, randomized per-episode seeds  
**Hyperparams:** lr=3e-4, batch=256, n_steps=2048, n_epochs=10, gamma=0.99, clip=0.2, ent_coef=0.01

---

## 1. Final Battery Results

### Hard Battery (50 seeds, 0-49)

| Metric | Value |
|--------|-------|
| **Win/Loss/Tie** | **3 / 46 / 1** |
| **Win rate** | **6%** |
| Mean delta (FCFS−RL) | -10.4 min |
| Median delta | -7.6 min |
| Best | seed 48 (+4.2 min) |
| Worst | seed 20 (-33.7 min) |

Wins: seeds 15 (+1.2), 21 (+1.7), 48 (+4.2). All marginal.

### OOD Battery (50 seeds, 200-249)

| Metric | Value |
|--------|-------|
| **Win/Loss/Tie** | **0 / 48 / 2** |
| **Win rate** | **0%** |
| Mean delta (FCFS−RL) | -7.8 min |
| Median delta | -6.1 min |
| Best | seed 220 (-0.3 min) |
| Worst | seed 209 (-26.5 min) |

Zero wins on out-of-distribution seeds.

### Combined (100 seeds)

| Metric | Value |
|--------|-------|
| **Win/Loss/Tie** | **3 / 94 / 3** |
| **Win rate** | **3%** |
| Mean delta | -9.1 min |
| Median delta | -6.7 min |

---

## 2. Milestone Trajectory

| Milestone | Hard Mean | Hard Wins | OOD Mean | OOD Wins | Entropy | Confidence | Interpretation |
|-----------|----------|-----------|----------|----------|---------|------------|----------------|
| 250k | -18.4 | 0/5 | -11.3 | 0/20 | 0.618 | 55% | Stable |
| 500k | -11.9 | **1/5** | -9.0 | 0/20 | 0.563 | 59% | Emerging |
| 750k | -16.7 | 0/5 | -8.0 | 0/20 | 0.491 | 65% | Stable |
| 1M | -14.6 | 0/5 | -9.6 | 0/20 | 0.447 | 68% | Approaching |
| 1.25M | -15.7 | 0/5 | -8.0 | 0/20 | 0.414 | 70% | Stable |
| 1.5M | -14.6 | 0/5 | -8.6 | 0/20 | 0.391 | 72% | Approaching |
| 1.75M | -15.4 | 0/5 | -7.7 | 0/20 | 0.403 | 71% | Stable |
| 2M | -18.2 | 0/5 | -8.1 | 0/20 | 0.381 | 73% | Stable |
| **2M final** | **-10.4** | **3/50** | **-7.8** | **0/50** | **0.341** | — | — |

Best checkpoint: **500k** — the only point where the policy beat FCFS on any hard battery seed (seed 19, -4.5 min). Performance did not improve after 500k; the policy oscillated in the -11 to -18 range on the 5-seed hard battery while entropy monotonically decreased.

---

## 3. Strategy Analysis — Seed 19 Across Training

| Checkpoint | RL Delay | Gap vs FCFS | Divergences | Entropy | First Divergence |
|------------|---------|-------------|-------------|---------|------------------|
| 250k | 173.5 | +3.3 | 32/79 (41%) | 0.609 | t=1s baggage_load over fuel |
| 1M | 175.2 | +5.0 | 37/79 (47%) | 0.489 | t=1s baggage_load over fuel |
| 2M final | 177.0 | +6.8 | 32/79 (41%) | 0.341 | t=329s baggage_load over fuel |

The policy's performance on seed 19 **degraded** over training (+3.3 → +6.8 min vs FCFS). Entropy dropped sharply (0.609 → 0.341) as the policy committed harder to its baggage-first strategy. The core divergence pattern — preferring `baggage_load` over `fuel` when both are available — persisted from 250k through 2M. This is the opposite of what FCFS does (fuel first by queue order), and the data shows it's consistently worse.

---

## 4. Policy Health (Structural)

All structural metrics remained clean throughout the entire 2M run:

| Metric | All Milestones |
|--------|---------------|
| HOLD rate | 0.0% |
| Conflicts | 0 |
| Abandonments | 0 |
| Avg decisions/ep | 74 |

The policy is **well-behaved** — it never holds when work is available, never creates resource conflicts, and never abandons tasks. It just makes worse scheduling decisions than FCFS.

---

## 5. Training Metrics Summary

| Metric | Start (250k) | End (2M) | Trend |
|--------|-------------|---------|-------|
| ep_rew_mean | 23.8 → 25.0 | 33.5 → 35.6 | Rising then plateau ~33-37 |
| explained_variance | 0.841 → 0.848 | 0.859 → 0.877 | Improving throughout |
| clip_fraction | 0.029 → 0.036 | 0.042 → 0.044 | Slight upward trend |

The value function steadily improved (explained_variance 0.84 → 0.88) and reward increased (25 → 35), indicating the agent is learning *something* — just not a strategy that beats FCFS.

---

## 6. Honest Verdict

### The policy does NOT beat FCFS.

After 2M steps of training with randomized schedules, the MaskablePPO agent:
- **Wins 3% of seeds** (3/100) with marginal victories (+1.2 to +4.2 min)
- **Loses by an average of 9.1 minutes** across 100 diverse schedules
- **Has 0 wins on out-of-distribution seeds** (0/50)
- **Peaked at 500k** — the only milestone with a hard battery win — then plateaued

### What the policy learned
The agent learned a **consistent but wrong heuristic**: prioritize baggage operations over fueling. This manifests as the "baggage-first" divergence pattern visible in every milestone's strategy emergence analysis. While this avoids structural failures (no HOLD abuse, no conflicts, no abandonments), it systematically delays fueling operations, particularly for aircraft requiring the single fuel truck.

### Why it doesn't work
FCFS processes tasks in queue order, which naturally balances resource utilization. The learned baggage-first policy creates **fuel truck idle time** while baggage tugs (BT×2) are overutilized, then creates **fuel bottlenecks** when multiple aircraft need fueling simultaneously. With only 1 fuel truck (FT×1), any delay in fueling cascades into departure delays.

### What this means for the project
1. **The reward signal is real** — reward increased from 25 to 35, and the value function is well-calibrated (explained_variance 0.88). The agent is learning; it's just converging to a local optimum worse than FCFS.
2. **The seeding fix worked** — the policy generalizes across seeds (consistent ~8-10 min deficit) rather than memorizing a few schedules. This is a healthier failure mode than the pre-fix stalled run.
3. **2M steps may not be enough** — but the plateau from 500k-2M (oscillating around -15 min on the 5-seed battery) suggests more steps alone won't help.
4. **Next steps to consider:**
   - **Reward shaping:** Add fuel-urgency bonuses or explicit penalties for fuel truck idle time
   - **Observation enrichment:** Expose remaining service time estimates or fuel truck utilization ratio
   - **Architecture:** Try a larger network (current: default MlpPolicy 64×64) or attention-based policy
   - **Curriculum:** Start with simpler schedules (fewer flights) and gradually increase complexity
   - **Alternative algorithms:** SAC or DQN with prioritized replay may handle the sparse reward better

---

## Appendix: Full Seed-by-Seed Results

<details>
<summary>Hard Battery (seeds 0-49)</summary>

| Seed | FCFS (min) | RL (min) | Delta | Result |
|------|-----------|---------|-------|--------|
| 0 | 64.1 | 72.5 | -8.4 | L |
| 1 | 43.8 | 45.8 | -2.0 | L |
| 2 | 36.8 | 42.2 | -5.4 | L |
| 3 | 68.6 | 69.5 | -0.9 | L |
| 4 | 44.6 | 47.8 | -3.2 | L |
| 5 | 87.7 | 97.1 | -9.4 | L |
| 6 | 102.5 | 110.6 | -8.1 | L |
| 7 | 64.5 | 70.3 | -5.8 | L |
| 8 | 34.2 | 39.4 | -5.2 | L |
| 9 | 76.1 | 81.8 | -5.7 | L |
| 10 | 137.5 | 153.0 | -15.5 | L |
| 11 | 62.5 | 71.0 | -8.5 | L |
| 12 | 91.2 | 111.9 | -20.7 | L |
| 13 | 40.5 | 40.9 | -0.4 | T |
| 14 | 32.1 | 44.2 | -12.1 | L |
| 15 | 54.6 | 53.4 | +1.2 | **W** |
| 16 | 45.9 | 57.1 | -11.2 | L |
| 17 | 76.4 | 82.6 | -6.2 | L |
| 18 | 47.6 | 50.3 | -2.7 | L |
| 19 | 170.2 | 177.0 | -6.8 | L |
| 20 | 105.6 | 139.3 | -33.7 | L |
| 21 | 34.9 | 33.2 | +1.7 | **W** |
| 22 | 45.4 | 62.5 | -17.1 | L |
| 23 | 60.0 | 68.0 | -8.0 | L |
| 24 | 91.7 | 109.1 | -17.4 | L |
| 25 | 84.1 | 116.3 | -32.2 | L |
| 26 | 48.4 | 52.2 | -3.8 | L |
| 27 | 82.5 | 100.8 | -18.3 | L |
| 28 | 27.1 | 33.4 | -6.3 | L |
| 29 | 94.0 | 97.4 | -3.4 | L |
| 30 | 68.6 | 74.6 | -6.0 | L |
| 31 | 30.1 | 33.0 | -2.9 | L |
| 32 | 36.1 | 64.9 | -28.8 | L |
| 33 | 149.7 | 162.7 | -13.0 | L |
| 34 | 59.5 | 74.5 | -15.0 | L |
| 35 | 57.3 | 76.3 | -19.0 | L |
| 36 | 52.5 | 55.1 | -2.6 | L |
| 37 | 139.4 | 167.2 | -27.8 | L |
| 38 | 72.6 | 90.9 | -18.3 | L |
| 39 | 38.1 | 42.0 | -3.9 | L |
| 40 | 87.0 | 107.5 | -20.5 | L |
| 41 | 64.7 | 81.1 | -16.4 | L |
| 42 | 133.7 | 161.8 | -28.1 | L |
| 43 | 26.1 | 30.1 | -4.0 | L |
| 44 | 79.3 | 92.1 | -12.8 | L |
| 45 | 33.2 | 40.5 | -7.3 | L |
| 46 | 24.7 | 26.8 | -2.1 | L |
| 47 | 81.3 | 99.9 | -18.6 | L |
| 48 | 73.2 | 69.0 | +4.2 | **W** |
| 49 | 30.9 | 32.0 | -1.1 | L |

</details>

<details>
<summary>OOD Battery (seeds 200-249)</summary>

| Seed | FCFS (min) | RL (min) | Delta | Result |
|------|-----------|---------|-------|--------|
| 200 | 40.4 | 41.2 | -0.8 | L |
| 201 | 28.2 | 30.4 | -2.2 | L |
| 202 | 67.6 | 75.3 | -7.7 | L |
| 203 | 44.4 | 50.7 | -6.3 | L |
| 204 | 74.3 | 83.5 | -9.2 | L |
| 205 | 54.9 | 56.9 | -2.0 | L |
| 206 | 34.9 | 44.7 | -9.8 | L |
| 207 | 132.4 | 138.3 | -5.9 | L |
| 208 | 66.8 | 74.5 | -7.7 | L |
| 209 | 110.2 | 136.7 | -26.5 | L |
| 210 | 79.4 | 85.9 | -6.5 | L |
| 211 | 92.9 | 98.6 | -5.7 | L |
| 212 | 64.3 | 75.3 | -11.0 | L |
| 213 | 32.2 | 43.4 | -11.2 | L |
| 214 | 71.9 | 76.4 | -4.5 | L |
| 215 | 25.6 | 26.2 | -0.6 | L |
| 216 | 50.3 | 53.4 | -3.1 | L |
| 217 | 57.0 | 67.5 | -10.5 | L |
| 218 | 67.0 | 71.9 | -4.9 | L |
| 219 | 80.7 | 106.5 | -25.8 | L |
| 220 | 53.3 | 53.6 | -0.3 | T |
| 221 | 38.4 | 44.7 | -6.3 | L |
| 222 | 43.9 | 52.8 | -8.9 | L |
| 223 | 46.4 | 59.6 | -13.2 | L |
| 224 | 50.1 | 53.4 | -3.3 | L |
| 225 | 57.6 | 61.7 | -4.1 | L |
| 226 | 112.0 | 117.9 | -5.9 | L |
| 227 | 56.7 | 57.5 | -0.8 | L |
| 228 | 98.9 | 113.8 | -14.9 | L |
| 229 | 98.1 | 117.1 | -19.0 | L |
| 230 | 32.5 | 42.8 | -10.3 | L |
| 231 | 28.2 | 29.4 | -1.2 | L |
| 232 | 75.1 | 86.4 | -11.3 | L |
| 233 | 184.9 | 197.9 | -13.0 | L |
| 234 | 64.9 | 84.0 | -19.1 | L |
| 235 | 64.5 | 69.0 | -4.5 | L |
| 236 | 102.4 | 106.0 | -3.6 | L |
| 237 | 68.2 | 73.5 | -5.3 | L |
| 238 | 61.4 | 71.0 | -9.6 | L |
| 239 | 39.4 | 40.2 | -0.8 | L |
| 240 | 124.9 | 126.9 | -2.0 | L |
| 241 | 109.0 | 114.9 | -5.9 | L |
| 242 | 59.1 | 71.5 | -12.4 | L |
| 243 | 93.2 | 114.3 | -21.1 | L |
| 244 | 127.1 | 127.6 | -0.5 | T |
| 245 | 36.1 | 41.7 | -5.6 | L |
| 246 | 31.4 | 34.9 | -3.5 | L |
| 247 | 68.1 | 74.9 | -6.8 | L |
| 248 | 55.2 | 65.1 | -9.9 | L |
| 249 | 44.5 | 47.4 | -2.9 | L |

</details>
