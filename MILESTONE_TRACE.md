# MILESTONE_TRACE.md

Accumulated milestone diagnostics for v5 2M retrain (fixed seeding).

**Config:** tight schedules, FT×1/BT×2/PB×1, HOLD masking, randomized per-episode seeds  
**Hyperparams:** lr=3e-4, batch=256, n_steps=2048, n_epochs=10, gamma=0.99, clip=0.2, ent_coef=0.01  
**Eval seed:** 6 (28% suboptimality, 131 min FCFS delay)

---

## Milestone: 250k

**Checkpoint:** `models/v5_2m_step_250000_steps.zip`  
**Time:** 2026-04-08 02:55 UTC

### (a) Hard Battery (seeds [6, 10, 19, 40, 42])

| Seed | FCFS (min) | RL (min) | Gap (min) | Divergence % |
|------|-----------|---------|----------|-------------|
| 6 | 102.5 | 115.4 | +12.9 | 30% |
| 10 | 137.5 | 153.0 | +15.5 | 30% |
| 19 | 170.2 | 173.5 | +3.3 | 41% |
| 40 | 87.0 | 111.5 | +24.5 | 48% |
| 42 | 133.7 | 169.7 | +36.0 | 48% |

**Mean delta (FCFS−RL):** -18.4 min | **Wins:** 0/5

### (b) OOD Battery (seeds 200-219)

**Mean delta:** -11.3 min | **W/L/T:** 0/20/0
**Best:** seed 208 (-0.6 min) | **Worst:** seed 209 (-33.5 min)

### (c) Strategy Emergence (seed 19)

Total decisions: 79 | Divergences from FCFS: 32 (41%)

First 5 divergence points:

| # | Time | Legal | RL chose | FCFS would |
|---|------|-------|----------|------------|
| 1 | 1s | 2 | baggage_load:RND13 | fuel:RND13 |
| 2 | 329s | 3 | baggage_load:RND01 | fuel:RND01 |
| 3 | 373s | 5 | baggage_load:RND02 | fuel:RND01 |
| 4 | 449s | 2 | fuel:RND03 | fuel:RND02 |
| 5 | 504s | 2 | fuel:RND04 | fuel:RND02 |

### (d) Policy Health

| Metric | Value | Status |
|--------|-------|--------|
| HOLD rate | 0.0% | OK |
| Mean entropy | 0.618 nats | — |
| Mean confidence | 55.4% | — |
| Avg decisions/ep | 74 | — |
| Conflicts | 0 | OK |
| Abandonments | 0 | OK |

### (e) Training Metrics

- ep_rew_mean: 23.8 → 25.0 (stable, slight upward)
- explained_variance: 0.841 → 0.848 (good value function fit)
- clip_fraction: 0.029 → 0.036 (healthy, not too aggressive)

**Interpretation: Stable** — Policy is learning diverse schedules (HOLD=0%, zero conflicts/abandonments). Hard battery mean -18.4 min, down from -22.2 at 200k smoke. OOD -11.3 similar to previous. Divergence pattern still shows baggage_load preference over fuel, but at lower rate (30-48% vs 42-57% in stalled run). Seed 19 gap only +3.3 min — closest to beating FCFS.

---
## Milestone: 500k

**Checkpoint:** `models/v5_2m_step_500000_steps.zip`  
**Time:** 2026-04-08 03:08 UTC

### (a) Hard Battery (seeds [6, 10, 19, 40, 42])

| Seed | FCFS (min) | RL (min) | Gap (min) | Divergence % |
|------|-----------|---------|----------|-------------|
| 6 | 102.5 | 120.8 | +18.3 | 31% |
| 10 | 137.5 | 147.1 | +9.6 | 23% |
| 19 | 170.2 | 165.7 | -4.5 | 43% |
| 40 | 87.0 | 104.5 | +17.5 | 42% |
| 42 | 133.7 | 152.1 | +18.4 | 39% |

**Mean delta (FCFS−RL):** -11.9 min | **Wins:** 1/5

### (b) OOD Battery (seeds 200-219)

**Mean delta:** -9.0 min | **W/L/T:** 0/19/1
**Best:** seed 200 (-0.4 min) | **Worst:** seed 219 (-23.5 min)

### (c) Strategy Emergence (seed 19)

Total decisions: 79 | Divergences from FCFS: 34 (43%)

First 5 divergence points:

