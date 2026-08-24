# NYC Mobility Operations Interview Answer

## The answer structure

Use this order:

1. Buyer.

2. Costly decision.

3. What you built.

4. What changed.

5. Measured system result.

6. Unmeasured business result.

7. Next proof step.

Do not lead with Bronze, Silver, Gold, MAD, Parquet, or anomaly thresholds. Those details answer “How?” They do not answer “So what?”

## Fifteen-second answer

I built a decision-support system for taxi fleet operations. It converted 3.7 million trip records into 436 ranked, evidence-linked investigation prompts. It identified where event closures displaced demand, where airport pickups collapsed during a storm, and where trip slowdowns persisted afterward.

## Forty-five-second answer

I built a decision-support system for a taxi fleet operations leader. The problem was not a lack of data. The problem was deciding where fleet attention and driver supply should move.

I processed 3.7 million NYC taxi trips into 436 ranked investigation prompts. My first configuration produced 8,423 alerts, so I tightened the eligibility and deviation rules and reduced alert noise by 94.8%.

Each final prompt includes its zone, hour, baseline, deviation, evidence query, and human-review step. In an operating workflow, those prompts support driver staging around New Year’s closures, airport dispatch review when LaGuardia pickups fall near zero, and extended storm-recovery monitoring when Manhattan trip times stay elevated.

The measured result is a smaller, prioritized, traceable review workload. Fleet revenue, passenger wait time, and empty-mile improvements remain untested. The next proof step is a controlled staging trial measured by trips per driver-hour, revenue per online hour, empty miles, and passenger wait time.

## Ninety-second answer

The buyer is a taxi fleet operations leader responsible for driver supply, shift timing, airport staging, event coverage, and disruption recovery.

The existing problem starts with too much data and no ranked decision. January 2026 contained 3.7 million Yellow Taxi records. An analyst still needed to decide which zone, hour, and metric deserved review.

I built a deterministic review system with an immutable raw layer, typed clean data, quarantined contract failures, zone-hour metrics, robust baselines, and five operational signals. The first configuration produced 8,423 alerts. I rejected the result because a human team would not review it. Stronger volume and deviation gates reduced the queue to 436 prompts, a 94.8% reduction.

The system surfaced three useful operating cases. New Year’s closures aligned with zero Times Square pickups and large increases in surrounding zones. LaGuardia pickups fell to zero during two late-night storm hours against baselines of 230 and 325. After the storm, duration and fare-per-mile prompts remained concentrated in Manhattan for three days.

Those findings support three decisions: stage drivers outside event closure zones, verify airport status before dispatching more vehicles, and extend recovery monitoring after snowfall ends.

Every prompt links to its evidence query and requires human disposition. I do not claim causation, fleet adoption, or financial impact. The system has proved decision triage and traceability. A fleet trial must prove trips per driver-hour, driver revenue, empty miles, and passenger wait-time improvement.

## If the interviewer asks, “What impact did you make?”

Say:

I produced measurable system impact, not production fleet impact. I reduced an unreviewable 8,423-alert first pass to 436 ranked prompts, linked every prompt to evidence, and defined the operating decisions and money metrics for a controlled fleet test. I would not claim revenue or wait-time improvement before running the trial.

## If the interviewer asks, “Why does anyone care?”

Say:

A taxi fleet loses money when drivers wait at a disrupted airport, miss an event-driven demand shift, or follow normal staffing plans during storm recovery. This system identifies the zone and hour requiring review, presents the evidence, and gives the operator a specific action hypothesis to test.

## If the interviewer asks, “Is this an AI agent?”

Say:

Not yet. The current product is an explainable anomaly-review system. A later agent layer would retrieve approved context, prepare a cited investigation brief, and wait for human approval. I separated deterministic evidence from narrative generation on purpose.

## Proof boundaries

Proved:

• 3,724,881 typed Silver records.

• 194,928 zone-hour metrics.

• 8,423 first-pass alerts reduced to 436 final prompts.

• 436 evidence receipts.

• 436 human-review records.

• Eight passing deterministic tests.

Not proved:

• Production deployment.

• Fleet adoption.

• Driver revenue improvement.

• Passenger wait-time improvement.

• Reduced empty miles.

• Production precision or recall.

## Rehearsal rule

Stop after the forty-five-second answer. Let the interviewer choose the technical follow-up.
