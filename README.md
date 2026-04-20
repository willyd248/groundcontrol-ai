# Airport Ground Ops — RL Vehicle Scheduling

A reinforcement learning agent for airport ground vehicle scheduling. A PPO policy learns to dispatch fuel trucks, baggage tugs, and pushback tractors to service aircraft — beating a first-come-first-served (FCFS) baseline on synthetic schedules.

This is **not** a live ADS-B tracker. It is a discrete-event simulator with a trained dispatch policy.

---

## What It Does

The simulator models a single airport day:
- Aircraft arrive, park at gates, receive services (fuel, baggage unload/load, pushback), and depart
- A fleet of ground vehicles must be dispatched to complete services before each departure window
- The RL agent replaces a naive FCFS dispatcher — it learns to anticipate upcoming needs and pre-position vehicles

The policy uses **MaskablePPO** (action masking on invalid assignments) with a 337-dimensional observation space encoding aircraft states, vehicle positions, pending tasks, and anticipated future work.

---

## Key Results

Evaluated on synthetic KFIC schedules (50-seed hard battery + 50-seed OOD):

| Metric | Value |
|--------|-------|
| Win rate vs FCFS | 21% |
| Mean delay delta (RL − FCFS) | −0.4 min |
| Conflicts | 0 |
| Abandonments | 0 |

Evaluated on real KAUS (Austin-Bergstrom) data — 40-flight BTS slice, Dec 10 2025:

| Metric | Value |
|--------|-------|
| Win rate vs FCFS | 0% |
| Mean delay delta (RL − FCFS) | +119.3 min |
| Flights completed | 36/40 (same as FCFS) |
| Hold rate | 69.3% |

The KAUS gap is caused by observation degradation: the policy was trained on KFIC node IDs (15-node graph) and sees fallback position values for KAUS nodes (119-node graph). The policy does not fail — zero conflicts, zero abandonments — but it is overly passive. Retraining on KAUS schedules is the next step.

---

## Side-by-Side Demo

![FCFS vs RL side-by-side demo](docs/demo_screenshot.png)
*Screenshot placeholder — run `python -m demo.side_by_side` to see live.*

```
python -m demo.side_by_side
```

The pygame window shows FCFS (left) and the trained agent (right) running in lockstep. Metrics update in real time.

---

## Repo Structure

```
sim/          Core simulator (dispatcher, entities, world graph, renderer)
env/          Gymnasium environment wrapping the simulator (MaskablePPO interface)
train/        PPO training pipeline (train_ppo.py, callbacks, evaluation)
eval/         Evaluation scripts (synthetic battery + KAUS real-data eval)
demo/         Side-by-side pygame demo, replay, scoreboard
data/         Schedules (BTS), taxiway graphs (OSM), raw data
models/       Trained model checkpoints (.zip)
tests/        148 pytest cases
```

---

## Tech Stack

| Layer | Tool |
|-------|------|
| RL algorithm | MaskablePPO (sb3-contrib) |
| Environment | Gymnasium |
| Simulation | Pure Python (networkx for taxiway graphs) |
| Visualization | Pygame |
| Training infra | stable-baselines3, SubprocVecEnv (8 parallel envs) |
| Airport graph | OpenStreetMap via Overpass API |
| Schedule data | BTS On-Time Performance |

---

## How to Run

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run the side-by-side demo (FCFS vs trained agent):**
```bash
python -m demo.side_by_side
```

**Run the FCFS-only simulator:**
```bash
python -m sim.main
```

**Run tests:**
```bash
python -m pytest tests/ -v
```

---

## How to Train

```bash
python -m train.train_ppo
```

Training runs 2M timesteps across 8 parallel environments. Checkpoints saved to `checkpoints/` every 50k steps; official releases to `models/` every 250k steps. TensorBoard logs go to `runs/`.

```bash
tensorboard --logdir runs/
```

---

## How to Evaluate

**Synthetic battery (50 seeds):**
```bash
python -m eval.eval_policy --model models/v5_anticipation_final.zip
```

**Real-world KAUS slice:**
```bash
python -m eval.eval_kaus_slice
```

Output writes to `POLICY_HEALTH_KAUS_SLICE.md`.

---

## Production Model

`models/v5_anticipation_final.zip` — trained 2M steps, OBS_DIM 337, action space 25 (16 task assignments + 8 reservations + 1 hold).

---

## Data Sources

- **Schedules:** [BTS On-Time Performance](https://www.transtats.bts.gov/), Dec 10 2025 (KAUS slice: 40 flights)
- **Taxiway graphs:** OpenStreetMap via [Overpass API](https://overpass-api.de/)
- No live data feeds. All data is pre-processed and stored as JSON.
