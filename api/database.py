"""Data access layer for the API.

CSV mode by default: reads data/processed/ into pandas DataFrames once at
startup and serves everything from memory (the full dataset is a few MB).
If DATABASE_URL is set and reachable, the same tables are read from
PostgreSQL instead — endpoint logic is identical either way.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

log = logging.getLogger("api.database")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ALERTS_CSV = PROJECT_ROOT / "automation" / "sample_alert_output.csv"

TABLES = [
    "dim_patient", "dim_provider", "dim_facility", "dim_payer",
    "dim_denial_reason", "dim_service_line", "dim_date",
    "fact_claims", "fact_denials", "fact_payments", "fact_ar_snapshot",
    "fact_followup_tasks",
]

DATE_COLUMNS = {
    "fact_claims": ["date_of_service", "claim_submission_date"],
    "fact_denials": ["denial_date", "appeal_submitted_date"],
    "fact_payments": ["payment_date"],
    "fact_ar_snapshot": ["snapshot_date"],
    "fact_followup_tasks": ["created_date", "due_date", "closed_date"],
}


class DataStore:
    """Holds all tables plus pre-joined claim views used by the endpoints."""

    def __init__(self) -> None:
        self.mode = "csv"
        self.tables: dict[str, pd.DataFrame] = {}
        self._load()
        self._build_views()

    # ------------------------------------------------------------------ load
    def _load(self) -> None:
        url = os.getenv("DATABASE_URL")
        if url:
            try:
                self._load_postgres(url)
                self.mode = "postgres"
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("PostgreSQL unavailable (%s) — falling back to CSV", exc)
        self._load_csv()

    def _load_postgres(self, url: str) -> None:
        from sqlalchemy import create_engine
        engine = create_engine(url)
        for name in TABLES:
            self.tables[name] = pd.read_sql_table(name, engine)
        log.info("Loaded %s tables from PostgreSQL", len(self.tables))

    def _load_csv(self) -> None:
        missing = []
        for name in TABLES:
            path = PROCESSED_DIR / f"{name}.csv"
            if not path.exists():
                missing.append(name)
                continue
            df = pd.read_csv(path)
            for col in DATE_COLUMNS.get(name, []):
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
            self.tables[name] = df
        if missing:
            raise RuntimeError(
                f"Missing processed tables: {missing}. "
                "Run `python etl/run_pipeline.py` and "
                "`python automation/generate_followup_tasks.py` first.")
        log.info("Loaded %s tables from CSV", len(self.tables))

    # ----------------------------------------------------------------- views
    def _build_views(self) -> None:
        """Pre-join claims with dimension names and latest denial info."""
        c = self.tables["fact_claims"].copy()
        c = c.merge(self.tables["dim_payer"][["payer_id", "payer_name", "payer_type"]],
                    on="payer_id")
        c = c.merge(self.tables["dim_facility"][["facility_id", "facility_name"]],
                    on="facility_id")
        c = c.merge(self.tables["dim_provider"][["provider_id", "provider_name", "specialty"]],
                    on="provider_id")
        c = c.merge(self.tables["dim_service_line"], on="service_line_id")

        denials = self.tables["fact_denials"].merge(
            self.tables["dim_denial_reason"][["denial_reason_id", "denial_category",
                                              "denial_code", "preventable_flag"]],
            on="denial_reason_id")
        c = c.merge(
            denials[["claim_id", "denial_category", "denial_code", "denied_amount",
                     "appeal_status", "appeal_outcome", "recovered_amount"]],
            on="claim_id", how="left")

        c["aging_bucket"] = pd.cut(
            c["claim_age_days"], bins=[-1, 30, 60, 90, 10_000],
            labels=["0-30", "31-60", "61-90", "90+"]).astype(str)

        open_tasks = self.tables["fact_followup_tasks"]
        open_tasks = open_tasks[open_tasks["status"].isin(["Open", "In Progress"])]
        priority_rank = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}
        top_task = (open_tasks.assign(_rank=open_tasks["priority"].map(priority_rank))
                    .sort_values("_rank")
                    .drop_duplicates("claim_id")
                    [["claim_id", "task_type", "priority"]]
                    .rename(columns={"task_type": "action_needed",
                                     "priority": "task_priority"}))
        c = c.merge(top_task, on="claim_id", how="left")
        self.claims_view = c
        log.info("Built claims view: %s rows", len(c))


@lru_cache(maxsize=1)
def get_store() -> DataStore:
    return DataStore()