| # | Time | Legal | RL chose | FCFS would |
|---|------|-------|----------|------------|
| 1 | 329s | 3 | baggage_load:RND01 | fuel:RND01 |
| 2 | 373s | 5 | baggage_unload:RND02 | fuel:RND01 |
| 3 | 392s | 4 | baggage_load:RND02 | fuel:RND01 |
| 4 | 449s | 3 | fuel:RND03 | fuel:RND01 |
| 5 | 546s | 4 | baggage_load:RND04 | baggage_unload:RND03 |

### (d) Policy Health

| Metric | Value | Status |
|--------|-------|--------|
| HOLD rate | 0.0% | OK |
| Mean entropy | 0.563 nats | — |
| Mean confidence | 59.4% | — |
| Avg decisions/ep | 74 | — |
| Conflicts | 0 | OK |
| Abandonments | 0 | OK |

### (e) Training Metrics

- ep_rew_mean: 32.7 → 36.0 (rising from 25 at 250k)
- explained_variance: 0.834 → 0.868 (improving value function)
- clip_fraction: 0.030 → 0.032 (stable)

**Interpretation: Emerging** — FIRST WIN on seed 19 (RL=165.7 vs FCFS=170.2, -4.5 min). Hard battery mean improved -18.4 → -11.9 min. Entropy dropping (0.618 → 0.563), confidence rising (55% → 59%). Strategy on seed 19: first divergence moved from t=1s to t=329s — policy now agrees with FCFS on the first decision (fuel:RND13). Baggage-first bias weakening.

---
## Milestone: 750k

**Checkpoint:** `models/v5_2m_step_750000_steps.zip`  
**Time:** 2026-04-08 03:20 UTC

### (a) Hard Battery (seeds [6, 10, 19, 40, 42])

| Seed | FCFS (min) | RL (min) | Gap (min) | Divergence % |
|------|-----------|---------|----------|-------------|
| 6 | 102.5 | 118.5 | +16.0 | 30% |
| 10 | 137.5 | 150.0 | +12.5 | 31% |
| 19 | 170.2 | 175.7 | +5.5 | 47% |
| 40 | 87.0 | 103.7 | +16.7 | 38% |
| 42 | 133.7 | 166.5 | +32.8 | 53% |

**Mean delta (FCFS−RL):** -16.7 min | **Wins:** 0/5

### (b) OOD Battery (seeds 200-219)

**Mean delta:** -8.0 min | **W/L/T:** 0/20/0
**Best:** seed 215 (-0.8 min) | **Worst:** seed 219 (-21.5 min)

### (c) Strategy Emergence (seed 19)

Total decisions: 79 | Divergences from FCFS: 37 (47%)

First 5 divergence points:

| # | Time | Legal | RL chose | FCFS would |
|---|------|-------|----------|------------|
| 1 | 329s | 3 | baggage_load:RND01 | fuel:RND01 |
| 2 | 373s | 5 | baggage_unload:RND02 | fuel:RND01 |
| 3 | 392s | 4 | baggage_load:RND02 | fuel:RND01 |
| 4 | 449s | 3 | fuel:RND03 | fuel:RND01 |
| 5 | 503s | 3 | fuel:RND04 | fuel:RND01 |

### (d) Policy Health

| Metric | Value | Status |
|--------|-------|--------|
| HOLD rate | 0.0% | OK |
| Mean entropy | 0.491 nats | — |
| Mean confidence | 64.6% | — |
| Avg decisions/ep | 74 | — |
| Conflicts | 0 | OK |
| Abandonments | 0 | OK |

### (e) Training Metrics

- ep_rew_mean: 36.0 → 37.1 (plateau around 32-38, noisy)
- explained_variance: 0.868 → 0.863 (stable, good value function fit)
- clip_fraction: 0.032 → 0.037 (healthy)

**Interpretation: Stable** — Lost seed 19 win from 500k (gap +5.5 vs -4.5 at 500k). Hard battery mean -16.7 (regression from -11.9 at 500k). OOD improved slightly -8.0 (from -9.0). Entropy continuing to drop (0.563 → 0.491), confidence rising (59% → 65%). Divergence on seed 19 up to 47% — policy exploring more aggressively but not yet productively. Baggage-first pattern persists (divergences 1-3 all baggage over fuel). No structural concerns — zero HOLD, conflicts, abandonments.

---
## Milestone: 1M

**Checkpoint:** `models/v5_2m_step_1000000_steps.zip`  
**Time:** 2026-04-08 03:33 UTC

### (a) Hard Battery (seeds [6, 10, 19, 40, 42])

