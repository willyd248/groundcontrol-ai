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

- [ ] **HOLD masking enabled** — HOLD is illegal when ANY actionable action exists (assignment OR reservation), not just assignments
  - Verify: `action_masks()` sets `mask[ACTION_HOLD] = not any_actionable`
  - Note: `any_actionable` is True if any assignment action (0-15) OR any reservation action (16-23) is legal. HOLD is only available when zero pending tasks AND zero compatible anticipated tasks exist.
  - File: `env/airport_env.py` → `action_masks()`

- [ ] **Action space size** is correct
  - Expected: Discrete(25) — 16 assign actions (0-15) + 8 reservation actions (16-23) + 1 HOLD action (24)
  - Actions 0-15: assign pending task slot N to a free compatible vehicle
  - Actions 16-23: reserve a free vehicle for anticipated_tasks[action-16] (pre-commit before task becomes active)
  - Action 24: HOLD — do nothing, advance sim one tick
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
  - `REWARD_FULFILLED_RESERVATION = +1.0` — fires when a reserved vehicle auto-converts to a real assignment (anticipated task becomes active and reserved vehicle is assigned)
  - `REWARD_EXPIRED_RESERVATION = -0.5` — fires when a reservation expires unused (anticipated task's window closes without the flight appearing, or vehicle reassigned)
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

- [ ] **Conflict terminates episode** — verify env terminates on first conflict (not just penalty)
  - Expected: `REWARD_CONFLICT_TERMINAL = -200.0` fires AND `terminated=True` is returned on the conflict tick
  - The episode does NOT continue after the first conflict (`_conflict_terminated` flag is set)
  - Subsequent conflicts in the same tick get `-50.0` each (REWARD_CONFLICT) but are rare
  - File: `env/airport_env.py` → `_compute_tick_reward()` conflict block, `step()` → `terminated` logic
  - Verify: `info["conflict_terminated"] == True` on any episode that ends with a conflict

---

## 8. Reservation Conversion Invariant

- [ ] **Reserved vehicles match BEFORE tasks hit pending queue**
  - When an anticipated task becomes active (flight arrives), the dispatcher must check reserved vehicles first and assign the reservation before adding to pending
  - Verify: in `sim/dispatcher.py` → `_update_anticipated_tasks()`, reserved vehicle is converted to ServiceTask and removed from anticipated_tasks before pending queue processes new arrivals
  - FAIL condition: a reserved vehicle ends up idle while the same flight's task sits in pending queue

- [ ] **Silent conversion does NOT trigger an agent query cycle**
  - Reservation auto-conversion is handled entirely inside `RLDispatcher._create_service_tasks()` — the task is moved from pending to active before control returns to the env, so no additional agent decision point is created
  - Verify: `test_silent_conversion_no_extra_agent_query` in `tests/test_anticipated.py` must pass before any retrain. The test asserts this by confirming no additional decision points are created when a reservation auto-converts.
  - File: `env/airport_env.py` → `RLDispatcher._create_service_tasks()` override (conversion is inline, not via agent step)

- [ ] **Reservation expiry fires correctly**
  - When a reservation's anticipated task expires (aircraft departs or window closes), `vehicle.reserved_for` is cleared and `REWARD_EXPIRED_RESERVATION` fires
  - Verify: `tests/test_anticipated.py` expiry tests pass
  - File: `env/airport_env.py` → expiry loop in `_compute_tick_reward()`

---

## 9. Checkpoint Name Prefix

- [ ] **`--name-prefix` is wired into ALL checkpoint paths**
  - Recovery checkpoints: `checkpoints/{prefix}/{prefix}_recovery_{N}_steps.zip`
  - Milestone snapshots: `models/{prefix}_step_{N}_steps.zip`
  - Final model: `models/{prefix}_final.zip`
  - File: `train/train_ppo.py` → `CheckpointCallback` constructions and `final_path`

- [ ] **Startup CHECKPOINT CONFIGURATION block is printed before training begins**
  - Verify: running `python -m train.train_ppo --name-prefix test_run --timesteps 1` prints:
    ```
    CHECKPOINT CONFIGURATION
      Name prefix:          test_run
      Recovery checkpoints: <abs_path>/checkpoints/test_run/
      Milestone snapshots:  <abs_path>/models/test_run_step_*.zip
      Final model:          <abs_path>/models/test_run_final.zip
      Working directory:    <abs_path>
    ```
  - File: `train/train_ppo.py` → startup print block

- [ ] **Training writes to the correct directory (worktree-local, not main repo)**
  - When running in a git worktree, verify `Working directory` line shows the worktree path, NOT the main repo path
  - Danger: main repo `models/` may contain baseline files with the same prefix — collision detection will catch this, but verify manually if running with `--force-overwrite`

---

## 10. Collision Detection

- [ ] **Training refuses to start if model files match the name prefix pattern**
  - Expected: `sys.exit(1)` with `COLLISION DETECTED` message if `models/{prefix}_step_*.zip` or `models/{prefix}_final.zip` already exists
  - File: `train/train_ppo.py` → collision detection block (uses `glob.glob`)

- [ ] **`--force-overwrite` bypasses the collision guard with a warning**
  - Expected: prints `WARNING: --force-overwrite active. N existing file(s) will be overwritten.` and continues
  - Only use when intentionally retraining from scratch with the same prefix
  - File: `train/train_ppo.py` → `args.force_overwrite` branch

- [ ] **No existing files match the new run's checkpoint path pattern before launch**
  - Check: `ls models/{prefix}_step_*.zip models/{prefix}_final.zip 2>/dev/null`
  - Either confirm no collision OR confirm `--force-overwrite` is intentionally passed

---

## Version History

| Date | Change | Reason |
|------|--------|--------|
| 2026-04-07 | Initial version | Created after discovering 8-fixed-seed training bug (FAILURE_DIAGNOSTIC.md) |
| 2026-04-08 | Added Section 7 (Checkpoint Path Integrity) in great-faraday branch | v5_anticipation 2M run used hardcoded `airport_ppo` recovery prefix, masking which run owned which checkpoints |
| 2026-04-11 | Gate 3 audit: OBS_DIM 258→337; Gate 3 Phase B: all 7 stale items resolved — action space, HOLD mask, conflict termination, reservation rewards, conversion invariant (Sec 8), name prefix (Sec 9), collision detection (Sec 10) | Anticipation upgrade (Steps 2-5) changed obs/action space; fixes from great-faraday cherry-picked |
