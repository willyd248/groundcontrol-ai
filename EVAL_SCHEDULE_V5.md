# EVAL_SCHEDULE_V5.md

**Eval seed:** 6  
**Schedule density:** tight  
**Fleet:** FT×1, BT×2, PB×1  
**Flight count:** 19 (17 turn + 2 departure-only)  
**Saved to:** `eval_schedule_v5.json`

---

## Why Seed 6?

From LEGAL_ACTION_DIAGNOSTIC_v5.md (50-seed scan):
- **FCFS delay:** 131.0 min — well above mean (83.0 min)
- **Greedy-suboptimality:** 28% of real-choice queries have a better alternative
- **Real-choice queries:** 53 (out of 74 total, 72% ratio)
- **Total queries:** 74 — high decision density
- **Zero undeparted flights** under FCFS

This seed creates maximum opportunity for the RL agent: high delay, many
decision points where order matters, and no pathological edge cases (all
flights depart under FCFS).

---

## Schedule Structure

Two arrival waves + 2 departure-only flights:

**Wave 1 (t=248–687s):** 8 flights, including 2× B777 + 3× CRJ900 + 2× B737 + 0× A320  
**Wave 2 (t=4271–4731s):** 9 flights, including 1× B777 + 5× A320 + 1× B737 + 2× CRJ900  
**Dep-only:** 2× B777 at t=787s and t=1196s

### Slack Distribution

| Flight | Type | Arrival (s) | Departure (s) | Slack (min) |
|--------|------|-------------|---------------|-------------|
| RND02 | CRJ900 | 248 | 469 | 3.7 |
| RND03 | B737 | 288 | 550 | 4.4 |
| RND04 | CRJ900 | 381 | 687 | 5.1 |
| RND05 | B737 | 468 | 1094 | 10.4 |
| RND06 | B777 | 557 | 1331 | 12.9 |
| RND07 | B737 | 644 | 1047 | 6.7 |
| RND08 | B777 | 655 | 1629 | 16.2 |
| RND09 | CRJ900 | 687 | 817 | 2.2 |
| RND11 | B777 | 4271 | 5273 | 16.7 |
| RND12 | A320 | 4387 | 4957 | 9.5 |
| RND13 | B737 | 4581 | 4814 | 5.2 |
| RND14 | CRJ900 | 4581 | 4672 | 1.5 |
| RND15 | A320 | 4592 | 4921 | 5.5 |
| RND16 | A320 | 4631 | 4914 | 4.7 |
| RND17 | A320 | 4648 | 5237 | 9.8 |
| RND18 | A320 | 4649 | 4721 | 1.2 |
| RND19 | B777 | 4731 | 5568 | 13.9 |
| RND10 | B777 | dep-only | 787 | — |
| RND01 | B777 | dep-only | 1196 | — |

**Slack summary:** 6/17 turn flights have <5 min slack, 11/17 have <10 min.  
Mean slack: 7.6 min. This is a hard schedule.
