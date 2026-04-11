# MORNING_BRIEFING.md

**Date:** 2026-04-08
**Branch:** fix-decision-trigger

---

## 1. Where We Are

We've exhausted what a reactive policy can do. The v5 2M retrain — with randomized seeds, event-based triggers, HOLD masking, and tight schedule density — produced a policy that wins 3% of the time on a 100-seed battery with a mean delta of -9.1 minutes vs FCFS. The seed randomization fix (FAILURE_DIAGNOSTIC.md) solved the memorization problem from the 500k run, but the policy still converges to a rigid task-reordering heuristic ("baggage-first") because it has no other strategic lever. DECISION_TRIGGER.md Section 5 identified this ceiling months ago: the agent is blind to upcoming arrivals and can't pre-commit resources. The v5 result confirms the diagnosis — the 14.1% greedy-suboptimality headroom measured in the v5 eval (SPEC.md, Session 5) exists, but a reactive agent can't capture it because the optimization requires knowing what's coming next. The anticipation upgrade (ANTICIPATION_DESIGN.md) adds a 600-second lookahead with anticipated tasks and vehicle reservations, giving the agent the information and actions it needs to make proactive scheduling decisions. This is the single largest architectural change since the Gymnasium env was built in Session 2.

---

## 2. Open Questions — Recommended Answers

**Q1. Lookahead horizon: 600s?**
Recommend: **Yes, 600s.** It covers the full APPROACHING -> AT_GATE pipeline (60-300s) with headroom. If we find the agent only uses near-term anticipation, we can shrink it later — but starting small risks missing the value of early reservation for B777 fuel.

**Q2. MAX_ANTICIPATED = 8 slots?**
Recommend: **Yes, 8.** The tight schedule produces 2-3 flights per wave at 0-120s spacing. 8 slots covers the peak of a single wave's anticipated services. Over-allocating slots wastes obs dimensions on zero-padded noise.

**Q3. Stationary reservation vs pre-positioning?**
Recommend: **Stationary for v1.** Pre-positioning is strictly better in theory but doubles the implementation complexity (path planning for estimated gates, rerouting on gate mismatch, partial-travel state tracking). Get the reservation mechanism working and measurably useful first. If win rate hits 30%+ with stationary reservations, pre-positioning becomes the v2 upgrade.

**Q4. Pushback in anticipated tasks?**
Recommend: **Exclude for v1.** Pushback timing depends on departure schedule AND service completion — two unknowns at anticipation time. The single PB1 is also the least contended resource (one pushback per flight, 120s fixed). If we see pushback as a bottleneck in 2M eval, add it then.

**Q5. Fleet size change?**
Recommend: **No change.** FT x1, BT x2, PB x1 is the whole point — anticipation's value proposition is smarter use of scarce resources. If we increase fleet, we reduce the value of anticipation and the gap vs FCFS.

**Q6. Reservation expiry at 2x?**
Recommend: **Start with 2x.** Tight expiry punishes exploration during early training. The -0.5 expiry penalty already discourages over-reserving. We can tighten to 1.5x after seeing the 100k reservation patterns.

**Q7. Event D trigger for anticipated tasks?**
Recommend: **Yes, implement this.** This is not optional — without Event D, the agent is never queried when a new anticipated task appears. The trigger should be: "new anticipated task entered the queue this tick AND a free compatible vehicle exists for its type." Same pattern as Event B but for anticipated_tasks.

**Q8. Network width increase?**
Recommend: **Yes, go to [128, 128].** The current [64, 64] has 64 neurons processing 258 inputs — already a 4:1 compression. At 337 inputs, it becomes 5.3:1 which is aggressive for a task that requires learning temporal relationships between anticipated and current tasks. [128, 128] is the minimal reasonable increase.

---

## 3. Concerns and Inconsistencies

**Concern 1: Auto-assignment bypasses action masking.** When a reservation fulfills (vehicle auto-assigned to materialized task), the assignment happens outside of `step()` — the agent doesn't make this decision. This means the env's internal state changes without going through the normal mask -> action -> assign pipeline. Need to ensure this doesn't create invalid states (e.g., auto-assigning a vehicle that's already en-route to something else). Mitigation: auto-assignment should only fire if the reserved vehicle is still IDLE and not committed to another task.

**Concern 2: Reservation + HOLD masking interaction.** If all pending tasks are assigned and only reservation actions are legal, HOLD should be masked (agent must reserve). But what if the agent shouldn't reserve anything? The current design makes reservation mandatory when it's the only legal action type, which might force poor reservations. Mitigation: consider keeping HOLD legal when only reservation actions (not assignment actions) are legal. This makes HOLD mean "I don't want to assign OR reserve right now," which is a valid choice.

**Concern 3: Anticipated task gate estimation.** For APPROACHING aircraft that don't have an assigned gate yet, we estimate the gate using `_find_nearest_free_gate`. But by the time the aircraft actually lands and gets assigned a gate, other aircraft may have taken that gate. The reservation then targets the wrong location. Impact: low, because the vehicle reservation is stationary (doesn't move until auto-assignment), so the "wrong gate" only affects the obs encoding, not the vehicle's position. But it could confuse the policy during training.

**Concern 4: OBS_DIM jump (258 -> 337) is 31% larger.** This is a significant increase in the curse of dimensionality for the MLP. The anticipated task features include 3-dim one-hot encodings (task type, aircraft size) which are sparse — most of the 72 new dims will be zero most of the time. Consider: could we compress the anticipated task representation? E.g., instead of one-hot, use single normalized values for type and size? That would cut from 9 features/task to 5 features/task, saving 32 dims (72 -> 40, total 305 instead of 337).

**Concern 5: The 600s horizon creates a non-stationary observation during Wave 1 start.** At t=0, most aircraft are still >600s away, so anticipated_tasks is empty. As the first wave approaches, anticipated_tasks fills rapidly. This creates a phase transition in the obs distribution that the policy must learn to handle. Not a blocker, but worth noting for training diagnostics — early-episode behavior may be noisier than mid-episode.

---

## 4. Today's Proposed Plan

| Step | Task | Estimated time | Notes |
|------|------|---------------|-------|
| 1 | **Will reviews ANTICIPATION_DESIGN.md** | 15-30 min | Decide on open questions, especially Q3 (pre-positioning) and Q7 (Event D). Flag any concerns from Section 3. |
| 2 | **Implement Steps 1-4** (anticipated tasks, obs, action mask, reservations) | 4-5 hours | Bulk of the work. Steps 1-4 are tightly coupled so implement together. Include Event D trigger. |
| 3 | **Implement Step 6** (tests) | 2-3 hours | Can partially overlap with step 2 (write tests for anticipated task generation while obs/mask code is being built). |
| 4 | **Smoke test** (Step 7) | 30 min | Quick validation: episodes run, shapes correct, no crashes. |
| 5 | **100k training** (Step 8) | 1 hour | First real signal: is the agent exploring reservations? Reward non-degenerate? |
| 6 | **Evaluate 100k, decide on 2M** | 30 min | If reservation rate > 0% and no crashes, proceed to 2M. If reservation rate = 0%, debug before continuing. |
| 7 | **Launch 2M training** (Step 9) | 6-8 hours (can run overnight) | Start end of day, evaluate tomorrow morning. |

**Total active work today: ~8-10 hours**
**Overnight: 2M training running**
**Tomorrow morning: 100-seed battery on 2M checkpoint**
