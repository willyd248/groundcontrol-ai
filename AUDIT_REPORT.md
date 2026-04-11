# AIRPORT RL PROJECT — AUDIT REPORT

**Generated:** 2026-04-11  
**Auditor:** Claude Code (read-only audit, no modifications to source)  
**Repo root:** `/Users/willdimaio/Desktop/Airport`

---

## SECTION 1 — Branch State

### Active Branch

`fix-decision-trigger` at commit `64cad41` (feat: Step 5 — REWARD_FULFILLED_RESERVATION=+1.0, REWARD_EXPIRED_RESERVATION=-0.5, wired into _compute_tick_reward)

### Git Status (on fix-decision-trigger)

**Modified files (not staged):**
- `.gitignore`
- `env/smoke_test.py`
- `sim/__pycache__/` (6 compiled .pyc files)

**Untracked files of note (not committed, not gitignored):**
- `.claude/` directory
- `ANTICIPATION_DESIGN.md`
- `MILESTONE_TRACE.md`
- `MORNING_BRIEFING.md`
- `POLICY_HEALTH_V5_FINAL.md`
- `checkpoints/` — 40 checkpoint files (airport_ppo_50000_steps.zip through airport_ppo_2000000_steps.zip)
- `models/` — 9 model files (session5_v5_final.zip, v5_2m_final.zip, v5_2m_final_REACTIVE_BASELINE.zip, v5_2m_step_*.zip)
- `runs/` — TensorBoard event directory
- `tests/test_anticipated.py`
- `train/milestone_diagnostic.py`

**Critical observation:** The bulk of the RL artifacts — all 40+ checkpoint files, all model ZIPs, all key design docs (ANTICIPATION_DESIGN.md, MILESTONE_TRACE.md, POLICY_HEALTH_V5_FINAL.md, MORNING_BRIEFING.md), and the new test file (test_anticipated.py) — are **untracked and would be lost on a fresh clone.** The `.gitignore` only ignores `.DS_Store`, `*.log`, `node_modules/`, `.env`, `.env.local`, `.vercel`.

### Total Branches

- **Local:** 50+ branches (all `claude/` prefixed worktree branches, plus `fix-decision-trigger`, `main`, `phase-2-realism`, `phase-3-ingest`, `phase-4-explainability`)
- **Remote-tracking:** 4 remotes (origin/claude/awesome-hertz, origin/claude/silly-moser, origin/claude/stoic-albattani, origin/main)
- **Active worktrees:** 46 (main repo + 45 worktrees in `.claude/worktrees/`)

### Worktree List (abbreviated — 46 total)

