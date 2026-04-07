# POLICY_HEALTH.md

Generated: 2026-04-07 23:08 UTC  
Checkpoint: `models/session5_fixed.zip`  
Episodes: 10 (seeds 42–51)

---

## 1. Gate Checks (HARD PASS required)

| Check | Target | Result | Status |
|-------|--------|--------|--------|
| Decisions / episode | 30–400 | 44.2 | ✅ |
| HOLD rate | ≤ 80% | 11.4% | ✅ |
| Services started = completed | exact match | 364=364 | ✅ |
| Abandonment count | 0 | 0 | ✅ |
| Conflict episodes | 0 | 0/10 | ✅ |
| Delay improvement vs FCFS | ≥ 20% | +0.0% | ⚠️ NOT YET |

**HARD PASS status:** PASS ✅

---

## 2. Decision Statistics (10 episodes)

| Metric | Value |
|--------|-------|
| Mean decisions / episode | 44.2 |
| Min decisions | 23 |
| Max decisions | 80 |
| Mean HOLD rate | 11.4% |
| Min HOLD rate | 0.0% |
| Max HOLD rate | 36.2% |

### Action Breakdown (seed=42)

| Action | Count | % |
|--------|-------|---|
| task[0] | 13 | 46.4% |
| task[1] | 7 | 25.0% |
| task[2] | 8 | 28.6% |

---

## 3. Entropy Distribution (all 10 episodes pooled)

*(Entropy in nats; higher = more uniform / uncertain policy)*

```
  HOLD decisions (n=78)
    min    = 0.1588 nats
    max    = 1.4660 nats
    mean   = 0.8481 nats
    median = 0.8487 nats
    p10    = 0.4451 nats
    p90    = 1.2890 nats
    histogram (10 buckets):
      [0.159, 0.290) | # 1
      [0.290, 0.420) | ##### 5
      [0.420, 0.551) | ##### 5
      [0.551, 0.682) | ############# 13
      [0.682, 0.812) | ########## 10
      [0.812, 0.943) | ############### 15
      [0.943, 1.074) | ############# 13
      [1.074, 1.205) | ##### 5
      [1.205, 1.335) | ##### 5
      [1.335, 1.466) | ###### 6

  Non-HOLD decisions (n=364)
    min    = 0.0001 nats
    max    = 2.0639 nats
    mean   = 0.6437 nats
    median = 0.6281 nats
    p10    = 0.0003 nats
    p90    = 1.3641 nats
    histogram (10 buckets):
      [0.000, 0.206) | ######################################## 110
      [0.206, 0.413) | ################################# 33
      [0.413, 0.619) | ###################################### 38
      [0.619, 0.826) | ######################################## 48
      [0.826, 1.032) | ############################# 29
      [1.032, 1.238) | ######################################## 44
      [1.238, 1.445) | ###################################### 38
      [1.445, 1.651) | ################# 17
      [1.651, 1.858) | #### 4
      [1.858, 2.064) | ### 3
```

---

## 4. Delay vs FCFS Baseline (seed=42)

| Agent | Total delay (min) | Avg delay (min) | Missed departures |
|-------|-------------------|-----------------|-------------------|
| RL (this policy) | 14.5 | 2.1 | 0 |
| FCFS baseline    | 14.5 | 2.1 | 0 |
| **Delta** (RL − FCFS) | **+0.0** | — | — |

Improvement over FCFS: **+0.0%**  
Target: ≥ 20% → NOT YET ⚠️

---

## 5. Per-Episode Summary

| Seed | Decisions | HOLD% | Delay(min) | Reward | Conflict |
|------|-----------|-------|------------|--------|----------|
| 42 | 28 | 0.0% | 14.5 | +55.4 | no ✅ |
| 43 | 23 | 0.0% | 12.5 | +47.5 | no ✅ |
| 44 | 54 | 20.4% | 25.6 | +93.3 | no ✅ |
| 45 | 37 | 0.0% | 23.8 | +76.3 | no ✅ |
| 46 | 27 | 0.0% | 16.6 | +53.4 | no ✅ |
| 47 | 56 | 23.2% | 22.9 | +85.8 | no ✅ |
| 48 | 80 | 36.2% | 31.0 | +38.1 | no ✅ |
| 49 | 28 | 0.0% | 16.0 | +54.0 | no ✅ |
| 50 | 74 | 33.8% | 45.7 | +35.9 | no ✅ |
| 51 | 35 | 0.0% | 18.1 | +41.9 | no ✅ |
