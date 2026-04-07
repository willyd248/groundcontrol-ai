# CHECKPOINT_1M_BATTERY.md

**Generated:** 2026-04-07 18:59 EDT  
**Checkpoint:** `checkpoints/airport_ppo_1000000_steps.zip`  
**Branch:** `fix-decision-trigger`

---

## Section 1 — Hard Battery (seeds 100–119)

| Seed | FCFS delay | RL delay | Delta | HOLD rate | Decisions | Choice ticks |
|------|-----------|---------|-------|-----------|-----------|-------------|
| 100 | 16.6 | 16.6 | +0.0 | 0.0% | 30 | 8 |
| 101 | 18.6 | 18.6 | +0.0 | 0.0% | 34 | 9 |
| 102 | 16.6 | 16.6 | +0.0 | 0.0% | 32 | 8 |
| 103 | 25.8 | 26.1 | +0.3 | 40.5% | 79 | 11 |
| 104 | 12.5 | 12.5 | +0.0 | 0.0% | 23 | 6 |
| 105 | 19.7 | 19.7 | +0.0 | 14.6% | 48 | 8 |
| 106 | 27.0 | 27.0 | +0.0 | 22.6% | 62 | 14 |
| 107 | 18.7 | 18.7 | +0.0 | 0.0% | 35 | 9 |
| 108 | 16.6 | 16.6 | +0.0 | 0.0% | 30 | 8 |
| 109 | 20.9 | 20.9 | +0.0 | 0.0% | 37 | 9 |
| 110 | 25.2 | 29.1 | +3.9 | 36.1% | 72 | 11 |
| 111 | 19.5 | 19.5 | +0.0 | 0.0% | 34 | 8 |
| 112 | 30.0 | 30.0 | +0.0 | 38.2% | 76 | 10 |
| 113 | 12.5 | 12.5 | +0.0 | 0.0% | 23 | 6 |
| 114 | 17.1 | 17.1 | +0.0 | 0.0% | 34 | 8 |
| 115 | 24.6 | 24.6 | +0.0 | 0.0% | 37 | 9 |
| 116 | 25.9 | 29.4 | +3.5 | 40.5% | 84 | 12 |
| 117 | 18.7 | 18.7 | +0.0 | 0.0% | 33 | 9 |
| 118 | 16.6 | 16.6 | +0.0 | 0.0% | 32 | 8 |
| 119 | 21.8 | 21.8 | +0.0 | 2.5% | 40 | 8 |

**RL beats FCFS:** 0/20  
**RL tied with FCFS:** 17/20  
**RL worse than FCFS:** 3/20  
**Mean delta:** +0.39 min  
**Wins on high-choice schedules (10+ ticks):** 0/5

---

## Section 2 — Comparison to 300k

| Seed | 300k delta | 1M delta | Change | Choice ticks |
|------|-----------|---------|--------|-------------|
| 100 | +0.0 | +0.0 | — tied | 8 |
| 101 | +0.6 | +0.0 | ✅ improved | 9 |
| 102 | +0.0 | +0.0 | — tied | 8 |
| 103 | +0.0 | +0.3 | ❌ regressed | 11 |
| 104 | +0.0 | +0.0 | — tied | 6 |
| 105 | +0.0 | +0.0 | — tied | 8 |
| 106 | +0.0 | +0.0 | — tied | 14 |
| 107 | +0.0 | +0.0 | — tied | 9 |
| 108 | +0.0 | +0.0 | — tied | 8 |
| 109 | +0.0 | +0.0 | — tied | 9 |
| 110 | +0.0 | +3.9 | ❌ regressed | 11 |
| 111 | +0.0 | +0.0 | — tied | 8 |
| 112 | +0.0 | +0.0 | — tied | 10 |
| 113 | +0.0 | +0.0 | — tied | 6 |
| 114 | +0.0 | +0.0 | — tied | 8 |
| 115 | +0.0 | +0.0 | — tied | 9 |
| 116 | -2.1 | +3.5 | ❌ regressed | 12 |
| 117 | +0.0 | +0.0 | — tied | 9 |
| 118 | +0.0 | +0.0 | — tied | 8 |
| 119 | +0.0 | +0.0 | — tied | 8 |

**300k mean delta:** -0.07 min  
**1M mean delta:**   +0.39 min  

| Metric | 300k | 1M |
|--------|------|----|
| Beats FCFS | 1/20 | 0/20 |
| Worse than FCFS | 1/20 | 3/20 |
| Improved vs prior | — | 1/20 |
| Regressed vs prior | — | 3/20 |
| Mean delta | -0.07 min | +0.39 min |

---

## Section 3 — seed=116 Deep Dive

seed=116 has 12 choice ticks — one of the highest-contention schedules in the 100–119 range.

| Checkpoint | RL delay | FCFS delay | Delta | HOLD rate | Decisions |
|------------|---------|-----------|-------|-----------|-----------|
| 300k | 23.8 | 25.9 | -2.1 | 0.0% (known) | ~9 (bug) |
| 500k | 25.9 | 25.9 | +0.0 | 22.7% | 66 |
| **1M** | **29.4** | **25.9** | **+3.5** | **40.5%** | **84** |

❌ **Regressed further.** 1M is worse than 500k on seed=116 (delta=+3.5 min). Concerning.

---

## Section 4 — Training Reward Status

TensorBoard latest step: **1,015,808** (ep_rew_mean=65.0258)  
Decisions/ep: 34.37  
Conflict term rate: 0.0  
Entropy loss: -0.4263  

**Reward since plateau start (~220k):**  
  Min: 62.879  
  Max: 65.317  
  Most recent: 65.026  
  Trend: **rising**  

ep_rew_mean last 5: `[(950272, 64.983), (966656, 64.749), (983040, 65.0528), (999424, 64.096), (1015808, 65.0258)]`

**eval callback** (seed=42, known non-strategic — expected 0.0):**  
  delay_improvement last 3: `[(900000, 0.0), (950000, 0.0), (1000000, 0.0)]`  
  rl_decisions: (1000000, 28.0)

---

## Section 5 — Verdict

**Scenario C — Regressing.**  
RL is worse than FCFS on 3 schedules vs better on 0. Mean delta +0.39 min vs -0.07 at 300k. Policy is degrading. Immediate investigation required.

**Anomaly flags:** none
