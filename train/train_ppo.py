"""
train_ppo.py — Train a MaskablePPO agent on the AirportEnv.

Usage:
    python -m train.train_ppo                      # 1M steps, default config
    python -m train.train_ppo --timesteps 500000   # custom total steps
    python -m train.train_ppo --resume checkpoints/airport_ppo_500000_steps

Configuration (hard-coded per spec):
    n_envs       = 8
    learning_rate = 3e-4
    batch_size   = 256
    n_steps      = 2048  (per env per rollout)
    n_epochs     = 10
    gamma        = 0.99
    clip_range   = 0.2
    ent_coef     = 0.01
    total_timesteps = 1_000_000

Outputs:
    checkpoints/airport_ppo_{N}_steps.zip          every 50k steps (recovery)
    models/session5_fixed_step_{N}.zip             every 250k steps (official)
    models/session5_fixed.zip                      final model
    runs/AirportPPO_*/                             TensorBoard logs
"""

from __future__ import annotations

import argparse
import os

from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor
from stable_baselines3.common.callbacks import CheckpointCallback, CallbackList, BaseCallback
from sb3_contrib import MaskablePPO

from env.airport_env import AirportEnv
from train.callbacks import AirportEvalCallback

# ── Config ────────────────────────────────────────────────────────────────────

N_ENVS             = 8
LEARNING_RATE      = 3e-4
BATCH_SIZE         = 256
N_STEPS            = 2048
N_EPOCHS           = 10
GAMMA              = 0.99
CLIP_RANGE         = 0.2
ENT_COEF           = 0.01
TOTAL_TIMESTEPS    = 2_000_000
CHECKPOINT_FREQ    = 50_000     # recovery checkpoints — every N timesteps (total)
MODELS_FREQ        = 250_000    # official model snapshots — every N timesteps (total)
EVAL_FREQ          = 50_000     # evaluate vs FCFS every N timesteps
EVAL_SEED          = 6     # v5 eval seed (28% suboptimality, 131 min FCFS delay)

CHECKPOINT_DIR     = "checkpoints"   # frequent recovery saves
MODELS_DIR         = "models"        # official release checkpoints
TENSORBOARD_LOG    = "runs"


# ── Env factory ───────────────────────────────────────────────────────────────

def _make_env(rank: int):
    """Return a thunk that creates a randomised AirportEnv for subprocess."""
    def _init():
        env = AirportEnv(randomise=True, seed=rank)
        env.reset(seed=rank)
        return env
    return _init


# ── EpisodeMetricsCallback ────────────────────────────────────────────────────

class EpisodeMetricsCallback(BaseCallback):
    """Tracks conflict terminations and abandonment counts across training episodes."""
    def __init__(self, verbose: int = 0) -> None:
        super().__init__(verbose)
        self._n_eps_conflict = 0
        self._n_eps_total    = 0

    def _on_step(self) -> bool:
        for done, info in zip(self.locals["dones"], self.locals["infos"]):
            if done:
                self._n_eps_total += 1
                if info.get("conflict_terminated", False):
                    self._n_eps_conflict += 1
        if self._n_eps_total > 0 and self.num_timesteps % 10_000 == 0:
            self.logger.record(
                "train/conflict_term_rate",
                self._n_eps_conflict / self._n_eps_total,
            )
            self.logger.record("train/n_eps_conflict", self._n_eps_conflict)
            self.logger.dump(self.num_timesteps)
        return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Train MaskablePPO on AirportEnv")
    parser.add_argument(
        "--timesteps", type=int, default=TOTAL_TIMESTEPS,
        help="Total training timesteps (default: 1_000_000)",
    )
    parser.add_argument(
        "--resume", type=str, default=None,
        help="Path to a checkpoint zip to resume from",
    )
    parser.add_argument(
        "--n-envs", type=int, default=N_ENVS,
        help="Number of parallel envs (default: 8)",
    )
    args = parser.parse_args()

    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(TENSORBOARD_LOG, exist_ok=True)

    # ── Build vectorised env ─────────────────────────────────────────────────
    vec_env = VecMonitor(SubprocVecEnv([_make_env(i) for i in range(args.n_envs)]))

    # ── Build or load model ──────────────────────────────────────────────────
    if args.resume:
        print(f"Resuming from checkpoint: {args.resume}")
        model = MaskablePPO.load(
            args.resume,
            env=vec_env,
            tensorboard_log=TENSORBOARD_LOG,
        )
    else:
        model = MaskablePPO(
            policy="MlpPolicy",
            env=vec_env,
            learning_rate=LEARNING_RATE,
            batch_size=BATCH_SIZE,
            n_steps=N_STEPS,
            n_epochs=N_EPOCHS,
            gamma=GAMMA,
            clip_range=CLIP_RANGE,
            ent_coef=ENT_COEF,
            verbose=1,
            tensorboard_log=TENSORBOARD_LOG,
        )

    # ── Callbacks ────────────────────────────────────────────────────────────
    # Recovery checkpoints — frequent, for resuming interrupted runs
    checkpoint_cb = CheckpointCallback(
        save_freq=max(1, CHECKPOINT_FREQ // args.n_envs),
        save_path=CHECKPOINT_DIR,
        name_prefix="airport_ppo",
        verbose=1,
    )
    # Official model snapshots — every 250k steps for policy health comparison
    models_cb = CheckpointCallback(
        save_freq=max(1, MODELS_FREQ // args.n_envs),
        save_path=MODELS_DIR,
        name_prefix="session5_fixed_step",
        verbose=1,
    )
    eval_cb = AirportEvalCallback(
        eval_freq=EVAL_FREQ,
        eval_seed=EVAL_SEED,
        verbose=1,
    )
    episode_cb = EpisodeMetricsCallback(verbose=1)
    callbacks = CallbackList([checkpoint_cb, models_cb, eval_cb, episode_cb])

    # ── Train ────────────────────────────────────────────────────────────────
    print(
        f"\nTraining MaskablePPO — {args.timesteps:,} steps | "
        f"{args.n_envs} envs | checkpoints → {CHECKPOINT_DIR}/ | "
        f"TensorBoard → {TENSORBOARD_LOG}/\n"
    )
    model.learn(
        total_timesteps=args.timesteps,
        callback=callbacks,
        tb_log_name="AirportPPO",
        reset_num_timesteps=(args.resume is None),
    )

    final_path = os.path.join(MODELS_DIR, "session5_fixed")
    model.save(final_path)
    print(f"\nTraining complete. Final model saved to {final_path}.zip")

    vec_env.close()


if __name__ == "__main__":
    main()
