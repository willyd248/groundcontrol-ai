# LEGAL_ACTION_DIAGNOSTIC_v3.md

**Generated:** 2026-04-07  
**Fleet:** FT×1, BT×2, PB×1 (4 vehicles, MAX_VEHICLES=4)  
**vs v1 fleet:** FT×2, BT×3, PB×2 (7 vehicles)  
**vs v2 fleet:** FT×3, BT×3, PB×2 (8 vehicles) — v2 was wrong direction (added vehicle)  
**Env:** masked (HOLD illegal when assignments exist)  
**Policy:** FCFS-greedy  
**Seeds:** 0-49 (50 episodes)  
**Forward simulation window:** 600 sim seconds per fork

---

## Section 1 — Per-Query Legal Action Distribution

Total queries: **1858**  
Mean queries/episode: **37.2**

| Legal actions at query | Count | % |
|------------------------|-------|----|
| 1 (forced) | 862 | 46.4% |
| 2 | 454 | 24.4% |
| 3 | 444 | 23.9% |
| 4+ | 98 | 5.3% |
| HOLD-only | 0 | 0.0% |

**Real-choice queries (2+):** 996 (53.6%)

---

## Section 2 — Per-Episode Decision Quality

| Metric | Value |
|--------|-------|
| Mean queries/episode | 37.2 |
| Median queries/episode | 36.5 |
| Mean real-choice/episode | 19.92 |
| Median real-choice/episode | 19.0 |
| Min real-choice | 11 |
| Max real-choice | 31 |
| Mean ratio (real/total) | 53.2% |

| Seed | Queries | Real-choice | Ratio |
|------|---------|-------------|-------|
| 0 | 47 | 24 | 51% |
| 1 | 31 | 15 | 48% |
| 2 | 24 | 13 | 54% |
| 3 | 36 | 18 | 50% |
| 4 | 33 | 19 | 58% |
| 5 | 37 | 19 | 51% |
| 6 | 26 | 13 | 50% |
| 7 | 40 | 23 | 57% |
| 8 | 34 | 18 | 53% |
| 9 | 48 | 26 | 54% |
| 10 | 24 | 12 | 50% |
| 11 | 46 | 27 | 59% |
| 12 | 49 | 28 | 57% |
| 13 | 39 | 21 | 54% |
| 14 | 27 | 14 | 52% |
| 15 | 34 | 18 | 53% |
| 16 | 42 | 21 | 50% |
| 17 | 53 | 31 | 58% |
| 18 | 30 | 16 | 53% |
| 19 | 24 | 13 | 54% |
| 20 | 31 | 15 | 48% |
| 21 | 29 | 15 | 52% |
| 22 | 32 | 16 | 50% |
| 23 | 37 | 22 | 59% |
| 24 | 45 | 23 | 51% |
| 25 | 44 | 27 | 61% |
| 26 | 34 | 17 | 50% |
| 27 | 50 | 26 | 52% |
| 28 | 26 | 13 | 50% |
| 29 | 52 | 28 | 54% |
| 30 | 53 | 29 | 55% |
| 31 | 22 | 11 | 50% |
| 32 | 28 | 14 | 50% |
| 33 | 31 | 16 | 52% |
| 34 | 48 | 29 | 60% |
| 35 | 53 | 29 | 55% |
| 36 | 41 | 22 | 54% |
| 37 | 26 | 13 | 50% |
| 38 | 44 | 24 | 55% |
| 39 | 34 | 18 | 53% |
| 40 | 48 | 27 | 56% |
| 41 | 45 | 24 | 53% |
| 42 | 28 | 15 | 54% |
| 43 | 23 | 11 | 48% |
| 44 | 43 | 25 | 58% |
| 45 | 37 | 19 | 51% |
| 46 | 27 | 13 | 48% |
| 47 | 43 | 23 | 53% |
| 48 | 52 | 28 | 54% |
| 49 | 28 | 15 | 54% |

---

## Section 3 — Strategic vs Forced Episodes

| Category | Episodes | % |
|----------|----------|---|
| 0 real-choice (purely forced) | 0 | 0% |
| 1-3 real-choice (sparse) | 0 | 0% |
| 4-9 real-choice (moderate) | 0 | 0% |
| 10+ real-choice (rich) | 50 | 100% |

---

## Section 4 — Greedy Optimality Check

Total real-choice queries analysed: **996**  
Queries where a better alternative exists: **15** (**1.5%**)  
v1 baseline (FT×2/BT×3/PB×2): 14/991 = 1.4%  
v2 (FT×3/BT×3/PB×2, wrong direction): 14/991 = 1.4% (unchanged)

When a better alternative exists:
  Mean improvement: 0.100 min
  Max improvement: 0.100 min
  Median improvement: 0.100 min

| Seed | Real-choice | Any-better | % better |
|------|-------------|------------|---------|
| 0 | 24 | 0 | 0% |
| 1 | 15 | 0 | 0% |
| 2 | 13 | 1 | 8% |
| 3 | 18 | 0 | 0% |
| 4 | 19 | 0 | 0% |
| 5 | 19 | 0 | 0% |
| 6 | 13 | 0 | 0% |
| 7 | 23 | 0 | 0% |
| 8 | 18 | 0 | 0% |
| 9 | 26 | 0 | 0% |
| 10 | 12 | 0 | 0% |
| 11 | 27 | 1 | 4% |
| 12 | 28 | 0 | 0% |
| 13 | 21 | 0 | 0% |
| 14 | 14 | 0 | 0% |
| 15 | 18 | 0 | 0% |
| 16 | 21 | 0 | 0% |
| 17 | 31 | 1 | 3% |
| 18 | 16 | 0 | 0% |
| 19 | 13 | 0 | 0% |
| 20 | 15 | 0 | 0% |
| 21 | 15 | 0 | 0% |
| 22 | 16 | 0 | 0% |
| 23 | 22 | 0 | 0% |
| 24 | 23 | 0 | 0% |
| 25 | 27 | 2 | 7% |
| 26 | 17 | 0 | 0% |
| 27 | 26 | 1 | 4% |
| 28 | 13 | 0 | 0% |
| 29 | 28 | 1 | 4% |
| 30 | 29 | 1 | 3% |
| 31 | 11 | 0 | 0% |
| 32 | 14 | 0 | 0% |
| 33 | 16 | 1 | 6% |
| 34 | 29 | 2 | 7% |
| 35 | 29 | 0 | 0% |
| 36 | 22 | 0 | 0% |
| 37 | 13 | 0 | 0% |
| 38 | 24 | 1 | 4% |
| 39 | 18 | 0 | 0% |
| 40 | 27 | 2 | 7% |
| 41 | 24 | 0 | 0% |
| 42 | 15 | 0 | 0% |
| 43 | 11 | 0 | 0% |
| 44 | 25 | 0 | 0% |
| 45 | 19 | 0 | 0% |
| 46 | 13 | 0 | 0% |
| 47 | 23 | 0 | 0% |
| 48 | 28 | 1 | 4% |
| 49 | 15 | 0 | 0% |

---

## Section 5 — Verdict

**% better:** 1.5%  
**Mean real-choice/episode:** 19.92  
**v1 % better:** 1.4%

| Threshold | Verdict |
|-----------|---------|
| ≥15% | Green light — contention fix worked. Recommend 2M retrain. |
| 5-15% | Partial fix. Recommend second variable change before retraining. |
| <5% | Problem deeper than vehicle count. Recommend stopping. |

**Result: 1.5% → <5%: problem deeper than vehicle count.**

**PROBLEM DEEPER THAN VEHICLE COUNT — recommend stopping and reconsidering.**
