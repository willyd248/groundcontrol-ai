# MILESTONE TRACE — v5_anticipation 2M Run

Training start: 2026-04-08  
Model prefix: `v5_anticipation`  
Total timesteps: 2,000,000  
Milestone interval: 250,000 steps  
Seeds — hard battery: 6, 10, 19, 40, 42 | OOD battery: 20 random seeds | Strategy: seed 19  

Baseline reference (v5 reactive @ 200k): mean delta +22.2m vs FCFS  
Baseline reference (v5 anticipation @ 200k): mean delta +24.5m vs FCFS  

---

<!-- Milestone blocks appended below in order -->

## Milestone: 250k steps

### Hard Battery (seeds 6, 10, 19, 40, 42)
| Seed | FCFS delay | RL delay | Gap | Res rate |
|------|-----------|---------|------|----------|
| 6 | 102.5m | 126.2m | +23.7m | 5.1% |
| 10 | 137.6m | 152.4m | +14.8m | 5.2% |
| 19 | 170.2m | 184.2m | +14.0m | 4.8% |
| 40 | 87.0m | 122.4m | +35.4m | 5.9% |
| 42 | 133.7m | 170.3m | +36.6m | 4.9% |
| Mean | | | +24.9m | 5.2% |

### Reservation Metrics
- Total reservations made: 20
- Reservations fulfilled: 5
- Reservations expired: 15
- Expiry rate: 75.0% (expired/total)
- Conversion rate: 25.0% (fulfilled/total)
- Reservation decision rate: 5.2% (res actions / all decisions)

### OOD Battery (20 seeds)
- Win rate: 0.0%
- Mean delta: +10.8m

### Strategy Emergence (seed 19)
Seed 19 episode: 83 decisions — 78 assignments (94%), 4 reservations (4.8%), 1 holds (1.2%). First reservation at step 1 (early episode). Reservation behaviour is regular — policy proactively pre-assigns vehicles. Episode delay: RL=184.2m vs FCFS=170.2m (gap +14.0m).

### Policy Health
- HOLD rate: 0.3%
- Conflicts: 0
- Abandonments: 0
- Mean entropy: -0.723 nats
- Explained variance: 0.843
- clip_fraction: 0.031
- Decision queries/ep: 78.6

### Training Metrics
- ep_rew_mean: 20.4
- Trend: [up]

### Watch-list flags
- [ ] Reservation expiry rate >70%: [YES] (actual: 75.0%)
- [ ] Reservation rate <3%: [NO] (actual: 5.2%)
- [ ] Hard battery worse than v5 at same milestone: [NO]
- [ ] Reward trending down 2 consecutive milestones: [NO]

## Milestone: 250k steps

### Hard Battery (seeds 6, 10, 19, 40, 42)
| Seed | FCFS delay | RL delay | Gap | Res rate |
|------|-----------|---------|------|----------|
| 6 | 102.5m | 123.7m | +21.2m | 5.1% |
| 10 | 137.6m | 147.8m | +10.2m | 6.5% |
| 19 | 170.2m | 177.9m | +7.7m | 4.9% |
| 40 | 87.0m | 124.7m | +37.7m | 5.8% |
| 42 | 133.7m | 144.8m | +11.1m | 6.1% |
| Mean | | | +17.6m | 5.7% |

### Reservation Metrics
- Total reservations made: 22
- Reservations fulfilled: 6
- Reservations expired: 16
- Expiry rate: 72.7% (expired/total)
- Conversion rate: 27.3% (fulfilled/total)
- Reservation decision rate: 5.7% (res actions / all decisions)

### OOD Battery (20 seeds)
- Win rate: 5.0%
- Mean delta: +10.4m

### Strategy Emergence (seed 19)
Seed 19 episode: 82 decisions — 78 assignments (95%), 4 reservations (4.9%), 0 holds (0.0%). First reservation at step 2 (early episode). Reservation behaviour is regular — policy proactively pre-assigns vehicles. Episode delay: RL=177.9m vs FCFS=170.2m (gap +7.7m).

### Policy Health
- HOLD rate: 0.0%
- Conflicts: 0
- Abandonments: 0
- Mean entropy: -0.728 nats
- Explained variance: 0.856
- clip_fraction: 0.047
- Decision queries/ep: 78.6

### Training Metrics
- ep_rew_mean: 15.1
- Trend: [up]

