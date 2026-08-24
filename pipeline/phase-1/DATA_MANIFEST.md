# NYC Mobility Operations Anomaly Agent

## Phase 1 data manifest

Profiled on 2026-08-05. Scope stops at acquisition and read-only profiling.

## Official sources

NYC TLC catalog: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

| File | Official URL | HTTP check | Bytes | Integrity |
| --- | --- | ---: | ---: | --- |
| `yellow_tripdata_2026-01.parquet` | https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2026-01.parquet | 200 | 64,165,080 | SHA-256 `8b3933fe6f0d7b6d8826613c0dd724edc680ff7c49e2bd4c7635c05102728637` |
| `taxi_zone_lookup.csv` | https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv | 200 | 12,331 | SHA-256 `1a99e105092230f8620f301edcca7f80d3080642ff404d28ed957d3fa222c8ed` |

The server exposed no separate published checksum. The Parquet ETag is multipart (`715f1a37bbf83f6ec7b8d21038e8dc22-13`), so it is not a file MD5. The lookup ETag (`c6064b7c144c716450641f769659d178`) matches the local MD5. Local SHA-256 values above are the integrity baseline.

## Yellow Taxi profile

| Measure | Result |
| --- | ---: |
| Rows | 3,724,889 |
| Row groups | 4 |
| Columns | 20 |
| Pickup range | 2025-12-31 23:57:29 to 2026-02-01 00:45:01 |
| Drop-off range | 2025-12-31 23:57:32 to 2026-02-01 23:35:31 |
| Pickup rows inside January 2026 | 3,724,882 |
| Pickup rows outside January 2026 | 7, or 0.000188% |

Schema:

| Field | Type |
| --- | --- |
| VendorID | int32 |
| tpep_pickup_datetime | timestamp microseconds |
| tpep_dropoff_datetime | timestamp microseconds |
| passenger_count | int64 |
| trip_distance | double |
| RatecodeID | int64 |
| store_and_fwd_flag | string |
| PULocationID | int32 |
| DOLocationID | int32 |
| payment_type | int64 |
| fare_amount | double |
| extra | double |
| mta_tax | double |
| tip_amount | double |
| tolls_amount | double |
| improvement_surcharge | double |
| total_amount | double |
| congestion_surcharge | double |
| Airport_fee | double |
| cbd_congestion_fee | double |

Core-field null profile:

| Field | Null rows | Null rate |
| --- | ---: | ---: |
| VendorID | 0 | 0% |
| tpep_pickup_datetime | 0 | 0% |
| tpep_dropoff_datetime | 0 | 0% |
| passenger_count | 1,088,058 | 29.210481% |
| trip_distance | 0 | 0% |
| PULocationID | 0 | 0% |
| DOLocationID | 0 | 0% |
| payment_type | 0 | 0% |
| fare_amount | 0 | 0% |
| total_amount | 0 | 0% |
| cbd_congestion_fee | 0 | 0% |

## Taxi Zone lookup profile

| Measure | Result |
| --- | ---: |
| Rows | 265 |
| Columns | 4 |
| Schema | LocationID int64, Borough string, Zone string, service_zone string |
| Unique LocationID values | 265 |
| Duplicate LocationID rows | 0 |
| Nulls across all four fields | 0 |

Trip-to-lookup coverage:

| Trip field | Non-null trip rows | Matched rows | Coverage | Unmatched IDs |
| --- | ---: | ---: | ---: | ---: |
| PULocationID | 3,724,889 | 3,724,889 | 100% | 0 |
| DOLocationID | 3,724,889 | 3,724,889 | 100% | 0 |

## Data quality limits

• `passenger_count` is null for 29.21% of trips. Treat it as optional unless a later approved phase defines an imputation or exclusion policy.

• Seven pickup timestamps fall outside January 2026. A later approved phase needs an explicit month-boundary rule.

• The TLC states the published trip records reflect provider submissions and does not attest to their accuracy. This profile checks structure, nulls, time bounds, and zone-key coverage. It does not establish semantic accuracy.

• All Parquet fields are nullable at the schema level even where this file contains zero nulls.

## Phase boundary

No app, transformation pipeline, anomaly logic, dashboard, or deployment was created. Phase 2 requires explicit user approval.
