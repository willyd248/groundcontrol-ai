# OVERNIGHT SUMMARY
**Date:** 2026-04-11  
**Session:** overnight autonomous run  
**Branch:** fix-decision-trigger  

---

## Phase 1 — v5_anticipation_final Comprehensive Evaluation

**Result: COMPLETED**  
**Verdict: HEALTHY**

### Key Numbers
| Metric | Value |
|--------|-------|
| Hard battery wins (seeds 0-49) | 12/50 (24%) |
| OOD battery wins (seeds 200-249) | 9/50 (18%) |
| Combined win rate | 21/100 (21%) |
| Hard mean delta (FCFS-RL) | -0.3 min |
| OOD mean delta | -0.5 min |
| Combined mean delta | -0.4 min |
| Combined median delta | -0.1 min |
| Best seed | 48 (+9.2 min) |
| Worst seed | 14 (-9.3 min) |
| Conflicts | 0 |
| Abandonments | 0 |

### Milestone Trace Completion (1M-2M)
| Milestone | Wins/5 | Mean Delta | Conflicts |
|-----------|--------|-----------|-----------|
| 1M | 0/5 | -0.2m | 0 |
| 1.25M | 0/5 | -0.3m | 0 |
| 1.5M | 1/5 | +1.6m | 0 |
| 1.75M | 0/5 | -0.3m | 0 |
| 2M | 1/5 | +1.6m | 0 |

### Notable Finding
The v5_anticipation policy uses reservations during training (5-10% rate in stochastic exploration) but the deterministic eval policy learned a pure assignment strategy — reservation rate is ~0% in deterministic rollouts except occasional outliers. Despite this, the policy achieves 21% win rate and near-parity with FCFS (-0.4m mean delta), satisfying HEALTHY criteria (≥10% win rate AND mean delta > -5m). This represents a dramatic improvement over the reactive v5 baseline (3% win rate, -9.1m mean delta).

---

## Phase 2 — v5_anticipation_v2 Retrain with Tuned Expiry Penalty

**Result: COMPLETED**  
**Verdict: WORSE** (vs V1)

### Configuration
- Gate: HEALTHY → REWARD_EXPIRED_RESERVATION tuned from -0.5 to -1.0
- Training: 2M steps, 8 workers, checkpoints every 250k
- Pre-retrain checklist: ALL PASSED
- Structural stops during training: NONE (zero conflicts/abandonments throughout)

### Key Numbers
| Metric | V1 | V2 | Change |
|--------|----|----|--------|
| Combined wins | 21/100 | 3/100 | -18 |
| Combined mean delta | -0.4m | -1.3m | -0.9m |
| Hard wins | 12/50 | 2/50 | -10 |
| OOD wins | 9/50 | 1/50 | -8 |
| Conflicts | 0 | 0 | 0 |
| Abandonments | 0 | 0 | 0 |

### Analysis
The stronger expiry penalty (-1.0 vs -0.5) made the policy more risk-averse about reservations. However, this overcorrected — the policy both made fewer reservations AND made worse assignment decisions on some seeds. The V2 eval on single-seed (seed 6) training callback showed consistent near-parity (-0.1m to -0.7m range throughout training), but the multi-seed evaluation reveals the V2 generalization is worse than V1.

**Recommendation: Use v5_anticipation_final.zip as the production model.** V1 achieves HEALTHY criteria and is strictly better than V2.

---

## Phase 3 — KAUS Slice Real-Data Smoke Run

**Result: SKIPPED**

- `phase-3-ingest` branch exists in the remote list
- `data/schedules/kaus_slice_*.json` files do NOT exist on disk
- Per instructions: skipped when data doesn't exist

---

## Total Wall Time

~12 hours (Phase 1: ~5 min, Phase 2 training: ~11.5 hours, Phase 2 eval: ~1 min, Phase 3: skipped)

---

## What to Read First

1. **PHASE_1_VERDICT.txt** — `HEALTHY` (one line)
2. **POLICY_HEALTH_ANTICIPATION_FINAL.md** — full 100-seed battery for V1, milestone trace, reservation analysis
3. **PHASE_2_VERDICT.txt** — `WORSE` (one line)
4. **POLICY_HEALTH_ANTICIPATION_V2_FINAL.md** — side-by-side V1 vs V2 comparison table
5. **MILESTONE_TRACE_ANTICIPATION.md** — now complete from 250k through 2M with TensorBoard metrics

---

## What to Do Next

### Immediate (high priority)
1. **Keep v5_anticipation_final.zip as the production model.** It achieves 21% win rate at near-parity with FCFS. V2 is worse — do not use it.

2. **Investigate why deterministic policy doesn't use reservations.** During training (stochastic), the 250k checkpoint uses reservations at ~8% rate. In deterministic eval, this collapses to ~0%. This suggests the reservation benefit is marginal and gets averaged out — the policy discovers that deterministic assignment without reservation is nearly optimal. This is not a bug; it means the anticipation capability is learned but the agent has learned that FCFS-like greedy assignment is already near-optimal for the current fleet/schedule combo.

3. **Consider increasing schedule tightness.** The v5 fleet (FT×1, BT×2, PB×1) with 10-20 tight flights may not have enough genuine contention for reservations to matter. Seeds where RL beats FCFS (21/100) are likely high-contention scenarios with multiple competing demands. To make reservations more valuable, consider:
   - Increasing flight density (tighter schedules, more simultaneous waves)
   - Adding arrival-only flights (makes BT utilization more contested)
   - Tightening departure slack further

4. **Do NOT retrain with -1.5 expiry penalty.** V2 (-1.0) was already worse than V1 (-0.5). Increasing further will only reduce reservation usage more.

### Medium priority
5. **Run full 100-seed battery on v5_2m_final.zip (reactive baseline).** The PRE_RETRAIN_CHECKLIST references -9.1m mean delta for the reactive policy. Confirming this with the same 100-seed methodology establishes a clean baseline for comparing anticipation improvement.

6. **Phase 3 KAUS data.** If `data/schedules/kaus_slice_*.json` can be generated (from KAUS ASDE-X or synthetic from real schedules), run the Phase 3 smoke to test real-world generalization.

### If retraining (lower priority)
7. **If retraining for better reservation utilization:** revert REWARD_EXPIRED_RESERVATION to -0.5, but change the reservation observation to include distance-to-expiry (currently `time_until_actionable / 600`). If the agent sees that reservations have a time budget, it may learn to time them better.
