#!/usr/bin/env python3
"""Prepare immutable NYC TLC Bronze inputs into typed Silver and quarantine outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import duckdb


SOURCE_URLS = {
    "trip_data": "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2026-01.parquet",
    "zone_lookup": "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv",
}

EXPECTED_TRIP_SCHEMA = [
    ("VendorID", "INTEGER"),
    ("tpep_pickup_datetime", "TIMESTAMP"),
    ("tpep_dropoff_datetime", "TIMESTAMP"),
    ("passenger_count", "BIGINT"),
    ("trip_distance", "DOUBLE"),
    ("RatecodeID", "BIGINT"),
    ("store_and_fwd_flag", "VARCHAR"),
    ("PULocationID", "INTEGER"),
    ("DOLocationID", "INTEGER"),
    ("payment_type", "BIGINT"),
    ("fare_amount", "DOUBLE"),
    ("extra", "DOUBLE"),
    ("mta_tax", "DOUBLE"),
    ("tip_amount", "DOUBLE"),
    ("tolls_amount", "DOUBLE"),
    ("improvement_surcharge", "DOUBLE"),
    ("total_amount", "DOUBLE"),
    ("congestion_surcharge", "DOUBLE"),
    ("Airport_fee", "DOUBLE"),
    ("cbd_congestion_fee", "DOUBLE"),
]

EXPECTED_ZONE_SCHEMA = [
    ("LocationID", "BIGINT"),
    ("Borough", "VARCHAR"),
    ("Zone", "VARCHAR"),
    ("service_zone", "VARCHAR"),
]

RAW_COLUMNS = [name for name, _ in EXPECTED_TRIP_SCHEMA]
REQUIRED_COLUMNS = [
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "trip_distance",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount",
    "total_amount",
    "cbd_congestion_fee",
]

QUARANTINE_RULES = {
    "required_field_missing": "required_field_missing",
    "pickup_outside_month": "pickup_outside_month",
    "dropoff_before_pickup": "dropoff_before_pickup",
    "unknown_pickup_zone": "unknown_pickup_zone",
    "unknown_dropoff_zone": "unknown_dropoff_zone",
    "invalid_trip_distance": "invalid_trip_distance",
    "invalid_passenger_count": "invalid_passenger_count",
    "nonfinite_monetary_value": "nonfinite_monetary_value",
    "exact_duplicate": "exact_duplicate",
}

WARNING_RULES = {
    "passenger_count_missing": "passenger_count_missing",
    "zero_duration": "zero_duration",
    "duration_over_24h": "duration_over_24h",
    "zero_trip_distance": "zero_trip_distance",
    "trip_distance_over_200": "trip_distance_over_200",
    "negative_fare_amount": "negative_fare_amount",
    "negative_total_amount": "negative_total_amount",
}


def sql_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def month_bounds(month: str) -> tuple[date, date]:
    start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    end = date(start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1, 1)
    return start, end


def describe_schema(connection: duckdb.DuckDBPyConnection, relation_sql: str) -> list[tuple[str, str]]:
    return [(row[0], row[1]) for row in connection.execute(f"DESCRIBE SELECT * FROM {relation_sql}").fetchall()]


def rows_as_dict(connection: duckdb.DuckDBPyConnection, query: str) -> list[dict[str, Any]]:
    result = connection.execute(query)
    names = [column[0] for column in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


def one_row(connection: duckdb.DuckDBPyConnection, query: str) -> dict[str, Any]:
    return rows_as_dict(connection, query)[0]


def verify_bronze_manifest(manifest_path: Path, payload: dict[str, Any]) -> str:
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text())
        for key in ("trip_data", "zone_lookup"):
            if existing["sources"][key]["sha256"] != payload["sources"][key]["sha256"]:
                raise RuntimeError(f"Bronze source hash changed for {key}; raw input rejected")
        return "preserved"
    atomic_json(manifest_path, payload)
    return "created"


def build_views(
    connection: duckdb.DuckDBPyConnection,
    raw_parquet: Path,
    zone_lookup: Path,
    month_start: date,
    month_end: date,
) -> None:
    raw = sql_literal(raw_parquet)
    zones = sql_literal(zone_lookup)
    partition_columns = ", ".join(f'r."{name}"' for name in RAW_COLUMNS)
    required_missing = " OR ".join(f'r."{name}" IS NULL' for name in REQUIRED_COLUMNS)
    money_columns = [
        "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
        "improvement_surcharge", "total_amount", "congestion_surcharge",
        "Airport_fee", "cbd_congestion_fee",
    ]
    nonfinite_money = " OR ".join(
        f'(r."{name}" IS NOT NULL AND NOT isfinite(r."{name}"))' for name in money_columns
    )

    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW zones AS
        SELECT CAST(LocationID AS BIGINT) AS LocationID, Borough, Zone, service_zone
        FROM read_csv({zones}, header = true, auto_detect = true)
    """)
    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW raw_numbered AS
        SELECT row_number() OVER ()::BIGINT AS source_row_number, *
        FROM read_parquet({raw})
    """)
    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW ranked AS
        SELECT r.*,
               row_number() OVER (
                   PARTITION BY {partition_columns}
                   ORDER BY r.source_row_number
               )::BIGINT AS exact_duplicate_rank
        FROM raw_numbered r
    """)
    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW flags AS
        SELECT
            r.*,
            pu.Borough AS pickup_borough,
            pu.Zone AS pickup_zone,
            pu.service_zone AS pickup_service_zone,
            dz.Borough AS dropoff_borough,
            dz.Zone AS dropoff_zone,
            dz.service_zone AS dropoff_service_zone,
            ({required_missing}) AS required_field_missing,
            (r.tpep_pickup_datetime IS NOT NULL AND
                (r.tpep_pickup_datetime < TIMESTAMP '{month_start}' OR
                 r.tpep_pickup_datetime >= TIMESTAMP '{month_end}')) AS pickup_outside_month,
            (r.tpep_pickup_datetime IS NOT NULL AND r.tpep_dropoff_datetime IS NOT NULL AND
                r.tpep_dropoff_datetime < r.tpep_pickup_datetime) AS dropoff_before_pickup,
            (r.PULocationID IS NOT NULL AND pu.LocationID IS NULL) AS unknown_pickup_zone,
            (r.DOLocationID IS NOT NULL AND dz.LocationID IS NULL) AS unknown_dropoff_zone,
            (r.trip_distance IS NOT NULL AND
                (NOT isfinite(r.trip_distance) OR r.trip_distance < 0)) AS invalid_trip_distance,
            (r.passenger_count IS NOT NULL AND
                (r.passenger_count < 0 OR r.passenger_count > 9)) AS invalid_passenger_count,
            ({nonfinite_money}) AS nonfinite_monetary_value,
            (r.exact_duplicate_rank > 1) AS exact_duplicate,
            (r.passenger_count IS NULL) AS passenger_count_missing,
            (r.tpep_pickup_datetime IS NOT NULL AND r.tpep_dropoff_datetime IS NOT NULL AND
                r.tpep_dropoff_datetime = r.tpep_pickup_datetime) AS zero_duration,
            (r.tpep_pickup_datetime IS NOT NULL AND r.tpep_dropoff_datetime IS NOT NULL AND
                r.tpep_dropoff_datetime - r.tpep_pickup_datetime > INTERVAL '24 hours') AS duration_over_24h,
            (r.trip_distance = 0) AS zero_trip_distance,
            (r.trip_distance > 200) AS trip_distance_over_200,
            (r.fare_amount < 0) AS negative_fare_amount,
            (r.total_amount < 0) AS negative_total_amount
        FROM ranked r
        LEFT JOIN zones pu ON r.PULocationID = pu.LocationID
        LEFT JOIN zones dz ON r.DOLocationID = dz.LocationID
    """)
    reason_parts = ", ".join(
        f"CASE WHEN {column} THEN '{code}' END" for column, code in QUARANTINE_RULES.items()
    )
    warning_parts = ", ".join(
        f"CASE WHEN {column} THEN '{code}' END" for column, code in WARNING_RULES.items()
    )
    quarantine_any = " OR ".join(QUARANTINE_RULES)
    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW evaluated AS
        SELECT *,
               ({quarantine_any}) AS should_quarantine,
               concat_ws('|', {reason_parts}) AS quarantine_reasons,
               concat_ws('|', {warning_parts}) AS quality_warning_codes
        FROM flags
    """)


