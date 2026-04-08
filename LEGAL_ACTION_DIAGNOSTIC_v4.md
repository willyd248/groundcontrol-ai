# LEGAL_ACTION_DIAGNOSTIC_v4.md

**Generated:** 2026-04-07  
**Fleet:** FT×2, BT×2, PB×2 (6 vehicles, MAX_VEHICLES=6)  
**Schedule density:** tight (10–20 flights, 2–3 waves, 0–15 min slack)  
**vs v1:** loose, FT×2/BT×3/PB×2 (7 veh), 6–14 flights, 30+ min slack  
**Env:** masked (HOLD illegal when assignments exist)  
**Policy:** FCFS-greedy  
**Seeds:** 0–49 (50 episodes)  
**Forward simulation window:** 600 sim seconds per fork

---

## Section 1 — Per-Query Legal Action Distribution

Total queries: **2979**  (v1 loose: 1858)
Mean queries/episode: **59.6**  (v1: 37.2)

| Legal actions at query | Count | % |
|------------------------|-------|----|
| 1 (forced) | 1105 | 37.1% |
| 2 | 640 | 21.5% |
| 3 | 533 | 17.9% |
| 4+ | 701 | 23.5% |
| HOLD-only | 0 | 0.0% |

**Real-choice queries (2+):** 1874 (62.9%)  (v1: 991/1858=53.3%)

---

## Section 2 — Per-Episode Decision Quality

| Metric | v4 (tight) | v1 (loose) |
|--------|------------|------------|
| Mean queries/episode | 59.6 | 37.2 |
| Median queries/episode | 58.5 | 35.5 |
| Mean real-choice/episode | 37.48 | 19.82 |
| Min real-choice | 18 | 11 |
| Max real-choice | 55 | 29 |
| Mean FCFS delay (min) | 69.5 | 21.4 |

| Seed | Queries | Real-choice | Ratio | FCFS Delay |
|------|---------|-------------|-------|-----------|
| 0 | 62 | 41 | 66% | 77.9 min |
| 1 | 47 | 25 | 53% | 34.1 min |
| 2 | 40 | 27 | 68% | 43.9 min |
| 3 | 51 | 32 | 63% | 64.1 min |
| 4 | 50 | 30 | 60% | 50.0 min |
| 5 | 73 | 49 | 67% | 88.9 min |
| 6 | 74 | 47 | 64% | 107.1 min |
| 7 | 58 | 31 | 53% | 52.3 min |
| 8 | 51 | 34 | 67% | 34.0 min |
| 9 | 68 | 43 | 63% | 62.0 min |
| 10 | 74 | 48 | 65% | 136.6 min |
| 11 | 66 | 40 | 61% | 56.8 min |
| 12 | 65 | 42 | 65% | 108.0 min |
| 13 | 55 | 27 | 49% | 34.8 min |
| 14 | 43 | 24 | 56% | 39.7 min |
| 15 | 51 | 32 | 63% | 54.0 min |
| 16 | 58 | 38 | 66% | 43.9 min |
| 17 | 71 | 42 | 59% | 78.3 min |
| 18 | 48 | 29 | 60% | 36.8 min |
| 19 | 79 | 54 | 68% | 149.1 min |
| 20 | 78 | 51 | 65% | 118.8 min |
| 21 | 46 | 27 | 59% | 32.7 min |
| 22 | 48 | 31 | 65% | 47.6 min |
| 23 | 55 | 32 | 58% | 51.6 min |
| 24 | 62 | 42 | 68% | 102.7 min |
| 25 | 58 | 39 | 67% | 118.4 min |
| 26 | 51 | 30 | 59% | 50.0 min |
| 27 | 78 | 46 | 59% | 88.9 min |
| 28 | 41 | 26 | 63% | 36.2 min |
| 29 | 71 | 45 | 63% | 91.8 min |
| 30 | 71 | 46 | 65% | 72.6 min |
| 31 | 39 | 24 | 62% | 29.1 min |
| 32 | 44 | 28 | 64% | 40.3 min |
| 33 | 73 | 51 | 70% | 160.3 min |
| 34 | 71 | 48 | 68% | 59.4 min |
| 35 | 70 | 46 | 66% | 57.3 min |
| 36 | 59 | 31 | 53% | 53.3 min |
| 37 | 76 | 52 | 68% | 134.8 min |
| 38 | 78 | 45 | 58% | 68.6 min |
| 39 | 51 | 30 | 59% | 40.0 min |
| 40 | 66 | 41 | 62% | 89.9 min |
| 41 | 63 | 37 | 59% | 66.3 min |
| 42 | 79 | 55 | 70% | 131.8 min |
| 43 | 40 | 29 | 72% | 29.7 min |
| 44 | 63 | 44 | 70% | 81.4 min |
| 45 | 53 | 32 | 60% | 39.2 min |
| 46 | 43 | 18 | 42% | 25.6 min |
| 47 | 58 | 46 | 79% | 98.0 min |
| 48 | 67 | 41 | 61% | 75.7 min |
| 49 | 43 | 26 | 60% | 29.3 min |

