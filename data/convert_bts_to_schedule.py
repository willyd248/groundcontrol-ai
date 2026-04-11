#!/usr/bin/env python3
"""Convert BTS On-Time Performance CSV to simulator schedule.json format.

Usage:
    python data/convert_bts_to_schedule.py data/raw/kaus_20251210.csv data/schedules/kaus_20251210.json
"""

import csv
import json
import sys
from collections import defaultdict

# Aircraft type mapping: carrier → default type
# Based on known fleet compositions for US domestic carriers
CARRIER_TYPE_MAP = {
    "WN": "B737",   # Southwest: all-737 fleet
    "AA": "B737",   # American: mostly 737/A321, default 737
    "DL": "B737",   # Delta: mixed, 737 most common domestic
    "UA": "B737",   # United: mixed, 737 most common domestic
    "B6": "A320",   # JetBlue: A320 family
    "NK": "A320",   # Spirit: A320 family
    "F9": "A320",   # Frontier: A320 family
    "AS": "B737",   # Alaska: 737 fleet
    "OO": "CRJ900", # SkyWest: regional jets
    "YX": "CRJ900", # Republic: regional jets
    "OH": "CRJ900", # PSA Airlines: regional jets
    "MQ": "CRJ900", # Envoy Air: regional jets
    "G4": "A320",   # Allegiant: A320 family
}

DEFAULT_TYPE = "B737"


def hhmm_to_seconds(hhmm_str: str) -> int:
    """Convert BTS HHMM time string to seconds from midnight.

    BTS uses integer HHMM format: 1430 = 14:30, 0800 = 8:00, 15 = 00:15.
    Midnight is sometimes encoded as 2400.
    """
    hhmm_str = hhmm_str.strip()
    if not hhmm_str:
        return None

    # Handle decimal strings like "1430.00"
    val = int(float(hhmm_str))

    if val == 2400:
        return 86400  # midnight = end of day

    hours = val // 100
    minutes = val % 100
    return hours * 3600 + minutes * 60


def get_aircraft_type(carrier: str) -> str:
    """Map carrier code to simulator aircraft type."""
    return CARRIER_TYPE_MAP.get(carrier, DEFAULT_TYPE)


def convert_bts_to_schedule(csv_path: str) -> list[dict]:
    """Convert BTS CSV to simulator schedule entries.

    Strategy:
    1. Separate rows into arrivals (dest=AUS) and departures (origin=AUS)
    2. Pair arrivals and departures by tail number to create turnaround flights
    3. Unmatched arrivals → arrival_only flights
    4. Unmatched departures → departure_only flights
    """
    arrivals = []   # flights arriving at AUS
    departures = [] # flights departing AUS

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip cancelled flights
            if row.get("Cancelled", "0").strip() in ("1", "1.0", "1.00"):
                continue

            origin = row["Origin"].strip()
            dest = row["Dest"].strip()
            carrier = row["Reporting_Airline"].strip()
            flight_num = row["Flight_Number_Reporting_Airline"].strip()
            tail = row.get("Tail_Number", "").strip()

            if dest == "AUS":
                arr_time = hhmm_to_seconds(row["CRSArrTime"])
                if arr_time is not None:
                    arrivals.append({
                        "carrier": carrier,
                        "flight_num": flight_num,
                        "flight_id": f"{carrier}{flight_num}",
                        "tail": tail,
                        "arr_seconds": arr_time,
                        "origin": origin,
                        "aircraft_type": get_aircraft_type(carrier),
                    })

            if origin == "AUS":
                dep_time = hhmm_to_seconds(row["CRSDepTime"])
                if dep_time is not None:
                    departures.append({
                        "carrier": carrier,
                        "flight_num": flight_num,
                        "flight_id": f"{carrier}{flight_num}",
                        "tail": tail,
                        "dep_seconds": dep_time,
                        "dest": dest,
                        "aircraft_type": get_aircraft_type(carrier),
                    })

    # Pair by tail number: for each tail, match earliest unmatched arrival
    # with earliest unmatched departure that comes after it
    tail_arrivals = defaultdict(list)
    tail_departures = defaultdict(list)

    for a in arrivals:
        if a["tail"]:
            tail_arrivals[a["tail"]].append(a)
    for d in departures:
        if d["tail"]:
            tail_departures[d["tail"]].append(d)

    # Sort by time
    for tail in tail_arrivals:
        tail_arrivals[tail].sort(key=lambda x: x["arr_seconds"])
    for tail in tail_departures:
        tail_departures[tail].sort(key=lambda x: x["dep_seconds"])

    schedule = []
    matched_arrivals = set()
    matched_departures = set()

    # Greedy matching: for each tail, pair arrivals with departures in order
    all_tails = set(tail_arrivals.keys()) | set(tail_departures.keys())
    for tail in all_tails:
        arrs = tail_arrivals.get(tail, [])
        deps = tail_departures.get(tail, [])
        dep_idx = 0

        for arr in arrs:
            # Find next departure after this arrival (with min turnaround of 30 min)
            min_dep_time = arr["arr_seconds"] + 1800  # 30 min turnaround
            paired = False
            while dep_idx < len(deps):
                dep = deps[dep_idx]
                if dep["dep_seconds"] >= min_dep_time:
                    # Matched turnaround
                    fid = f"{arr['flight_id']}-{dep['flight_id']}"
                    schedule.append({
                        "flight_id": fid,
                        "aircraft_type": arr["aircraft_type"],
                        "scheduled_arrival": arr["arr_seconds"],
                        "scheduled_departure": dep["dep_seconds"],
                        "is_arrival_only": False,
                        "is_departure_only": False,
                    })
                    matched_arrivals.add(id(arr))
                    matched_departures.add(id(dep))
                    dep_idx += 1
                    paired = True
                    break
                dep_idx += 1

            if not paired:
                pass  # Will be added as unmatched below

    # Unmatched arrivals → arrival_only
    for a in arrivals:
        if id(a) not in matched_arrivals:
            schedule.append({
                "flight_id": a["flight_id"],
                "aircraft_type": a["aircraft_type"],
                "scheduled_arrival": a["arr_seconds"],
                "scheduled_departure": None,
                "is_arrival_only": True,
                "is_departure_only": False,
            })

    # Unmatched departures → departure_only
    for d in departures:
        if id(d) not in matched_departures:
            schedule.append({
                "flight_id": d["flight_id"],
                "aircraft_type": d["aircraft_type"],
                "scheduled_arrival": None,
                "scheduled_departure": d["dep_seconds"],
                "is_arrival_only": False,
                "is_departure_only": True,
            })

    # Ensure unique flight_ids
    seen = {}
    for entry in schedule:
        fid = entry["flight_id"]
        if fid in seen:
            seen[fid] += 1
            entry["flight_id"] = f"{fid}_{seen[fid]}"
        else:
            seen[fid] = 0

    # Sort by earliest time
    def sort_key(e):
        arr = e["scheduled_arrival"] if e["scheduled_arrival"] is not None else float("inf")
        dep = e["scheduled_departure"] if e["scheduled_departure"] is not None else float("inf")
        return (arr, dep)

    schedule.sort(key=sort_key)

    return schedule


