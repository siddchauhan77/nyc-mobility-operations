# NYC Mobility Operations Anomaly Agent

## Phase 3 data and metric contract

Version: 3.0.0

Scope: deterministic Gold metrics and human-review prompts. No LLM, causal inference, fraud classification, prescribed action, dashboard, integration, public app, or deployment.

## Input

Source: Phase 2 `yellow_taxi_2026-01_silver.parquet`.

Grain: one accepted Yellow Taxi trip.

Required period: pickup dates from 2026-01-01 through 2026-01-31.

The run verifies the Silver SHA-256 against the Phase 2 quality report. It reads the file without mutation and verifies the hash again after processing.

## Gold grains

`zone_hour_metrics.parquet`

• One row per pickup zone, service date, and hour.

• Includes zero-volume cells through a complete January date-hour spine.

• Measures trip count, gross fare total, gross fare per trip, median trip duration, eligible fare-per-mile count, and median fare per mile.

`zone_hour_scored_metrics.parquet`

• Adds leave-one-date-out baselines for the same pickup zone, ISO weekday, and hour.

• Baseline location is the median across peer dates.

• Baseline dispersion is median absolute deviation, or MAD.

• Robust score equals `(observed - baseline median) / max(metric floor, 1.4826 × MAD)`.

`payment_distribution_metrics.parquet`

• One row per zone, service date, hour, and payment type.

• Current share equals payment-type trips divided by zone-hour trips.

• Baseline share uses the leave-one-date-out median share for peer weekdays and hours, normalized to sum to one.

`payment_method_shifts.parquet`

• One row per zone, service date, and hour.

• Distribution distance uses Jensen-Shannon divergence and total variation distance.

`anomaly_alerts.parquet`

• One row per metric alert.

• Each row contains observed value, baseline, dispersion, score, relative deviation, threshold, direction, priority, evidence source, investigation prompt, and interpretation boundary.

## Metric definitions

Trip volume: trip count for the pickup zone-hour.

Gross fare per trip: arithmetic mean of `total_amount`. Negative provider correction records remain included. Phase 3 does not clip or recode them.

Median trip duration: median `trip_duration_seconds`.

Median fare per mile: median `fare_amount / trip_distance` where distance is at least 0.25 miles and fare is nonnegative and finite. Excluded rows remain in Silver. Exclusion only affects this metric denominator.

Payment-method shift: Jensen-Shannon divergence plus total variation distance between current and robust baseline payment shares.

## Alert thresholds

All numerical alerts require at least three leave-one-date-out baseline periods.

• Trip volume: current or baseline median volume at least 75 trips, absolute robust score at least 6.0, and absolute relative deviation at least 100%.

• Gross fare per trip: current volume at least 75, absolute robust score at least 6.0, and absolute relative deviation at least 75%.

• Median duration: current volume at least 75, absolute robust score at least 6.0, and absolute relative deviation at least 75%.

• Median fare per mile: current volume at least 75, at least 45 eligible fare-per-mile trips, absolute robust score at least 6.0, and absolute relative deviation at least 75%.

• Payment distribution: current and baseline median volume at least 75, Jensen-Shannon divergence at least 0.20, and total variation distance at least 0.35.

Score floors stop zero MAD from producing infinite scores: one trip, one dollar per trip, 60 seconds, and $0.25 per mile.

## Interpretation boundary

Every alert is an investigation prompt. An alert states an observed deviation from a limited historical baseline. It does not establish cause, fraud, fault, service failure, business impact, or a prescribed action.

## Limitations

• January supplies only three or four peer dates after leave-one-out filtering.

• Same-weekday and same-hour matching does not control for weather, holidays, events, road closures, policy changes, or provider reporting behavior.

• Pickup zone uses reported location IDs, not raw GPS validation.

• Multiple alerts across correlated metrics are not independent events.

• Thresholds are review-oriented defaults. They have no calibrated false-positive rate on labeled NYC operational incidents.

• Controlled seeded evaluation measures implementation behavior only. It does not estimate production precision or recall.

The controlled evaluation report is `reports/controlled_demand_spike_evaluation.json`.

## Human review

`human_review_queue.csv` starts every alert at `pending`. A reviewer records name, notes, and disposition outside the deterministic build. The pipeline never assigns a causal conclusion or operational action.

## Phase 4 gate

Any dashboard, narrative layer, LLM agent, external integration, public app, or deployment requires explicit user approval.
