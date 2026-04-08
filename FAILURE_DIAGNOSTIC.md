# FAILURE_DIAGNOSTIC.md

**Generated:** 2026-04-07  
**Checkpoint:** `models/session5_v5_500k_stalled.zip` (500k steps, v5 config)  
**Branch:** fix-decision-trigger  
**Symptom:** RL policy loses to FCFS on 0/5 hard battery seeds and 0/20 OOD seeds

---

## DIAGNOSTIC 1 — Training Schedule Distribution

### The Seeding Strategy

**How envs are created** (`train/train_ppo.py:63-69`):

```python
def _make_env(rank: int):
    def _init():
        env = AirportEnv(randomise=True, seed=rank)
        env.reset(seed=rank)
        return env
    return _init
```

8 SubprocVecEnv workers are created with `rank ∈ {0, 1, 2, 3, 4, 5, 6, 7}`.

**What happens on auto-reset** (`airport_env.py:230-233`):

```python
if self.randomise:
    effective_seed = seed if seed is not None else self._init_seed
    aircraft_list = generate_schedule(seed=effective_seed, density=self.density)
```

When SB3 auto-resets after episode end, it calls `env.reset()` with **no seed argument**. This means `seed=None`, so `effective_seed = self._init_seed = rank`. **Every worker replays the same schedule every episode.**

### Empirical Verification

The 2M training log contains 13,678 schedule prints. The flight-count distribution:

| Flight count | Occurrences | Source seed(s) |
|-------------|-------------|----------------|
| 16 | 1,505 | seed 0 |
| 12 | 1,985 | seed 1 |
| 10 | 2,332 | seed 2 |
| 13 | 3,695 | seeds 3, 4 |
| 19 | 2,553 | seeds 5, 6 |
| 15 | 1,608 | seed 7 |

**Total unique schedules seen during training: 8.**

### Overlap with Hard Battery

