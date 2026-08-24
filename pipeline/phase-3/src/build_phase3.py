#!/usr/bin/env python3
"""Build explainable Phase 3 Gold metrics and a human-review anomaly queue."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import duckdb


CONFIG: dict[str, Any] = {
    "contract_version": "3.0.0",
    "month": "2026-01",
    "baseline": "leave-one-date-out median and MAD for the same pickup zone, ISO weekday, and hour",
    "minimum_baseline_periods": 3,
    "minimum_zone_hour_trips": 75,
    "minimum_fare_per_mile_trips": 45,
    "robust_z_threshold": 6.0,
    "volume_relative_threshold": 1.00,
    "gross_fare_per_trip_relative_threshold": 0.75,
    "median_duration_relative_threshold": 0.75,
    "fare_per_mile_relative_threshold": 0.75,
    "payment_js_divergence_threshold": 0.20,
    "payment_total_variation_threshold": 0.35,
    "fare_per_mile_minimum_distance": 0.25,
    "scale_floors": {
        "trip_volume": 1.0,
        "gross_fare_per_trip": 1.0,
        "median_duration_seconds": 60.0,
        "median_fare_per_mile": 0.25,
    },
}

REQUIRED_SILVER_SCHEMA = {
    "record_id": "VARCHAR",
    "PULocationID": "INTEGER",
    "pickup_date": "DATE",
    "tpep_pickup_datetime": "TIMESTAMP",
    "total_amount": "DOUBLE",
    "fare_amount": "DOUBLE",
    "trip_distance": "DOUBLE",
    "trip_duration_seconds": "BIGINT",
    "payment_type": "BIGINT",
    "pickup_borough": "VARCHAR",
    "pickup_zone": "VARCHAR",
    "pickup_service_zone": "VARCHAR",
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
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    os.replace(temporary, path)


def month_bounds(month: str) -> tuple[date, date]:
    start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    end = date(start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1, 1)
    return start, end


def describe(connection: duckdb.DuckDBPyConnection, relation: str) -> dict[str, str]:
    return {row[0]: row[1] for row in connection.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()}


def rows_as_dict(connection: duckdb.DuckDBPyConnection, query: str) -> list[dict[str, Any]]:
    result = connection.execute(query)
    names = [column[0] for column in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


def one_row(connection: duckdb.DuckDBPyConnection, query: str) -> dict[str, Any]:
    return rows_as_dict(connection, query)[0]


def copy_parquet(connection: duckdb.DuckDBPyConnection, query: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    connection.execute(
        f"COPY ({query}) TO {sql_literal(temporary)} "
        "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )
    os.replace(temporary, destination)


def copy_csv(connection: duckdb.DuckDBPyConnection, query: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    connection.execute(
        f"COPY ({query}) TO {sql_literal(temporary)} "
        "(FORMAT CSV, HEADER, DELIMITER ',')"
    )
    os.replace(temporary, destination)


def create_metric_views(
    connection: duckdb.DuckDBPyConnection,
    silver_path: Path,
    start: date,
    end: date,
    config: dict[str, Any],
) -> None:
    silver = sql_literal(silver_path)
    min_distance = config["fare_per_mile_minimum_distance"]
    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW silver_source AS
        SELECT * FROM read_parquet({silver})
    """)
    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW zone_dimension AS
        SELECT
            PULocationID,
            any_value(pickup_borough) AS pickup_borough,
            any_value(pickup_zone) AS pickup_zone,
            any_value(pickup_service_zone) AS pickup_service_zone
        FROM silver_source
        GROUP BY PULocationID
    """)
    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW calendar_hours AS
        SELECT
            day_value::DATE AS service_date,
            isodow(day_value)::INTEGER AS iso_weekday,
            hour_value::INTEGER AS hour_of_day
        FROM range(DATE '{start}', DATE '{end}', INTERVAL 1 DAY) AS d(day_value)
        CROSS JOIN range(0, 24) AS h(hour_value)
    """)
    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW trip_features AS
        SELECT
            PULocationID,
            pickup_date AS service_date,
            isodow(pickup_date)::INTEGER AS iso_weekday,
            hour(tpep_pickup_datetime)::INTEGER AS hour_of_day,
            total_amount,
            fare_amount,
            trip_duration_seconds,
            payment_type,
            CASE
                WHEN trip_distance >= {min_distance}
                     AND fare_amount >= 0
                     AND isfinite(fare_amount)
                     AND isfinite(trip_distance)
                THEN fare_amount / trip_distance
            END AS fare_per_mile
        FROM silver_source
    """)
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW observed_zone_hour AS
        SELECT
            PULocationID,
            service_date,
            iso_weekday,
            hour_of_day,
            count(*)::BIGINT AS trip_count,
            sum(total_amount)::DOUBLE AS gross_fare_total,
            avg(total_amount)::DOUBLE AS gross_fare_per_trip,
            median(trip_duration_seconds)::DOUBLE AS median_trip_duration_seconds,
            count(fare_per_mile)::BIGINT AS fare_per_mile_trip_count,
            median(fare_per_mile)::DOUBLE AS median_fare_per_mile
        FROM trip_features
        GROUP BY PULocationID, service_date, iso_weekday, hour_of_day
    """)
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW zone_hour_metrics AS
        SELECT
            c.service_date,
            c.iso_weekday,
            c.hour_of_day,
            z.PULocationID,
            z.pickup_borough,
            z.pickup_zone,
            z.pickup_service_zone,
            coalesce(o.trip_count, 0)::BIGINT AS trip_count,
            o.gross_fare_total,
            o.gross_fare_per_trip,
            o.median_trip_duration_seconds,
            coalesce(o.fare_per_mile_trip_count, 0)::BIGINT AS fare_per_mile_trip_count,
            o.median_fare_per_mile
        FROM calendar_hours c
        CROSS JOIN zone_dimension z
        LEFT JOIN observed_zone_hour o
          ON c.service_date = o.service_date
         AND c.iso_weekday = o.iso_weekday
         AND c.hour_of_day = o.hour_of_day
         AND z.PULocationID = o.PULocationID
    """)
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW zone_hour_baselines AS
        SELECT
            c.*,
            count(p.service_date)::INTEGER AS baseline_periods,
            median(p.trip_count)::DOUBLE AS baseline_trip_count,
            mad(p.trip_count)::DOUBLE AS baseline_trip_count_mad,
            median(p.gross_fare_per_trip)::DOUBLE AS baseline_gross_fare_per_trip,
            mad(p.gross_fare_per_trip)::DOUBLE AS baseline_gross_fare_per_trip_mad,
            median(p.median_trip_duration_seconds)::DOUBLE AS baseline_median_trip_duration_seconds,
            mad(p.median_trip_duration_seconds)::DOUBLE AS baseline_median_trip_duration_seconds_mad,
            median(p.median_fare_per_mile)::DOUBLE AS baseline_median_fare_per_mile,
            mad(p.median_fare_per_mile)::DOUBLE AS baseline_median_fare_per_mile_mad
        FROM zone_hour_metrics c
        JOIN zone_hour_metrics p
          ON c.PULocationID = p.PULocationID
         AND c.iso_weekday = p.iso_weekday
         AND c.hour_of_day = p.hour_of_day
         AND c.service_date <> p.service_date
        GROUP BY ALL
    """)
    floors = config["scale_floors"]
    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW zone_hour_scored_metrics AS
        SELECT
            b.*,
            (trip_count - baseline_trip_count)
                / greatest({floors['trip_volume']}, 1.4826 * coalesce(baseline_trip_count_mad, 0))
                AS trip_volume_robust_z,
            (trip_count - baseline_trip_count) / nullif(abs(baseline_trip_count), 0)
                AS trip_volume_relative_deviation,
            (gross_fare_per_trip - baseline_gross_fare_per_trip)
                / greatest({floors['gross_fare_per_trip']}, 1.4826 * coalesce(baseline_gross_fare_per_trip_mad, 0))
                AS gross_fare_per_trip_robust_z,
            (gross_fare_per_trip - baseline_gross_fare_per_trip)
                / nullif(abs(baseline_gross_fare_per_trip), 0)
                AS gross_fare_per_trip_relative_deviation,
            (median_trip_duration_seconds - baseline_median_trip_duration_seconds)
                / greatest({floors['median_duration_seconds']}, 1.4826 * coalesce(baseline_median_trip_duration_seconds_mad, 0))
                AS median_duration_robust_z,
            (median_trip_duration_seconds - baseline_median_trip_duration_seconds)
                / nullif(abs(baseline_median_trip_duration_seconds), 0)
                AS median_duration_relative_deviation,
            (median_fare_per_mile - baseline_median_fare_per_mile)
                / greatest({floors['median_fare_per_mile']}, 1.4826 * coalesce(baseline_median_fare_per_mile_mad, 0))
                AS fare_per_mile_robust_z,
            (median_fare_per_mile - baseline_median_fare_per_mile)
                / nullif(abs(baseline_median_fare_per_mile), 0)
                AS fare_per_mile_relative_deviation
        FROM zone_hour_baselines b
    """)


def create_payment_views(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW payment_types AS
        SELECT DISTINCT payment_type FROM trip_features
    """)
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW observed_payment_counts AS
        SELECT PULocationID, service_date, iso_weekday, hour_of_day, payment_type, count(*)::BIGINT AS payment_count
        FROM trip_features
        GROUP BY PULocationID, service_date, iso_weekday, hour_of_day, payment_type
    """)
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW payment_daily_distribution AS
        SELECT
            m.service_date,
            m.iso_weekday,
            m.hour_of_day,
            m.PULocationID,
            m.pickup_borough,
            m.pickup_zone,
            m.trip_count,
            p.payment_type,
            coalesce(o.payment_count, 0)::BIGINT AS payment_count,
            CASE WHEN m.trip_count > 0 THEN coalesce(o.payment_count, 0)::DOUBLE / m.trip_count ELSE 0 END AS payment_share
        FROM zone_hour_metrics m
        CROSS JOIN payment_types p
        LEFT JOIN observed_payment_counts o
          ON m.service_date = o.service_date
         AND m.PULocationID = o.PULocationID
         AND m.hour_of_day = o.hour_of_day
         AND p.payment_type = o.payment_type
    """)
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW payment_peer_medians AS
        SELECT
            c.service_date,
            c.iso_weekday,
            c.hour_of_day,
            c.PULocationID,
            c.pickup_borough,
            c.pickup_zone,
            c.trip_count,
            c.payment_type,
            c.payment_count,
            c.payment_share,
            count(p.service_date)::INTEGER AS baseline_periods,
            median(p.payment_share)::DOUBLE AS baseline_raw_median_share,
            median(p.trip_count)::DOUBLE AS baseline_trip_count
        FROM payment_daily_distribution c
        JOIN payment_daily_distribution p
          ON c.PULocationID = p.PULocationID
         AND c.iso_weekday = p.iso_weekday
         AND c.hour_of_day = p.hour_of_day
         AND c.payment_type = p.payment_type
         AND c.service_date <> p.service_date
        GROUP BY ALL
    """)
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW payment_distribution_metrics AS
        SELECT
            *,
            CASE
                WHEN sum(baseline_raw_median_share) OVER (
                    PARTITION BY service_date, PULocationID, hour_of_day
                ) > 0
                THEN baseline_raw_median_share / sum(baseline_raw_median_share) OVER (
                    PARTITION BY service_date, PULocationID, hour_of_day
                )
                ELSE 0
            END AS baseline_payment_share
        FROM payment_peer_medians
    """)
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW payment_method_shifts AS
        WITH components AS (
            SELECT
                *,
                (payment_share + baseline_payment_share) / 2 AS midpoint_share
            FROM payment_distribution_metrics
        )
        SELECT
            service_date,
            iso_weekday,
            hour_of_day,
            PULocationID,
            pickup_borough,
            pickup_zone,
            max(trip_count)::BIGINT AS trip_count,
            min(baseline_periods)::INTEGER AS baseline_periods,
            max(baseline_trip_count)::DOUBLE AS baseline_trip_count,
            sum(
                0.5 * CASE WHEN payment_share > 0 THEN payment_share * ln(payment_share / midpoint_share) ELSE 0 END
              + 0.5 * CASE WHEN baseline_payment_share > 0 THEN baseline_payment_share * ln(baseline_payment_share / midpoint_share) ELSE 0 END
            )::DOUBLE AS jensen_shannon_divergence,
            (0.5 * sum(abs(payment_share - baseline_payment_share)))::DOUBLE AS total_variation_distance,
            string_agg(payment_type::VARCHAR || ':' || round(payment_share, 6)::VARCHAR, ',' ORDER BY payment_type)
                AS current_distribution,
            string_agg(payment_type::VARCHAR || ':' || round(baseline_payment_share, 6)::VARCHAR, ',' ORDER BY payment_type)
                AS baseline_distribution
        FROM components
        GROUP BY service_date, iso_weekday, hour_of_day, PULocationID, pickup_borough, pickup_zone
    """)


def create_alert_view(connection: duckdb.DuckDBPyConnection, config: dict[str, Any]) -> None:
    z = config["robust_z_threshold"]
    min_periods = config["minimum_baseline_periods"]
    min_trips = config["minimum_zone_hour_trips"]
    min_fpm = config["minimum_fare_per_mile_trips"]
    vol_rel = config["volume_relative_threshold"]
    gross_rel = config["gross_fare_per_trip_relative_threshold"]
    dur_rel = config["median_duration_relative_threshold"]
    fpm_rel = config["fare_per_mile_relative_threshold"]
    jsd = config["payment_js_divergence_threshold"]
    tv = config["payment_total_variation_threshold"]

    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW metric_alert_candidates AS
        SELECT 'trip_volume' AS metric_name, service_date, iso_weekday, hour_of_day, PULocationID,
               pickup_borough, pickup_zone, trip_count, trip_count::DOUBLE AS observed_value,
               baseline_trip_count AS baseline_value, baseline_trip_count_mad AS baseline_mad,
               trip_volume_robust_z AS robust_z, trip_volume_relative_deviation AS relative_deviation,
               {z}::DOUBLE AS score_threshold, {vol_rel}::DOUBLE AS relative_threshold,
               baseline_periods, 'zone_hour_scored_metrics' AS evidence_table
        FROM zone_hour_scored_metrics
        WHERE baseline_periods >= {min_periods}
          AND (trip_count >= {min_trips} OR baseline_trip_count >= {min_trips})
          AND abs(trip_volume_robust_z) >= {z}
          AND abs(trip_volume_relative_deviation) >= {vol_rel}
        UNION ALL
        SELECT 'gross_fare_per_trip', service_date, iso_weekday, hour_of_day, PULocationID,
               pickup_borough, pickup_zone, trip_count, gross_fare_per_trip,
               baseline_gross_fare_per_trip, baseline_gross_fare_per_trip_mad,
               gross_fare_per_trip_robust_z, gross_fare_per_trip_relative_deviation,
               {z}, {gross_rel}, baseline_periods, 'zone_hour_scored_metrics'
        FROM zone_hour_scored_metrics
        WHERE baseline_periods >= {min_periods} AND trip_count >= {min_trips}
          AND abs(gross_fare_per_trip_robust_z) >= {z}
          AND abs(gross_fare_per_trip_relative_deviation) >= {gross_rel}
        UNION ALL
        SELECT 'median_trip_duration', service_date, iso_weekday, hour_of_day, PULocationID,
               pickup_borough, pickup_zone, trip_count, median_trip_duration_seconds,
               baseline_median_trip_duration_seconds, baseline_median_trip_duration_seconds_mad,
               median_duration_robust_z, median_duration_relative_deviation,
               {z}, {dur_rel}, baseline_periods, 'zone_hour_scored_metrics'
        FROM zone_hour_scored_metrics
        WHERE baseline_periods >= {min_periods} AND trip_count >= {min_trips}
          AND abs(median_duration_robust_z) >= {z}
          AND abs(median_duration_relative_deviation) >= {dur_rel}
        UNION ALL
        SELECT 'median_fare_per_mile', service_date, iso_weekday, hour_of_day, PULocationID,
               pickup_borough, pickup_zone, trip_count, median_fare_per_mile,
               baseline_median_fare_per_mile, baseline_median_fare_per_mile_mad,
               fare_per_mile_robust_z, fare_per_mile_relative_deviation,
               {z}, {fpm_rel}, baseline_periods, 'zone_hour_scored_metrics'
        FROM zone_hour_scored_metrics
        WHERE baseline_periods >= {min_periods} AND trip_count >= {min_trips}
          AND fare_per_mile_trip_count >= {min_fpm}
          AND abs(fare_per_mile_robust_z) >= {z}
          AND abs(fare_per_mile_relative_deviation) >= {fpm_rel}
    """)
    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW anomaly_alerts AS
        SELECT
            'a_' || substr(md5(metric_name || '|' || service_date::VARCHAR || '|' ||
                PULocationID::VARCHAR || '|' || hour_of_day::VARCHAR), 1, 16) AS alert_id,
            metric_name,
            service_date,
            iso_weekday,
            hour_of_day,
            PULocationID,
            pickup_borough,
            pickup_zone,
            trip_count AS current_trip_count,
            observed_value,
            baseline_value,
            baseline_mad,
            robust_z,
            relative_deviation,
            score_threshold,
            relative_threshold,
            baseline_periods,
            CASE WHEN observed_value > baseline_value THEN 'high' ELSE 'low' END AS direction,
            CASE WHEN abs(robust_z) >= 10 OR abs(relative_deviation) >= 2 THEN 'high' ELSE 'medium' END AS review_priority,
            evidence_table,
            'Review source records and operational context for this zone-hour deviation.' AS investigation_prompt,
            'Investigation prompt only. This alert does not establish cause, fraud, fault, or a prescribed action.' AS interpretation_boundary
        FROM metric_alert_candidates
        UNION ALL
        SELECT
            'a_' || substr(md5('payment_method_distribution|' || service_date::VARCHAR || '|' ||
                PULocationID::VARCHAR || '|' || hour_of_day::VARCHAR), 1, 16),
            'payment_method_distribution',
            service_date,
            iso_weekday,
            hour_of_day,
            PULocationID,
            pickup_borough,
            pickup_zone,
            trip_count,
            jensen_shannon_divergence,
            0::DOUBLE,
            NULL::DOUBLE,
            NULL::DOUBLE,
            total_variation_distance,
            {jsd}::DOUBLE,
            {tv}::DOUBLE,
            baseline_periods,
            'changed',
            CASE WHEN jensen_shannon_divergence >= {jsd * 2} OR total_variation_distance >= {min(0.70, tv * 2)}
                 THEN 'high' ELSE 'medium' END,
            'payment_distribution_metrics',
            'Review payment-type mix and source records for this zone-hour shift.',
            'Investigation prompt only. This alert does not establish cause, fraud, fault, or a prescribed action.'
        FROM payment_method_shifts
        WHERE baseline_periods >= {min_periods}
          AND trip_count >= {min_trips}
          AND baseline_trip_count >= {min_trips}
          AND jensen_shannon_divergence >= {jsd}
          AND total_variation_distance >= {tv}
    """)


def write_evidence_receipts(
    connection: duckdb.DuckDBPyConnection,
    output_dir: Path,
    input_sha256: str,
) -> Path:
    alerts = rows_as_dict(connection, "SELECT * FROM anomaly_alerts ORDER BY alert_id")
    gold_dir = output_dir / "gold"
    receipts_path = output_dir / "evidence" / "evidence_receipts.jsonl"
    receipts_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipts_path.with_suffix(".jsonl.tmp")
    with temporary.open("w") as handle:
        for alert in alerts:
            source_file = (
                gold_dir / "payment_distribution_metrics.parquet"
                if alert["evidence_table"] == "payment_distribution_metrics"
                else gold_dir / "zone_hour_scored_metrics.parquet"
            )
            query = (
                f"SELECT * FROM read_parquet('{source_file}') "
                f"WHERE service_date = DATE '{alert['service_date']}' "
                f"AND PULocationID = {alert['PULocationID']} "
                f"AND hour_of_day = {alert['hour_of_day']}"
            )
            receipt = {
                "alert_id": alert["alert_id"],
                "metric_name": alert["metric_name"],
                "silver_input_sha256": input_sha256,
                "gold_table": str(source_file.resolve()),
                "gold_query": query,
                "observed_value": alert["observed_value"],
                "baseline_value": alert["baseline_value"],
                "baseline_mad": alert["baseline_mad"],
                "robust_z": alert["robust_z"],
                "relative_deviation": alert["relative_deviation"],
                "thresholds": {
                    "score": alert["score_threshold"],
                    "relative_or_distribution": alert["relative_threshold"],
                },
                "interpretation_boundary": alert["interpretation_boundary"],
            }
            handle.write(json.dumps(receipt, default=str, sort_keys=True) + "\n")
    os.replace(temporary, receipts_path)
    return receipts_path


def build_phase3(
    silver_path: Path,
    output_dir: Path,
    month: str = "2026-01",
    expected_input_sha256: str | None = None,
) -> dict[str, Any]:
    if not silver_path.is_file():
        raise FileNotFoundError(silver_path)
    start, end = month_bounds(month)
    input_hash_before = sha256_file(silver_path)
    if expected_input_sha256 and input_hash_before != expected_input_sha256:
        raise RuntimeError("Phase 2 Silver hash does not match the approved quality report")

    connection = duckdb.connect()
    connection.execute("SET threads = 4")
    relation = f"read_parquet({sql_literal(silver_path)})"
    schema = describe(connection, relation)
    mismatches = {
        name: {"expected": kind, "actual": schema.get(name)}
        for name, kind in REQUIRED_SILVER_SCHEMA.items()
        if schema.get(name) != kind
    }
    if mismatches:
        raise RuntimeError(f"Silver schema contract failed: {mismatches}")
    source_profile = one_row(connection, f"""
        SELECT count(*)::BIGINT AS row_count, min(pickup_date) AS min_date, max(pickup_date) AS max_date,
               count(DISTINCT PULocationID)::BIGINT AS pickup_zone_count
        FROM {relation}
    """)
    if source_profile["min_date"] < start or source_profile["max_date"] >= end:
        raise RuntimeError(f"Silver date contract failed: {source_profile}")

    config = {**CONFIG, "month": month}
    create_metric_views(connection, silver_path, start, end, config)
    create_payment_views(connection)
    create_alert_view(connection, config)

    gold = output_dir / "gold"
    artifacts = {
        "zone_hour_metrics": gold / "zone_hour_metrics.parquet",
        "zone_hour_scored_metrics": gold / "zone_hour_scored_metrics.parquet",
        "payment_distribution_metrics": gold / "payment_distribution_metrics.parquet",
        "payment_method_shifts": gold / "payment_method_shifts.parquet",
        "anomaly_alerts": gold / "anomaly_alerts.parquet",
    }
    copy_parquet(connection, "SELECT * FROM zone_hour_metrics ORDER BY service_date, PULocationID, hour_of_day", artifacts["zone_hour_metrics"])
    copy_parquet(connection, "SELECT * FROM zone_hour_scored_metrics ORDER BY service_date, PULocationID, hour_of_day", artifacts["zone_hour_scored_metrics"])
    copy_parquet(connection, "SELECT * FROM payment_distribution_metrics ORDER BY service_date, PULocationID, hour_of_day, payment_type", artifacts["payment_distribution_metrics"])
    copy_parquet(connection, "SELECT * FROM payment_method_shifts ORDER BY service_date, PULocationID, hour_of_day", artifacts["payment_method_shifts"])
    copy_parquet(connection, "SELECT * FROM anomaly_alerts ORDER BY review_priority, service_date, PULocationID, hour_of_day, metric_name", artifacts["anomaly_alerts"])

    review_path = output_dir / "review" / "human_review_queue.csv"
    copy_csv(connection, """
        SELECT
            alert_id,
            review_priority,
            'pending' AS review_status,
            metric_name,
            service_date,
            hour_of_day,
            PULocationID,
            pickup_borough,
            pickup_zone,
            current_trip_count,
            observed_value,
            baseline_value,
            robust_z,
            relative_deviation,
            direction,
            investigation_prompt,
            interpretation_boundary,
            '' AS reviewer,
            '' AS review_notes,
            '' AS disposition
        FROM anomaly_alerts
        ORDER BY CASE review_priority WHEN 'high' THEN 1 ELSE 2 END,
                 service_date, PULocationID, hour_of_day, metric_name
    """, review_path)
    receipts_path = write_evidence_receipts(connection, output_dir, input_hash_before)

    alert_counts = rows_as_dict(connection, """
        SELECT metric_name, review_priority, direction, count(*)::BIGINT AS alert_count
        FROM anomaly_alerts
        GROUP BY metric_name, review_priority, direction
        ORDER BY metric_name, review_priority, direction
    """)
    eligibility = one_row(connection, f"""
        SELECT
            count(*)::BIGINT AS zone_hour_cells,
            count(*) FILTER (WHERE baseline_periods >= {config['minimum_baseline_periods']}
                AND (trip_count >= {config['minimum_zone_hour_trips']} OR baseline_trip_count >= {config['minimum_zone_hour_trips']}))::BIGINT
                AS volume_evaluated_cells,
            count(*) FILTER (WHERE baseline_periods >= {config['minimum_baseline_periods']}
                AND trip_count >= {config['minimum_zone_hour_trips']})::BIGINT AS per_trip_metric_evaluated_cells,
            count(*) FILTER (WHERE baseline_periods >= {config['minimum_baseline_periods']}
                AND trip_count >= {config['minimum_zone_hour_trips']}
                AND fare_per_mile_trip_count >= {config['minimum_fare_per_mile_trips']})::BIGINT AS fare_per_mile_evaluated_cells
        FROM zone_hour_scored_metrics
    """)
    gold_counts = {
        name: connection.execute(f"SELECT count(*) FROM read_parquet({sql_literal(path)})").fetchone()[0]
        for name, path in artifacts.items()
    }
    input_hash_after = sha256_file(silver_path)
    if input_hash_after != input_hash_before:
        raise RuntimeError("Phase 2 Silver input changed during Phase 3")

    artifact_manifest: dict[str, dict[str, Any]] = {}
    all_artifacts = {**artifacts, "human_review_queue": review_path, "evidence_receipts": receipts_path}
    evaluation_path = output_dir / "reports" / "controlled_demand_spike_evaluation.json"
    if evaluation_path.exists():
        all_artifacts["controlled_demand_spike_evaluation"] = evaluation_path
    for name, path in all_artifacts.items():
        artifact_rows = gold_counts.get(name)
        if name in {"human_review_queue", "evidence_receipts"}:
            artifact_rows = gold_counts["anomaly_alerts"]
        artifact_manifest[name] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "rows": artifact_rows,
        }
    report = {
        "run_version": "3.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "scope_boundary": "Deterministic Gold metrics and human-review prompts only. No causal claim, LLM, UI, integration, or deployment.",
        "silver_input": {
            "path": str(silver_path.resolve()),
            "sha256": input_hash_before,
            "hash_unchanged": input_hash_before == input_hash_after,
            **source_profile,
        },
        "configuration": config,
        "eligibility": eligibility,
        "gold_row_counts": gold_counts,
        "alert_count": gold_counts["anomaly_alerts"],
        "human_review_queue_rows": gold_counts["anomaly_alerts"],
        "evidence_receipt_rows": gold_counts["anomaly_alerts"],
        "alert_counts": alert_counts,
        "artifacts": artifact_manifest,
    }
    report_path = output_dir / "reports" / "run_metrics.json"
    atomic_json(report_path, report)
    report["run_metrics_path"] = str(report_path.resolve())
    return report


def load_expected_hash(phase2_report: Path) -> str:
    payload = json.loads(phase2_report.read_text())
    return payload["artifacts"]["silver"]["sha256"]


def parse_args() -> argparse.Namespace:
    phase3 = Path(__file__).resolve().parents[1]
    phase2 = phase3.parent / "phase-2"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silver", type=Path, default=phase2 / "silver" / "yellow_taxi_2026-01_silver.parquet")
    parser.add_argument("--phase2-report", type=Path, default=phase2 / "reports" / "quality_report.json")
    parser.add_argument("--output-dir", type=Path, default=phase3)
    parser.add_argument("--month", default="2026-01")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    outcome = build_phase3(
        silver_path=arguments.silver,
        output_dir=arguments.output_dir,
        month=arguments.month,
        expected_input_sha256=load_expected_hash(arguments.phase2_report),
    )
    print(json.dumps({
        "status": outcome["status"],
        "gold_row_counts": outcome["gold_row_counts"],
        "alert_count": outcome["alert_count"],
        "alert_counts": outcome["alert_counts"],
        "run_metrics_path": outcome["run_metrics_path"],
    }, indent=2, default=str))