def validate_schedule(schedule: list[dict]) -> list[str]:
    """Validate schedule against simulator requirements."""
    errors = []
    valid_types = {"B737", "A320", "B777", "CRJ900"}
    flight_ids = set()

    for i, entry in enumerate(schedule):
        fid = entry["flight_id"]

        # Unique flight_id
        if fid in flight_ids:
            errors.append(f"Duplicate flight_id: {fid}")
        flight_ids.add(fid)

        # Valid aircraft type
        if entry["aircraft_type"] not in valid_types:
            errors.append(f"{fid}: invalid aircraft_type '{entry['aircraft_type']}'")

        # Time consistency
        arr = entry.get("scheduled_arrival")
        dep = entry.get("scheduled_departure")

        if not entry.get("is_arrival_only") and not entry.get("is_departure_only"):
            if arr is not None and dep is not None and arr >= dep:
                errors.append(f"{fid}: arrival ({arr}) >= departure ({dep})")

        # Time range (0-86400 seconds in a day)
        if arr is not None and (arr < 0 or arr > 86400):
            errors.append(f"{fid}: arrival time {arr} out of range")
        if dep is not None and (dep < 0 or dep > 86400):
            errors.append(f"{fid}: departure time {dep} out of range")

    return errors


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input.csv> <output.json>")
        sys.exit(1)

    csv_path = sys.argv[1]
    json_path = sys.argv[2]

    print(f"Converting {csv_path}...")
    schedule = convert_bts_to_schedule(csv_path)

    errors = validate_schedule(schedule)
    if errors:
        print(f"\nValidation errors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    with open(json_path, "w") as f:
        json.dump(schedule, f, indent=2)

    # Stats
    turnarounds = sum(1 for e in schedule if not e.get("is_arrival_only") and not e.get("is_departure_only"))
    arr_only = sum(1 for e in schedule if e.get("is_arrival_only"))
    dep_only = sum(1 for e in schedule if e.get("is_departure_only"))

    from collections import Counter
    types = Counter(e["aircraft_type"] for e in schedule)

    print(f"\nSchedule written to {json_path}")
    print(f"  Total flights: {len(schedule)}")
    print(f"  Turnarounds:   {turnarounds}")
    print(f"  Arrival-only:  {arr_only}")
    print(f"  Departure-only:{dep_only}")
    print(f"  Aircraft types: {dict(types)}")


if __name__ == "__main__":
    main()
