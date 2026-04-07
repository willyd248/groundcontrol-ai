# KFIC Demo — How to Run

## Quick Start

```bash
python -m demo.side_by_side \
    --checkpoint checkpoints/latest.zip \
    --scenario   demo/scenarios/medium.json
```

This opens a 1560×710 pygame window split down the middle:

- **Left** — FCFS Baseline (amber label)
- **Right** — Trained Agent (teal label)
- **Top bar** — live scoreboard with time, delay totals, and a running delta

Both sides run on the **exact same schedule** starting from t=0.

---

## Controls

| Key | Action |
|-----|--------|
| `SPACE` | Pause / resume the live run |
| `←` / `→` | Step one display-frame backward / forward (works while paused or in replay) |
| `ESC` | Quit at any time |

After the episode ends the demo automatically enters **Replay Mode** — you can step through every recorded sim-second of both sides simultaneously.

---

## CLI Options

```
--checkpoint PATH   (required) MaskablePPO .zip checkpoint
--scenario   PATH   (required) Scenario JSON file
--speed      INT    Sim-seconds per wall-second (default 60)
--fps        INT    Display FPS (default 30)
--record     PATH   Save the window to an mp4 file (requires imageio-ffmpeg)
--seed       INT    RNG seed (default 0; reserved for future use)
```

### Recording an mp4

```bash
pip install imageio imageio-ffmpeg

python -m demo.side_by_side \
    --checkpoint checkpoints/latest.zip \
    --scenario   demo/scenarios/stress.json \
    --speed 30 \
    --record     stress_demo.mp4
```

`--speed 30` slows the sim to half real-time (0.5 sim-min per wall-second) so details are visible in the recording.

---

## Scenarios

### `demo/scenarios/easy.json` — Light Traffic

4 flights (CRJ900, B737, A320, CRJ900), arrivals spread every 20-30 minutes.
Vehicle competition is minimal. Both policies should finish with zero delay.
**What to look for:** The agent should still dispatch slightly earlier in some cases.
**Expected delta:** Agent ≤ 2 min ahead.

### `demo/scenarios/medium.json` — Moderate Traffic (recommended for demos)

8 flights including 2 back-to-back B777s arriving at t=0 and t=60.

**The critical dynamics:**
- FCFS dispatches both fuel trucks (FT1, FT2) to the two B777s first — those are the oldest tasks.
- Each B777 requires 120 seconds of fueling (12,000 gal ÷ 100 gal/s).
- A B737 (MD303) and an A320 (MD404) arrive 60–120 seconds later with **tight 45-min departure windows**.
- Under FCFS, they cannot get fuel until both B777 tanks are topped off (~200–300s later).
- The trained agent recognises the urgency gap: it defers the B777 fuel jobs and sends trucks to the time-critical B737/A320 first.

**What to look for:** Watch the scoreboard — within the first 5 sim-minutes the delay counter on the FCFS side starts climbing while the agent side stays near zero.
**Expected delta:** Agent 8–15 min ahead.

### `demo/scenarios/stress.json` — Heavy Traffic

12 flights, including 3 B777s arriving within the first 10 minutes alongside 4 flights with very tight (~40 min) departure windows.

**The critical dynamics:**
- All three B777s would monopolise both fuel trucks for 300+ seconds under FCFS.
- ST103 (B737), ST104 (A320), ST105 (B737), ST106 (CRJ900) all arrive within 5 min with 38–40 min windows.
- FCFS services by task age — B777 tasks get created first, starving the tight-deadline flights.
- The agent aggressively prioritises departing flights; B777 fueling is deferred until trucks are freed.

**What to look for:** Multiple flights on the FCFS side turn orange (SERVICING) and stay orange well past their scheduled departure. The scoreboard delta climbs to 15–25+ minutes.
**Expected delta:** Agent 15–30 min ahead.

---

## Visual Guide

### Airport Layout (each panel, scaled 65%)

```
DEPOT ── TWY_SERVICE ─────────────────────────────────────────
              │
  INTER_NW ── TWY_NORTH ── INTER_NE
     │                         │
 RWY_09L               RWY_09R
     │                         │
 TWY_A_ENTRY          TWY_B_ENTRY
     │                         │
  A1  A2  A3             B1  B2  B3
```

### Entity Colours

| Colour | Entity |
|--------|--------|
| Yellow triangle | Aircraft (taxiing or waiting) |
| Orange triangle | Aircraft (being serviced — overdue indicator) |
| Red square | Fuel truck |
| Blue square | Baggage tug |
| Orange square | Pushback tractor |
| Purple box | Depot |
| Cyan circles | Gates |
| Green line | Runways |

Occupied taxiway segments turn **red** so you can see congestion at a glance.

### Scoreboard Columns

```
┌─ FCFS Baseline ──┬── 00:04:10 ──┬─ Trained Agent ──┐
│ Departed: 3      │  ● LIVE      │ Departed: 4      │
│ Delay: 8.3 min   │ (SPACE pause)│ Delay: 3.1 min   │
│ Avg:   2.8 min   │              │ Avg:   0.8 min   │
│ Max:   4.1 min   │ Agent +5.2   │ Max:   1.1 min   │
│                  │ min ahead    │                  │
│ Conflicts: 0     │              │ Conflicts: 0     │
└──────────────────┴──────────────┴──────────────────┘
```

- **Delay** (red if > 0, green if 0) — total delay minutes accumulated so far
- **Delta** — green means agent winning; red means FCFS winning (should not happen on stress scenario with a well-trained policy)
- **Conflicts must always be 0** — if either side shows conflicts, that's a simulator bug and the demo will halt with a FATAL error

---

## Safety Guarantees

The demo enforces two hard invariants and halts loudly if either is violated:

1. **No illegal actions** — after calling `model.predict()`, the demo asserts the action passes the action mask. MaskablePPO should never produce a masked action; if it does, the training pipeline has a bug.

2. **Zero conflicts** — after every sim-tick on both sides, `dispatcher.conflict_count` is checked. A conflict (two entities assigned to the same taxiway segment) indicates a dispatcher bug, not a policy bug.

Both violations print a `FATAL:` message with full context and raise `RuntimeError`.

---

## Replay

After the episode finishes, the demo enters replay mode automatically:

- The full state of every sim-second is stored in memory during the live run.
- `←` / `→` steps through frames; the scoreboard shows `REPLAY N/Total`.
- Both panels render from snapshot proxies — no simulation is running.
- Press `ESC` to exit replay.

---

## Troubleshooting

**`ModuleNotFoundError: sb3_contrib`**
```bash
pip install sb3-contrib
```

**`ModuleNotFoundError: imageio`** (only needed for `--record`)
```bash
pip install imageio imageio-ffmpeg
```

**Checkpoint not found**
Run `python -m train.train_ppo` first (or a short sanity check: `--timesteps 10000`).
The checkpoint path defaults to `checkpoints/airport_ppo_XXXXXX_steps.zip`.

**Agent doesn't visibly outperform FCFS on easy.json**
That's expected — easy.json has no vehicle contention. Use medium or stress.

**FATAL: Trained policy produced ILLEGAL action**
The checkpoint was saved before the policy converged. Train longer or use a later checkpoint.