| Seed | FCFS (min) | RL (min) | Gap (min) | Divergence % |
|------|-----------|---------|----------|-------------|
| 6 | 102.5 | 114.6 | +12.1 | 26% |
| 10 | 137.5 | 150.4 | +12.9 | 30% |
| 19 | 170.2 | 175.2 | +5.0 | 47% |
| 40 | 87.0 | 100.8 | +13.8 | 41% |
| 42 | 133.7 | 162.9 | +29.2 | 56% |

**Mean delta (FCFS−RL):** -14.6 min | **Wins:** 0/5

### (b) OOD Battery (seeds 200-219)

**Mean delta:** -9.6 min | **W/L/T:** 0/19/1
**Best:** seed 201 (+0.0 min) | **Worst:** seed 213 (-22.0 min)

### (c) Strategy Emergence (seed 19)

Total decisions: 79 | Divergences from FCFS: 37 (47%)

First 5 divergence points:

| # | Time | Legal | RL chose | FCFS would |
|---|------|-------|----------|------------|
| 1 | 1s | 2 | baggage_load:RND13 | fuel:RND13 |
| 2 | 329s | 3 | baggage_load:RND01 | fuel:RND01 |
| 3 | 373s | 5 | baggage_unload:RND02 | fuel:RND01 |
| 4 | 392s | 4 | baggage_load:RND02 | fuel:RND01 |
| 5 | 449s | 3 | fuel:RND02 | fuel:RND01 |

### (d) Policy Health

| Metric | Value | Status |
|--------|-------|--------|
| HOLD rate | 0.0% | OK |
| Mean entropy | 0.447 nats | — |
| Mean confidence | 67.8% | — |
| Avg decisions/ep | 74 | — |
| Conflicts | 0 | OK |
| Abandonments | 0 | OK |

### (e) Training Metrics

- ep_rew_mean: 37.1 → 30.1 (noisy, range 21-40)
- explained_variance: 0.863 → 0.876 (improving — best yet)
- clip_fraction: 0.037 → 0.049 (rising slightly, still acceptable)

**Interpretation: Approaching** — Hard battery mean -14.6 (improving from -16.7 at 750k). Seed 6 gap narrowed to +12.1 (from +16.0). Seed 42 remains worst at +29.2. OOD -9.6 (slight regression from -8.0). Entropy still dropping (0.491 → 0.447), confidence 68%. Strategy on seed 19: first divergence moved BACK to t=1s (baggage_load over fuel) — policy oscillating on early-game strategy. Explained variance at 0.876 suggests value function getting better. Clip fraction rising (0.049) indicates larger policy updates — could be productive exploration.

---
## Milestone: 1.25M

**Checkpoint:** `models/v5_2m_step_1250000_steps.zip`  
**Time:** 2026-04-08 03:46 UTC

### (a) Hard Battery (seeds [6, 10, 19, 40, 42])

| Seed | FCFS (min) | RL (min) | Gap (min) | Divergence % |
|------|-----------|---------|----------|-------------|
| 6 | 102.5 | 114.6 | +12.1 | 28% |
| 10 | 137.5 | 149.9 | +12.4 | 36% |
| 19 | 170.2 | 176.0 | +5.8 | 43% |
| 40 | 87.0 | 107.2 | +20.2 | 44% |
| 42 | 133.7 | 161.7 | +28.0 | 48% |

**Mean delta (FCFS−RL):** -15.7 min | **Wins:** 0/5

### (b) OOD Battery (seeds 200-219)

**Mean delta:** -8.0 min | **W/L/T:** 0/20/0
**Best:** seed 215 (-0.7 min) | **Worst:** seed 219 (-24.6 min)

### (c) Strategy Emergence (seed 19)

Total decisions: 79 | Divergences from FCFS: 34 (43%)

First 5 divergence points:

| # | Time | Legal | RL chose | FCFS would |
|---|------|-------|----------|------------|
| 1 | 1s | 2 | baggage_load:RND13 | fuel:RND13 |
| 2 | 329s | 3 | baggage_load:RND01 | fuel:RND01 |
| 3 | 373s | 5 | baggage_load:RND02 | fuel:RND01 |
| 4 | 392s | 4 | baggage_unload:RND02 | fuel:RND01 |
| 5 | 449s | 3 | fuel:RND03 | fuel:RND01 |

### (d) Policy Health

| Metric | Value | Status |
|--------|-------|--------|
| HOLD rate | 0.0% | OK |
| Mean entropy | 0.414 nats | — |
| Mean confidence | 70.1% | — |
| Avg decisions/ep | 74 | — |
| Conflicts | 0 | OK |
| Abandonments | 0 | OK |

### (e) Training Metrics