def output_select(include_quarantine_flags: bool) -> str:
    raw_fields = ",\n            ".join(f'CAST("{name}" AS {kind}) AS "{name}"' for name, kind in EXPECTED_TRIP_SCHEMA)
    common = f"""
            'yellow-2026-01:' || lpad(source_row_number::VARCHAR, 7, '0') AS record_id,
            source_row_number,
            {raw_fields},
            date_trunc('day', tpep_pickup_datetime)::DATE AS pickup_date,
            date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime)::BIGINT AS trip_duration_seconds,
            (passenger_count IS NOT NULL) AS passenger_count_known,
            pickup_borough,
            pickup_zone,
            pickup_service_zone,
            dropoff_borough,
            dropoff_zone,
            dropoff_service_zone,
            quality_warning_codes
    """
    if not include_quarantine_flags:
        return common
    flags = ",\n            ".join(QUARANTINE_RULES)
    return common + f",\n            {flags},\n            quarantine_reasons"


def copy_parquet(connection: duckdb.DuckDBPyConnection, query: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    connection.execute(f"COPY ({query}) TO {sql_literal(temporary)} (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)")
    os.replace(temporary, destination)


def run_preparation(raw_parquet: Path, zone_lookup: Path, output_dir: Path, month: str) -> dict[str, Any]:
    for source in (raw_parquet, zone_lookup):
        if not source.is_file():
            raise FileNotFoundError(source)

    start, end = month_bounds(month)
    raw_before = {
        "trip_data": {"path": str(raw_parquet.resolve()), "bytes": raw_parquet.stat().st_size, "sha256": sha256_file(raw_parquet)},
        "zone_lookup": {"path": str(zone_lookup.resolve()), "bytes": zone_lookup.stat().st_size, "sha256": sha256_file(zone_lookup)},
    }

    connection = duckdb.connect()
    connection.execute("SET threads = 4")
    trip_relation = f"read_parquet({sql_literal(raw_parquet)})"
    zone_relation = f"read_csv({sql_literal(zone_lookup)}, header = true, auto_detect = true)"
    actual_trip_schema = describe_schema(connection, trip_relation)
    actual_zone_schema = describe_schema(connection, zone_relation)
    if actual_trip_schema != EXPECTED_TRIP_SCHEMA:
        raise RuntimeError(f"Trip schema mismatch: {actual_trip_schema}")
    if actual_zone_schema != EXPECTED_ZONE_SCHEMA:
        raise RuntimeError(f"Zone schema mismatch: {actual_zone_schema}")

    zone_profile = one_row(connection, f"""
        SELECT count(*) AS row_count,
               count(DISTINCT LocationID) AS unique_location_ids,
               count(*) FILTER (WHERE LocationID IS NULL OR Borough IS NULL OR Zone IS NULL OR service_zone IS NULL) AS incomplete_rows
        FROM {zone_relation}
    """)
    if zone_profile != {"row_count": 265, "unique_location_ids": 265, "incomplete_rows": 0}:
        raise RuntimeError(f"Zone lookup contract failed: {zone_profile}")

    bronze_manifest = {
        "contract_version": "2.0.0",
        "dataset": "NYC TLC Yellow Taxi, 2026-01",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "immutability_policy": "Raw sources are read-only. Hash drift stops preparation.",
        "sources": {
            "trip_data": {**raw_before["trip_data"], "official_url": SOURCE_URLS["trip_data"]},
            "zone_lookup": {**raw_before["zone_lookup"], "official_url": SOURCE_URLS["zone_lookup"]},
        },
        "schemas": {
            "trip_data": [{"name": name, "type": kind} for name, kind in actual_trip_schema],
            "zone_lookup": [{"name": name, "type": kind} for name, kind in actual_zone_schema],
        },
    }
    bronze_path = output_dir / "bronze" / "manifest.json"
    bronze_status = verify_bronze_manifest(bronze_path, bronze_manifest)

    build_views(connection, raw_parquet, zone_lookup, start, end)
    input_rows = connection.execute("SELECT count(*) FROM evaluated").fetchone()[0]
    reason_counts = {
        name: connection.execute(f"SELECT count(*) FROM evaluated WHERE {name}").fetchone()[0]
        for name in QUARANTINE_RULES
    }
    warning_counts = {
        name: connection.execute(f"SELECT count(*) FROM evaluated WHERE {name}").fetchone()[0]
        for name in WARNING_RULES
    }
    null_expressions = ", ".join(
        f'count(*) FILTER (WHERE "{name}" IS NULL) AS "{name}"' for name in RAW_COLUMNS
    )
    null_counts = one_row(connection, f"SELECT {null_expressions} FROM evaluated")

    silver_path = output_dir / "silver" / "yellow_taxi_2026-01_silver.parquet"
    quarantine_path = output_dir / "quarantine" / "yellow_taxi_2026-01_quarantine.parquet"
    copy_parquet(
        connection,
        f"SELECT {output_select(False)} FROM evaluated WHERE NOT should_quarantine ORDER BY source_row_number",
        silver_path,
    )
    copy_parquet(
        connection,
        f"SELECT {output_select(True)} FROM evaluated WHERE should_quarantine ORDER BY source_row_number",
        quarantine_path,
    )

    silver_rows = connection.execute(f"SELECT count(*) FROM read_parquet({sql_literal(silver_path)})").fetchone()[0]
    quarantine_rows = connection.execute(f"SELECT count(*) FROM read_parquet({sql_literal(quarantine_path)})").fetchone()[0]
    if input_rows != silver_rows + quarantine_rows:
        raise RuntimeError("Row conservation failed")
    raw_after = {
        "trip_data": sha256_file(raw_parquet),
        "zone_lookup": sha256_file(zone_lookup),
    }
    raw_unchanged = all(raw_before[key]["sha256"] == raw_after[key] for key in raw_after)
    if not raw_unchanged:
        raise RuntimeError("Raw source changed during preparation")

    output_artifacts = {}
    for key, path in {"silver": silver_path, "quarantine": quarantine_path}.items():
        output_artifacts[key] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "rows": silver_rows if key == "silver" else quarantine_rows,
            "schema": [
                {"name": name, "type": kind}
                for name, kind in describe_schema(connection, f"read_parquet({sql_literal(path)})")
            ],
        }

    report = {
        "report_version": "2.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "month": month,
        "row_counts": {
            "bronze_input": input_rows,
            "silver_output": silver_rows,
            "quarantine_output": quarantine_rows,
            "row_conservation_passed": input_rows == silver_rows + quarantine_rows,
        },
        "bronze": {
            "manifest_path": str(bronze_path.resolve()),
            "manifest_status": bronze_status,
            "raw_unchanged": raw_unchanged,
            "sources": raw_before,
        },
        "checks": {
            "schema": {"status": "pass", "trip_fields": len(actual_trip_schema), "zone_fields": len(actual_zone_schema)},
            "temporal": {
                "status": "pass",
                "pickup_outside_month": reason_counts["pickup_outside_month"],
                "dropoff_before_pickup": reason_counts["dropoff_before_pickup"],
                "zero_duration_warning": warning_counts["zero_duration"],
                "duration_over_24h_warning": warning_counts["duration_over_24h"],
            },
            "geographic": {
                "status": "pass",
                "unknown_pickup_zone": reason_counts["unknown_pickup_zone"],
                "unknown_dropoff_zone": reason_counts["unknown_dropoff_zone"],
                "lookup": zone_profile,
            },
            "numeric_plausibility": {
                "status": "pass",
                "invalid_trip_distance": reason_counts["invalid_trip_distance"],
                "invalid_passenger_count": reason_counts["invalid_passenger_count"],
                "nonfinite_monetary_value": reason_counts["nonfinite_monetary_value"],
                "warning_counts": {key: warning_counts[key] for key in (
                    "zero_trip_distance", "trip_distance_over_200", "negative_fare_amount", "negative_total_amount"
                )},
            },
            "completeness": {
                "status": "pass",
                "required_field_missing": reason_counts["required_field_missing"],
                "null_counts": null_counts,
                "passenger_count_policy": "Preserve null as unknown; do not impute; retain row with passenger_count_known=false.",
            },
            "duplication": {"status": "pass", "exact_duplicate": reason_counts["exact_duplicate"]},
        },
        "quarantine_counts_by_reason": reason_counts,
        "warning_counts": warning_counts,
        "artifacts": output_artifacts,
        "policies": {
            "passenger_count": "Null is allowed and means unknown. No imputation. Values below 0 or above 9 are quarantined.",
            "month_boundary": f"Pickup must be within [{start}, {end}). Outside rows are quarantined without timestamp repair.",
            "anomaly_retention": "Plausible outliers and provider correction records remain in Silver with warning codes.",
            "silent_repair": "No source values are imputed, clipped, normalized, or overwritten.",
        },
    }
    report_path = output_dir / "reports" / "quality_report.json"
    atomic_json(report_path, report)
    report["quality_report_path"] = str(report_path.resolve())
    return report


def parse_args() -> argparse.Namespace:
    phase2 = Path(__file__).resolve().parents[1]
    phase1 = phase2.parent / "phase-1"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-parquet", type=Path, default=phase1 / "yellow_tripdata_2026-01.parquet")
    parser.add_argument("--zone-lookup", type=Path, default=phase1 / "taxi_zone_lookup.csv")
    parser.add_argument("--output-dir", type=Path, default=phase2)
    parser.add_argument("--month", default="2026-01")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    outcome = run_preparation(arguments.raw_parquet, arguments.zone_lookup, arguments.output_dir, arguments.month)
    print(json.dumps({
        "status": outcome["status"],
        "row_counts": outcome["row_counts"],
        "quarantine_counts_by_reason": outcome["quarantine_counts_by_reason"],
        "quality_report_path": outcome["quality_report_path"],
    }, indent=2))
