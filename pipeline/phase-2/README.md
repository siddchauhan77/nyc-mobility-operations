# NYC Mobility Operations Anomaly Agent

## Phase 2 data readiness

This directory holds the data-quality layer. It does not contain agent or product code.

## Reproduce

From this directory:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python src/prepare_phase2.py
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python tests/seeded_validation.py
```

Generated artifacts:

• `bronze/manifest.json`

• `silver/yellow_taxi_2026-01_silver.parquet`

• `quarantine/yellow_taxi_2026-01_quarantine.parquet`

• `reports/quality_report.json`

• `reports/seeded_validation_report.json`

Raw Phase 1 files remain in the sibling `phase-1` directory and are never overwritten.