| Worktree Path | Commit | Branch |
|---|---|---|
| `/Users/willdimaio/Desktop/Airport` | `64cad41` | fix-decision-trigger |
| `.claude/worktrees/upbeat-moore` | `64cad41` | claude/upbeat-moore |
| `.claude/worktrees/great-faraday` | `30ce63a` | claude/great-faraday |
| `.claude/worktrees/gifted-euclid` | `e0802c4` | phase-4-explainability |
| `.claude/worktrees/trusting-albattani` | `a9c3bb9` | phase-2-realism |
| `.claude/worktrees/funny-spence` | `7eeab4f` | phase-3-ingest |
| (41 additional worktrees) | various | claude/* branches |

---

## SECTION 2 — Recent Commit History

### Last 30 Commits (all branches, chronological newest-first)

| Hash | Date | Author | Message |
|---|---|---|---|
| `30ce63a` | 2026-04-08 | willyd248 | docs: add checkpoint path verification items to PRE_RETRAIN_CHECKLIST.md |
| `22a720a` | 2026-04-08 | willyd248 | fix: wire --name-prefix into all checkpoint paths to prevent silent overwrites |
| `ff56322` | 2026-04-08 | willyd248 | feat: Step 9 — 2M run scaffold (MODELS_FREQ=250k, run_milestone.py, trace file) |
| `a55a3ac` | 2026-04-08 | willyd248 | fix: correct sign comparison in eval verdict logic |
| `64cad41` | 2026-04-08 | willyd248 | feat: Step 5 — REWARD_FULFILLED_RESERVATION=+1.0, REWARD_EXPIRED_RESERVATION=-0.5, wired into _compute_tick_reward |
| `eaf4499` | 2026-04-08 | willyd248 | feat: Step 4 — reservation conversion ordering in RLDispatcher, burst event, expiry event A' |
| `660874a` | 2026-04-08 | willyd248 | feat: Step 8 pre-flight — REWARD_FUNCTION.md signals 7-8, verify_pretrain, eval_hard_battery, v5_anticipation naming |
| `8598790` | 2026-04-08 | willyd248 | feat: Steps 2+3 — OBS_DIM 337, Discrete(25), reservation action mask, vehicle is_reserved, expiry loop |
| `028e0b0` | 2026-04-08 | willyd248 | feat: Step 7 — smoke test (5 episodes, all checks pass) |
| `258a384` | 2026-04-08 | willyd248 | fix: update test_masked_actions_have_vehicles for reservation actions (0..15 assign, 16..23 reserve) |
| `02a913e` | 2026-04-08 | willyd248 | fix: add decision_query_count + silent-conversion tests (Item 1 & 2 resolution) |
| `0a53421` | 2026-04-08 | willyd248 | feat: Step 6 — complete test_anticipated.py (15 tests, Gate 2 full suite) |
| `ed4797c` | 2026-04-08 | willyd248 | feat: Step 6 (partial) — test_anticipated.py with Gate 1 tests |
| `38194b4` | 2026-04-08 | willyd248 | feat: Steps 2-5 — OBS_DIM 337, Discrete(25), reservation conversion ordering, reward signals |
| `bd43191` | 2026-04-08 | willyd248 | feat: Step 1 — AnticipatedTask dataclass, _update_anticipated_tasks in dispatcher, Vehicle.reserved_for |
| `473a217` | 2026-04-08 | willyd248 | chore: rename checkpoint paths to v5_2m convention |
| `d25c4a3` | 2026-04-08 | willyd248 | docs: ANTICIPATION_DESIGN_v2.md — design for anticipation upgrade with v1 fixes |
| `1129ead` | 2026-04-07 | willyd248 | docs: PRE_RETRAIN_CHECKLIST.md — pre-flight checks before every retrain |
| `33f4ded` | 2026-04-07 | willyd248 | fix: randomize schedule seed per episode instead of reusing worker rank |
| `a79e803` | 2026-04-07 | willyd248 | docs: FAILURE_DIAGNOSTIC.md — 500k policy trained on 8 fixed seeds |
| `a60a140` | 2026-04-07 | willyd248 | feat: v5 eval seed 6 — 28% suboptimality, 131 min FCFS delay, 19 flights |
| `fa80380` | 2026-04-07 | willyd248 | feat: lock v5 config as production training distribution |
| `02f9a83` | 2026-04-07 | willyd248 | feat: v5 config (tight+FT×1/BT×2/PB×1) — 14.1% suboptimality, 0.722 min mean improvement |
| `86b66bc` | 2026-04-07 | willyd248 | feat: tight schedule density + fleet FT×2/BT×2/PB×2 — v4 diagnostic 9.8% suboptimality |
| `0c5bd40` | 2026-04-07 | willyd248 | fix: correct contention fix — FT×1/BT×2/PB×1, v3 diagnostic confirms 1.5% suboptimality |
| `49bfc76` | 2026-04-07 | willyd248 | feat: contention fix (FT×3) + LEGAL_ACTION_DIAGNOSTIC_v2 — World 2 confirmed |
| `8ea0378` | 2026-04-07 | willyd248 | feat: LEGAL_ACTION_DIAGNOSTIC — World 2 verdict, 1.4% greedy suboptimality across 50 seeds |
| `5781b93` | 2026-04-07 | willyd248 | feat: Item 3 — 250k masked smoke retrain, session5_masked_smoke_250k.zip |
| `e0802c4` | 2026-04-07 | willyd248 | fix: normalize AC state obs by dynamic state count (9 states after LINE_UP_AND_WAIT) |
| `9d67a0b` | 2026-04-07 | willyd248 | feat: Item 2 — HOLD action masking (HOLD illegal when assignments exist) |

**78 commits total in the last 7 days.** All commits are by a single author (`willyd248`). Commit cadence is extremely high — entire RL training pipeline, evaluation, diagnostics, and anticipation upgrade architecture were developed within a 2-day window (2026-04-07 to 2026-04-08).

---

## SECTION 3 — Design Docs Inventory

All files found at `/Users/willdimaio/Desktop/Airport/*.md`. Entries marked with `*` are **untracked** (not in git).

| File | Size | Date | Tracked | Summary |
|---|---|---|---|---|
| `ABANDONMENT_FIX.md` | 7.5 KB | Apr 7 16:42 | Yes | Documents the committed-flag abandonment penalty fix — vehicles mid-service cannot be reassigned. |
| `ANTICIPATION_DESIGN.md` | 22 KB | Apr 8 12:47 | **No*** | v1 design doc for anticipation upgrade. Identifies reactive ceiling: 3% win rate, -9.1 min mean delta vs FCFS. Proposes 600s lookahead, AnticipatedTask, vehicle reservations. |
| `ANTICIPATION_DESIGN_v2.md` | 30 KB | Apr 8 12:47 | Yes (committed) | v2 design with 6 fixes: OBS_DIM arithmetic consistency (4×5=20 → 337 total), reservation conversion ordering, decision trigger interaction, kill criterion #5, network arch recommendation, seed 40 B777 verification. |
| `CHECKPOINT_1M_BATTERY.md` | 4.0 KB | Apr 7 18:59 | Yes | Hard battery results for 1M step checkpoint (seeds 100–119). |
| `CONTENTION_FIX.md` | 3.2 KB | Apr 7 21:01 | Yes | Documents the fleet contention fix (FT×1/BT×2/PB×1 vs earlier FT×3 attempt). |
| `DECISION_TRIGGER.md` | 25 KB | Apr 7 19:11 | Yes | Diagnoses 243:1 noise ratio in old trigger. Specifies event-based trigger (Events A/B/C + safety valve). Identifies reactive ceiling as fundamental problem. |
| `DEMO.md` | 7.2 KB | Apr 7 14:17 | Yes | Instructions for running the split-screen demo (Session 4). |
| `EVAL_DIAGNOSTIC.md` | 8.2 KB | Apr 7 17:48 | Yes | Three-part analysis of why eval seed=42 is inadequate. |
| `EVAL_SCHEDULE_V5.md` | 2.0 KB | Apr 7 21:18 | Yes | Eval schedule config for v5. |
| `FAILURE_DIAGNOSTIC.md` | 10 KB | Apr 7 22:13 | Yes | Root cause of 500k policy failure: 8 fixed seeds caused memorization, not generalization. Fix: randomize seed per episode. |
| `LEGAL_ACTION_DIAGNOSTIC.md` | 4.8 KB | Apr 7 19:54 | Yes | World 2 diagnostic — 1.4% greedy suboptimality. |
| `LEGAL_ACTION_DIAGNOSTIC_v2.md` | 4.5 KB | Apr 7 20:15 | Yes | v2 of diagnostic. |
| `LEGAL_ACTION_DIAGNOSTIC_v3.md` | 4.7 KB | Apr 7 20:27 | Yes | v3 of diagnostic. |
| `LEGAL_ACTION_DIAGNOSTIC_v4.md` | 5.4 KB | Apr 7 20:50 | Yes | v4 of diagnostic. |
| `LEGAL_ACTION_DIAGNOSTIC_v5.md` | 6.0 KB | Apr 7 21:00 | Yes | v5 (final) diagnostic. |
| `MILESTONE_TRACE.md` | 17 KB | Apr 8 00:25 | **No*** | Per-milestone training trace for v5 2M retrain. Covers 250k through 2M. Mean hard delta ranged -18.4 (250k) to -10.4 (2M final). |
| `MORNING_BRIEFING.md` | 7.8 KB | Apr 8 12:47 | **No*** | Session start briefing. Confirms v5 2M result, frames anticipation upgrade as the next step. Answers design questions (600s horizon, 8 anticipated slots, stationary reservation, exclude pushback, no fleet change). |
| `POLICY_HEALTH.md` | 3.4 KB | Apr 7 19:08 | Yes | Earlier policy health report (pre-2M). |
| `POLICY_HEALTH_V5_FINAL.md` | 10 KB | Apr 8 00:29 | **No*** | Final v5 2M policy health. Hard battery: 3/50 wins (6%), mean delta -10.4 min. OOD battery: 0/50 wins (0%), mean delta -7.8 min. Combined: 3% win rate, -9.1 min mean. Best checkpoint: 500k. Policy learned rigid "baggage-first" heuristic. |
| `PRE_RETRAIN_CHECKLIST.md` | 4.1 KB | Apr 7 22:20 | Yes | Pre-flight checklist before any retrain. Items: fleet config, schedule density, OBS_DIM, HOLD masking, conflict termination, checkpoint naming. **Note: OBS_DIM listed as 258 but current code implements 337 after anticipation upgrade.** |
| `README.md` | 297 B | Apr 6 13:21 | Yes | One-paragraph project description. References JavaScript demo only, not the RL pipeline. |
| `REWARD_FUNCTION.md` | 11 KB | Apr 7 16:59 | Yes | Complete reward signal reference. 8 constants: REWARD_PER_DELAY_MINUTE=-1.0, REWARD_ONTIME_DEPARTURE=+10.0, REWARD_LATE_DEPARTURE=+2.0, REWARD_HOLD_WITH_WORK=-0.1, REWARD_CONFLICT_TERMINAL=-200.0, REWARD_CONFLICT=-50.0, REWARD_PENDING_AT_TIMEOUT=-20.0, REWARD_ABANDONMENT=-1.0. Signals 7-8 (REWARD_FULFILLED_RESERVATION=+1.0, REWARD_EXPIRED_RESERVATION=-0.5) added by anticipation upgrade. |
| `SCHEDULE_DENSITY.md` | 4.7 KB | Apr 7 20:45 | Yes | Comparative analysis of schedule density modes. |
| `SPEC.md` | 21 KB | Apr 7 21:12 | Yes | Full project specification. Covers all entities, state machines, action space, observation space, training config. |
| `TRAINING_DISTRIBUTION_DIAGNOSTIC.md` | 8.0 KB | Apr 7 19:05 | Yes | Diagnostic of training distribution issues. |

**Files requested but not found:**
- `AUDIT.md` — Not found
- `COMPATIBILITY_REPORT.md` — Not found
- `MILESTONE_TRACE_ANTICIPATION.md` — Not found (there is `MILESTONE_TRACE.md` but no anticipation-specific version)

---

## SECTION 4 — Model Checkpoints Inventory

### `checkpoints/` directory (22 MB total)

40 checkpoint files, all 550 KB each. Naming convention: `airport_ppo_{N}_steps.zip`.

| Filename | Size | Date |
|---|---|---|
| `airport_ppo_50000_steps.zip` | 550 KB | Apr 7 22:42 |
| `airport_ppo_100000_steps.zip` | 550 KB | Apr 7 22:45 |
| `airport_ppo_150000_steps.zip` | 550 KB | Apr 7 22:48 |
| `airport_ppo_200000_steps.zip` | 550 KB | Apr 7 22:50 |
| `airport_ppo_250000_steps.zip` | 550 KB | Apr 7 22:53 |
| `airport_ppo_300000_steps.zip` | 550 KB | Apr 7 22:56 |
| `airport_ppo_350000_steps.zip` | 550 KB | Apr 7 22:59 |
| `airport_ppo_400000_steps.zip` | 550 KB | Apr 7 23:01 |
| `airport_ppo_450000_steps.zip` | 550 KB | Apr 7 23:04 |
| `airport_ppo_500000_steps.zip` | 550 KB | Apr 7 23:06 |
| `airport_ppo_550000_steps.zip` | 550 KB | Apr 7 23:09 |
| `airport_ppo_600000_steps.zip` | 550 KB | Apr 7 23:12 |
| `airport_ppo_650000_steps.zip` | 550 KB | Apr 7 23:15 |
| `airport_ppo_700000_steps.zip` | 550 KB | Apr 7 23:17 |
| `airport_ppo_750000_steps.zip` | 550 KB | Apr 7 23:20 |
| `airport_ppo_800000_steps.zip` | 550 KB | Apr 7 23:22 |
| `airport_ppo_850000_steps.zip` | 550 KB | Apr 7 23:25 |
| `airport_ppo_900000_steps.zip` | 550 KB | Apr 7 23:27 |
| `airport_ppo_950000_steps.zip` | 550 KB | Apr 7 23:30 |
| `airport_ppo_1000000_steps.zip` | 550 KB | Apr 7 23:33 |
| `airport_ppo_1050000_steps.zip` | 550 KB | Apr 7 23:35 |
| `airport_ppo_1100000_steps.zip` | 550 KB | Apr 7 23:38 |
| `airport_ppo_1150000_steps.zip` | 550 KB | Apr 7 23:41 |
| `airport_ppo_1200000_steps.zip` | 550 KB | Apr 7 23:44 |
| `airport_ppo_1250000_steps.zip` | 550 KB | Apr 7 23:46 |
| `airport_ppo_1300000_steps.zip` | 550 KB | Apr 7 23:49 |
| `airport_ppo_1350000_steps.zip` | 550 KB | Apr 7 23:52 |
| `airport_ppo_1400000_steps.zip` | 550 KB | Apr 7 23:54 |
| `airport_ppo_1450000_steps.zip` | 550 KB | Apr 7 23:57 |
| `airport_ppo_1500000_steps.zip` | 550 KB | Apr 7 23:59 |
| `airport_ppo_1550000_steps.zip` | 550 KB | Apr 8 00:02 |
| `airport_ppo_1600000_steps.zip` | 550 KB | Apr 8 00:05 |
| `airport_ppo_1650000_steps.zip` | 550 KB | Apr 8 00:07 |
| `airport_ppo_1700000_steps.zip` | 550 KB | Apr 8 00:09 |
| `airport_ppo_1750000_steps.zip` | 550 KB | Apr 8 00:12 |
| `airport_ppo_1800000_steps.zip` | 550 KB | Apr 8 00:15 |
| `airport_ppo_1850000_steps.zip` | 550 KB | Apr 8 00:17 |
| `airport_ppo_1900000_steps.zip` | 550 KB | Apr 8 00:20 |
| `airport_ppo_1950000_steps.zip` | 550 KB | Apr 8 00:22 |
| `airport_ppo_2000000_steps.zip` | 550 KB | Apr 8 00:25 |

These correspond to the v5 2M run (50k-step frequency). All are untracked by git. Timestamps show a consistent ~3-minute interval between checkpoints, indicating automated saving during a single training run completed overnight April 7–8.

### `models/` directory (8.1 MB total)

| Filename | Size | Date | Notes |
|---|---|---|---|
| `README.md` | 2.5 KB | Apr 7 19:45 | Tracked |
| `session5_masked_smoke_250k.zip` | 569 KB | Apr 7 19:45 | Tracked — 250k masked smoke retrain |
| `session5_reactive_300k.zip` | 569 KB | Apr 7 19:09 | Tracked — pre-divergence baseline |
| `session5_reactive_diverged.zip` | 569 KB | Apr 7 19:03 | Tracked — diverged reactive checkpoint |
| `session5_v5_500k_stalled.zip` | 550 KB | Apr 7 22:07 | Tracked |
| `session5_v5_final.zip` | 550 KB | Apr 7 22:32 | Tracked — v5 config final |
| `v5_2m_final.zip` | 550 KB | Apr 8 00:26 | **Untracked*** — primary deliverable model |
| `v5_2m_final_REACTIVE_BASELINE.zip` | 550 KB | Apr 8 16:11 | **Untracked*** — reactive baseline for comparison |
| `v5_2m_step_250000_steps.zip` | 550 KB | Apr 7 22:53 | **Untracked*** |
| `v5_2m_step_500000_steps.zip` | 550 KB | Apr 7 23:06 | **Untracked*** |
| `v5_2m_step_750000_steps.zip` | 550 KB | Apr 7 23:20 | **Untracked*** |
| `v5_2m_step_1000000_steps.zip` | 550 KB | Apr 7 23:33 | **Untracked*** |
| `v5_2m_step_1250000_steps.zip` | 550 KB | Apr 7 23:46 | **Untracked*** |
| `v5_2m_step_1500000_steps.zip` | 550 KB | Apr 7 23:59 | **Untracked*** |
| `v5_2m_step_1750000_steps.zip` | 550 KB | Apr 8 00:12 | **Untracked*** |
| `v5_2m_step_2000000_steps.zip` | 550 KB | Apr 8 00:25 | **Untracked*** |

**Note:** `v5_2m_final_REACTIVE_BASELINE.zip` was created on Apr 8 16:11, which is the most recent file modification in the entire repo after the main session ended (Apr 8 12:47). It is byte-for-byte identical in size to `v5_2m_final.zip` (562,958 bytes) suggesting it is a copy.

---

## SECTION 5 — Training Run Status

### Active Training Processes

No training processes running. `ps aux | grep train_ppo` returned no results.

### TensorBoard Event Files

| File | Size | Path | Notes |
|---|---|---|---|
| `events.out.tfevents.1775587589.Wills-MBP-6.15893.0` | 45 KB | `.claude/worktrees/trusting-albattani/runs/AirportPPO_1/` | Apr 7 16:27 — phase-2-realism run |
| `events.out.tfevents.1775675441.Wills-MacBook-Pro-6.local.66865.0` | 14 KB | `.claude/worktrees/great-faraday/runs/AirportPPO_1/` | Apr 8 15:35 |
| `events.out.tfevents.1775677995.Wills-MacBook-Pro-6.local.70882.0` | 31 KB | `.claude/worktrees/great-faraday/runs/AirportPPO_2/` | Apr 8 16:13 |
| `events.out.tfevents.1775679351.Wills-MacBook-Pro-6.local.72168.0` | 134 KB | `.claude/worktrees/great-faraday/runs/AirportPPO_3/` | Apr 8 20:28 |
| `events.out.tfevents.1775616028.Wills-MBP-6.41087.0` | 134 KB | `runs/AirportPPO_1/` | Apr 8 00:26 |

The main v5 2M run is `runs/AirportPPO_1/` (134 KB event file, ending at Apr 8 00:26 — matching the final checkpoint timestamp). Three additional runs in the `great-faraday` worktree ending Apr 8 20:28 (the most recent file in the entire repo). These appear to be anticipation upgrade retrain experiments or test runs initiated after the main v5 2M completion.

**No log files found** at the repo root (`.gitignore` ignores `*.log`; none present in tracked directories).

---

## SECTION 6 — Test Suite Health

### Collection Results

Python 3 (python3) successfully collected **146 tests** in 0.32 seconds across 6 test files.

```
146 tests collected in 0.32s
```

### Test File Breakdown

| File | Line Count | Tests Collected | Notes |
|---|---|---|---|
| `tests/test_anticipated.py` | 644 | 23 | **Untracked** — new anticipation upgrade tests. Covers AnticipatedTask population, reservation mask, auto-assign, expiry, conversion priority, OBS_DIM=337, action_space=25, HOLD masking, full episode. |
| `tests/test_dispatcher.py` | (original) | 22 | Core dispatcher tests |
| `tests/test_entities.py` | (original) | 27 | Entity model tests |
| `tests/test_env.py` | 729 | 44 | Env wrapper tests — covers obs/mask shapes, conflict termination, no-conflict runs, episode termination, reward finiteness, mask validity, abandonment protection, event triggers. |
| `tests/test_scheduler.py` | (original) | ~8 | Scheduler tests |
| `tests/test_world.py` | (original) | ~8 | World/graph tests |

### Notable Test Groups

- `TestObsDimCorrect::test_obs_dim_is_337` — validates new OBS_DIM=337 after anticipation upgrade
- `TestActionSpaceCorrect::test_action_space_is_25` — validates Discrete(25) (16 assign + 8 reserve + 1 hold)
- `TestReservationActionMask` — 3 tests for reservation masking logic
- `TestReservationAutoAssign` — 2 tests for auto-assign behavior
- `TestReservationExpiry` — 2 tests for expiry and penalty
- `TestReservationConversionPriority` — 2 tests for priority ordering

**The test collection succeeds cleanly with no import errors.** The environment (python3, all dependencies) is functional for test collection. Tests have not been run per audit instructions.

---

## SECTION 7 — Recent Activity Timeline

### Files Modified Most Recently (last 7 days, excluding .git, .claude, __pycache__)

| File | Date | Notes |
|---|---|---|
| `models/v5_2m_final_REACTIVE_BASELINE.zip` | Apr 8 16:11 | Most recent change in entire repo — reactive baseline copy |
| `.claude/worktrees/great-faraday/runs/AirportPPO_3/events.*` | Apr 8 20:28 | Most recent TensorBoard event (worktree-based training run) |
| `tests/test_anticipated.py` | Apr 8 15:30 | Anticipation test suite |
| `env/smoke_test.py` | Apr 8 15:34 | Smoke test (modified, unstaged) |
| `env/airport_env.py` | Apr 8 15:21 | Main env file (900 lines, last updated with anticipation upgrade) |
| `tests/test_env.py` | Apr 8 15:00 | Updated env tests |
| `sim/dispatcher.py` | Apr 8 13:59 | Core dispatcher (743 lines) |
| `sim/entities.py` | Apr 8 13:58 | Entities (8.5 KB) |
| `ANTICIPATION_DESIGN.md` | Apr 8 12:47 | v1 design doc (untracked) |
| `ANTICIPATION_DESIGN_v2.md` | Apr 8 12:47 | v2 design doc |
| `MORNING_BRIEFING.md` | Apr 8 12:47 | Session briefing (untracked) |
| `POLICY_HEALTH_V5_FINAL.md` | Apr 8 00:29 | Final policy health (untracked) |
| `MILESTONE_TRACE.md` | Apr 8 00:25 | Training trace (untracked) |
| `models/v5_2m_final.zip` | Apr 8 00:26 | Primary deliverable model (untracked) |
| `runs/AirportPPO_1/events.*` | Apr 8 00:26 | v5 2M training run |
| `train/milestone_diagnostic.py` | Apr 7 22:41 | Milestone diagnostic tool (untracked) |
| `train/train_ppo.py` | Apr 7 22:40 | Training script |
| `FAILURE_DIAGNOSTIC.md` | Apr 7 22:13 | Failure analysis doc |
| `train/smoke_eval_v5.py` | Apr 7 21:19 | Smoke eval |

### Activity Narrative

- **Apr 6 (start of project):** Initial JavaScript demo, landing page, ATC UI aesthetic, SEO.
- **Apr 7 (RL development day):** Full day of RL work — env wrapper, action masking, HOLD masking, abandonment fix, reward function, eval diagnostics, schedule density tuning, fleet composition tuning. v5 config locked. v5 2M training initiated.
- **Apr 8 00:00–00:30:** v5 2M training completes. All 40 checkpoints written, final model saved.
- **Apr 8 00:29:** POLICY_HEALTH_V5_FINAL.md written — 3% win rate conclusion.
- **Apr 8 12:47:** MORNING_BRIEFING.md and anticipation design docs written. Anticipation upgrade designed.
- **Apr 8 13:58–15:34:** Anticipation upgrade implementation — dispatcher.py, entities.py, airport_env.py updated. test_anticipated.py written.
- **Apr 8 16:11:** REACTIVE_BASELINE model copy created.
- **Apr 8 16:15–20:28:** Additional training runs in great-faraday worktree (anticipation policy experiments, not the main repo).

---

## SECTION 8 — Anomalies and Concerns

### 8.1 Critical: Major Untracked Files

The following files are **not tracked by git** and would be lost on a branch switch or fresh clone:

- `ANTICIPATION_DESIGN.md` (v1 design — 22 KB)
- `MILESTONE_TRACE.md` (training trace — 17 KB, contains all milestone eval data)
- `MORNING_BRIEFING.md` (session state — 7.8 KB)
- `POLICY_HEALTH_V5_FINAL.md` (final results — 10 KB)
- `tests/test_anticipated.py` (23 tests — 26 KB)
- `train/milestone_diagnostic.py` (11 KB tool)
- All 40 checkpoint files in `checkpoints/` (22 MB total)
- `models/v5_2m_final.zip` (primary deliverable — 550 KB)
- `models/v5_2m_final_REACTIVE_BASELINE.zip` (550 KB)
- `models/v5_2m_step_*.zip` (8 milestone models, ~4.4 MB)
- `runs/` directory (TensorBoard logs)

**Impact:** If the `fix-decision-trigger` branch is deleted, checked out to another branch, or the worktree is pruned, all of the above are permanently lost. The primary trained model (`v5_2m_final.zip`) and all diagnostic data are at risk.

### 8.2 PRE_RETRAIN_CHECKLIST.md — OBS_DIM Stale

`PRE_RETRAIN_CHECKLIST.md` item 1.3 states: "Expected: OBS_DIM=258 (with MAX_VEHICLES=4)". The anticipation upgrade changed OBS_DIM to **337**. This checklist item will give a false FAIL on the new codebase and is a hazard for the next retrain.

### 8.3 Large Worktree Accumulation

45 worktrees are checked out under `.claude/worktrees/` totaling approximately **264 MB**. Most appear to be stale Claude Code session worktrees from earlier iterations of the project (JavaScript demo work, ATC UI, etc.) that have no active development. This is disk-consuming but not functionally harmful. The worktrees branch names (`claude/admiring-edison`, `claude/amazing-lamarr`, etc.) are all local-only with no remote tracking.

### 8.4 No Large Files > 10 MB

No single file (outside `.git` and `.claude/worktrees/`) exceeds 10 MB. The 40 checkpoint files at 550 KB each total 22 MB in `checkpoints/`. This is expected.

### 8.5 No Lock Files

No `*.lock` files found outside `.git/`. No dependency lock files (no `package-lock.json`, no `Pipfile.lock`, no `poetry.lock`). Only `requirements.txt` is present for Python dependencies.

### 8.6 .gitignore Does Not Cover RL Artifacts

`.gitignore` contains only: `.DS_Store`, `*.log`, `node_modules/`, `.env`, `.env.local`, `.vercel`. It does not exclude `checkpoints/`, `models/`, or `runs/`. These are deliberately untracked (not in `.gitignore` either) — meaning they appear as untracked files in every `git status` call, adding noise and risk.

### 8.7 README.md References JS Demo Only

`README.md` (297 bytes) describes a JavaScript airport visualization. It makes no mention of the RL training pipeline, Python environment, Gymnasium wrapper, PPO training, or the sessions of work documented in the design docs. The README is effectively stale for anyone trying to understand the current state of the project.

### 8.8 Most Recent Training Activity in Worktree, Not Main Repo

The most recent TensorBoard event file (`AirportPPO_3`, 134 KB, Apr 8 20:28) is in `.claude/worktrees/great-faraday/`, not in the main repo's `runs/`. This suggests anticipation upgrade training was run in the `claude/great-faraday` worktree. The results of those runs are not reflected in the main `runs/` directory and any resulting models are not in the main repo's `models/` or `checkpoints/`.

### 8.9 v5_2m_final_REACTIVE_BASELINE.zip Creation Date Anomaly

`models/v5_2m_final_REACTIVE_BASELINE.zip` was created Apr 8 16:11 — 15 hours after the v5 2M run completed and approximately 3.5 hours after the anticipation upgrade implementation was committed. Its byte size (562,958) is identical to `v5_2m_final.zip`. This appears to be a copy of the reactive baseline saved for comparison against the anticipated upgrade's future results. Its late creation and untracked status mean it could easily be confused with a trained anticipation model.

### 8.10 Policy Performance — Below Baseline

As documented in POLICY_HEALTH_V5_FINAL.md, the v5 2M policy achieves **3% win rate** against FCFS with a **mean delta of -9.1 minutes** (i.e., RL is *worse* than FCFS on average). This is the documented motivation for the anticipation upgrade currently in-progress. This is not an anomaly — it is the documented project state — but it means the current best checkpoint (`v5_2m_final.zip`) does not beat the FCFS baseline in production-like evaluation.

---

## SECTION 9 — Project State Summary

### Current Development Phase

The project is mid-implementation of the **anticipation upgrade** — a major architectural change to add a 600-second lookahead, `AnticipatedTask` dataclass, vehicle reservation actions, and two new reward signals. The implementation spans commits `bd43191` through `64cad41` (Steps 1–5 of the design spec). The work is on branch `fix-decision-trigger` (which was named before the anticipation upgrade was identified as the next step; the name no longer reflects the current work).

### Completed Work

- **Sessions 1–4:** Airport simulator (Python), Gymnasium env wrapper, MaskablePPO training pipeline, split-screen demo.
- **Session 5:** Realism upgrades (heterogeneity, wake turbulence, disruptions), HOLD masking, abandonment fix, event-based decision trigger.
- **v5 2M Retrain:** 2 million step MaskablePPO run completed. Results: 3% win rate vs FCFS, -9.1 min mean delta. Conclusively demonstrated reactive ceiling.
- **Anticipation upgrade Steps 1–9:** AnticipatedTask dataclass, `_update_anticipated_tasks` in dispatcher, `Vehicle.reserved_for`, OBS_DIM expanded to 337, action space expanded to Discrete(25), reservation action mask, expiry loop, reservation conversion ordering, reward signals (+1.0/-0.5), 23-test test suite, smoke test, 2M run scaffold.

### What Is NOT Yet Done

- Anticipation upgrade retrain (v5_anticipation 2M run) has not been initiated in the main repo.
- `train/milestone_diagnostic.py` exists as an untracked file but the run infrastructure (`run_milestone.py`) is not yet visible in the main source tree.
- The `great-faraday` worktree has 3 training runs and a more recent TensorBoard event file (Apr 8 20:28), suggesting experimental anticipation training may have occurred there without results being transferred back to the main repo.

### Key Metrics Snapshot

| Metric | Value |
|---|---|
| Total commits (all branches, last 7 days) | 78 |
| Branches (local) | 50+ |
| Active worktrees | 46 |
| Tests collected | 146 |
| Checkpoint files | 40 (checkpoints/) + 16 (models/) = 56 total |
| Total checkpoint storage | ~30 MB |
| Worktree storage | ~264 MB |
| v5 2M win rate vs FCFS | 3% (hard battery), 0% (OOD) |
| v5 2M mean delta vs FCFS | -9.1 min (RL worse) |
| Current OBS_DIM | 337 |
| Current action space | Discrete(25): 16 assign + 8 reserve + 1 hold |
