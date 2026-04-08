# CONTENTION_FIX.md

**Applied:** 2026-04-07  
**Branch:** `fix-decision-trigger`

---

## Final Vehicle Count Change

| Type | Original | v2 (error) | v3 (this fix) | IDs |
|------|----------|------------|---------------|-----|
| FuelTruck | 2 | 3 (wrong direction) | **1** | FT1 |
| BaggageTug | 3 | 3 | **2** | BT1, BT2 |
| PushbackTractor | 2 | 2 | **1** | PB1 |
| **Total** | **7** | **8** | **4** | — |

Observation space: `Box(shape=(270,))` → `Box(shape=(258,))` (3 fewer vehicle slots × 4 features = −12).  
Any pre-existing model checkpoints are **incompatible** with the new obs space.

---

## Error History

### v2 mistake (initial attempt)
The first attempt changed FT×2 → FT×3 (ADDED a fuel truck). This was the wrong direction. The goal was to create resource contention via scarcity; adding a vehicle reduces contention. v2 diagnostic showed 14/991 = 1.4% greedy-suboptimal — byte-for-byte identical to v1. 

Root cause of the error: the Edit tool resolved the absolute path `/Users/willdimaio/Desktop/Airport/env/airport_env.py` to the **main repo** copy, while the worktree at `/Users/willdimaio/Desktop/Airport/.claude/worktrees/festive-almeida/env/airport_env.py` was left unmodified. The main repo was the runtime source of truth for diagnostic scripts (which use `sys.path.insert(0, '/Users/willdimaio/Desktop/Airport')`), but the change was FT×2→FT×3 (wrong direction regardless).

### v3 fix
Reduced to FT×1/BT×2/PB×1. Smoke test confirmed: `FLEET: FT=1 BT=2 PB=1`. Change propagated. v3 diagnostic: 15/996 = 1.5% — still ~1.4%. Vehicle count is not the binding variable.

---

## Reasoning

The goal was to create genuine resource contention so that dispatch order has measurable consequences. Real airports are vehicle-constrained, not flight-constrained.

**Finding from v3 diagnostic:** Even with only 4 vehicles (FT×1, BT×2, PB×1) serving 6–14 flights per schedule, FCFS greedy assignment remains near-optimal at 98.5% of real-choice queries. Reducing vehicle count from 7 to 4 moved the needle by 0.1 percentage points (1.4% → 1.5%).

**Conclusion:** Vehicle count is not the lever. The root cause is schedule structure:
- Flights arrive spread across a 4-hour window
- At each decision point, competing tasks are for different service types or different gates
- The "nearest vehicle" heuristic is trivially correct when task-vehicle distance dominates timing considerations
- 600-second lookahead window sees too little future structure to differentiate greedy from alternatives

---

## What Must Change Instead

| Option | Expected impact | Complexity |
|--------|----------------|------------|
| Denser schedules (more simultaneous arrivals, tighter windows) | High — creates real queuing | Medium |
| Asymmetric service durations (B777 fuel: 120s, CRJ900: 20s) | Medium — makes priority matter | Low |
| Both above simultaneously | Highest | Medium |

See `LEGAL_ACTION_DIAGNOSTIC_v3.md` Section 5 for the full verdict.

---

## Files Changed

- `env/airport_env.py`: `_build_fleet()` + `MAX_VEHICLES` + docstring + `OBS_DIM` comment
- `SPEC.md`: obs shape, slice table, fleet reference
- `LEGAL_ACTION_DIAGNOSTIC_v2.md`: v2 run (FT×3, wrong direction)
- `LEGAL_ACTION_DIAGNOSTIC_v3.md`: v3 run (FT×1/BT×2/PB×1, confirmed propagation)
