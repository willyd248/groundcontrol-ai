# CONTENTION_FIX.md

**Applied:** 2026-04-07  
**Branch:** `fix-decision-trigger`

---

## Current Configuration (v5)

| Type | Count | IDs |
|------|-------|-----|
| FuelTruck | **1** | FT1 |
| BaggageTug | **2** | BT1, BT2 |
| PushbackTractor | **1** | PB1 |
| **Total** | **4** | — |

Schedule density: **tight** (10–20 flights, 2–3 waves, 0–15 min slack).  
Observation space: `Box(shape=(258,))` (4 vehicles × 4 features = 16 vehicle features).  
Any pre-existing checkpoints are incompatible with this obs shape.

---

## Diagnostic History

| Version | Fleet | Density | % better | Mean improvement |
|---------|-------|---------|---------|-----------------|
| v1 | FT×2/BT×3/PB×2 (7) | loose | 1.4% | — |
| v2 | FT×3/BT×3/PB×2 (8) | loose | 1.4% | — (wrong direction) |
| v3 | FT×1/BT×2/PB×1 (4) | loose | 1.5% | — |
| v4 | FT×2/BT×2/PB×2 (6) | tight | 9.8% | — |
| **v5** | **FT×1/BT×2/PB×1 (4)** | **tight** | **14.1%** | **0.722 min** |

---

## Root Cause Summary

**v1–v3:** Vehicle count alone could not move the needle past 1.5%. With loose
schedules, every flight had 29–175 min of slack. Service ordering cannot
produce measurable downstream differences when there are 30+ minutes of buffer.

**v3→v4:** Switching to tight density (10–20 flights, 0–15 min slack) moved
% better from 1.5% → 9.8%. Mean FCFS delay: 21.4 → 69.5 min. The schedule
structure was the binding constraint, not fleet size.

**v4→v5:** Reducing fleet from 6 to 4 vehicles (combining both changes) moved
% better from 9.8% → 14.1%. Mean improvement when non-greedy wins: 0.722 min.
Zero undeparted flights across all 50 seeds.

---

## Verdict

**MARGINAL (10–15%).** 14.1% is just below the 15% green-light threshold but
the mean improvement (0.722 min) clears the 0.5 min quality bar. The signal is
real and consistent: 47/50 seeds have at least one suboptimal greedy choice;
only seed=13 has 0 any-better forks.

**Recommendation:** Proceed with 2M retrain on v5 config. The signal is
strong enough for RL to learn from — 14.1% of real-choice queries have a
non-greedy alternative that saves 0.72 min on average, mean FCFS delay is
83.0 min giving a large reward range to exploit.

---

## Reasoning

The goal was to create genuine resource contention so that dispatch order has
measurable consequences. Real airports are vehicle-constrained, not
flight-constrained. v5 achieves this via two compounding changes:

1. **Tight schedules:** flights arrive in waves with 0–15 min of slack, so
   delayed service causes missed departure windows
2. **Reduced fleet:** 1 fuel truck and 1 pushback tractor force sequential
   servicing of simultaneous demand — the order genuinely matters

---

## Files Changed

- `env/airport_env.py`: `_build_fleet()` (FT×1/BT×2/PB×1), `MAX_VEHICLES=4`,
  obs shape 266→258, `density` param + construction print
- `env/random_schedule.py`: `density` param, `"tight"` mode as default
- `SPEC.md`: obs shape, slice table, fleet reference
- `LEGAL_ACTION_DIAGNOSTIC_v[2-5].md`: progressive diagnostic results
- `SCHEDULE_DENSITY.md`: slack analysis and tight mode parameters