The hard battery seeds are {6, 10, 19, 40, 42}. Of these, **only seed 6 overlaps** with the training distribution (it's worker rank 6). Seeds 10, 19, 40, 42 are completely unseen during training.

### Verdict

The policy was trained on exactly 8 fixed schedules. It has zero generalization capacity because it never needed to generalize — it memorized the optimal (or near-optimal) action sequence for 8 specific schedule instances. Any seed outside {0-7} is out-of-distribution.

---

## DIAGNOSTIC 2 — Per-Seed Action Divergence Analysis

For each hard battery seed, the 500k policy was run alongside a simulated FCFS baseline. At each decision point, the policy's action was compared to what FCFS would choose (task index 0 = first legal assignment = nearest-vehicle-first).

### Summary Table

| Seed | Total decisions | Divergences | % diverged | First divergence | All reorder | HOLD-vs-assign | RL delay (min) | FCFS delay (min) |
|------|----------------|-------------|-----------|-----------------|-------------|---------------|----------------|------------------|
| 6 | 74 | 31 | 41.9% | t=1s | 31 | 0 | 106.2 | 102.5 |
| 10 | 74 | 42 | 56.8% | t=1s | 42 | 0 | 160.2 | 137.5 |
| 19 | 79 | 39 | 49.4% | t=1s | 39 | 0 | 187.8 | 170.2 |
| 40 | 66 | 33 | 50.0% | t=107s | 33 | 0 | 114.6 | 87.0 |
| 42 | 79 | 39 | 49.4% | t=1s | 39 | 0 | 168.0 | 133.7 |

### Key Findings

1. **100% of divergences are task reorderings, zero are HOLD-vs-assign.** The HOLD masking is working perfectly — the agent never holds when work is available.

2. **Divergence rate is 42-57% across all seeds.** The policy has learned a strong preference for a different task ordering than FCFS, and it applies this ordering consistently regardless of schedule.

3. **The dominant pattern is "baggage_load first, fuel later."** Nearly every early divergence across all seeds shows the same thing:
   - FCFS picks `fuel:RNDXX` (the fuel truck goes first as nearest vehicle)
   - RL picks `baggage_load:RNDXX` (sends the baggage tug first instead)

4. **First divergence detail per seed:**

| Seed | RL chose | FCFS would choose |
|------|----------|-------------------|
| 6 | `baggage_load:RND01` | `fuel:RND10` |
| 10 | `baggage_load:RND04` | `fuel:RND08` |
| 19 | `baggage_load:RND13` | `fuel:RND13` |
| 40 | `baggage_load:RND04` | `fuel:RND04` |
| 42 | `baggage_load:RND03` | `fuel:RND03` |

The policy learned a rigid "always dispatch baggage before fuel" heuristic from its 8 training schedules. This heuristic happens to be suboptimal on most unseen schedules because it ties up the baggage tugs (the bottleneck resource at BT×2) too early.

---

## DIAGNOSTIC 3 — The Seed 40 Anomaly

### Why Seed 40 Has the Largest Relative Loss

**Seed 40 schedule structure:**
- 17 flights (15 turn + 2 dep-only)
- 2 waves: Wave 1 (8 flights, t=125-535s, 410s span), Wave 2 (7 flights, t=3798-4072s, 274s span)
- Mean slack: 7.1 min, Min slack: 0.9 min (RND05)
- Flights with <5 min slack: 2 (RND05 at 0.9 min, RND07 at 1.8 min)
- 3× B777 in Wave 1 (heavy fuel consumers: RND01, RND06, RND08)

**Comparison to other hard battery seeds:**

| Seed | Flights | Turn | Dep-only | Mean slack |
|------|---------|------|----------|------------|
| 6 | 19 | 17 | 2 | 7.6 min |
| 10 | 19 | 17 | 2 | 4.6 min |
| 19 | 20 | 19 | 1 | 6.8 min |
| 40 | **17** | 15 | 2 | 7.1 min |
| 42 | 20 | 19 | 1 | 6.6 min |

Seed 40 has the **fewest flights** in the battery. With only 17 flights and mean slack of 7.1 min, FCFS handles it relatively well (87.0 min delay — lowest in the battery). But the policy's learned heuristic causes disproportionate damage on this specific schedule because:

### Where the Delay Accumulates

**RL delay trace on seed 40:**

| Step | Sim time | RL action | Delay (min) |
|------|----------|-----------|-------------|
| 0-16 | 49-613s | (various, 9 divergences) | 0.0 |
| 17 | 735s | pushback:RND03 | 3.5 |
| 18 | 859s | pushback:RND02 | 6.7 |
| 19 | 929s | pushback:RND17 | 10.7 |
| ... | | | |
| 22 | 1052s | baggage_load:RND06 | 14.5 |
| 35 | 1655s | pushback:RND07 | 32.1 |
| 36 | 1779s | **pushback:RND08** | **51.2** |

The critical moment is **steps 17-19 (t=735-929s)** where the policy triggers pushbacks for RND03, RND02, RND17 in rapid succession. By t=929s the delay has already reached 10.7 min. FCFS at this point has ~0 min delay.

**Root cause:** The policy reordered early service assignments (baggage_load before fuel at steps 2, 4, 5, 8) which delayed fuel delivery to RND01 (B777). This cascaded: the single fuel truck was occupied on lower-priority baggage-related reorderings, leaving the B777s waiting for fuel. Since B777s have the longest fuel times (120s), any delay in starting their fuel service has outsized downstream impact.

**The jump from 32.1 → 51.2 min at step 36** (pushback:RND08) represents the B777 RND08's delay crystallizing — it couldn't depart because its fuel service was delayed by the early reordering cascade.

### Why Seed 40 Specifically

Seed 40 has 3× B777 in Wave 1 (8 flights). The single fuel truck (FT×1) is the binding constraint. The policy's "baggage first, fuel later" heuristic is maximally destructive when the fuel truck is the bottleneck and the schedule has heavy fuel consumers clustered together. Seeds with 19-20 flights spread the damage across more flights, diluting the per-flight impact. Seed 40's compact 17-flight schedule concentrates it.

---

## DIAGNOSTIC 4 — Out-of-Distribution Check (Seeds 200-219)

20 fresh schedules, definitely outside the training range (seeds 0-7).

| Seed | Flights | FCFS delay (min) | RL delay (min) | Gap (min) | Winner |
|------|---------|------------------|----------------|-----------|--------|
| 200 | 10 | 40.4 | 40.8 | -0.4 | TIE |
| 201 | 11 | 28.2 | 30.4 | -2.2 | FCFS |
| 202 | 16 | 67.6 | 82.3 | -14.7 | FCFS |
| 203 | 11 | 44.4 | 50.6 | -6.2 | FCFS |
| 204 | 16 | 74.3 | 87.0 | -12.7 | FCFS |
| 205 | 16 | 54.9 | 61.2 | -6.3 | FCFS |
| 206 | 10 | 34.9 | 37.9 | -3.0 | FCFS |
| 207 | 18 | 132.4 | 146.8 | -14.4 | FCFS |
| 208 | 14 | 66.8 | 67.7 | -0.9 | FCFS |
| 209 | 18 | 110.2 | 136.4 | -26.2 | FCFS |
| 210 | 16 | 79.4 | 88.7 | -9.3 | FCFS |
| 211 | 19 | 92.9 | 100.6 | -7.7 | FCFS |
| 212 | 16 | 64.3 | 79.4 | -15.1 | FCFS |
| 213 | 12 | 32.2 | 43.6 | -11.4 | FCFS |
| 214 | 18 | 71.9 | 76.9 | -5.0 | FCFS |
| 215 | 10 | 25.6 | 26.2 | -0.6 | FCFS |
| 216 | 13 | 50.3 | 70.7 | -20.4 | FCFS |
| 217 | 14 | 57.0 | 71.0 | -14.0 | FCFS |
| 218 | 14 | 67.0 | 72.9 | -5.9 | FCFS |
| 219 | 20 | 80.7 | 106.8 | -26.1 | FCFS |

### Summary

| Metric | Value |
|--------|-------|
| RL wins | 0/20 |
| FCFS wins | 19/20 |
| Ties | 1/20 |
| Mean delta (FCFS − RL) | **-10.1 min** |
| Median delta | -8.5 min |
| Min delta (worst RL loss) | -26.2 min |
| Max delta (closest to win) | -0.4 min |

### Verdict

The failure is **systemic**, not specific to the hard battery. The policy loses to FCFS on 19/20 completely fresh OOD seeds with a mean deficit of 10.1 minutes. The hard battery (0/5, mean deficit ~21 min) is somewhat harder than random OOD (0/20, mean deficit 10 min), but the pattern is the same everywhere: the policy's learned "baggage-first" heuristic is uniformly worse than FCFS's nearest-vehicle-first approach on any schedule it hasn't memorized.

The OOD results confirm that the policy did not learn any generalizable scheduling insight. It memorized action sequences for 8 schedules and extrapolates a harmful heuristic to everything else.

---

## Appendix — Raw Data

### Training distribution (8 seeds)

| Seed | Flights | AC types |
|------|---------|----------|
| 0 | 16 | B737, A320, B777, CRJ900 |
| 1 | 12 | B737, A320, B777, CRJ900 |
| 2 | 10 | B737, A320, B777, CRJ900 |
| 3 | 13 | B737, A320, B777, CRJ900 |
| 4 | 13 | B737, A320, B777, CRJ900 |
| 5 | 19 | B737, A320, B777, CRJ900 |
| 6 | 19 | B737, A320, B777, CRJ900 |
| 7 | 15 | B737, A320, B777, CRJ900 |

### 500k Eval Trajectory (seed 6)

| Step | RL delay (min) | FCFS delay (min) | Gap |
|------|----------------|------------------|-----|
| 50k | 125.6 | 102.5 | -23.1 |
| 100k | 125.6 | 102.5 | -23.1 |
| 150k | 123.0 | 102.5 | -20.5 |
| 200k | 119.6 | 102.5 | -17.1 |
| 250k | 110.4 | 102.5 | -7.9 |
| 300k | 107.0 | 102.5 | -4.5 |
| 350k | 107.0 | 102.5 | -4.5 |
| 400k | 107.0 | 102.5 | -4.5 |
| 450k | 107.0 | 102.5 | -4.5 |
| 500k | 106.2 | 102.5 | -3.7 |

Note: The eval seed (6) IS in the training distribution. The policy nearly matches FCFS on this seed (-3.7 min gap) while being 10-27 min worse on every other seed tested.
