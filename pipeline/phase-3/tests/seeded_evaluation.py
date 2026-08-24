#!/usr/bin/env python3
"""Evaluate Phase 3 alert behavior with a seeded demand spike and normal variation."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb

PHASE3 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PHASE3 / "src"))

from build_phase3 import atomic_json, build_phase3  # noqa: E402


SILVER_SCHEMA_SQL = """
    record_id VARCHAR,
    PULocationID INTEGER,
    pickup_date DATE,
    tpep_pickup_datetime TIMESTAMP,
    total_amount DOUBLE,
    fare_amount DOUBLE,
    trip_distance DOUBLE,
    trip_duration_seconds BIGINT,
    payment_type BIGINT,
    pickup_borough VARCHAR,
    pickup_zone VARCHAR,
    pickup_service_zone VARCHAR
"""


def create_seeded_silver(path: Path) -> dict:
    thursdays = [date(2026, 1, day) for day in (1, 8, 15, 22, 29)]
    seeded = {
        "demand_spike": {"zone": 1, "date": "2026-01-29", "hour": 10, "volume": 220},
        "spike_zone_normal_volumes": [100, 102, 98, 101],
        "normal_zone_volumes": [100, 104, 97, 103, 99],
    }
    rows = []
    row_number = 0
    for zone_id, zone_name, volumes in (
        (1, "Seeded Spike Zone", [100, 102, 98, 101, 220]),
        (2, "Seeded Normal Zone", [100, 104, 97, 103, 99]),
    ):
        for service_date, volume in zip(thursdays, volumes):
            start = datetime.combine(service_date, datetime.min.time()).replace(hour=10)
            for index in range(volume):
                row_number += 1
                pickup = start + timedelta(seconds=index % 3600)
                rows.append((
                    f"seed:{row_number}", zone_id, service_date, pickup,
                    12.0, 10.0, 2.0, 600, 1,
                    "Seed Borough", zone_name, "Seed Service",
                ))
    connection = duckdb.connect()
    connection.execute(f"CREATE TABLE seeded_silver ({SILVER_SCHEMA_SQL})")
    connection.executemany("INSERT INTO seeded_silver VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    connection.execute(f"COPY seeded_silver TO '{path}' (FORMAT PARQUET)")
    seeded["row_count"] = len(rows)
    return seeded


def run_seeded_evaluation(report_path: Path | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix="nyc-phase3-seeded-") as temporary:
        root = Path(temporary)
        silver = root / "seeded_silver.parquet"
        seeded = create_seeded_silver(silver)
        output = root / "phase3"
        run = build_phase3(silver, output, month="2026-01")
        connection = duckdb.connect()
        alerts_path = output / "gold" / "anomaly_alerts.parquet"
        alerts = connection.execute(f"""
            SELECT metric_name, service_date::VARCHAR, hour_of_day, PULocationID
            FROM read_parquet('{alerts_path}')
            ORDER BY metric_name, service_date, hour_of_day, PULocationID
        """).fetchall()
        expected = {("trip_volume", "2026-01-29", 10, 1)}
        detected = set(alerts)
        true_positives = len(expected & detected)
        false_positives = len(detected - expected)
        false_negatives = len(expected - detected)
        precision = true_positives / (true_positives + false_positives) if detected else 0.0
        recall = true_positives / len(expected)
        result = {
            "status": "pass" if true_positives == 1 and false_positives == 0 and false_negatives == 0 else "fail",
            "scope": "Controlled synthetic demand-spike evaluation only. Metrics do not estimate production precision or recall.",
            "seeded_input": seeded,
            "expected_alerts": [list(item) for item in sorted(expected)],
            "detected_alerts": [list(item) for item in sorted(detected)],
            "confusion_counts": {
                "true_positives": true_positives,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "true_negatives": 9,
            },
            "precision": precision,
            "recall": recall,
            "assertions": {
                "seeded_spike_detected": true_positives == 1,
                "normal_variation_not_alerted": false_positives == 0,
                "no_seeded_spike_missed": false_negatives == 0,
                "source_rows_preserved": run["silver_input"]["hash_unchanged"],
                "only_deterministic_gold_outputs": run["status"] == "pass",
            },
        }
        if result["status"] != "pass" or not all(result["assertions"].values()):
            raise AssertionError(json.dumps(result, indent=2))
        if report_path is not None:
            atomic_json(report_path, result)
        return result


if __name__ == "__main__":
    target = PHASE3 / "reports" / "controlled_demand_spike_evaluation.json"
    result = run_seeded_evaluation(target)
    print(json.dumps({"status": result["status"], "report_path": str(target)}, indent=2))