---

## Section 3 — Strategic vs Forced Episodes

| Category | Episodes | % |
|----------|----------|---|
| 0 real-choice | 0 | 0% |
| 1-3 real-choice (sparse) | 0 | 0% |
| 4-9 real-choice (moderate) | 0 | 0% |
| 10+ real-choice (rich) | 50 | 100% |

---

## Section 4 — Greedy Optimality Check

Total real-choice queries analysed: **1874**  
Queries where a better alternative exists: **184** (**9.8%**)  
v1 baseline (loose, FT×2/BT×3/PB×2): 14/991 = 1.4%  
v3 (loose, FT×1/BT×2/PB×1): 15/996 = 1.5%

When a better alternative exists:
  Mean improvement: 0.346 min
  Max improvement: 3.000 min
  Median improvement: 0.100 min

| Seed | Real-choice | Any-better | % better |
|------|-------------|------------|---------|
| 0 | 41 | 7 | 17% |
| 1 | 25 | 2 | 8% |
| 2 | 27 | 2 | 7% |
| 3 | 32 | 2 | 6% |
| 4 | 30 | 7 | 23% |
| 5 | 49 | 3 | 6% |
| 6 | 47 | 5 | 11% |
| 7 | 31 | 2 | 6% |
| 8 | 34 | 3 | 9% |
| 9 | 43 | 3 | 7% |
| 10 | 48 | 1 | 2% |
| 11 | 40 | 5 | 12% |
| 12 | 42 | 6 | 14% |
| 13 | 27 | 0 | 0% |
| 14 | 24 | 6 | 25% |
| 15 | 32 | 3 | 9% |
| 16 | 38 | 7 | 18% |
| 17 | 42 | 8 | 19% |
| 18 | 29 | 4 | 14% |
| 19 | 54 | 8 | 15% |
| 20 | 51 | 2 | 4% |
| 21 | 27 | 1 | 4% |
| 22 | 31 | 5 | 16% |
| 23 | 32 | 2 | 6% |
| 24 | 42 | 3 | 7% |
| 25 | 39 | 3 | 8% |
| 26 | 30 | 3 | 10% |
| 27 | 46 | 2 | 4% |
| 28 | 26 | 6 | 23% |
| 29 | 45 | 0 | 0% |
| 30 | 46 | 7 | 15% |
| 31 | 24 | 0 | 0% |
| 32 | 28 | 4 | 14% |
| 33 | 51 | 5 | 10% |
| 34 | 48 | 6 | 12% |
| 35 | 46 | 3 | 7% |
| 36 | 31 | 3 | 10% |
| 37 | 52 | 7 | 13% |
| 38 | 45 | 3 | 7% |
| 39 | 30 | 3 | 10% |
| 40 | 41 | 4 | 10% |
| 41 | 37 | 6 | 16% |
| 42 | 55 | 5 | 9% |
| 43 | 29 | 1 | 3% |
| 44 | 44 | 1 | 2% |
| 45 | 32 | 3 | 9% |
| 46 | 18 | 1 | 6% |
| 47 | 46 | 3 | 7% |
| 48 | 41 | 7 | 17% |
| 49 | 26 | 1 | 4% |

---

## Section 5 — Verdict

**% better:** 9.8%  (v1: 1.4%, v3: 1.5%)
**Mean real-choice/episode:** 37.48  (v1: 19.82)
**Mean FCFS delay:** 69.5 min  (v1: 21.4 min)

| Threshold | Verdict |
|-----------|---------|
| ≥15% | Green light — density fix worked. Recommend 2M retrain. |
| 5-15% | Partial fix. Consider combining density + fleet reduction. |
| <5% | Density alone not enough. Deeper structural issue. |

**Result: 9.8% → 5-15%: partial fix.**

**PARTIAL FIX — density helped but not enough. Consider reducing fleet further or combining both changes.**
