# NYC Mobility Operations Anomaly Agent

## Phase 3 explainable anomaly layer

This layer turns the approved Phase 2 Silver dataset into deterministic Gold metrics, evidence receipts, and a human-review export.

## Reproduce

From this directory:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python src/build_phase3.py
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python tests/seeded_evaluation.py
```

## Outputs

• `gold/zone_hour_metrics.parquet`

• `gold/zone_hour_scored_metrics.parquet`

• `gold/payment_distribution_metrics.parquet`

• `gold/payment_method_shifts.parquet`

• `gold/anomaly_alerts.parquet`

• `review/human_review_queue.csv`

• `evidence/evidence_receipts.jsonl`

• `reports/run_metrics.json`

• `reports/controlled_demand_spike_evaluation.json`

• `contracts/PHASE3_DATA_METRIC_CONTRACT.md`

## Scope boundary

Alerts are investigation prompts. No result claims cause, fraud, fault, or a required action. Phase 3 contains no dashboard, UI, LLM agent, integration, public app, or deployment.