### Watch-list flags
- [ ] Reservation expiry rate >70%: [YES] (actual: 72.7%)
- [ ] Reservation rate <3%: [NO] (actual: 5.7%)
- [ ] Hard battery worse than v5 at same milestone: [NO]
- [ ] Reward trending down 2 consecutive milestones: [NO]

## Milestone: 500k steps

### Hard Battery (seeds 6, 10, 19, 40, 42)
| Seed | FCFS delay | RL delay | Gap | Res rate |
|------|-----------|---------|------|----------|
| 6 | 102.5m | 117.6m | +15.1m | 7.6% |
| 10 | 137.6m | 146.1m | +8.5m | 8.9% |
| 19 | 170.2m | 175.1m | +4.9m | 6.0% |
| 40 | 87.0m | 115.0m | +28.0m | 4.3% |
| 42 | 133.7m | 166.4m | +32.7m | 7.4% |
| Mean | | | +17.8m | 6.8% |

### Reservation Metrics
- Total reservations made: 27
- Reservations fulfilled: 8
- Reservations expired: 19
- Expiry rate: 70.4% (expired/total)
- Conversion rate: 29.6% (fulfilled/total)
- Reservation decision rate: 6.9% (res actions / all decisions)

### OOD Battery (20 seeds)
- Win rate: 0.0%
- Mean delta: +8.4m

### Strategy Emergence (seed 19)
Seed 19 episode: 83 decisions — 78 assignments (94%), 5 reservations (6.0%), 0 holds (0.0%). First reservation at step 2 (early episode). Reservation behaviour is regular — policy proactively pre-assigns vehicles. Episode delay: RL=175.1m vs FCFS=170.2m (gap +4.9m).

### Policy Health
- HOLD rate: 0.0%
- Conflicts: 0
- Abandonments: 0
- Mean entropy: -0.547 nats
- Explained variance: 0.869
- clip_fraction: 0.034
- Decision queries/ep: 79.2

### Training Metrics
- ep_rew_mean: 25.8
- Trend: [up]

### Watch-list flags
- [ ] Reservation expiry rate >70%: [YES] (actual: 70.4%)
- [ ] Reservation rate <3%: [NO] (actual: 6.9%)
- [ ] Hard battery worse than v5 at same milestone: [NO]
- [ ] Reward trending down 2 consecutive milestones: [NO]

## Milestone: 750k steps

### Hard Battery (seeds 6, 10, 19, 40, 42)
| Seed | FCFS delay | RL delay | Gap | Res rate |
|------|-----------|---------|------|----------|
| 6 | 102.5m | 115.9m | +13.4m | 7.6% |
| 10 | 137.6m | 146.1m | +8.5m | 10.1% |
| 19 | 170.2m | 173.0m | +2.8m | 6.0% |
| 40 | 87.0m | 121.0m | +34.0m | 4.3% |
| 42 | 133.7m | 153.9m | +20.2m | 5.1% |
| Mean | | | +15.8m | 6.6% |

### Reservation Metrics
- Total reservations made: 26
- Reservations fulfilled: 9
- Reservations expired: 17
- Expiry rate: 65.4% (expired/total)
- Conversion rate: 34.6% (fulfilled/total)
- Reservation decision rate: 6.7% (res actions / all decisions)

### OOD Battery (20 seeds)
- Win rate: 0.0%
- Mean delta: +7.1m

### Strategy Emergence (seed 19)
Seed 19 episode: 83 decisions — 78 assignments (94%), 5 reservations (6.0%), 0 holds (0.0%). First reservation at step 2 (early episode). Reservation behaviour is regular — policy proactively pre-assigns vehicles. Episode delay: RL=173.0m vs FCFS=170.2m (gap +2.8m).

### Policy Health
- HOLD rate: 0.0%
- Conflicts: 0
- Abandonments: 0
- Mean entropy: -0.493 nats
- Explained variance: 0.875
- clip_fraction: 0.039
- Decision queries/ep: 78.8

### Training Metrics
- ep_rew_mean: 31.3
- Trend: [up]

### Watch-list flags
- [ ] Reservation expiry rate >70%: [NO] (actual: 65.4%)
- [ ] Reservation rate <3%: [NO] (actual: 6.7%)
- [ ] Hard battery worse than v5 at same milestone: [NO]
- [ ] Reward trending down 2 consecutive milestones: [NO]
