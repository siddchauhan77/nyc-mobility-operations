#!/usr/bin/env python3
"""Run seeded invalid-record cases against the Phase 2 preparation layer."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import duckdb

PHASE2 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PHASE2 / "src"))

from prepare_phase2 import atomic_json, run_preparation, sha256_file  # noqa: E402


TRIP_SCHEMA_SQL = """
    VendorID INTEGER,
    tpep_pickup_datetime TIMESTAMP,
    tpep_dropoff_datetime TIMESTAMP,
    passenger_count BIGINT,
    trip_distance DOUBLE,
    RatecodeID BIGINT,
    store_and_fwd_flag VARCHAR,
    PULocationID INTEGER,
    DOLocationID INTEGER,
    payment_type BIGINT,
    fare_amount DOUBLE,
    extra DOUBLE,
    mta_tax DOUBLE,
    tip_amount DOUBLE,
    tolls_amount DOUBLE,
    improvement_surcharge DOUBLE,
    total_amount DOUBLE,
    congestion_surcharge DOUBLE,
    Airport_fee DOUBLE,
    cbd_congestion_fee DOUBLE
"""


def base_row() -> tuple:
    return (
        1, "2026-01-10 10:00:00", "2026-01-10 10:20:00", 1, 3.2, 1, "N",
        1, 2, 1, 15.0, 0.5, 0.5, 3.0, 0.0, 1.0, 20.0, 2.5, 0.0, 0.75,
    )


def replace(row: tuple, index: int, value: object) -> tuple:
    values = list(row)
    values[index] = value
    return tuple(values)


def create_seeded_inputs(root: Path) -> tuple[Path, Path, list[dict[str, str]]]:
    raw = root / "seeded.parquet"
    lookup = root / "zones.csv"
    valid = base_row()
    null_passenger_negative_fare = replace(replace(replace(valid, 3, None), 10, -15.0), 16, -20.0)
    cases = [
        {"case": "valid", "expected": "silver"},
        {"case": "optional passenger null and negative fare", "expected": "silver_with_warnings"},
        {"case": "pickup outside month", "expected": "pickup_outside_month"},
        {"case": "dropoff before pickup", "expected": "dropoff_before_pickup"},
        {"case": "unknown pickup zone", "expected": "unknown_pickup_zone"},
        {"case": "unknown drop-off zone", "expected": "unknown_dropoff_zone"},
        {"case": "negative distance", "expected": "invalid_trip_distance"},
        {"case": "passenger count above contract maximum", "expected": "invalid_passenger_count"},
        {"case": "required VendorID missing", "expected": "required_field_missing"},
        {"case": "nonfinite fare", "expected": "nonfinite_monetary_value"},
        {"case": "exact duplicate of valid row", "expected": "exact_duplicate"},
    ]
    rows = [
        valid,
        null_passenger_negative_fare,
        replace(valid, 1, "2025-12-31 23:59:00"),
        replace(valid, 2, "2026-01-10 09:59:00"),
        replace(valid, 7, 999),
        replace(valid, 8, 999),
        replace(valid, 4, -1.0),
        replace(valid, 3, 10),
        replace(valid, 0, None),
        replace(valid, 10, float("nan")),
        valid,
    ]
    connection = duckdb.connect()
    connection.execute(f"CREATE TABLE seeded ({TRIP_SCHEMA_SQL})")
    placeholders = ",".join("?" for _ in range(20))
    connection.executemany(f"INSERT INTO seeded VALUES ({placeholders})", rows)
    connection.execute(f"COPY seeded TO '{raw}' (FORMAT PARQUET)")
    connection.execute("CREATE TABLE zones(LocationID BIGINT, Borough VARCHAR, Zone VARCHAR, service_zone VARCHAR)")
    connection.executemany(
        "INSERT INTO zones VALUES (?, ?, ?, ?)",
        [(i, "Test Borough", f"Zone {i}", "Test Service") for i in range(1, 266)],
    )
    connection.execute(f"COPY zones TO '{lookup}' (HEADER, DELIMITER ',')")
    return raw, lookup, cases


def run_seeded_validation(report_path: Path | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix="nyc-phase2-seeded-") as directory:
        root = Path(directory)
        raw, lookup, cases = create_seeded_inputs(root)
        before = {"raw": sha256_file(raw), "lookup": sha256_file(lookup)}
        report = run_preparation(raw, lookup, root / "output", "2026-01")
        repeat_report = run_preparation(raw, lookup, root / "output", "2026-01")
        after = {"raw": sha256_file(raw), "lookup": sha256_file(lookup)}
        expected_reasons = {
            "required_field_missing": 1,
            "pickup_outside_month": 1,
            "dropoff_before_pickup": 1,
            "unknown_pickup_zone": 1,
            "unknown_dropoff_zone": 1,
            "invalid_trip_distance": 1,
            "invalid_passenger_count": 1,
            "nonfinite_monetary_value": 1,
            "exact_duplicate": 1,
        }
        assertions = {
            "input_rows_11": report["row_counts"]["bronze_input"] == 11,
            "silver_rows_2": report["row_counts"]["silver_output"] == 2,
            "quarantine_rows_9": report["row_counts"]["quarantine_output"] == 9,
            "reason_counts_match": report["quarantine_counts_by_reason"] == expected_reasons,
            "null_passenger_retained": report["warning_counts"]["passenger_count_missing"] == 1,
            "negative_fare_retained_as_warning": report["warning_counts"]["negative_fare_amount"] == 1,
            "row_conservation": report["row_counts"]["row_conservation_passed"],
            "raw_hashes_unchanged": before == after,
            "bronze_manifest_preserved_on_repeat": repeat_report["bronze"]["manifest_status"] == "preserved",
            "repeat_counts_match": repeat_report["row_counts"] == report["row_counts"],
        }
        result = {
            "status": "pass" if all(assertions.values()) else "fail",
            "seeded_cases": cases,
            "assertions": assertions,
            "observed": {
                "row_counts": report["row_counts"],
                "quarantine_counts_by_reason": report["quarantine_counts_by_reason"],
                "warning_counts": report["warning_counts"],
            },
        }
        if result["status"] != "pass":
            raise AssertionError(json.dumps(result, indent=2))
        if report_path is not None:
            atomic_json(report_path, result)
        return result


if __name__ == "__main__":
    target = PHASE2 / "reports" / "seeded_validation_report.json"
    outcome = run_seeded_validation(target)
    print(json.dumps({"status": outcome["status"], "report_path": str(target)}, indent=2))
