import json
from datetime import datetime, timezone
from pathlib import Path

from run_phase3 import metric_is_alert, payment_total_variation


cases = [
    {"case": "demand_spike", "observed": 180, "median": 100, "mad": 2, "relative_threshold": 0.25, "expected": True},
    {"case": "fare_per_trip_spike", "observed": 18, "median": 12, "mad": 0.5, "relative_threshold": 0.20, "expected": True},
    {"case": "duration_spike", "observed": 1500, "median": 900, "mad": 50, "relative_threshold": 0.25, "expected": True},
    {"case": "fare_per_mile_spike", "observed": 6, "median": 4, "mad": 0.2, "relative_threshold": 0.25, "expected": True},
    {"case": "normal_variation", "observed": 104, "median": 100, "mad": 2, "relative_threshold": 0.25, "expected": False},
]
for case in cases:
    case["actual"] = metric_is_alert(
        case["observed"], case["median"], case["mad"],
        z_threshold=3.5, relative_threshold=case["relative_threshold"],
    )
    case["passed"] = case["actual"] == case["expected"]

payment_cases = [
    {"case": "payment_distribution_spike", "observed": [0.45, 0.55], "baseline": [0.75, 0.25], "expected": True},
    {"case": "payment_normal_variation", "observed": [0.72, 0.28], "baseline": [0.75, 0.25], "expected": False},
]
for case in payment_cases:
    case["total_variation_distance"] = payment_total_variation(case["observed"], case["baseline"])
    case["actual"] = case["total_variation_distance"] >= 0.20
    case["passed"] = case["actual"] == case["expected"]

cases.extend(payment_cases)

payload = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "seed": "fixed-explicit-fixtures-v1",
    "cases": cases,
    "status": "pass" if all(case["passed"] for case in cases) else "fail",
}
output = Path(__file__).resolve().parents[1] / "reports" / "seeded_validation_report.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(json.dumps(payload, indent=2))
raise SystemExit(0 if payload["status"] == "pass" else 1)
