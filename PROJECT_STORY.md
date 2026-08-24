# NYC Mobility Operations Anomaly Review System

## Honest positioning

Current state: explainable anomaly detection and human-review system.

Not yet built: an autonomous or LLM-based agent.

Use “agent” only after a later layer performs bounded evidence retrieval, assembles a review packet, and waits for human approval.

## Problem

NYC TLC publishes millions of taxi-trip records. Raw records do not tell an operations team where to investigate first.

The project question:

How do we turn public mobility data into a small, explainable review queue without presenting statistical deviation as cause, fraud, or operational failure?

## Process

1. Acquired one official January 2026 Yellow Taxi Parquet file and the official Taxi Zone lookup.

2. Pinned source URLs, file sizes, schemas, row counts, date spans, null rates, zone coverage, and SHA-256 hashes.

3. Preserved immutable Bronze data.

4. Produced typed Silver data and a quarantine dataset.

5. Kept missing passenger counts as unknown. No imputation or silent repair.

6. Quarantined seven month-boundary pickups and one record where drop-off preceded pickup.

7. Aggregated Gold metrics at pickup-zone, date, and hour grain.

8. Compared each zone-hour with leave-one-date-out medians and MAD for the same zone, weekday, and hour.

9. Scored five signals: trip volume, gross fare per trip, median duration, fare per mile, and payment-method mix.

10. Rejected an initial 8,423-alert configuration as review noise. Tightened volume and deviation gates to produce 436 prompts.

11. Linked every alert to a Gold-table evidence query and a human-review row.

12. Passed eight tests, including a controlled demand spike and normal variation.

## Payoff

### System payoff

• 3,724,889 Bronze rows.

• 3,724,881 Silver rows.

• 8 quarantined rows.

• 194,928 zone-hour Gold cells.

• 436 final review prompts.

• 436 matching review rows.

• 436 matching evidence receipts.

### Hiring payoff

The project proves:

• Reproducible public-data ingestion.

• Explicit data contracts.

• Quarantine instead of silent repair.

• Robust and explainable anomaly scoring.

• Threshold calibration against review capacity.

• Test and evaluation design.

• Query-level provenance.

• Human approval boundaries.

Not yet proved:

• Production deployment ownership.

• Operator adoption.

• Measured business or service impact.

• A calibrated production false-positive rate.

• An autonomous agent.

## What remains

### Minimum portfolio finish line

1. Review 10 high-priority alerts manually.

2. Add event, holiday, and weather context to three selected alerts.

3. Record a disposition for each selected alert: plausible operational event, reporting artifact, expected calendar effect, or unresolved.

4. Build a small review interface around the existing queue and evidence receipts.

5. Publish a public-safe sample, architecture diagram, test results, and three reviewed alert stories.

6. Add a three-minute demo video and this case study to the portfolio.

### Optional agent layer

Add only after the deterministic review flow works:

• Retrieve the evidence receipt for a selected alert.

• Retrieve approved context sources.

• Produce a cited investigation brief.

• Ask a human to approve, reject, or request more evidence.

• Never assign cause or trigger an operational action automatically.

## Thirty-second interview answer

“NYC publishes millions of taxi records, but raw data does not tell an operations team where to look first. I built a reproducible Bronze-to-Silver-to-Gold pipeline over 3.7 million January trips. It validates and quarantines bad records, then scores five zone-hour signals against same-weekday and same-hour robust baselines. My first thresholds produced 8,423 alerts, which was unusable, so I tightened the minimum-volume and deviation gates to 436 review prompts. Every prompt links to its Gold evidence query and requires human review. The work proves data quality, evaluation, explainability, provenance, and approval-boundary design. It does not claim production impact or causation.”

## Resume bullet

Built an explainable NYC mobility anomaly-review pipeline over 3.7M TLC taxi trips, using typed Bronze/Silver/Gold contracts, MAD-based zone-hour baselines, record quarantine, seeded evaluations, and query-level provenance to reduce 8,423 first-pass alerts to 436 human-review prompts.

## Carousel sequence

1. Cover: project and transformation.

2. Problem: raw data does not equal operational priority.

3. Process: Bronze, Silver, and quarantine.

4. Process: robust baseline and five signals.

5. Result: alert calibration and evidence checks.

6. Payoff: proven skills, remaining work, and honest boundary.

## LinkedIn caption

NYC publishes millions of taxi-trip records. The harder problem is deciding where a human should investigate first.

I built an explainable anomaly-review system over 3.7 million January 2026 Yellow Taxi trips.

The pipeline:

• Preserves official raw files and source hashes.

• Types and validates 3,724,881 Silver records.

• Quarantines eight contract failures without silent repair.

• Scores five zone-hour signals against same-weekday and same-hour median and MAD baselines.

• Links every alert to its Gold evidence query and a human-review row.

The first configuration produced 8,423 alerts. That was not useful. I tightened the minimum-volume and deviation gates until the system produced 436 traceable review prompts.

The result is not proof of fraud, cause, or production impact. It is proof of a reproducible data pipeline, explainable detection, evaluation, provenance, and human approval boundaries.

Next: review ten high-priority alerts, add event and weather context, then build the review interface.
