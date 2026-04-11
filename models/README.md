# models/ — Saved Policy Checkpoints

Binary `.zip` files are excluded from git (see `.gitignore`). This README is the documentation layer. Each entry records what the file contains and when it was created.

---

## Reactive Baseline (session5 era — Apr 7 2026)

### session5_masked_smoke_250k.zip
250k smoke retrain with HOLD masking (HOLD illegal when assignments exist). HOLD rate = 0% on all 5 eval seeds (42, 100, 106, 110, 116). Matches FCFS exactly — no divergence observed. Reward stable 64.8–65.3 from step 0, starting from prior weights (warm start). Zero conflicts. Gate-pass baseline before full 2M retrain.

### session5_reactive_300k.zip
Pre-divergence reactive baseline. HOLD rate ~0% on eval. Matches FCFS, occasional 1-2 min wins on high-choice schedules (seed=116: −2.1 min at 300k). Comparison floor for future training runs. See `CHECKPOINT_1M_BATTERY.md` for the 300k delta table.

### session5_reactive_diverged.zip
**DO NOT USE FOR PRODUCTION.** Copy of `checkpoints/airport_ppo_1000000_steps.zip`. Training killed at 1M steps — policy learned destructive HOLD behaviour (36–41% HOLD rate on hard seeds). Performance on 20-seed battery regressed from −0.07 min delta (300k) to +0.39 min delta (1M). Root cause: training seeds 0–49 have too few real choice ticks. See `FAILURE_DIAGNOSTIC.md`.

### session5_v5_500k_stalled.zip
v5 config (FT×1 BT×2 PB×1, tight schedule) at 500k steps. Training stalled — reward plateau before meaningful FCFS improvement. Kept as reference for v5 config iteration.

### session5_v5_final.zip
v5 config final policy before the v5_2m retrain. Suboptimality ~14.1%, mean delta +22.2m vs FCFS. Used as warm start for v5_2m run.

---

## v5 Reactive — Full 2M Run (Apr 7-8 2026)

Trained with: `python -m train.train_ppo --timesteps 2000000 --n-envs 8 --name-prefix v5_2m`  
Config: FT×1 BT×2 PB×1, tight schedule density, randomised seeds per episode.

### v5_2m_step_250000_steps.zip
v5_2m milestone at 250k steps. ep_rew_mean rising from baseline.

### v5_2m_step_500000_steps.zip
v5_2m milestone at 500k steps.

### v5_2m_step_750000_steps.zip
v5_2m milestone at 750k steps.

### v5_2m_step_1000000_steps.zip
v5_2m milestone at 1M steps.

### v5_2m_step_1250000_steps.zip
v5_2m milestone at 1.25M steps.

### v5_2m_step_1500000_steps.zip
v5_2m milestone at 1.5M steps.

### v5_2m_step_1750000_steps.zip
v5_2m milestone at 1.75M steps.

### v5_2m_step_2000000_steps.zip
v5_2m milestone at 2M steps (final checkpoint before end-of-run save).

### v5_2m_final.zip
**v5 reactive final model.** End-of-run save at 2M steps. Hard battery mean delta +22.2m vs FCFS. Zero conflicts, zero abandonments. Renamed `v5_2m_final_REACTIVE_BASELINE.zip` after anticipation upgrade began.

### v5_2m_final_REACTIVE_BASELINE.zip
Alias/copy of `v5_2m_final.zip`. Explicit name to distinguish from anticipation model during side-by-side evaluation.

---

## v5 Anticipation — Full 2M Run (Apr 8 2026)

Trained with: `python -m train.train_ppo --timesteps 2000000 --n-envs 8 --name-prefix v5_anticipation`  
Config: Same v5 base + reservation actions (OBS_DIM=337, Discrete(25), anticipation reward signals).  
Run completed: Apr 8 20:28. tfevents in `runs/AirportPPO_anticipation_2M/`.

### v5_anticipation_step_250000_steps.zip
Anticipation model at 250k steps. ep_rew_mean=18.75. Hard battery mean delta +24.9m vs FCFS. Reservation expiry rate 75% (policy still learning when to reserve). Eval seed 6 gap +23.7m.

### v5_anticipation_step_500000_steps.zip
Anticipation model at 500k steps. ep_rew_mean=28.97. Hard battery mean delta +17.8m. Reservation conversion rate improving (29.6%). Expiry rate 70.4%.

### v5_anticipation_step_750000_steps.zip
Anticipation model at 750k steps. ep_rew_mean=35.23. Hard battery mean delta +15.8m. Reservation expiry rate drops to 65.4% — policy making better reservation decisions. Eval see MILESTONE_TRACE_ANTICIPATION.md.

### v5_anticipation_step_1000000_steps.zip
Anticipation model at 1M steps. ep_rew_mean=31.38. (Slight dip — normal PPO variance.) Milestone battery evaluation not yet run — see MILESTONE_TRACE_ANTICIPATION.md.

### v5_anticipation_step_1250000_steps.zip
Anticipation model at 1.25M steps. ep_rew_mean=33.34. Milestone battery evaluation pending.

### v5_anticipation_step_1500000_steps.zip
Anticipation model at 1.5M steps. ep_rew_mean=36.21. Milestone battery evaluation pending.

### v5_anticipation_step_1750000_steps.zip
Anticipation model at 1.75M steps. ep_rew_mean=42.37 (peak of run). Milestone battery evaluation pending.

### v5_anticipation_step_2000000_steps.zip
Anticipation model at 2M steps. ep_rew_mean=39.44. Milestone battery evaluation pending.

### v5_anticipation_final.zip
**v5 anticipation final model. PRIMARY ARTIFACT.** End-of-run save at 2,015,232 steps. ep_rew_mean=39.44 (vs -75.92 at training start). explained_variance=0.871. Zero conflicts, zero abandonments at final eval. eval/rl_total_delay_min=118.9 vs eval/fcfs_total_delay_min=102.5 on eval seed 6 (hardest seed — this seed is structurally disadvantaged for RL). Milestone hard-battery evaluations for 1M–2M pending (see MILESTONE_TRACE_ANTICIPATION.md).
