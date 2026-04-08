# LEGAL_ACTION_DIAGNOSTIC_v2.md

**Generated:** 2026-04-07  
**Fleet:** FT×3, BT×3, PB×2 (8 vehicles, MAX_VEHICLES=8)  
**vs v1 fleet:** FT×2, BT×3, PB×2 (7 vehicles)  
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
| 1 (forced) | 867 | 46.7% |
| 2 | 448 | 24.1% |
| 3 | 440 | 23.7% |
| 4+ | 103 | 5.5% |
| HOLD-only | 0 | 0.0% |

**Real-choice queries (2+):** 991 (53.3%)

---

## Section 2 — Per-Episode Decision Quality

| Metric | Value |
|--------|-------|
| Mean queries/episode | 37.2 |
| Median queries/episode | 36.5 |
| Mean real-choice/episode | 19.82 |
| Median real-choice/episode | 19.0 |
| Min real-choice | 11 |
| Max real-choice | 29 |
| Mean ratio (real/total) | 52.9% |

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
| 17 | 53 | 29 | 55% |
| 18 | 30 | 16 | 53% |
| 19 | 24 | 13 | 54% |
| 20 | 31 | 15 | 48% |
| 21 | 29 | 15 | 52% |
| 22 | 32 | 16 | 50% |
| 23 | 37 | 21 | 57% |
| 24 | 45 | 24 | 53% |
| 25 | 44 | 26 | 59% |
| 26 | 34 | 17 | 50% |
| 27 | 50 | 26 | 52% |
| 28 | 26 | 13 | 50% |
| 29 | 52 | 28 | 54% |
| 30 | 53 | 29 | 55% |
| 31 | 22 | 11 | 50% |
| 32 | 28 | 14 | 50% |
| 33 | 31 | 16 | 52% |
| 34 | 48 | 29 | 60% |
| 35 | 53 | 28 | 53% |
| 36 | 41 | 22 | 54% |
| 37 | 26 | 13 | 50% |
| 38 | 44 | 24 | 55% |
| 39 | 34 | 18 | 53% |
| 40 | 48 | 27 | 56% |
| 41 | 45 | 23 | 51% |
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

Total real-choice queries analysed: **991**  
Queries where a better alternative exists: **14** (**1.4%**)  
v1 comparison: was 14/991 = 1.4%

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
| 4 | 19 | 1 | 5% |
| 5 | 19 | 0 | 0% |
| 6 | 13 | 0 | 0% |
| 7 | 23 | 0 | 0% |
| 8 | 18 | 0 | 0% |
| 9 | 26 | 0 | 0% |
| 10 | 12 | 0 | 0% |
| 11 | 27 | 1 | 4% |
| 12 | 28 | 0 | 0% |
| 13 | 21 | 1 | 5% |
| 14 | 14 | 0 | 0% |
| 15 | 18 | 0 | 0% |
| 16 | 21 | 0 | 0% |
| 17 | 29 | 0 | 0% |
| 18 | 16 | 0 | 0% |
| 19 | 13 | 0 | 0% |
| 20 | 15 | 0 | 0% |
| 21 | 15 | 0 | 0% |
| 22 | 16 | 0 | 0% |
| 23 | 21 | 1 | 5% |
| 24 | 24 | 0 | 0% |
| 25 | 26 | 0 | 0% |
| 26 | 17 | 0 | 0% |
| 27 | 26 | 1 | 4% |
| 28 | 13 | 0 | 0% |
| 29 | 28 | 1 | 4% |
| 30 | 29 | 1 | 3% |
| 31 | 11 | 0 | 0% |
| 32 | 14 | 0 | 0% |
| 33 | 16 | 0 | 0% |
| 34 | 29 | 1 | 3% |
| 35 | 28 | 0 | 0% |
| 36 | 22 | 0 | 0% |
| 37 | 13 | 0 | 0% |
| 38 | 24 | 0 | 0% |
| 39 | 18 | 1 | 6% |
| 40 | 27 | 0 | 0% |
| 41 | 23 | 0 | 0% |
| 42 | 15 | 1 | 7% |
| 43 | 11 | 0 | 0% |
| 44 | 25 | 1 | 4% |
| 45 | 19 | 0 | 0% |
| 46 | 13 | 0 | 0% |
| 47 | 23 | 1 | 4% |
| 48 | 28 | 0 | 0% |
| 49 | 15 | 1 | 7% |

---

## Section 5 — Verdict

**% better:** 1.4%  
**Mean real-choice/episode:** 19.82  
**v1 % better:** 1.4%

| Threshold | Verdict |
|-----------|---------|
| ≥15% | Green light — contention fix worked. Recommend 2M retrain. |
| 5-15% | Partial fix. Recommend second variable change before retraining. |
| <5% | Problem deeper than vehicle count. Recommend stopping. |

**Result: 1.4% → <5%: problem deeper than vehicle count.**

**PROBLEM DEEPER THAN VEHICLE COUNT — recommend stopping and reconsidering.**
