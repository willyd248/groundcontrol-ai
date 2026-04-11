# Schema Mapping: BTS On-Time Performance → Simulator Schedule

## Simulator Schedule Format

Each flight in `schedule.json` requires:

```json
{
  "flight_id": "string",          // unique identifier (e.g., "AA101")
  "aircraft_type": "string",      // one of: B737, A320, B777, CRJ900
  "scheduled_arrival": number,    // seconds from sim start, or null (dep-only)
  "scheduled_departure": number,  // seconds from sim start
  "is_arrival_only": boolean,     // optional, default false
  "is_departure_only": boolean    // optional, default false
}
```

Service requirements are derived automatically from `aircraft_type`:
- B737: fuel=5000, baggage=120
- A320: fuel=4500, baggage=110
- B777: fuel=12000, baggage=300
- CRJ900: fuel=2000, baggage=60

## BTS Field Mapping

| BTS Field | Sim Field | Mapping Logic |
|-----------|-----------|---------------|
| `OP_CARRIER` + `OP_CARRIER_FL_NUM` | `flight_id` | Concatenate: "AA" + "101" → "AA101" |
| `CRS_ARR_TIME` | `scheduled_arrival` | Convert HHMM local → seconds from midnight (sim start) |
| `CRS_DEP_TIME` | `scheduled_departure` | Convert HHMM local → seconds from midnight (sim start) |
| `TAIL_NUM` | — | Used to look up aircraft type (see below) |
| — | `aircraft_type` | Inferred from BTS data (see Aircraft Type Resolution) |
| — | `is_arrival_only` | True for flights arriving at KAUS but not departing |
| — | `is_departure_only` | True for flights departing KAUS but not arriving |

## Key BTS Fields Used

| BTS Field | Description | Example |
|-----------|-------------|---------|
| `ORIGIN` | Origin airport IATA code | "DFW" |
| `DEST` | Destination airport IATA code | "AUS" |
| `CRS_DEP_TIME` | Scheduled departure (HHMM local) | 1430 |
| `CRS_ARR_TIME` | Scheduled arrival (HHMM local) | 1615 |
| `OP_CARRIER` | Operating carrier code | "AA" |
| `OP_CARRIER_FL_NUM` | Flight number | 101 |
| `TAIL_NUM` | Aircraft tail number | "N12345" |
| `CANCELLED` | Was flight cancelled? | 0.0 / 1.0 |

## Mismatch Resolution

### 1. Aircraft Type (CRITICAL)

**Problem:** BTS has tail numbers (N12345), not aircraft types (B737). The simulator needs one of exactly 4 types.

**Solution — Carrier + Route heuristic:**
Since we don't have a tail-number-to-type lookup table, use carrier and route characteristics:

| Carrier Pattern | Likely Type | Reasoning |
|----------------|-------------|-----------|
| Regional carriers (OO, YX, OH) | CRJ900 | SkyWest, Republic, PSA fly CRJ/ERJ on short hops |
| Mainline domestic (AA, UA, DL, WN, NK, F9) | B737 | 737 is workhorse of US domestic |
| Southwest (WN) specifically | B737 | All-737 fleet |
| Long-haul / widebody routes | B777 | Rare at KAUS, but possible |
| JetBlue (B6), Frontier (F9) | A320 | Airbus operators |

**Fallback:** Default to B737 (most common US domestic narrowbody). This is imperfect but produces reasonable service requirement distributions.

**Open question for Will:** Should we invest time in a tail-number lookup (FAA registry cross-reference) or is the carrier heuristic good enough for v1?

### 2. Service Requirements

**Problem:** BTS doesn't include service requirements (fuel amount, baggage count).

**Solution:** Fully handled by the simulator — `load_schedule()` derives service requirements from `aircraft_type` using `AIRCRAFT_TYPE_DEFAULTS`. No BTS mapping needed.

### 3. Time Conversion (Seconds from Start)

**Problem:** BTS times are HHMM in local time. Simulator uses seconds from an arbitrary start point.

**Solution:**
```
sim_seconds = (hour * 3600) + (minute * 60)
```
- Sim start = midnight (00:00) local time
- A flight at 14:30 → 52200 seconds
- Day wraps are unlikely at KAUS (minimal red-eye operations)
- If any departure < arrival for same flight pair, flag as overnight (handle as arrival_only + departure_only pair)

### 4. Gate Assignments

**Problem:** BTS does not include gate assignments. The simulator assigns gates dynamically.

**Solution:** Omit gate assignments from schedule.json. The simulator's gate assignment logic handles this at runtime. No field needed.

### 5. Arrival-Only vs Departure-Only Flights

**Problem:** BTS treats each flight leg independently. A plane arriving at KAUS from DFW and later departing to ORD are separate BTS records.

**Solution:**
- Flights where DEST = "AUS": these are arrivals at KAUS
- Flights where ORIGIN = "AUS": these are departures from KAUS
- **Pairing:** Match arrival and departure records by tail number on the same day. An arrival followed by a departure on the same tail = one turnaround.
- **Unmatched arrivals** (plane overnights): `is_arrival_only = true`
- **Unmatched departures** (plane started day at KAUS): `is_departure_only = true`

### 6. Cancelled Flights

**Problem:** BTS includes cancelled flights.

**Solution:** Filter out records where `CANCELLED == 1.0`. We only want flights that actually operated.

## Output Validation

The conversion script must verify:
1. All `flight_id` values are unique
2. All `aircraft_type` values are in {B737, A320, B777, CRJ900}
3. All `scheduled_arrival` < `scheduled_departure` for turnaround flights
4. Departure-only flights have `scheduled_arrival = null`
5. Arrival-only flights have reasonable arrival times (within 0–86400 seconds)
6. Total flight count is plausible for KAUS (~150-250 movements/day)
