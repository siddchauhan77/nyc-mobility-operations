#!/usr/bin/env python3
"""Build deterministic Gold metrics and investigation-only anomaly prompts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import duckdb


CONTRACT_VERSION = "3.0.0"
DEFAULT_THRESHOLDS = {
    "minimum_baseline_periods": 3,
    "minimum_zone_hour_trips": 25,
    "minimum_baseline_median_trips": 25,
    "minimum_payment_trips": 40,
    "robust_z_threshold": 3.5,
    "trip_volume_minimum_relative_shift": 0.25,
    "gross_fare_per_trip_minimum_relative_shift": 0.20,
    "median_duration_minimum_relative_shift": 0.25,
    "fare_per_mile_minimum_relative_shift": 0.25,
    "payment_total_variation_threshold": 0.20,
}


def sql_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    os.replace(temporary, path)


def copy_parquet(connection: duckdb.DuckDBPyConnection, query: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep .parquet as the final suffix. DuckDB otherwise appends it and the
    # atomic rename looks for a different filename.
    temporary = path.with_name(path.stem + ".tmp" + path.suffix)
    if temporary.exists():
        temporary.unlink()
    connection.execute(
        f"COPY ({query}) TO {sql_literal(temporary)} "
        "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )
    os.replace(temporary, path)


def relation_rows(connection: duckdb.DuckDBPyConnection, relation: str) -> int:
    return connection.execute(f"SELECT count(*) FROM {relation}").fetchone()[0]


def robust_z(value: float, median: float, mad: float) -> float | None:
    """Return the standard MAD score. A zero MAD has no defined score."""
    if mad <= 0:
        return None
    return 0.6744897501960817 * (value - median) / mad


def metric_is_alert(
    value: float,
    baseline_median: float,
    baseline_mad: float,
    *,
    z_threshold: float,
    relative_threshold: float,
) -> bool:
    score = robust_z(value, baseline_median, baseline_mad)
    if score is None or baseline_median == 0:
        return False
    relative_change = (value - baseline_median) / abs(baseline_median)
    return abs(score) >= z_threshold and abs(relative_change) >= relative_threshold


def payment_total_variation(observed: list[float], baseline: list[float]) -> float:
    """Return total variation distance for aligned payment-share vectors."""
    if len(observed) != len(baseline):
        raise ValueError("Payment-share vectors must have the same length")
    return 0.5 * sum(abs(left - right) for left, right in zip(observed, baseline))


def validate_input(silver_path: Path, quality_report_path: Path) -> dict[str, Any]:
    if not silver_path.is_file() or not quality_report_path.is_file():
        raise FileNotFoundError("Phase 2 Silver data and quality report are required")
    quality = json.loads(quality_report_path.read_text())
    expected = quality["artifacts"]["silver"]
    actual_hash = sha256_file(silver_path)
    if actual_hash != expected["sha256"]:
        raise RuntimeError("Phase 2 Silver hash drift detected")
    return {
        "path": str(silver_path.resolve()),
        "rows": expected["rows"],
        "bytes": silver_path.stat().st_size,
        "sha256": actual_hash,
        "quality_report": str(quality_report_path.resolve()),
    }


def build_gold(connection: duckdb.DuckDBPyConnection, silver_path: Path, output_dir: Path) -> dict[str, Path]:
    source = sql_literal(silver_path)
    connection.execute(f"CREATE OR REPLACE VIEW silver AS SELECT * FROM read_parquet({source})")
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW daily_metrics AS
        SELECT
            pickup_date,
            dayofweek(pickup_date)::UTINYINT AS weekday_number,
            count(*)::BIGINT AS trip_count,
            count(DISTINCT PULocationID)::INTEGER AS active_pickup_zones,
            sum(total_amount)::DOUBLE AS gross_fare_total,
            avg(total_amount)::DOUBLE AS gross_fare_per_trip,
            count(*) FILTER (WHERE trip_duration_seconds BETWEEN 60 AND 14400)::BIGINT AS duration_eligible_trips,
            median(trip_duration_seconds) FILTER (WHERE trip_duration_seconds BETWEEN 60 AND 14400)::DOUBLE AS median_trip_duration_seconds,
            count(*) FILTER (WHERE trip_distance > 0 AND trip_distance <= 200 AND total_amount >= 0)::BIGINT AS fare_per_mile_eligible_trips,
            median(total_amount / trip_distance) FILTER (
                WHERE trip_distance > 0 AND trip_distance <= 200 AND total_amount >= 0
            )::DOUBLE AS median_fare_per_mile
        FROM silver
        GROUP BY pickup_date
    """)
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW zone_hour_metrics AS
        SELECT
            pickup_date,
            dayofweek(pickup_date)::UTINYINT AS weekday_number,
            hour(tpep_pickup_datetime)::UTINYINT AS pickup_hour,
            PULocationID::INTEGER AS pickup_location_id,
            pickup_borough,
            pickup_zone,
            count(*)::BIGINT AS trip_count,
            sum(total_amount)::DOUBLE AS gross_fare_total,
            avg(total_amount)::DOUBLE AS gross_fare_per_trip,
            count(*) FILTER (WHERE trip_duration_seconds BETWEEN 60 AND 14400)::BIGINT AS duration_eligible_trips,
            median(trip_duration_seconds) FILTER (WHERE trip_duration_seconds BETWEEN 60 AND 14400)::DOUBLE AS median_trip_duration_seconds,
            count(*) FILTER (WHERE trip_distance > 0 AND trip_distance <= 200 AND total_amount >= 0)::BIGINT AS fare_per_mile_eligible_trips,
            median(total_amount / trip_distance) FILTER (
                WHERE trip_distance > 0 AND trip_distance <= 200 AND total_amount >= 0
            )::DOUBLE AS median_fare_per_mile
        FROM silver
        GROUP BY ALL
    """)
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW payment_distribution AS
        WITH counts AS (
            SELECT pickup_date,
                   dayofweek(pickup_date)::UTINYINT AS weekday_number,
                   hour(tpep_pickup_datetime)::UTINYINT AS pickup_hour,
                   PULocationID::INTEGER AS pickup_location_id,
                   payment_type::BIGINT AS payment_type,
                   count(*)::BIGINT AS payment_trip_count
            FROM silver
            GROUP BY ALL
        )
        SELECT *,
               sum(payment_trip_count) OVER (
                   PARTITION BY pickup_date, pickup_hour, pickup_location_id
               )::BIGINT AS zone_hour_trip_count,
               payment_trip_count::DOUBLE / sum(payment_trip_count) OVER (
                   PARTITION BY pickup_date, pickup_hour, pickup_location_id
               ) AS payment_share
        FROM counts
    """)
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW peer_baselines AS
        WITH peers AS (
            SELECT current.pickup_date,
                   current.weekday_number,
                   current.pickup_hour,
                   current.pickup_location_id,
                   current.pickup_borough,
                   current.pickup_zone,
                   current.trip_count,
                   current.gross_fare_per_trip,
                   current.duration_eligible_trips,
                   current.median_trip_duration_seconds,
                   current.fare_per_mile_eligible_trips,
                   current.median_fare_per_mile,
                   peer.pickup_date AS peer_date,
                   peer.trip_count AS peer_trip_count,
                   peer.gross_fare_per_trip AS peer_gross_fare_per_trip,
                   peer.median_trip_duration_seconds AS peer_duration,
                   peer.median_fare_per_mile AS peer_fare_per_mile
            FROM zone_hour_metrics current
            JOIN zone_hour_metrics peer
              ON current.pickup_location_id = peer.pickup_location_id
             AND current.pickup_hour = peer.pickup_hour
             AND current.weekday_number = peer.weekday_number
             AND current.pickup_date <> peer.pickup_date
        ), medians AS (
            SELECT pickup_date, weekday_number, pickup_hour, pickup_location_id,
                   pickup_borough, pickup_zone, trip_count, gross_fare_per_trip,
                   duration_eligible_trips, median_trip_duration_seconds,
                   fare_per_mile_eligible_trips, median_fare_per_mile,
                   count(DISTINCT peer_date)::INTEGER AS baseline_periods,
                   median(peer_trip_count)::DOUBLE AS trip_count_baseline_median,
                   median(peer_gross_fare_per_trip)::DOUBLE AS gross_fare_per_trip_baseline_median,
                   median(peer_duration)::DOUBLE AS duration_baseline_median,
                   median(peer_fare_per_mile)::DOUBLE AS fare_per_mile_baseline_median
            FROM peers GROUP BY ALL
        )
        SELECT m.*,
               median(abs(p.peer_trip_count - m.trip_count_baseline_median))::DOUBLE AS trip_count_baseline_mad,
               median(abs(p.peer_gross_fare_per_trip - m.gross_fare_per_trip_baseline_median))::DOUBLE AS gross_fare_per_trip_baseline_mad,
               median(abs(p.peer_duration - m.duration_baseline_median))::DOUBLE AS duration_baseline_mad,
               median(abs(p.peer_fare_per_mile - m.fare_per_mile_baseline_median))::DOUBLE AS fare_per_mile_baseline_mad
        FROM medians m
        JOIN peers p USING (pickup_date, weekday_number, pickup_hour, pickup_location_id)
        GROUP BY ALL
    """)
    paths = {
        "daily_metrics": output_dir / "gold" / "daily_metrics.parquet",
        "zone_hour_metrics": output_dir / "gold" / "zone_hour_metrics.parquet",
        "zone_hour_peer_baselines": output_dir / "gold" / "zone_hour_peer_baselines.parquet",
        "payment_method_distribution": output_dir / "gold" / "payment_method_distribution.parquet",
    }
    copy_parquet(connection, "SELECT * FROM daily_metrics ORDER BY pickup_date", paths["daily_metrics"])
    copy_parquet(connection, "SELECT * FROM zone_hour_metrics ORDER BY pickup_date, pickup_hour, pickup_location_id", paths["zone_hour_metrics"])
    copy_parquet(connection, "SELECT * FROM peer_baselines ORDER BY pickup_date, pickup_hour, pickup_location_id", paths["zone_hour_peer_baselines"])
    copy_parquet(connection, "SELECT * FROM payment_distribution ORDER BY pickup_date, pickup_hour, pickup_location_id, payment_type", paths["payment_method_distribution"])
    return paths


def build_alerts(connection: duckdb.DuckDBPyConnection, output_dir: Path, thresholds: dict[str, Any]) -> tuple[Path, Path]:
    t = thresholds
    z = t["robust_z_threshold"]
    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW numeric_alert_candidates AS
        WITH scored AS (
            SELECT *,
                CASE WHEN trip_count_baseline_mad > 0 THEN 0.6744897501960817 *
                    (trip_count - trip_count_baseline_median) / trip_count_baseline_mad END AS trip_volume_robust_z,
                CASE WHEN gross_fare_per_trip_baseline_mad > 0 THEN 0.6744897501960817 *
                    (gross_fare_per_trip - gross_fare_per_trip_baseline_median) / gross_fare_per_trip_baseline_mad END AS gross_fare_per_trip_robust_z,
                CASE WHEN duration_baseline_mad > 0 THEN 0.6744897501960817 *
                    (median_trip_duration_seconds - duration_baseline_median) / duration_baseline_mad END AS duration_robust_z,
                CASE WHEN fare_per_mile_baseline_mad > 0 THEN 0.6744897501960817 *
                    (median_fare_per_mile - fare_per_mile_baseline_median) / fare_per_mile_baseline_mad END AS fare_per_mile_robust_z
            FROM peer_baselines
        ), long_form AS (
            SELECT *, unnest([
                struct_pack(metric := 'trip_volume', observed := trip_count::DOUBLE, baseline := trip_count_baseline_median, mad := trip_count_baseline_mad, score := trip_volume_robust_z, relative_threshold := {t['trip_volume_minimum_relative_shift']}::DOUBLE, eligible := trip_count >= {t['minimum_zone_hour_trips']}),
                struct_pack(metric := 'gross_fare_per_trip', observed := gross_fare_per_trip, baseline := gross_fare_per_trip_baseline_median, mad := gross_fare_per_trip_baseline_mad, score := gross_fare_per_trip_robust_z, relative_threshold := {t['gross_fare_per_trip_minimum_relative_shift']}::DOUBLE, eligible := trip_count >= {t['minimum_zone_hour_trips']}),
                struct_pack(metric := 'median_trip_duration', observed := median_trip_duration_seconds, baseline := duration_baseline_median, mad := duration_baseline_mad, score := duration_robust_z, relative_threshold := {t['median_duration_minimum_relative_shift']}::DOUBLE, eligible := duration_eligible_trips >= {t['minimum_zone_hour_trips']}),
                struct_pack(metric := 'fare_per_mile', observed := median_fare_per_mile, baseline := fare_per_mile_baseline_median, mad := fare_per_mile_baseline_mad, score := fare_per_mile_robust_z, relative_threshold := {t['fare_per_mile_minimum_relative_shift']}::DOUBLE, eligible := fare_per_mile_eligible_trips >= {t['minimum_zone_hour_trips']})
            ]) AS s
            FROM scored
            WHERE baseline_periods >= {t['minimum_baseline_periods']}
              AND trip_count_baseline_median >= {t['minimum_baseline_median_trips']}
        )
        SELECT pickup_date, pickup_hour, weekday_number, pickup_location_id,
               pickup_borough, pickup_zone, trip_count, baseline_periods,
               s.metric AS metric_name, s.observed AS observed_value,
               s.baseline AS baseline_median, s.mad AS baseline_mad,
               s.score AS robust_z,
               (s.observed - s.baseline) / abs(s.baseline) AS relative_change,
               'gold/zone_hour_peer_baselines.parquet' AS evidence_table
        FROM long_form
        WHERE s.eligible AND s.mad > 0 AND s.baseline <> 0
          AND abs(s.score) >= {z}
          AND abs((s.observed - s.baseline) / abs(s.baseline)) >= s.relative_threshold
    """)
    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW payment_alert_candidates AS
        WITH current_keys AS (
            SELECT DISTINCT pickup_date, weekday_number, pickup_hour, pickup_location_id,
                   zone_hour_trip_count AS trip_count
            FROM payment_distribution
        ), peer_dates AS (
            SELECT c.*, p.pickup_date AS peer_date
            FROM current_keys c JOIN current_keys p
              ON c.weekday_number = p.weekday_number
             AND c.pickup_hour = p.pickup_hour
             AND c.pickup_location_id = p.pickup_location_id
             AND c.pickup_date <> p.pickup_date
        ), baseline_shares AS (
            SELECT pd.pickup_date, pd.weekday_number, pd.pickup_hour, pd.pickup_location_id,
                   pd.trip_count, d.payment_type,
                   avg(coalesce(p.payment_share, 0)) AS baseline_share,
                   count(DISTINCT pd.peer_date)::INTEGER AS baseline_periods
            FROM peer_dates pd
            CROSS JOIN (SELECT DISTINCT payment_type FROM payment_distribution) d
            LEFT JOIN payment_distribution p
              ON p.pickup_date = pd.peer_date
             AND p.pickup_hour = pd.pickup_hour
             AND p.pickup_location_id = pd.pickup_location_id
             AND p.payment_type = d.payment_type
            GROUP BY ALL
        ), distances AS (
            SELECT b.pickup_date, b.weekday_number, b.pickup_hour, b.pickup_location_id,
                   b.trip_count, b.baseline_periods,
                   0.5 * sum(abs(coalesce(c.payment_share, 0) - b.baseline_share)) AS total_variation_distance
            FROM baseline_shares b
            LEFT JOIN payment_distribution c
              ON c.pickup_date = b.pickup_date
             AND c.pickup_hour = b.pickup_hour
             AND c.pickup_location_id = b.pickup_location_id
             AND c.payment_type = b.payment_type
            GROUP BY ALL
        )
        SELECT d.pickup_date, d.pickup_hour, d.weekday_number, d.pickup_location_id,
               m.pickup_borough, m.pickup_zone, d.trip_count, d.baseline_periods,
               'payment_method_distribution' AS metric_name,
               d.total_variation_distance AS observed_value,
               0.0::DOUBLE AS baseline_median,
               NULL::DOUBLE AS baseline_mad,
               NULL::DOUBLE AS robust_z,
               d.total_variation_distance AS relative_change,
               'gold/payment_method_distribution.parquet' AS evidence_table
        FROM distances d
        JOIN zone_hour_metrics m USING (pickup_date, pickup_hour, pickup_location_id)
        WHERE d.trip_count >= {t['minimum_payment_trips']}
          AND d.baseline_periods >= {t['minimum_baseline_periods']}
          AND d.total_variation_distance >= {t['payment_total_variation_threshold']}
    """)
    connection.execute("""
        CREATE OR REPLACE TEMP VIEW review_queue AS
        WITH combined AS (
            SELECT * FROM numeric_alert_candidates
            UNION ALL
            SELECT * FROM payment_alert_candidates
        )
        SELECT
            'P3-' || strftime(pickup_date, '%Y%m%d') || '-' || lpad(pickup_hour::VARCHAR, 2, '0') ||
                '-' || pickup_location_id::VARCHAR || '-' || metric_name AS alert_id,
            pickup_date, pickup_hour, weekday_number, pickup_location_id,
            pickup_borough, pickup_zone, metric_name, trip_count, baseline_periods,
            observed_value, baseline_median, baseline_mad, robust_z, relative_change,
            CASE WHEN relative_change >= 0 THEN 'above_peer_baseline' ELSE 'below_peer_baseline' END AS direction,
            'Investigate this deviation against source records and operating context. The statistic does not identify a cause.' AS investigation_prompt,
            'unreviewed' AS review_status,
            evidence_table
        FROM combined
        ORDER BY abs(coalesce(robust_z, relative_change)) DESC, pickup_date, pickup_hour, pickup_location_id, metric_name
    """)
    parquet_path = output_dir / "alerts" / "anomaly_review_queue.parquet"
    csv_path = output_dir / "alerts" / "anomaly_review_queue.csv"
    copy_parquet(connection, "SELECT * FROM review_queue", parquet_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = csv_path.with_suffix(".csv.tmp")
    connection.execute(f"COPY (SELECT * FROM review_queue) TO {sql_literal(temporary)} (HEADER, DELIMITER ',')")
    os.replace(temporary, csv_path)
    return parquet_path, csv_path


def artifact_record(connection: duckdb.DuckDBPyConnection, path: Path) -> dict[str, Any]:
    relation = f"read_parquet({sql_literal(path)})" if path.suffix == ".parquet" else None
    result = {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
    if relation:
        result["rows"] = relation_rows(connection, relation)
    return result


def create_receipts(connection: duckdb.DuckDBPyConnection, output_dir: Path, queue_path: Path) -> list[dict[str, Any]]:
    queue = sql_literal(queue_path)
    zone_hour = sql_literal(output_dir / "gold" / "zone_hour_metrics.parquet")
    daily = sql_literal(output_dir / "gold" / "daily_metrics.parquet")
    baselines = sql_literal(output_dir / "gold" / "zone_hour_peer_baselines.parquet")
    payments = sql_literal(output_dir / "gold" / "payment_method_distribution.parquet")
    queries = {
        "gold_row_counts": f"""
            SELECT 'zone_hour_metrics' AS gold_table, count(*) AS rows FROM read_parquet({zone_hour})
            UNION ALL SELECT 'daily_metrics', count(*) FROM read_parquet({daily})
            UNION ALL SELECT 'zone_hour_peer_baselines', count(*) FROM read_parquet({baselines})
            UNION ALL SELECT 'payment_method_distribution', count(*) FROM read_parquet({payments})
            ORDER BY gold_table
        """,
        "gold_key_duplicates": f"""
            SELECT 'zone_hour_metrics' AS gold_table, count(*) AS duplicate_keys FROM (
                SELECT pickup_date, pickup_hour, pickup_location_id FROM read_parquet({zone_hour})
                GROUP BY ALL HAVING count(*) > 1
            )
            UNION ALL SELECT 'daily_metrics', count(*) FROM (
                SELECT pickup_date FROM read_parquet({daily}) GROUP BY ALL HAVING count(*) > 1
            )
            UNION ALL SELECT 'zone_hour_peer_baselines', count(*) FROM (
                SELECT pickup_date, pickup_hour, pickup_location_id FROM read_parquet({baselines})
                GROUP BY ALL HAVING count(*) > 1
            )
            UNION ALL SELECT 'payment_method_distribution', count(*) FROM (
                SELECT pickup_date, pickup_hour, pickup_location_id, payment_type FROM read_parquet({payments})
                GROUP BY ALL HAVING count(*) > 1
            ) ORDER BY gold_table
        """,
        "alert_count_by_metric": f"SELECT metric_name, count(*) AS alerts FROM read_parquet({queue}) GROUP BY metric_name ORDER BY metric_name",
        "alert_evidence_join": f"SELECT q.alert_id, q.metric_name, count(*) AS evidence_rows FROM read_parquet({queue}) q LEFT JOIN read_parquet({zone_hour}) g USING (pickup_date, pickup_hour, pickup_location_id) GROUP BY q.alert_id, q.metric_name ORDER BY q.alert_id",
        "unmatched_alerts": f"SELECT count(*) AS unmatched FROM read_parquet({queue}) q LEFT JOIN read_parquet({zone_hour}) g USING (pickup_date, pickup_hour, pickup_location_id) WHERE g.pickup_date IS NULL",
    }
    receipts = []
    for name, query in queries.items():
        result = connection.execute(query)
        columns = [item[0] for item in result.description]
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
        normalized_query = " ".join(query.split())
        receipts.append({
            "receipt_id": name,
            "query": normalized_query,
            "query_sha256": hashlib.sha256(normalized_query.encode()).hexdigest(),
            "result": rows,
        })
    return receipts


def run(silver_path: Path, quality_report_path: Path, output_dir: Path) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    source = validate_input(silver_path, quality_report_path)
    thresholds = dict(DEFAULT_THRESHOLDS)
    connection = duckdb.connect()
    # A single execution thread keeps aggregation and Parquet row ordering stable
    # across reruns, which matters for reproducible evidence receipts.
    connection.execute("SET threads = 1")
    gold_paths = build_gold(connection, silver_path, output_dir)
    queue_path, queue_csv = build_alerts(connection, output_dir, thresholds)
    artifacts = {name: artifact_record(connection, path) for name, path in gold_paths.items()}
    artifacts["anomaly_review_queue_parquet"] = artifact_record(connection, queue_path)
    artifacts["anomaly_review_queue_csv"] = artifact_record(connection, queue_csv)
    alert_counts = {
        row[0]: row[1]
        for row in connection.execute("SELECT metric_name, count(*) FROM review_queue GROUP BY metric_name ORDER BY metric_name").fetchall()
    }
    eligibility_result = connection.execute(f"""
        SELECT
          count(*) AS observed_zone_hours,
          count(*) FILTER (WHERE baseline_periods >= {thresholds['minimum_baseline_periods']}) AS baseline_eligible_zone_hours,
          count(*) FILTER (WHERE trip_count >= {thresholds['minimum_zone_hour_trips']} AND trip_count_baseline_median >= {thresholds['minimum_baseline_median_trips']}) AS volume_eligible_zone_hours,
          count(*) FILTER (WHERE trip_count_baseline_mad = 0) AS zero_trip_count_mad_rows
        FROM peer_baselines
    """)
    eligibility = dict(zip(
        [column[0] for column in eligibility_result.description],
        eligibility_result.fetchone(),
    ))
    receipts = create_receipts(connection, output_dir, queue_path)
    receipt_checks = {
        "all_alerts_match_gold": receipts[-1]["result"][0]["unmatched"] == 0,
        "gold_keys_unique": all(row["duplicate_keys"] == 0 for row in receipts[1]["result"]),
    }
    atomic_json(output_dir / "reports" / "evidence_receipts.json", {
        "contract_version": CONTRACT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "receipts": receipts,
        "checks": receipt_checks,
        "status": "pass" if all(receipt_checks.values()) else "fail",
    })
    seeded_report_path = output_dir / "reports" / "seeded_validation_report.json"
    seeded_report = json.loads(seeded_report_path.read_text()) if seeded_report_path.exists() else {
        "status": "not_run", "cases": []
    }
    seeded_cases = seeded_report["cases"]
    positive_cases = [case for case in seeded_cases if case["expected"]]
    negative_cases = [case for case in seeded_cases if not case["expected"]]
    true_positives = sum(case["actual"] for case in positive_cases)
    true_negatives = sum(not case["actual"] for case in negative_cases)
    seeded_quality = {
        "status": seeded_report["status"],
        "cases": len(seeded_cases),
        "true_positives": true_positives,
        "true_negatives": true_negatives,
        "sensitivity": true_positives / len(positive_cases) if positive_cases else None,
        "specificity": true_negatives / len(negative_cases) if negative_cases else None,
    }
    evaluation = {
        "evaluation_version": CONTRACT_VERSION,
        "status": "pass" if seeded_report["status"] == "pass" and all(receipt_checks.values()) else "fail",
        "method": "seeded synthetic sensitivity and normal-variation specificity tests plus production eligibility accounting",
        "seeded_quality": seeded_quality,
        "checks": {
            "seeded_spike_and_normal_variation_pass": seeded_report["status"] == "pass",
            **receipt_checks,
        },
        "alert_counts_by_metric": alert_counts,
        "production_eligibility": eligibility,
        "known_limits": [
            "One month supplies only three or four leave-one-out peers for most weekday-hour baselines.",
            "Zero MAD groups receive no numeric robust-z alert because dispersion is undefined.",
            "Payment change uses total variation distance and does not attribute a cause.",
            "Observed zone-hours only. Missing zero-trip zone-hours are outside this release.",
            "Alerts are statistical investigation prompts, not findings of fraud, error, or causation.",
        ],
    }
    atomic_json(output_dir / "reports" / "alert_quality_evaluation.json", evaluation)
    finished = datetime.now(timezone.utc)
    report = {
        "run_version": CONTRACT_VERSION,
        "status": evaluation["status"],
        "started_at_utc": started.isoformat(),
        "finished_at_utc": finished.isoformat(),
        "elapsed_seconds": (finished - started).total_seconds(),
        "input": source,
        "thresholds": thresholds,
        "artifacts": artifacts,
        "alert_counts_by_metric": alert_counts,
        "eligibility": eligibility,
        "scope": "Phase 3 deterministic Gold metrics, alert scoring, and human-review export only",
    }
    atomic_json(output_dir / "reports" / "run_metrics.json", report)
    connection.close()
    return report


def main() -> None:
    # src/run_phase3.py -> phase-3 is one level above src.
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--silver", type=Path, default=project.parent / "phase-2" / "silver" / "yellow_taxi_2026-01_silver.parquet")
    parser.add_argument("--quality-report", type=Path, default=project.parent / "phase-2" / "reports" / "quality_report.json")
    parser.add_argument("--output-dir", type=Path, default=project)
    args = parser.parse_args()
    report = run(args.silver, args.quality_report, args.output_dir)
    print(json.dumps({"status": report["status"], "alerts": report["alert_counts_by_metric"], "artifacts": report["artifacts"]}, indent=2))


if __name__ == "__main__":
    main()
