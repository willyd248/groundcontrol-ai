# LEGAL_ACTION_DIAGNOSTIC_v5.md

**Generated:** 2026-04-07  
**Fleet:** FT×1, BT×2, PB×1 (4 vehicles, MAX_VEHICLES=4)  
**Schedule density:** tight (10–20 flights, 2–3 waves, 0–15 min slack)  
**Combined change:** tight schedules (v4) + reduced fleet (v3 config)  
**vs v4:** FT×2/BT×2/PB×2 + tight → 184/1874 = 9.8%  
**vs v1 baseline:** loose + original fleet → 14/991 = 1.4%  
**Forward simulation window:** 600 sim seconds per fork

---

## Section 1 — Per-Query Legal Action Distribution

Total queries: **2979**  (v4: 2979, v1: 1858)
Mean queries/episode: **59.6**  (v4: 59.6, v1: 37.2)

| Legal actions | Count | % |
|--------------|-------|----|
| 1 (forced) | 1001 | 33.6% |
| 2 | 719 | 24.1% |
| 3 | 614 | 20.6% |
| 4+ | 645 | 21.7% |
| HOLD-only | 0 | 0.0% |

**Real-choice queries (2+):** 1978 (66.4%)

---

## Section 2 — Per-Episode Decision Quality

| Metric | v5 (tight+FT×1) | v4 (tight+FT×2) | v1 (loose) |
|--------|----------------|----------------|------------|
| Mean queries/ep | 59.6 | 59.6 | 37.2 |
| Mean real-choice/ep | 39.56 | 37.5 | 19.82 |
| Min real-choice | 19 | — | 11 |
| Max real-choice | 59 | — | 29 |
| Mean FCFS delay | 83.0 min | 69.5 min | 21.4 min |

| Seed | Queries | Real-choice | Ratio | FCFS Delay | Undep |
|------|---------|-------------|-------|-----------|-------|
| 0 | 62 | 39 | 63% | 80.6 min | 0 |
| 1 | 47 | 27 | 57% | 44.8 min | 0 |
| 2 | 40 | 30 | 75% | 56.6 min | 0 |
| 3 | 51 | 29 | 57% | 72.0 min | 0 |
| 4 | 50 | 33 | 66% | 57.3 min | 0 |
| 5 | 73 | 48 | 66% | 103.6 min | 0 |
| 6 | 74 | 53 | 72% | 131.0 min | 0 |
| 7 | 58 | 39 | 67% | 72.9 min | 0 |
| 8 | 51 | 33 | 65% | 38.7 min | 0 |
| 9 | 68 | 44 | 65% | 83.3 min | 0 |
| 10 | 74 | 49 | 66% | 148.0 min | 0 |
| 11 | 66 | 43 | 65% | 73.9 min | 0 |
| 12 | 65 | 50 | 77% | 129.7 min | 0 |
| 13 | 55 | 27 | 49% | 40.9 min | 0 |
| 14 | 43 | 27 | 63% | 51.2 min | 0 |
| 15 | 51 | 32 | 63% | 65.2 min | 0 |
| 16 | 58 | 40 | 69% | 55.7 min | 0 |
| 17 | 71 | 50 | 70% | 104.2 min | 0 |
| 18 | 48 | 35 | 73% | 52.3 min | 0 |
| 19 | 79 | 59 | 75% | 180.2 min | 0 |
| 20 | 78 | 55 | 71% | 150.0 min | 0 |
| 21 | 46 | 27 | 59% | 38.2 min | 0 |
| 22 | 48 | 39 | 81% | 69.2 min | 0 |
| 23 | 55 | 36 | 65% | 68.2 min | 0 |
| 24 | 62 | 38 | 61% | 111.3 min | 0 |
| 25 | 58 | 40 | 69% | 128.6 min | 0 |
| 26 | 51 | 35 | 69% | 57.0 min | 0 |
| 27 | 78 | 50 | 64% | 100.8 min | 0 |
| 28 | 41 | 26 | 63% | 38.1 min | 0 |
| 29 | 71 | 45 | 63% | 99.5 min | 0 |
| 30 | 71 | 47 | 66% | 95.2 min | 0 |
| 31 | 39 | 25 | 64% | 36.4 min | 0 |
| 32 | 44 | 29 | 66% | 55.2 min | 0 |
| 33 | 73 | 47 | 64% | 170.4 min | 0 |
| 34 | 71 | 53 | 75% | 83.5 min | 0 |
| 35 | 70 | 49 | 70% | 74.5 min | 0 |
| 36 | 59 | 33 | 56% | 59.8 min | 0 |
| 37 | 76 | 57 | 75% | 163.7 min | 0 |
| 38 | 78 | 48 | 62% | 78.6 min | 0 |
| 39 | 51 | 29 | 57% | 45.4 min | 0 |
| 40 | 66 | 46 | 70% | 114.9 min | 0 |
| 41 | 63 | 41 | 65% | 87.6 min | 0 |
| 42 | 79 | 55 | 70% | 153.5 min | 0 |
| 43 | 40 | 27 | 68% | 30.9 min | 0 |
| 44 | 63 | 47 | 75% | 95.9 min | 0 |
| 45 | 53 | 33 | 62% | 41.2 min | 0 |
| 46 | 43 | 19 | 44% | 28.5 min | 0 |
| 47 | 58 | 42 | 72% | 108.4 min | 0 |
| 48 | 67 | 45 | 67% | 84.0 min | 0 |
| 49 | 43 | 28 | 65% | 37.1 min | 0 |

