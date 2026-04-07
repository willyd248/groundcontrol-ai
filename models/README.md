# models/ — Saved Policy Checkpoints

## session5_masked_smoke_250k.zip
250k smoke retrain with HOLD masking (HOLD illegal when assignments exist). HOLD rate = 0% on all 5 eval seeds (42, 100, 106, 110, 116). Matches FCFS exactly — no divergence observed. Reward stable 64.8–65.3 from step 0, starting from prior weights (warm start). Zero conflicts. Use as gate-pass baseline before full 2M retrain.

**Health check results:** reward rising ✅ | HOLD rate 0% on all seeds ✅ | matches FCFS seed=42 ✅ | beats FCFS on 0/4 hard seeds ✗ (expected at 250k — no divergence is the pass criterion).

## session5_reactive_300k.zip
Pre-divergence reactive baseline. HOLD rate ~0% on eval. Matches FCFS, occasional 1-2 min wins on high-choice schedules (seed=116: −2.1 min at 300k). Use as comparison floor for future training runs. See `CHECKPOINT_1M_BATTERY.md` Section 2 for the 300k delta table.

## session5_fixed_step_250000_steps.zip
Intermediate snapshot at 250k steps. Policy not yet beating FCFS. Saved for reference.

## session5_fixed_step_500000_steps.zip
Intermediate snapshot at 500k steps. HOLD behavior beginning to emerge on high-choice schedules (seed=116: 22.7% HOLD), but not yet translating to delay improvement. Matches FCFS on eval seed=42.

## session5_fixed_step_1000000_steps.zip
Intermediate snapshot at 1M steps (same as session5_reactive_diverged.zip). See below.

## session5_reactive_diverged.zip
**DO NOT USE FOR PRODUCTION.**

Copy of `checkpoints/airport_ppo_1000000_steps.zip`. Training was killed at 1M steps after this checkpoint showed active regression.

**What went wrong:** The policy learned to HOLD aggressively on high-choice-tick schedules (36–41% HOLD rate on seeds 103, 106, 110, 112, 116) but the HOLDs were counter-productive — adding delay instead of reducing it. Performance on the 20-seed hard battery (seeds 100–119) regressed from:
- 300k: 1/20 beats FCFS, mean delta −0.07 min
- 1M: 0/20 beats FCFS, mean delta +0.39 min

seed=116 trajectory: −2.1 min (300k) → +0.0 min (500k) → +3.5 min (1M)

**Root cause hypothesis:** Training schedules (seeds 0–49 drawn from `generate_schedule()`) have very few real choice ticks. The policy never received consistent positive gradient from beneficial HOLDs, so it learned a noisy HOLD-on-complexity heuristic that generalises poorly.

**Evidence:** See `CHECKPOINT_1M_BATTERY.md`, `EVAL_DIAGNOSTIC.md`, and `TRAINING_DISTRIBUTION_DIAGNOSTIC.md`.

**Training was killed at 1M/2M steps on 2026-04-07 after this diagnosis.**
