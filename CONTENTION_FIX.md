# CONTENTION_FIX.md

**Applied:** 2026-04-07  
**Branch:** `fix-decision-trigger`

---

## Vehicle Count Change

| Type | Old count | New count | IDs |
|------|-----------|-----------|-----|
| FuelTruck | 2 | **3** | FT1, FT2, FT3 |
| BaggageTug | 3 | 3 | BT1, BT2, BT3 |
| PushbackTractor | 2 | 2 | PB1, PB2 |
| **Total** | **7** | **8** | — |

Observation space: `Box(shape=(270,))` → `Box(shape=(274,))` (4 new vehicle-slot features).  
Any pre-existing model checkpoints are **incompatible** with the new obs space and cannot be loaded without retraining.

---

## Reasoning

`LEGAL_ACTION_DIAGNOSTIC.md` (v1, seeds 0–49, FT×2/BT×3/PB×2) showed:

- **1.4%** of real-choice queries had a non-greedy alternative that produced lower delay.
- FCFS greedy assignment order was optimal or near-optimal on **98.6%** of queries.
- Mean real-choice queries per episode: 19.82 (frequency is adequate; quality of choice is the problem).

The root cause: with 2 fuel trucks and 3 baggage tugs serving 6–14 flights per schedule, the fleet is rarely a binding constraint. Most assignment decisions are "assign the closest vehicle to this task" — and the closest vehicle is almost always also the optimal vehicle, because no other task is competing for it right now.

**The goal is to create genuine resource contention so that dispatch order has measurable consequences.** If two flights need fuel simultaneously and only 2 fuel trucks exist, the order in which they are served matters — one flight gets delayed, and choosing which one is delayed has downstream consequences (pushback sequencing, gate conflicts). Real airports are vehicle-constrained, not flight-constrained, so this aligns the sim with reality.

Adding a third fuel truck was the minimal intervention: fuel tasks are the longest-duration services (gallons/rate-limited), so fuel truck contention is the highest-leverage bottleneck. Baggage tugs (3) and pushback tractors (2) are unchanged.

---

## Files Changed

- `env/airport_env.py`: `_build_fleet()` + `MAX_VEHICLES` + docstring + `OBS_DIM` comment
- `sim/main.py`: `build_fleet()`
- `SPEC.md`: obs shape, slice table, fleet reference

---

## Verification

See `LEGAL_ACTION_DIAGNOSTIC_v2.md` for Section 4 greedy-optimality result on new config.  
Target: ≥15% of real-choice queries have a strictly better non-greedy alternative.
