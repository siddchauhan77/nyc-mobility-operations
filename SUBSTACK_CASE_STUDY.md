# 3.7 Million Taxi Trips. 436 Places to Investigate.

## How I built an explainable mobility anomaly review system for taxi fleet operations

[IMAGE 1: 01-cover.png]

NYC taxi data contains millions of trip records each month.

A fleet operations leader does not need millions of rows. The leader needs answers to four questions:

• Where did demand change?

• When did service conditions change?

• Which drivers or vehicles need different instructions?

• Which finding deserves human review first?

I built a review system around those questions using 3,724,889 official Yellow Taxi records from January 2026.

The system reduced the raw dataset to 436 traceable investigation prompts. Each prompt identifies a zone, hour, metric, baseline, deviation, and evidence query.

This is a portfolio case study. It does not claim production deployment, fleet adoption, revenue growth, or autonomous decisions.

## The primary buyer

The primary buyer is a taxi fleet operations leader.

This person manages driver supply, shift timing, airport staging, event coverage, and service recovery after disruptions.

The financial problem is simple. A vehicle sitting in the wrong zone creates unpaid time. A vehicle missing a demand surge loses trip revenue. A poor airport dispatch decision creates empty miles and driver frustration.

The buyer needs earlier signals and a short review queue. The buyer does not need another dashboard full of charts.

## So what changed for the decision-maker?

Before this system, a fleet analyst would need to search millions of trip records, choose a metric, choose a location, choose a time window, calculate a comparison, and decide whether the result deserved attention.

After this system, the analyst receives 436 ranked prompts. Each prompt already contains the zone, hour, metric, baseline, deviation, priority, evidence query, and human-review boundary.

The system changed the operating workflow in four ways:

• From broad record searching to ranked investigation.

• From anecdotal disruption reports to evidence-linked prompts.

• From one generic operating plan to event, airport, and storm-recovery decisions.

• From unexplained model output to a human disposition and measurable test.

The validated system impact is narrower than fleet impact:

• Reduced first-pass alert volume from 8,423 to 436, a 94.8% reduction.

• Assigned 343 prompts to high priority and 93 to medium priority.

• Linked all 436 prompts to evidence receipts and review records.

• Passed eight deterministic tests.

The unvalidated business impact includes driver revenue, passenger wait time, empty miles, and completed trips per driver-hour. Those outcomes require a fleet trial.

## The problem

[IMAGE 2: 02-problem.png]

Raw trip records describe completed activity. They do not explain operational significance.

A high trip count might reflect an event, a closure, shifted pickup geography, unusual driver supply, or a reporting issue. A long trip might reflect congestion, weather, routing, road conditions, or a different destination mix.

The system therefore treats every alert as an investigation prompt.

It does not label fraud. It does not assign blame. It does not prescribe an operational action.

The project question became:

How do I turn public mobility data into a small, explainable review queue without confusing deviation with cause?

## The data-quality layer

[IMAGE 3: 03-process-data-quality.png]

I started with one official January 2026 NYC TLC Yellow Taxi Parquet file and the official Taxi Zone lookup.

The preparation process followed three layers:

• Bronze preserved 3,724,889 source records and source hashes.

• Silver produced 3,724,881 typed records.

• Quarantine held eight contract failures. Seven pickups fell outside the target month. One trip recorded drop-off before pickup.

Passenger count was missing for 29.21% of records. I preserved the field as unknown. I did not impute passengers or silently repair source values.

This decision matters. A clean-looking dataset built on invented values creates false confidence.

## The anomaly logic

[IMAGE 4: 04-process-anomaly-logic.png]

I aggregated the Silver records into 194,928 pickup-zone and hour cells.

For each cell, the system compared the observed value with a leave-one-date-out median for the same pickup zone, weekday, and hour. Median absolute deviation measured the size of the difference.

The system evaluated five signals:

• Trip volume.

• Gross fare per trip.

• Median trip duration.

• Median fare per mile.

• Payment-method distribution.

Minimum trip counts and deviation thresholds limited weak alerts.

The first configuration produced 8,423 alerts. No operations team should review 8,423 monthly prompts.

I treated the result as a product failure, not a successful model run.

After tightening eligibility and deviation rules, the final queue contained 436 prompts:

• 278 trip-volume prompts.

• 110 trip-duration prompts.

• 36 fare-per-mile prompts.

• 11 gross-fare prompts.

• One payment-distribution prompt.

Every prompt received a matching evidence receipt and human-review row. Eight deterministic tests passed. A controlled demand-spike test produced one true positive, zero false positives, and zero false negatives.

The controlled test does not estimate production precision or recall.

## Finding one: New Year’s demand moved around closures

[IMAGE 5: 05-results.png]

January 1 produced 176 of the 436 prompts. All 176 occurred between midnight and 5 a.m. Trip volume accounted for 155.

Times Square recorded zero pickups at midnight against a 78.5-trip baseline. Nearby zones such as Chelsea, Greenwich Village, Lower East Side, Clinton, and East Village recorded large increases.

NYC’s official New Year’s operations notice documented vehicle restrictions across the Times Square event area.

Inference: closures displaced pickup activity from Times Square into surrounding neighborhoods.

Fleet decision:

• Establish temporary staging zones outside closure boundaries.

• Send drivers a closure and pickup-zone map before the shift.