---

## Section 3 — Strategic vs Forced Episodes

| Category | Episodes | % |
|----------|----------|---|
| 0 real-choice | 0 | 0% |
| 1-3 real-choice | 0 | 0% |
| 4-9 real-choice | 0 | 0% |
| 10+ real-choice (rich) | 50 | 100% |

---

## Section 4 — Greedy Optimality Check

Total real-choice queries: **1978**  
Queries beating greedy: **279** (**14.1%**)  
v4 baseline (tight+FT×2): 184/1874 = 9.8%  
v1 baseline (loose): 14/991 = 1.4%

**When a better alternative exists:**
  Mean improvement: **0.722 min**  (v4: not recorded)
  Max improvement: 14.500 min
  Median improvement: 0.100 min

**Per-seed % better distribution:**
  Seeds with 0% better: 1/50
  Seeds with ≥5% better: 42/50
  Seeds with ≥15% better: 21/50
  Std dev of per-seed %: 7.7%

| Seed | Real-choice | Any-better | % better |
|------|-------------|------------|---------|
| 0 | 39 | 7 | 18% |
| 1 | 27 | 5 | 19% |
| 2 | 30 | 9 | 30% |
| 3 | 29 | 7 | 24% |
| 4 | 33 | 6 | 18% |
| 5 | 48 | 7 | 15% |
| 6 | 53 | 15 | 28% |
| 7 | 39 | 4 | 10% |
| 8 | 33 | 1 | 3% |
| 9 | 44 | 6 | 14% |
| 10 | 49 | 2 | 4% |
| 11 | 43 | 6 | 14% |
| 12 | 50 | 6 | 12% |
| 13 | 27 | 0 | 0% |
| 14 | 27 | 8 | 30% |
| 15 | 32 | 2 | 6% |
| 16 | 40 | 6 | 15% |
| 17 | 50 | 8 | 16% |
| 18 | 35 | 1 | 3% |
| 19 | 59 | 7 | 12% |
| 20 | 55 | 12 | 22% |
| 21 | 27 | 1 | 4% |
| 22 | 39 | 7 | 18% |
| 23 | 36 | 5 | 14% |
| 24 | 38 | 3 | 8% |
| 25 | 40 | 7 | 18% |
| 26 | 35 | 6 | 17% |
| 27 | 50 | 2 | 4% |
| 28 | 26 | 4 | 15% |
| 29 | 45 | 3 | 7% |
| 30 | 47 | 10 | 21% |
| 31 | 25 | 3 | 12% |
| 32 | 29 | 6 | 21% |
| 33 | 47 | 4 | 9% |
| 34 | 53 | 11 | 21% |
| 35 | 49 | 2 | 4% |
| 36 | 33 | 2 | 6% |
| 37 | 57 | 6 | 11% |
| 38 | 48 | 6 | 12% |
| 39 | 29 | 3 | 10% |
| 40 | 46 | 13 | 28% |
| 41 | 41 | 8 | 20% |
| 42 | 55 | 11 | 20% |
| 43 | 27 | 1 | 4% |
| 44 | 47 | 6 | 13% |
| 45 | 33 | 4 | 12% |
| 46 | 19 | 1 | 5% |
| 47 | 42 | 5 | 12% |
| 48 | 45 | 12 | 27% |
| 49 | 28 | 2 | 7% |

---

## Section 5 — Verdict

**% better than greedy:** 14.1%  
**Mean improvement when better:** 0.722 min  
**Mean real-choice/episode:** 39.56  
**Mean FCFS delay:** 83.0 min

| Threshold | Verdict |
|-----------|---------|
| ≥15% AND mean improvement ≥0.5 min | Green light — retrain on v5 config |
| 10-15% | Marginal — recommend retraining anyway |
| <10% | Combination didn't compound — need different approach |

### MARGINAL

**10-15%: recommend retraining anyway — signal is real.**

**Does % better cross 15%?** No — 14.1%
**Does mean improvement exceed v4's 0.35 min?** Yes — 0.722 min
**Is the distribution uniform or concentrated?**  
  Seeds with ≥5% better: 42/50 (84%)  
  Seeds with 0% better: 1/50 (2%)  
  Std dev: 7.7% — moderately uniform
