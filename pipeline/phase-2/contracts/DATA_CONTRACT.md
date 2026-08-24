# NYC TLC Yellow Taxi Phase 2 data contract

## Contract

Version: 2.0.0

Grain: one provider-submitted Yellow Taxi trip record.

Coverage: pickup timestamps from 2026-01-01 00:00:00 inclusive through 2026-02-01 00:00:00 exclusive.

Sources:

• NYC TLC January 2026 Yellow Taxi Parquet.

• NYC TLC Taxi Zone lookup CSV.

Bronze files remain read-only. The Bronze manifest pins paths, byte sizes, SHA-256 hashes, and source schemas. Hash drift stops the run.

## Silver transformations

• Cast all 20 source fields to explicit contract types.

• Add a deterministic source-row identifier tied to the pinned Parquet order.

• Add pickup date and trip duration in seconds.

• Add pickup and drop-off borough, zone, and service-zone labels through lookup joins.

• Add `passenger_count_known` and pipe-delimited `quality_warning_codes`.

• Preserve every source value. No imputation, clipping, normalization, timestamp movement, or monetary repair occurs.

## Quarantine rules

Rows enter quarantine when one or more rules fail:

• Required field is null.

• Pickup timestamp falls outside January 2026.

• Drop-off precedes pickup.

• Pickup or drop-off location ID is absent from the official lookup.

• Trip distance is negative or nonfinite.

• Known passenger count is below 0 or above 9.

• A monetary field is nonfinite.

• Row is an exact duplicate after the first occurrence.

Each quarantined row keeps its raw values, rule booleans, and reason codes.

## Explicit policies

Passenger count: null means unknown. Null does not mean zero. Silver retains these rows and sets `passenger_count_known=false`. No imputation occurs. Known values outside 0 through 9 enter quarantine.

Month boundaries: Silver includes pickups in `[2026-01-01, 2026-02-01)`. The seven source rows outside this interval enter quarantine. Timestamps stay unchanged.

Anomaly retention: zero duration, duration over 24 hours, zero distance, distance over 200 miles, negative fare, and negative total remain in Silver with warning codes. These records might represent operational anomalies, corrections, or source errors. Phase 2 does not decide which interpretation is correct.

## Limitations

• TLC publishes provider submissions and does not attest to semantic accuracy.

• Zone enrichment validates keys, not GPS truth.

• Exact-duplicate checks do not identify near-duplicates.

• Warning thresholds support review. They do not prove fraud, error, or operational failure.

• Source-row identifiers remain stable only while the pinned Bronze file hash remains unchanged.

## Phase 3 inputs

Phase 3 receives:

• Typed Silver Parquet.

• Quarantine Parquet with reason codes.

• Machine-readable quality report.

• Preserved Bronze manifest.

• Seeded validation report.

Phase 3 requires separate user approval. Phase 2 does not include anomaly models, agent logic, dashboards, product UI, public apps, or deployment.
