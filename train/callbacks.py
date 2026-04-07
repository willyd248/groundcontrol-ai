"""
callbacks.py — Custom SB3 callbacks for airport PPO training.

AirportEvalCallback:
  Every `eval_freq` timesteps:
    1. Runs the current policy deterministically on a fixed eval schedule (seed=42).
    2. Runs the FCFS baseline on the same schedule (cached after first run).
    3. Logs both sets of metrics + deltas to TensorBoard.

Logged keys (visible in TensorBoard):
  eval/rl_total_delay_min       — RL agent total delay (minutes)
  eval/rl_avg_delay_min         — RL agent average delay per flight
  eval/rl_conflict_count        — conflicts (must stay 0)
  eval/rl_missed_departures     — flights still pending at episode end
  eval/rl_flights_departed      — flights that departed
  eval/fcfs_total_delay_min     — FCFS baseline total delay
  eval/fcfs_missed_departures   — FCFS baseline pending flights
  eval/delay_improvement        — fcfs_delay − rl_delay (positive = RL better)
  eval/missed_improvement       — fcfs_missed − rl_missed  (positive = RL better)
"""

from __future__ import annotations

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from env.airport_env import AirportEnv
from env.random_schedule import generate_schedule
from sim.world import build_taxiway_graph, build_gates, build_runways
from env.airport_env import _build_fleet, SIM_HORIZON
from sim.dispatcher import Dispatcher
from sim.entities import AircraftState


# ── FCFS baseline runner ──────────────────────────────────────────────────────

def run_fcfs_episode(seed: int = 42) -> dict:
    """
    Run the original FCFS dispatcher to completion on a fixed random schedule.
    Returns the metrics dict from dispatcher.metrics().
    """
    G       = build_taxiway_graph()
    gates   = build_gates()
    runways = build_runways()
    fleet   = _build_fleet()
    aircraft = generate_schedule(seed=seed)

    dispatcher = Dispatcher(
        graph=G, gates=gates, runways=runways,
        aircraft=aircraft, vehicles=fleet,
    )

    # Pre-mark gates for departure-only aircraft already at gate
    for ac in aircraft:
        if ac.state == AircraftState.AT_GATE and ac.assigned_gate is not None:
            gate = dispatcher.gates.get(ac.assigned_gate)
            if gate is not None:
                gate.occupied_by = ac.flight_id

    sim_time = 0.0
    while sim_time < SIM_HORIZON:
        dispatcher.tick(sim_time, dt=1.0)
        sim_time += 1.0
        if all(a.state == AircraftState.DEPARTED for a in dispatcher.aircraft.values()):
            break

    return dispatcher.metrics()


# ── Policy evaluation runner ──────────────────────────────────────────────────

def run_policy_episode(model, seed: int = 42) -> dict:
    """
    Run `model` deterministically on a fixed random schedule (seed).
    Returns the info dict from the final step.
    """
    eval_env = AirportEnv(randomise=True, seed=seed)
    obs, info = eval_env.reset(seed=seed)

    done = False
    while not done:
        masks = eval_env.action_masks()
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)
        obs, _reward, terminated, truncated, info = eval_env.step(int(action))
        done = terminated or truncated

    eval_env.close()
    return info


# ── Callback ──────────────────────────────────────────────────────────────────

class AirportEvalCallback(BaseCallback):
    """
    Evaluates the current policy vs. the FCFS baseline every `eval_freq` steps.
    Logs comparison metrics to TensorBoard.

    Parameters
    ----------
    eval_freq : int
        Evaluate every this many *total* timesteps (across all envs).
    eval_seed : int
        Seed for the fixed evaluation schedule (default 42).
    verbose : int
        0 = silent, 1 = print results to stdout.
    """

    def __init__(
        self,
        eval_freq: int = 50_000,
        eval_seed: int = 42,
        verbose: int = 1,
    ) -> None:
        super().__init__(verbose)
        self.eval_freq  = eval_freq
        self.eval_seed  = eval_seed
        self._fcfs_metrics: dict | None = None
        self._last_eval_step: int = 0

    def _on_training_start(self) -> None:
        """Cache the FCFS baseline once at training start."""
        if self.verbose:
            print("[AirportEvalCallback] Computing FCFS baseline (seed={})...".format(self.eval_seed))
        self._fcfs_metrics = run_fcfs_episode(self.eval_seed)
        if self.verbose:
            m = self._fcfs_metrics
            print(
                f"  FCFS baseline — delay: {m['total_delay_minutes']:.1f} min | "
                f"missed: {m['flights_pending']} | conflicts: {m['conflict_count']}"
            )

    def _on_step(self) -> bool:
        if (self.num_timesteps - self._last_eval_step) >= self.eval_freq:
            self._last_eval_step = self.num_timesteps
            self._run_eval()
        return True  # return False to stop training

    def _run_eval(self) -> None:
        rl = run_policy_episode(self.model, self.eval_seed)
        fc = self._fcfs_metrics

        delay_improvement  = fc["total_delay_minutes"]  - rl["total_delay_minutes"]
        missed_improvement = fc["flights_pending"]       - rl["flights_pending"]

        # ── TensorBoard logging ──────────────────────────────────────────────
        self.logger.record("eval/rl_total_delay_min",   rl["total_delay_minutes"])
        self.logger.record("eval/rl_avg_delay_min",     rl["avg_delay_minutes"])
        self.logger.record("eval/rl_conflict_count",    rl["conflict_count"])
        self.logger.record("eval/rl_missed_departures", rl["flights_pending"])
        self.logger.record("eval/rl_flights_departed",  rl["flights_departed"])

        self.logger.record("eval/fcfs_total_delay_min",   fc["total_delay_minutes"])
        self.logger.record("eval/fcfs_missed_departures", fc["flights_pending"])

        self.logger.record("eval/delay_improvement",  delay_improvement)
        self.logger.record("eval/missed_improvement", missed_improvement)
        self.logger.dump(self.num_timesteps)

        if self.verbose:
            sign = "+" if delay_improvement >= 0 else ""
            print(
                f"[eval @ {self.num_timesteps:,}] "
                f"delay: RL={rl['total_delay_minutes']:.1f} vs FCFS={fc['total_delay_minutes']:.1f} "
                f"({sign}{delay_improvement:.1f} min) | "
                f"missed: RL={rl['flights_pending']} vs FCFS={fc['flights_pending']} | "
                f"conflicts: {rl['conflict_count']}"
            )
            if delay_improvement < 0 and self.num_timesteps >= 200_000:
                print(
                    "  !! WARNING: RL not beating FCFS at step 200k — "
                    "consider debugging reward signal or observation space."
                )
