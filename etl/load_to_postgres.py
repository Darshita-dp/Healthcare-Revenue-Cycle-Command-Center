"""Load processed CSVs into the PostgreSQL star schema.

Connection comes from environment variables (or a .env file):
    DATABASE_URL=postgresql+psycopg2://rcm_user:rcm_password@localhost:5432/revenue_cycle
or the individual parts:
    POSTGRES_HOST / POSTGRES_PORT / POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD

Prerequisites:
    docker compose up -d          # or any running PostgreSQL 13+
    psql -f database/schema.sql   # done automatically by the Docker image

Tables load in dependency order (dims first, then facts) with truncation,
so the loader is rerunnable. If PostgreSQL is unreachable the script exits
with clear instructions — the rest of the project (API, automation, BI)
works from CSVs and does not require this step.

Usage:
    python etl/load_to_postgres.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from etl import config  # noqa: E402

log = logging.getLogger("etl.load")

# Load order matters: dimensions before facts, claims before claim children
LOAD_ORDER = [
    "dim_date", "dim_facility", "dim_payer", "dim_service_line",
    "dim_denial_reason", "dim_patient", "dim_provider",
    "fact_claims", "fact_denials", "fact_payments", "fact_ar_snapshot",
    "fact_followup_tasks",
]


def database_url() -> str:
    try:
        from dotenv import load_dotenv
        load_dotenv(config.PROJECT_ROOT / ".env")
    except ImportError:
        pass
    if url := os.getenv("DATABASE_URL"):
        return url
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "revenue_cycle")
    user = os.getenv("POSTGRES_USER", "rcm_user")
    pw = os.getenv("POSTGRES_PASSWORD", "rcm_password")
    return f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}"


def main() -> int:
    url = database_url()
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — any driver error means "not reachable"
        log.error("Cannot reach PostgreSQL: %s", exc)
        print(
            "\nPostgreSQL is not reachable. To use database mode:\n"
            "  1. docker compose up -d        (starts PostgreSQL 16 with schema)\n"
            "  2. python etl/load_to_postgres.py\n\n"
            "CSV mode needs no database — the API and analytics read\n"
            "data/processed/ directly, so you can skip this step entirely.",
            file=sys.stderr,
        )
        return 2

    loaded = 0
    with engine.begin() as conn:
        # Truncate in reverse dependency order for rerunnability
        existing = [t for t in LOAD_ORDER
                    if (config.PROCESSED_DIR / f"{t}.csv").exists()]
        conn.execute(text(
            "TRUNCATE " + ", ".join(reversed(existing)) + " CASCADE"))
        for table in existing:
            df = pd.read_csv(config.PROCESSED_DIR / f"{table}.csv")
            df.to_sql(table, conn, if_exists="append", index=False,
                      method="multi", chunksize=1000)
            log.info("Loaded %-22s %7d rows", table, len(df))
            loaded += 1

    print(f"Loaded {loaded} tables into PostgreSQL ({url.split('@')[-1]})")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())