- ep_rew_mean: 30.1 → 35.1 (range 29-37, stabilizing)
- explained_variance: 0.876 → 0.845 (slight dip, still good)
- clip_fraction: 0.049 → 0.041 (normalizing)

**Interpretation: Stable** — Hard battery mean -15.7 (slight regression from -14.6 at 1M). Seed 6 unchanged at +12.1. Seed 42 still worst at +28.0. OOD steady at -8.0 (same as 750k). Entropy continues monotonic decline (0.447 → 0.414), confidence 70% — policy becoming more deterministic. Strategy on seed 19: still baggage-first at t=1s, 43% divergence. No structural concerns. The policy appears to be converging but hasn't found a strategy that consistently beats FCFS.

---
## Milestone: 1.5M

**Checkpoint:** `models/v5_2m_step_1500000_steps.zip`  
**Time:** 2026-04-08 04:00 UTC

### (a) Hard Battery (seeds [6, 10, 19, 40, 42])

| Seed | FCFS (min) | RL (min) | Gap (min) | Divergence % |
|------|-----------|---------|----------|-------------|
| 6 | 102.5 | 112.1 | +9.6 | 31% |
| 10 | 137.5 | 148.9 | +11.4 | 41% |
| 19 | 170.2 | 173.3 | +3.1 | 43% |
| 40 | 87.0 | 106.7 | +19.7 | 44% |
| 42 | 133.7 | 162.8 | +29.1 | 46% |

**Mean delta (FCFS−RL):** -14.6 min | **Wins:** 0/5

### (b) OOD Battery (seeds 200-219)

**Mean delta:** -8.6 min | **W/L/T:** 0/20/0
**Best:** seed 215 (-0.7 min) | **Worst:** seed 219 (-24.6 min)

### (c) Strategy Emergence (seed 19)

Total decisions: 79 | Divergences from FCFS: 34 (43%)

First 5 divergence points:

| # | Time | Legal | RL chose | FCFS would |
|---|------|-------|----------|------------|
| 1 | 329s | 3 | baggage_load:RND01 | fuel:RND01 |
| 2 | 373s | 5 | baggage_load:RND02 | fuel:RND01 |
| 3 | 392s | 4 | baggage_unload:RND02 | fuel:RND01 |
| 4 | 449s | 3 | fuel:RND02 | fuel:RND01 |
| 5 | 525s | 5 | baggage_unload:RND04 | baggage_unload:RND01 |

### (d) Policy Health

| Metric | Value | Status |
|--------|-------|--------|
| HOLD rate | 0.0% | OK |
| Mean entropy | 0.391 nats | — |
| Mean confidence | 71.8% | — |
| Avg decisions/ep | 74 | — |
| Conflicts | 0 | OK |
| Abandonments | 0 | OK |

### (e) Training Metrics

- ep_rew_mean: 35.1 → 34.0 (stable plateau ~30-35)
- explained_variance: 0.845 → 0.850 (stable)
- clip_fraction: 0.041 → 0.048 (slightly elevated)

