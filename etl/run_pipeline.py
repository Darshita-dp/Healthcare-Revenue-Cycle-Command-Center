"""ETL pipeline orchestrator.

Runs the full build: dimensions -> claims -> denials -> payments -> A/R
snapshots, then writes all tables to data/processed/ (full) and
data/sample/ (first N rows for quick review / Power BI prototyping).

Usage:
    python etl/run_pipeline.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow running as a script from the repo root or the etl/ folder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from etl import config  # noqa: E402
from etl.generate_synthetic_data import generate_all  # noqa: E402
from etl.transform_claims import transform_claims  # noqa: E402
from etl.generate_denials import generate_denials  # noqa: E402
from etl.generate_payments import generate_payments, generate_ar_snapshots  # noqa: E402

log = logging.getLogger("etl.pipeline")

CLAIM_EXPORT_COLUMNS = [
    "claim_id", "patient_id", "provider_id", "facility_id", "payer_id",
    "service_line_id", "date_of_service", "claim_submission_date",
    "claim_status", "billed_amount", "allowed_amount", "paid_amount",
    "patient_responsibility", "outstanding_amount", "claim_age_days",
    "is_denied", "is_paid", "is_open", "is_high_value",
]


def write_outputs(tables: dict[str, pd.DataFrame]) -> None:
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    config.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        full_path = config.PROCESSED_DIR / f"{name}.csv"
        df.to_csv(full_path, index=False)
        df.head(config.SAMPLE_ROWS).to_csv(config.SAMPLE_DIR / f"{name}.csv", index=False)
        log.info("Wrote %-25s %7d rows -> %s", name, len(df), full_path.name)


def run() -> dict[str, pd.DataFrame]:
    log.info("=== Revenue cycle ETL pipeline start (seed=%s, as_of=%s) ===",
             config.RANDOM_SEED, config.AS_OF_DATE)
    try:
        data = generate_all()
        base_claims = data.pop("base_claims")

        claims = transform_claims(base_claims)
        denials, claims = generate_denials(claims)
        payments = generate_payments(claims)
        snapshots = generate_ar_snapshots(claims)

        tables: dict[str, pd.DataFrame] = {
            **data,
            "fact_claims": claims[CLAIM_EXPORT_COLUMNS],
            "fact_denials": denials,
            "fact_payments": payments,
            "fact_ar_snapshot": snapshots,
        }
        write_outputs(tables)
        log.info("=== Pipeline complete: %s tables written ===", len(tables))
        return tables
    except Exception:
        log.exception("Pipeline failed")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    tables = run()
    print("\nRow counts:")
    for name, df in tables.items():
        print(f"  {name:25s} {len(df):>8,}")
