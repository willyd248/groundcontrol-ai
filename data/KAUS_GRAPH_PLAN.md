# KAUS Taxiway Graph Plan

## FAA Diagram Source

Official FAA airport diagram for KAUS (Austin-Bergstrom International):
- Available at: https://www.faa.gov/airports/runway_safety/diagrams/
- Search for "AUS" or "KAUS"
- Document type: Airport Diagram (10-9 series), updated on standard AIRAC cycle

## OpenStreetMap Data Assessment

**Result: OSM has excellent KAUS taxiway data. No manual tracing needed for v1.**

Data retrieved via Overpass API:
- **127 taxiway ways** forming a connected network
- **2 runway ways** (18R/36L and 18L/36R) — matches real KAUS
- **40 gate nodes** (Gates 1-37 + S1, S2, S3)
- ~34% of taxiways have `ref` tags (A, B, C, C1, C2, G1-G3, etc.)

### Graph Extraction Results

Automated extraction via `parse_osm_taxiways.py`:
- **271 nodes** (226 intersections, 40 gates, 4 runway entries, 1 depot)
- **798 directed edges** (399 bidirectional pairs)
- Edge weights computed from haversine distance / aircraft speed (7.0 m/s)
- Gates connected to nearest taxiway node (within 500m threshold)

### Limitations

1. **No named labels for ~66% of taxiway segments** — routing works fine, but debug output won't show taxiway names for connector stubs
2. **Gate-to-taxiway connections are approximated** — snapped to nearest node, not official stand layout
3. **No hold-short positions or runway crossing points explicitly tagged** — would need FAA chart cross-reference for precision
4. **Graph is much larger than current sim's 15-node toy graph** — may need performance testing

### Manual Tracing Alternative (NOT needed for v1)

If higher fidelity were required:
- Download FAA KAUS diagram PDF
- Hand-trace key nodes (runway entries, hold-short positions, terminal apron entries, gates)
- Estimate distances from diagram scale
- Estimated effort: 2-4 hours for ~50 key nodes, 100 edges
- Would produce a cleaner, smaller graph than the 271-node OSM extraction

### Recommendation

Use the OSM-extracted graph for v1. It's topologically correct and complete. Refinement (pruning minor connector stubs, adding proper taxiway labels) can happen in v2 if the graph size causes performance issues.

## Output Files

- `data/raw/kaus_osm.json` — raw Overpass API response (cached)
- `data/graphs/kaus_taxiways.json` — extracted networkx-compatible graph
- `data/parse_osm_taxiways.py` — extraction script (re-runnable)