**Interpretation: Approaching** — Hard battery mean -14.6 (unchanged from 1M). Seed 19 gap narrowed to +3.1 (closest since 500k's -4.5 win). Seed 6 improved to +9.6 (best yet). Strategy shift on seed 19: first divergence moved PAST t=1s again — policy now agrees with FCFS on initial fuel decision, diverges at t=329s with baggage_load. Entropy still falling (0.414 → 0.391), confidence 72%. OOD -8.6 (stable). Seed 42 remains stubborn at +29.1. Policy approaching FCFS parity on easier seeds but struggling on complex ones.

---
## Milestone: 1.75M

**Checkpoint:** `models/v5_2m_step_1750000_steps.zip`  
**Time:** 2026-04-08 04:12 UTC

### (a) Hard Battery (seeds [6, 10, 19, 40, 42])

| Seed | FCFS (min) | RL (min) | Gap (min) | Divergence % |
|------|-----------|---------|----------|-------------|
| 6 | 102.5 | 112.8 | +10.3 | 28% |
| 10 | 137.5 | 149.9 | +12.4 | 43% |
| 19 | 170.2 | 174.9 | +4.7 | 46% |
| 40 | 87.0 | 108.8 | +21.8 | 38% |
| 42 | 133.7 | 161.6 | +27.9 | 43% |

**Mean delta (FCFS−RL):** -15.4 min | **Wins:** 0/5

### (b) OOD Battery (seeds 200-219)

**Mean delta:** -7.7 min | **W/L/T:** 0/19/1
**Best:** seed 201 (+0.0 min) | **Worst:** seed 219 (-22.9 min)

### (c) Strategy Emergence (seed 19)

Total decisions: 79 | Divergences from FCFS: 36 (46%)

First 5 divergence points:

| # | Time | Legal | RL chose | FCFS would |
|---|------|-------|----------|------------|
| 1 | 329s | 3 | baggage_load:RND01 | fuel:RND01 |
| 2 | 373s | 5 | baggage_load:RND02 | fuel:RND01 |
| 3 | 392s | 4 | baggage_unload:RND02 | fuel:RND01 |
| 4 | 449s | 3 | fuel:RND02 | fuel:RND01 |
| 5 | 525s | 5 | baggage_load:RND03 | baggage_unload:RND01 |

### (d) Policy Health

| Metric | Value | Status |
|--------|-------|--------|
| HOLD rate | 0.0% | OK |
| Mean entropy | 0.403 nats | — |
| Mean confidence | 70.9% | — |
| Avg decisions/ep | 74 | — |
| Conflicts | 0 | OK |
| Abandonments | 0 | OK |

### (e) Training Metrics

- ep_rew_mean: 34.0 → 38.7 (highest recent reading)
- explained_variance: 0.850 → 0.859 (stable)
- clip_fraction: 0.048 → 0.046 (stable)

**Interpretation: Stable** — Hard battery mean -15.4 (slight regression from -14.6 at 1.5M). OOD best yet at -7.7 (from -8.6). Seed 42 improving slightly (+27.9 from +29.1). Entropy leveling off (0.391 → 0.403, first uptick). Strategy on seed 19: stable — first divergence at t=329s, baggage_load preference persists. Policy plateauing in the -14 to -16 range on hard battery. One more milestone remaining.

---
## Milestone: 2M

**Checkpoint:** `models/v5_2m_step_2000000_steps.zip`  
**Time:** 2026-04-08 04:25 UTC

### (a) Hard Battery (seeds [6, 10, 19, 40, 42])

| Seed | FCFS (min) | RL (min) | Gap (min) | Divergence % |
|------|-----------|---------|----------|-------------|
| 6 | 102.5 | 120.8 | +18.3 | 39% |
| 10 | 137.5 | 153.0 | +15.5 | 43% |
| 19 | 170.2 | 177.6 | +7.4 | 41% |
| 40 | 87.0 | 108.5 | +21.5 | 41% |
| 42 | 133.7 | 162.1 | +28.4 | 42% |

**Mean delta (FCFS−RL):** -18.2 min | **Wins:** 0/5

### (b) OOD Battery (seeds 200-219)

**Mean delta:** -8.1 min | **W/L/T:** 0/20/0
**Best:** seed 215 (-0.6 min) | **Worst:** seed 209 (-26.1 min)

### (c) Strategy Emergence (seed 19)

Total decisions: 79 | Divergences from FCFS: 32 (41%)

First 5 divergence points:

| # | Time | Legal | RL chose | FCFS would |
|---|------|-------|----------|------------|
| 1 | 1s | 2 | baggage_load:RND13 | fuel:RND13 |
| 2 | 329s | 3 | baggage_load:RND01 | fuel:RND01 |
| 3 | 373s | 5 | baggage_load:RND02 | fuel:RND01 |
| 4 | 392s | 4 | baggage_unload:RND02 | fuel:RND01 |
| 5 | 449s | 3 | fuel:RND02 | fuel:RND01 |

### (d) Policy Health

| Metric | Value | Status |
|--------|-------|--------|
| HOLD rate | 0.0% | OK |
| Mean entropy | 0.381 nats | — |
| Mean confidence | 72.5% | — |
| Avg decisions/ep | 74 | — |
| Conflicts | 0 | OK |
| Abandonments | 0 | OK |

### (e) Training Metrics

- ep_rew_mean: 38.7 → 35.6 (stable plateau ~33-37)
- explained_variance: 0.859 → 0.877 (best yet)
- clip_fraction: 0.046 → 0.042 (healthy)

**Interpretation: Stable** — FINAL MILESTONE. Hard battery regressed to -18.2 min (from -15.4 at 1.75M, -14.6 at 1.5M). Seed 6 worst reading at +18.3 (was +9.6 at 1.5M). Seed 19 back to +7.4 (was +3.1 at 1.5M). OOD -8.1 (stable). Strategy on seed 19 oscillated: first divergence back to t=1s (baggage_load:RND13 over fuel:RND13). Entropy 0.381 (lowest), confidence 73% (highest). Policy converged to a deterministic strategy that consistently loses to FCFS by ~15 min on hard seeds and ~8 min on OOD. No structural issues throughout entire 2M run.

---
