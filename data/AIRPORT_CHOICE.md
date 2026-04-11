# Airport Selection: KAUS (Austin-Bergstrom International)

## Decision

**KAUS** is the v1 target airport for real-data integration.

## Why KAUS

### Manageable Complexity
- **2 parallel runways** (17L/35R and 17R/35L) — maps cleanly to our simulator's 2-runway layout
- **~30 gates** across terminals — enough to stress-test scheduling without combinatorial explosion
- Our current sim has 6 gates; KAUS lets us scale 5x without jumping to JFK's 128 gates

### Clean Data Availability
- **Mostly domestic operations** — BTS On-Time Performance dataset covers ~95% of KAUS traffic
- International flights are minimal (a few Mexico/Caribbean routes), so BTS gaps are small
- No complex international terminal routing to model

### Capacity-Constrained and Growing
- Austin is one of the fastest-growing metro areas in the US
- KAUS consistently ranks in the top airports for delays relative to size
- "AI helps you handle more flights with the same infrastructure" pitch lands perfectly here
- New South Terminal under construction validates the capacity pressure narrative

### Public Data
- FAA publishes official airport diagrams (10-9 series) for KAUS
- OpenStreetMap has KAUS taxiway/apron data (quality TBD)
- BTS has complete on-time performance coverage

## Alternatives Considered

### KBOS (Boston Logan)
- **Pros:** Complex enough to be interesting, major delays, good BTS coverage
- **Cons:** 6 runways with dependent operations, international terminal complexity, runway configuration changes with wind direction. Too complex for v1 — would require modeling runway-config switching logic we don't have.

### KSAN (San Diego Lindbergh)
- **Pros:** Single runway = simplest possible layout, heavy domestic traffic
- **Cons:** Single runway means our 2-runway sim doesn't map well. The interesting optimization problem (runway assignment) doesn't exist. Also has unusual approach constraints (downtown proximity) that don't generalize.

### KJFK (New York JFK)
- **Pros:** Everyone knows it, massive delay problems, great narrative
- **Cons:** 4 runways, 6 terminals, 128+ gates, heavy international traffic (BTS gaps), complex taxi routing. Would take months to model accurately. v2+ candidate.

## Selection Matrix

| Criterion | KAUS | KBOS | KSAN | KJFK |
|-----------|------|------|------|------|
| Runway count match (2) | ✓ | ✗ (6) | ✗ (1) | ✗ (4) |
| Gate count (manageable) | ✓ (~30) | ~ (90+) | ✓ (~35) | ✗ (128+) |
| BTS coverage | ✓ (95%+) | ✓ (85%) | ✓ (90%) | ~ (70%) |
| Growth narrative | ✓✓ | ~ | ~ | ✓ |
| Public diagram data | ✓ | ✓ | ✓ | ✓ |
| Complexity for v1 | ✓ | ✗ | ✗ | ✗ |

**KAUS wins on data quality + sim compatibility + market narrative.**

## Day Selection

**Chosen day: Wednesday, December 10, 2025**

- **Source:** BTS On-Time Reporting Carrier Performance, December 2025 (most recent fully published month as of April 2026)
- **Why this day:**
  - Wednesday = typical midweek operations (no weekend leisure surge, no Monday/Friday business peaks)
  - Mid-month (10th) = no holiday effects (Thanksgiving Nov 27, Christmas Dec 25)
  - 0 cancellations = clean data, no weather events
  - 466 flight records (234 arrivals, 232 departures) = representative daily volume
- **Carriers present:** WN (200), DL (76), AA (70), UA (64), OO (33), AS (12), NK (5), B6 (4), F9 (2)
- **Raw data:** `data/raw/kaus_20251210.csv`
