# SCHEDULE_DENSITY.md

**Generated:** 2026-04-07  
**Branch:** `fix-decision-trigger`

---

## Section 1 — Current (Loose) Schedule Parameters

| Parameter | Value |
|-----------|-------|
| `n_flights` | 6–14 (uniform random) |
| First arrival | 0–600 s (0–10 min) into sim |
| Inter-arrival gap | 400–1800 s (6.7–30 min) |
| `dep_only` probability | 20% |
| `dep_only` departure time | 1800–10 800 s (30 min – 3 h) |
| B737/A320 turnaround | 2700–4500 s (45–75 min) |
| B777 turnaround | 3600–5400 s (60–90 min) |
| CRJ900 turnaround | 2100–3600 s (35–60 min) |

---

## Section 2 — Minimum Parallel Service Times

Fuel truck (FT), baggage unload (BT1), and baggage load (BT2) are dispatched
concurrently when vehicles are available. The minimum time to complete all
ground services = max(fuel_time, unload_time, load_time).

| Aircraft | fuel (s) | unload (s) | load (s) | min_service (s) | min_service (min) |
|----------|----------|------------|----------|----------------|-------------------|
| B737     | 50       | 60         | 60       | **60**         | 1.0               |
| A320     | 45       | 55         | 55       | **55**         | 0.9               |
| B777     | 120      | 150        | 150      | **150**        | 2.5               |
| CRJ900   | 20       | 30         | 30       | **30**         | 0.5               |

---

## Section 3 — Slack Distribution (Loose Mode, Seeds 0–49)

**slack = scheduled_departure − arrival_time − min_parallel_service_time**

| Metric | Value |
|--------|-------|
| N flights (total, 50 seeds) | 493 |
| Min slack | **29.2 min** |
| Max slack | 174.6 min |
| Mean slack | 65.5 min |
| Median slack | 59.7 min |
| p10 | 44.1 min |
| p25 | 49.5 min |
| p75 | 71.2 min |
| p90 | 90.5 min |

| Slack bucket | % of flights |
|--------------|-------------|
| < 10 min | **0.0%** |
| < 20 min | **0.0%** |
| < 30 min | 0.2% |
| ≥ 30 min | **99.8%** |

**Smoking gun:** Zero flights have <10 min slack. Zero have <20 min slack. The minimum slack across all 493 flights over 50 seeds is 29.2 minutes. With service times of 0.5–2.5 minutes, the ratio of slack to service time is 12×–60×. Service ordering cannot possibly matter when there is 30+ minutes of buffer on every flight.

### Turnaround distribution

| Metric | Value |
|--------|-------|
| Min turnaround | 36.2 min |
| Max turnaround | 89.6 min |
| Mean turnaround | 60.7 min |
| Median turnaround | 59.5 min |

### Inter-departure gap distribution

| Metric | Value |
|--------|-------|
| N gaps (total) | 443 |
| Min gap | 0.0 min |
| Max gap | 60.9 min |
| Mean gap | 16.2 min |
| Median gap | 12.6 min |
| < 10 min gaps | 42.4% |

---

## Section 4 — Tight Mode Parameters

| Parameter | Loose | Tight |
|-----------|-------|-------|
| `n_flights` | 6–14 | **10–20** |
| Arrival structure | Even spacing | **2–3 waves** |
| Within-wave gap | 400–1800 s | **0–120 s** |
| Between-wave gap | N/A | **1800–3600 s** |
| `dep_only` probability | 20% | **10%** |
| `dep_only` departure | 1800–10 800 s | **600–3600 s** |
| B737/A320 turnaround | 2700–4500 s | **60–660 s (1–11 min)** |
| B777 turnaround | 3600–5400 s | **150–1050 s (2.5–17.5 min)** |
| CRJ900 turnaround | 2100–3600 s | **30–330 s (0.5–5.5 min)** |

**Tight turnaround formula:** `min_service_time + rng.randint(lo, hi)`

| Aircraft | buffer range | resulting slack |
|----------|-------------|----------------|
| B737 | 0–600 s | 0–10 min |
| A320 | 0–600 s | 0–10 min |
| B777 | 0–900 s | 0–15 min |
| CRJ900 | 0–300 s | 0–5 min |

---

## Section 5 — Tight Mode Smoke Test (Seed 0)

| Metric | Tight (seed=0) | Loose (seed=0) |
|--------|----------------|----------------|
| Flights | 16 | 12 |
| Dep window | 6.8–125.0 min | 69.6–281.3 min |
| Min inter-dep gap | 0.1 min | 2.0 min |
| Mean inter-dep gap | 7.9 min | 19.2 min |
| Min slack | 1.1 min | 44.9 min |
| Mean slack | 8.4 min | 62.3 min |
| < 5 min slack | 56% | 0% |
| < 10 min slack | 88% | 0% |
| ≥ 30 min slack | 12% | 100% |

**FCFS episode (seed=0):**

| Metric | Tight | Loose (v1) | Change |
|--------|-------|-----------|--------|
| Delay | 77.90 min | 24.20 min | +222% |
| Queries | 62 | 47 | +32% |
| Real-choice queries | 41 | 24 | +71% |
| Undeparted | 0 | 1 (horizon) | — |

---

## Section 6 — Verdict

See `LEGAL_ACTION_DIAGNOSTIC_v4.md` for Section 4 greedy-optimality result.

The tight mode structurally changes the problem: flights compete for the same vehicles at the same time, ordering decisions have immediate cascade effects on departure delays, and the 77.90 min delay (vs 24.20 min loose) provides a much richer reward signal for RL.
