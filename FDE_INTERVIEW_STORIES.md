# NYC Mobility Operations as an FDE Case Study

## Honest classification

This is an FDE-aligned portfolio project.

It is not a completed FDE deployment.

The project proves technical scoping, data preparation, system design, implementation, evaluation, prioritization, provenance, and human approval boundaries.

It does not prove live customer discovery, production integration, user adoption, workflow change, or measured fleet impact.

## What makes work FDE work

An FDE owns the path from an ambiguous customer problem to a working production workflow.

The core sequence is:

1. Understand the operator and the expensive decision.

2. Define a narrow workflow and success metric.

3. Connect messy customer data and systems.

4. Build the smallest useful solution.

5. Evaluate quality, safety, and failure modes.

6. Deploy into the customer workflow.

7. Drive adoption and measure operating impact.

8. Return field feedback to product and engineering.

## Project mapping

### Proved

• Technical problem definition.

• Official data ingestion.

• Typed data contracts.

• Record quarantine.

• Explainable detection logic.

• Evaluation and threshold calibration.

• Evidence receipts.

• Human review boundaries.

• Interactive decision explanation.

### Partially proved

• Buyer definition. Taxi fleet operations is a researched hypothesis, not a signed customer.

• Workflow design. The review flow exists, but no fleet operator has validated it.

• Success metrics. Trips per driver-hour, empty miles, revenue per online hour, and passenger wait time are defined but unmeasured.

### Not proved

• Customer interviews.

• Production deployment.

• Dispatch-system integration.

• Live vehicle-supply data.

• Operator adoption.

• Revenue or service improvement.

• Production support ownership.

## Why this is more than a data-science project

A data-science project ends with anomaly accuracy.

This project continues into:

• Which operator receives the alert?

• Which evidence supports review?

• Which action deserves a test?

• Which human approves the action?

• Which money or service metric measures success?

Those questions make the project FDE-aligned.

## Why this is not yet a full FDE engagement

No customer has changed a workflow based on the system.

No dispatch integration exists.

No operator has adopted the review queue.

No fleet metric has moved.

The final FDE mile is field validation and adoption.

## How an FDE would create impact

### Discovery

Interview a fleet operations leader and a dispatcher.

Identify one costly decision, such as airport staging during disruptions.

Define the current response time, empty miles, airport waiting time, and trips per driver-hour.

### Integration

Connect:

• Live vehicle location and availability.

• Pickup demand.

• Flight and airport status.

• Weather alerts.

• Street closures.

• Dispatch instructions.

### Workflow

Produce one review packet:

• Signal.

• Evidence.

• Context.

• Recommended test.

• Human approval.

• Outcome metric.

### Adoption

Run the workflow beside the existing dispatch process.

Train dispatchers.

Record accepted and rejected recommendations.

Review false alarms and missed events weekly.

### Measurement

Compare test and control zones on:

• Trips per driver-hour.

• Revenue per online hour.

• Empty miles.

• Airport waiting time.

• Passenger pickup delay.

## Interview answer: Why is this FDE-related?

This project is FDE-aligned because I started with an operator decision, not a model. A taxi fleet leader needs to decide where driver supply should move during events, airport disruptions, and storm recovery. I built the data, evaluation, evidence, and human-review layers required for those decisions. I also rejected an 8,423-alert first pass because it failed the operator’s attention constraint. The work crosses data engineering, product judgment, evaluation, and operational workflow design. I would not call it a completed FDE deployment because I have not integrated with a fleet or measured adoption. The next FDE step is customer discovery followed by one controlled airport-staging trial.

## Interview story: Ambiguous problem

### Context

NYC publishes millions of taxi records, but the data does not tell a fleet operator where to investigate or how to change operations.

### Action

I selected taxi fleet operations as the buyer and reframed the technical task around three decisions: event staging, airport dispatch, and storm recovery. I built a reproducible pipeline, five explainable signals, evidence receipts, and a human-review queue.

### Stakes

A weak system would create thousands of alerts, waste dispatcher attention, and encourage unsupported causal claims.

### Evidence

The first run produced 8,423 alerts. I tightened the eligibility and deviation rules, reduced the queue by 94.8% to 436 prompts, linked every prompt to evidence, and passed eight deterministic tests.

### Honest ending

This proves decision triage. A fleet trial must prove operating impact.

## Interview story: Pushing back on a bad result

### Question

Tell me about a time your first solution failed.

### Answer

My first anomaly configuration produced 8,423 alerts. The code worked, but the product failed. No dispatcher should review thousands of monthly prompts. I treated human attention as a system constraint, increased minimum-volume and deviation thresholds, and separated expected event patterns from unexplained deviations. The final queue contained 436 prompts, 94.8% fewer than the first pass. Every prompt retained its evidence trail. I learned to evaluate operational usefulness, not only technical correctness.

## Interview story: Safety and judgment

### Question

How did you manage AI or model risk?

### Answer

I separated signal detection from causal interpretation. Every alert states it is an investigation prompt, not evidence of fraud, fault, or cause. I preserved source records, quarantined contract failures, avoided silent imputation, and attached evidence queries to all 436 prompts. A later language-model layer would retrieve approved context and prepare a cited brief, but a human would approve every operational action.

## Interview story: Measuring impact

### Question

How would you know the project worked?

### Answer

The current system result is measurable: 8,423 first-pass alerts became 436 ranked, evidence-linked prompts. Business success needs a controlled fleet test. I would compare alert-informed staging zones with control zones and measure trips per driver-hour, revenue per online hour, empty miles, airport waiting time, and passenger pickup delay. I would only claim fleet impact after those metrics moved.

## Interview answer: Why FDE instead of data scientist?

A data scientist might optimize the detection method. My interest starts one step earlier and ends several steps later. I want to understand the operator’s decision, connect the required systems, build the workflow, handle failure modes, guide adoption, and measure operational value. This project shows the technical and product middle of the sequence. The missing customer deployment is the next skill I need to prove.

## Interview answer: What would you do next?

I would stop adding anomaly methods. I would interview one fleet operator and one dispatcher, select airport disruption as the first workflow, connect live airport and vehicle-supply context, and run a controlled staging trial. The goal would be lower airport waiting time and empty miles without reducing passenger service.

## Questions to ask an FDE interviewer

• Where does discovery end and implementation begin on your team?

• Which customer workflow metric decides whether a deployment expands?

• How do FDEs balance customer-specific work with reusable product improvements?

• What evidence separates a successful prototype from a production deployment?

• Which adoption failure appears most often after technical delivery?

## Red flags to avoid

• Do not call the current system production.

• Do not claim fleet impact.

• Do not call the deterministic detector an AI agent.

• Do not imply real customer discovery.

• Do not lead with pipeline terminology.

• Do not end the story at model accuracy.
