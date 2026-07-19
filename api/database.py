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

from automation.priority_scoring import score_claim

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
                "Cannot start the API — required processed CSV files are missing "
                f"from {PROCESSED_DIR}: {missing}. Generate the synthetic dataset "
                "first by running `python etl/run_pipeline.py` and "
                "`python automation/generate_followup_tasks.py` from the repository "
                "root. In a hosted deployment these run as part of the build step, "
                "so a missing-file error here usually means the build did not "
                "complete successfully.")
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
                     "denial_date", "appeal_status", "appeal_outcome", "recovered_amount"]],
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

        # "As of" horizon for age-sensitive logic (the dataset's newest claim)
        self.as_of = self.tables["fact_claims"]["claim_submission_date"].max()

        self._attach_priority_scores(c)
        self.claims_view = c
        log.info("Built claims view: %s rows", len(c))

    # -------------------------------------------------------- priority scores
    def _attach_priority_scores(self, c: pd.DataFrame) -> None:
        """Compute the explainable priority score for every claim in place.

        Adds four columns: priority_score, priority_tier, priority_top_driver,
        and priority_drivers (list of {label, points, category} dicts). The
        scoring itself lives in automation.priority_scoring so the exact same
        rules power the API, and could power the ETL/automation layer too.
        """
        # Payer denial rate feeds the "payer risk" rule
        payer_rate = self.tables["fact_claims"].groupby("payer_id")["is_denied"].mean()

        days_since_denial = (self.as_of - c["denial_date"]).dt.days

        scores, tiers, tops, driver_lists = [], [], [], []
        for i, row in enumerate(c.itertuples(index=False)):
            dsd = days_since_denial.iloc[i]
            result = score_claim(
                is_denied=bool(row.is_denied),
                denied_amount=getattr(row, "denied_amount", 0.0),
                claim_age_days=int(row.claim_age_days),
                outstanding_amount=float(row.outstanding_amount),
                payer_denial_rate=float(payer_rate.get(row.payer_id, 0.0)),
                appeal_status=(row.appeal_status if isinstance(row.appeal_status, str) else None),
                days_since_denial=None if pd.isna(dsd) else int(dsd),
                denial_category=(row.denial_category if isinstance(row.denial_category, str) else None),
            )
            scores.append(result.score)
            tiers.append(result.tier)
            tops.append(result.top_driver)
            driver_lists.append(result.drivers_as_dicts())

        c["priority_score"] = scores
        c["priority_tier"] = tiers
        c["priority_top_driver"] = tops
        c["priority_drivers"] = driver_lists


@lru_cache(maxsize=1)
def get_store() -> DataStore:
    return DataStore()
