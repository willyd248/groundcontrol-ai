# PRE_RETRAIN_CHECKLIST.md

Run through every item before launching a retrain. Check the box and note the
observed value. If any item shows FAIL, fix it before training.

---

## 1. Environment Configuration

- [ ] **Fleet composition** matches target config
  - Expected: FT×1, BT×2, PB×1 (4 vehicles, MAX_VEHICLES=4)
  - Verify: printed at env construction: `FLEET: FT=1 BT=2 PB=1`
  - File: `env/airport_env.py` → `_build_fleet()`

- [ ] **Schedule density** defaults to target mode
  - Expected: `density="tight"` (10-20 flights, 2-3 waves, 0-15 min slack)
  - Verify: printed at env construction: `SCHEDULE_DENSITY: tight`
  - File: `env/airport_env.py` → `AirportEnv.__init__` default, `env/random_schedule.py` → `generate_schedule` default

- [ ] **Observation space** matches fleet size
  - Expected: OBS_DIM=337 (with MAX_VEHICLES=4, post-anticipation upgrade)
  - Note: Updated from 258 → 337 post-anticipation upgrade (+79 dims total). Breakdown of new dims: +4 vehicle is_reserved (1 per vehicle × 4 vehicles), +72 anticipated-task slots (MAX_ANTICIPATED=8 × ANT_FEATURES=9), +3 global anticipation scalars (n_anticipated_norm, n_anticipated_beyond_norm, n_reservations_norm). Steps 2-5.
  - Verify: `python3 -c "from env.airport_env import OBS_DIM; print(OBS_DIM)"`

---

## 2. Action Masking

- [ ] **HOLD masking enabled** — HOLD is illegal when any assignment action is legal
  - Verify: `action_masks()` sets `mask[ACTION_HOLD] = not any_assignment`
  - File: `env/airport_env.py` → `action_masks()`

- [ ] **Action space size** is correct
  - Expected: Discrete(17) — 16 task slots + 1 HOLD
  - Verify: `python3 -c "from env.airport_env import AirportEnv; e=AirportEnv(); print(e.action_space)"`

---

## 3. Seed Strategy (CRITICAL — see FAILURE_DIAGNOSTIC.md)

- [ ] **Training seeds are randomized per episode**
  - Each auto-reset must draw a fresh seed from `self._rng`
  - Verify: run 5k smoke with 8 workers → ≥100 unique schedules (check flight count diversity)
  - FAIL condition: all workers stuck on same schedule (e.g., only 6-8 distinct flight counts in log)
  - File: `env/airport_env.py` → `reset()` branch `seed is None`

- [ ] **Eval seeds are deterministic**
  - Eval callback must pass explicit `seed=N` to `reset(seed=N)`
  - Verify: same eval seed produces identical obs on 3 consecutive resets
  - File: `train/callbacks.py` → `run_policy_episode(model, seed=...)`

- [ ] **Workers produce different sequences**
  - Worker rank seeds `np.random.default_rng(rank)` so each worker explores different schedules
  - Verify: worker 0 and worker 3 produce different seed sequences over 10 resets

---

## 4. Reward Function

- [ ] **Reward constants match spec** (compare against `REWARD_FUNCTION.md`):
  - `REWARD_PER_DELAY_MINUTE = -1.0`
  - `REWARD_ONTIME_DEPARTURE = +10.0`
  - `REWARD_LATE_DEPARTURE = +2.0`
  - `REWARD_HOLD_WITH_WORK = -0.1`
  - `REWARD_CONFLICT = -50.0`
  - `REWARD_CONFLICT_TERMINAL = -200.0`
  - `REWARD_PENDING_AT_TIMEOUT = -20.0`
  - `REWARD_ABANDONMENT = -1.0`
  - File: `env/airport_env.py` top-level constants

---

## 5. Training Infrastructure

- [ ] **Checkpoint frequency** — recovery checkpoints every 50k steps
  - File: `train/train_ppo.py` → `CHECKPOINT_FREQ`
  - Save path: `checkpoints/`

- [ ] **Model snapshot frequency** — official snapshots every 250k steps
  - File: `train/train_ppo.py` → `MODELS_FREQ`
  - Save path: `models/`

- [ ] **Eval frequency** — eval vs FCFS every 50k steps
  - File: `train/train_ppo.py` → `EVAL_FREQ`

- [ ] **Eval seed** matches the selected v5 eval seed
  - Expected: seed=6 (28% suboptimality, 131 min FCFS delay)
  - File: `train/train_ppo.py` → `EVAL_SEED`

- [ ] **Total timesteps** set correctly for intended run length
  - File: `train/train_ppo.py` → `TOTAL_TIMESTEPS` or `--timesteps` CLI arg

- [ ] **VecMonitor wrapping** is enabled (for episode reward/length logging)
  - File: `train/train_ppo.py` → `VecMonitor(SubprocVecEnv(...))`

---

## 6. Quick Smoke Test

- [ ] **5k smoke produces diverse schedules** (≥100 unique across 8 workers)
- [ ] **Zero conflicts** in smoke log (`conflict_term_rate = 0`)
- [ ] **Reward is non-degenerate** (ep_rew_mean not stuck at large negative)

---

## Version History

| Date | Change | Reason |
|------|--------|--------|
| 2026-04-07 | Initial version | Created after discovering 8-fixed-seed training bug (FAILURE_DIAGNOSTIC.md) |
