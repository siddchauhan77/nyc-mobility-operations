# LinkedIn post

## Ready-to-publish copy

My first NYC taxi anomaly system produced 8,423 alerts.

The code worked. The product failed.

No operations team should review thousands of monthly warnings without knowing which ones matter or why.

I rebuilt the system around human attention.

I processed 3,724,889 official January 2026 NYC Yellow Taxi records through a reproducible Bronze, Silver, and Gold pipeline.

The system:

• Preserves source hashes and raw-data provenance

• Quarantines contract failures instead of silently repairing them

• Compares each zone by weekday and hour using median and MAD baselines

• Scores five explainable operational signals

• Links every final prompt to supporting evidence

• Leaves every decision with a human reviewer

After calibrating minimum-volume and deviation thresholds, the review queue fell from 8,423 alerts to 436 evidence-linked prompts.

That is a 94.8% reduction in review volume.

What did this prove?

• Data-quality and contract design

• Explainable anomaly detection

• Evaluation against normal variation and seeded failures

• Query-level provenance

• Human approval boundaries

What did it not prove?

It did not prove fleet revenue growth, better pickup times, causation, or production ownership.

The real-world next step is a 30-day pilot with a fleet operations director. Dispatch managers would review ranked zone-hour prompts before shifts, approve a staging test, and compare test zones with matched controls.

The measures would be trips per driver-hour, revenue per online hour, empty miles, and pickup delay.

Live case study: https://nyc-mobility-operations.vercel.app/?v=3ps

GitHub: [ADD_REPOSITORY_URL_AFTER_CREATION]

I am building evidence for Forward Deployed Engineer and Applied AI roles focused on reliable, human-reviewed systems.

If you work in fleet operations, mobility, AI deployment, or applied data systems, I would value one answer:

Which operating decision would you test first with this review queue?

## Suggested first comment

Technical boundary: this is a deterministic anomaly-review system built from public historical data. It is not a live fleet platform or autonomous agent. The repository includes the data-quality and anomaly code, contracts, evaluations, public review queue, and interactive case study.

## Suggested media

Attach these three images in order:

1. `carousel/01-cover.png`

2. `carousel/05-results.png`

3. `carousel/06-payoff-and-next.png`
