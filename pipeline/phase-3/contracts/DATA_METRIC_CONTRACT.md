# NYC Mobility Operations Phase 3 data and metric contract

## Contract

Version: 3.0.0

Input: the hash-pinned Phase 2 Silver Parquet with 3,724,881 Yellow Taxi trip records.

Observation grain: one observed pickup zone, pickup date, and pickup hour.

Baseline peer group: same pickup zone, weekday number, and hour on other dates. The scored observation never contributes to its own baseline.

## Gold tables

• `daily_metrics.parquet`: one systemwide row per pickup date with weekday number, trip count, active pickup zones, gross fare metrics, eligible trip counts, median trip duration, and median fare per mile. It supports inspection and reporting. Alerts use the zone-hour grain below.

• `zone_hour_metrics.parquet`: trip count, gross fare total, gross fare per trip, eligible trip counts, median trip duration, and median fare per mile.

• `zone_hour_peer_baselines.parquet`: observation values plus leave-one-date-out peer medians and median absolute deviations.

• `payment_method_distribution.parquet`: payment counts and shares by observed zone-hour and TLC payment type.

Gross fare means `total_amount`. Gross fare per trip equals `sum(total_amount) / trip_count`.

Trip-duration metrics include trips from 60 seconds through 14,400 seconds. Fare-per-mile metrics include trips with distance above 0 and at most 200 miles and nonnegative total amount. The trip-volume metric counts every Silver record.

## Robust statistics

Numeric deviation score:

`robust_z = 0.6744897501960817 × (observed − peer median) / peer MAD`

MAD means median absolute deviation from the peer median. A zero MAD produces no numeric alert. Numeric alerts require all of these gates:

• At least three leave-one-out baseline dates.

• At least 25 observed trips and a baseline median of at least 25 trips.

• Absolute robust z-score of at least 3.5.

• Absolute relative shift of at least 25% for volume, duration, and fare per mile, or 20% for gross fare per trip.

Payment-method change uses total variation distance: `0.5 × sum(abs(observed share − peer mean share))`. It requires 40 observed trips, three peer dates, and distance of at least 0.20.

## Interpretation policy

Every row in the review queue is an investigation prompt. No row establishes causation, fraud, data error, operational failure, or a prescribed action. Human reviewers must inspect source records and operating context.

## Limits

• January 2026 provides only three or four leave-one-out peers for most weekday-and-hour groups.

• This release scores observed zone-hours. It does not generate explicit zero-trip rows for every zone-hour combination.

• Provider-submitted TLC data carries the Phase 2 source limitations.

• Multiple correlated metrics might flag the same zone-hour.

• No seasonal, weather, event, traffic, enforcement, or business context enters the statistics.