• Move available supply toward surrounding demand zones from midnight through 5 a.m.

• Evaluate completed trips per driver-hour against the prior event plan.

## Finding two: LaGuardia pickup volume collapsed during the storm

LaGuardia recorded zero pickups at 10 p.m. and 11 p.m. on January 25. The normal baselines were 230 and 325 pickups.

NYC Emergency Management had issued a winter-storm warning for January 25 and 26, with 8 to 14 inches of snow forecast.

Inference: the airport pickup collapse aligned with the storm disruption window. Taxi records alone do not establish airport closure, flight cancellation, or passenger-demand cause.

Fleet decision:

• Trigger an airport disruption review after a near-zero pickup signal.

• Check official airport and flight status before dispatching more vehicles.

• Pause airport staging instructions when travel demand disappears.

• Track avoided airport waiting time and empty miles.

## Finding three: mobility friction continued after the snow ended

[IMAGE: impact-visual/nyc-map-post-storm.png]

January 27 through 29 produced 138 prompts.

Those three dates contained 95 of 110 duration prompts and 28 of 36 fare-per-mile prompts. Many appeared from noon through 5 p.m. across Midtown and the Upper East Side.

Official city updates described continued dangerous cold and snow operations after the January 25 and 26 storm.

Inference: residual road, curb, traffic, or trip-mix conditions created mobility friction after snowfall ended.

Fleet decision:

• Extend storm monitoring for 72 hours after snowfall.

• Add ETA buffers for affected zones and hours.

• Review driver shift coverage during the recovery period.

• Compare route distance, traffic speed, and destination mix before assigning a cause.

## How to use the map

1. Select New Year’s event, LaGuardia storm, or post-storm recovery.

2. Inspect the highlighted taxi zones.

3. Review the zone, hour, metric, baseline, and evidence receipt.

4. Choose one human-approved operating action.

The map shows alert geography. It does not show live vehicle supply or prove cause.

## How to test the decision

1. Select five alert-informed test zones.

2. Select five comparable control zones.

3. Change one decision in the test zones: staging, airport dispatch, or ETA guidance.

4. Keep the control-zone workflow unchanged.

5. Compare trips per driver-hour, revenue per online hour, empty miles, and pickup delay.

6. Record operator acceptance, rejection, and reason.

This trial determines whether the system creates fleet value.

## The operational product

The useful product is not the anomaly score.

The useful product is a decision packet:

1. Alert: zone, hour, metric, and priority.

2. Evidence: observed value, baseline, deviation, and source query.

3. Context: event, weather, airport status, street closure, or unresolved condition.

4. Human disposition: expected event, plausible disruption, data issue, or unresolved.

5. Proposed test: staging change, dispatch change, ETA adjustment, or no action.

6. Outcome measure: trips per driver-hour, revenue per online hour, empty miles, waiting time, or pickup delay.

The decision packet creates one clear change: a fleet leader moves from asking “What happened?” to choosing “What should we test, where, and for how long?”

An LLM layer belongs after this workflow works. Its job should retrieve approved evidence, prepare a cited brief, and wait for human approval.

## What the project proves

• Reproducible public-data ingestion.

• Typed data contracts.

• Quarantine instead of silent repair.

• Explainable robust-statistics methods.

• Threshold calibration around review capacity.

• Seeded evaluation design.

• Query-level provenance.

• Human approval boundaries.

## What the project does not prove

• Production service ownership.

• Fleet adoption.

• Improved driver earnings.

• Reduced passenger wait time.

• A calibrated production false-positive rate.

• Autonomous agent behavior.

## The business test

[IMAGE 6: 06-payoff-and-next.png]

The next phase should not add more anomaly methods.

It should test one operating decision.

For the next planned event:

• Select five alert-informed staging zones.

• Select five comparable control zones.

• Change driver guidance only in the test zones.

• Measure completed trips per driver-hour, revenue per online hour, empty miles, airport waiting time, and passenger pickup delay.

This experiment connects the technical system to money and service outcomes.

Until then, the honest payoff is faster operational attention, not measured financial impact.

## What I learned

The first model result was not the product.

The first result produced 8,423 alerts. The correct response was to reject it.

Operational software earns value when it helps a person make a better decision within real time and attention limits.

My next step is to review three cases in full:

• New Year’s demand displacement.

• LaGuardia pickup collapse.

• Post-storm Manhattan trip slowdown.

Those three reviews form the bridge from anomaly detection to fleet operations evidence.

## Sources

• NYC TLC Trip Record Data: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

• NYC Open Data Taxi Zones: https://data.cityofnewyork.us/Transportation/NYC-Taxi-Zones/8meu-9t5y

• Official TLC taxi-zone shapefile used by the interactive map: https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip

• NYC 2025–2026 Times Square New Year’s operations notice: https://www.nyc.gov/assets/cecm/downloads/pdf/2025-nye-street-closures-info.pdf

• NYC Emergency Management January 2026 winter-storm advisory: https://www.nyc.gov/site/em/about/press-releases/20260123_pr_nycem_issues-hazardous-travel-advisory.page

• NYC January 27 cold-weather update: https://www.nyc.gov/mayors-office/news/2026/01/mayor-mamdani-releases-new-video-urging-new-yorkers-to-take-prec

## Closing question

If you managed a taxi fleet, which signal would deserve your first review: event displacement, airport demand collapse, or post-storm trip slowdown?
