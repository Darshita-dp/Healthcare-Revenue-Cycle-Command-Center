"""Rules engine: turn revenue cycle data into prioritized follow-up work.

Reads data/processed/ and applies five business rules (documented in
automation/alert_rules.md):

  1. High-value denial        -> High task, Denials Team
  2. A/R aging risk           -> Medium/High task, AR Follow-up Team
  3. Missing documentation    -> High task, Documentation Team
  4. Payer escalation         -> payer-level alert (not a claim task)
  5. Appeal deadline          -> Urgent task, Appeals Team

Outputs:
  data/processed/fact_followup_tasks.csv   (claim-level tasks)
  automation/sample_alert_output.csv       (payer-level alerts)

Idempotency: one task per (claim_id, task_type). Re-running regenerates the
same deterministic set — no duplicate explosion. A deterministic share of
tasks is marked In Progress/Completed to make work-queue KPIs meaningful.

Usage:
    python automation/generate_followup_tasks.py
"""

from __future__ import annotations

import logging
import random
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from etl import config  # noqa: E402

log = logging.getLogger("automation.rules")

AUTOMATION_SEED_OFFSET = 5

# Rule thresholds — single source of truth for docs and code
HIGH_VALUE_DENIAL_THRESHOLD = 5_000.00
AGING_OUTSTANDING_THRESHOLD = 1_000.00
AGING_DAYS_THRESHOLD = 60
AGING_HIGH_PRIORITY_DAYS = 90
PAYER_DENIAL_RATE_THRESHOLD = 0.20
APPEAL_DEADLINE_DAYS = 20

DUE_DAYS = {"Urgent": 2, "High": 5, "Medium": 10, "Low": 15}


def load_inputs() -> dict[str, pd.DataFrame]:
    tables = {}
    for name in ["fact_claims", "fact_denials", "dim_denial_reason", "dim_payer"]:
        path = config.PROCESSED_DIR / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} missing — run `python etl/run_pipeline.py` first")
        tables[name] = pd.read_csv(path)
    return tables


def build_tasks(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    claims = tables["fact_claims"]
    denials = tables["fact_denials"].merge(
        tables["dim_denial_reason"], on="denial_reason_id", how="left")
    denials = denials.merge(
        claims[["claim_id", "claim_status", "outstanding_amount", "is_open"]],
        on="claim_id", how="left")

    candidates: list[dict] = []

    # ---- Rule 1: High-value denial --------------------------------------
    # Unresolved denials worth more than $5,000 get direct review.
    r1 = denials[(denials["denied_amount"] > HIGH_VALUE_DENIAL_THRESHOLD)
                 & (denials["is_open"])]
    for rec in r1.to_dict("records"):
        candidates.append({
            "claim_id": rec["claim_id"],
            "task_type": "Review high-value denied claim",
            "priority": "High",
            "assigned_team": "Denials Team",
            "reason": (f"Rule 1 — denied amount ${rec['denied_amount']:,.2f} "
                       f"exceeds ${HIGH_VALUE_DENIAL_THRESHOLD:,.0f} threshold"),
        })

    # ---- Rule 2: A/R aging risk ------------------------------------------
    # Open claims with meaningful balances aging past 60 days; escalate to
    # High priority once they cross 90 days.
    r2 = claims[(claims["is_open"])
                & (claims["outstanding_amount"] > AGING_OUTSTANDING_THRESHOLD)
                & (claims["claim_age_days"] > AGING_DAYS_THRESHOLD)]
    for rec in r2.to_dict("records"):
        priority = "High" if rec["claim_age_days"] > AGING_HIGH_PRIORITY_DAYS else "Medium"
        candidates.append({
            "claim_id": rec["claim_id"],
            "task_type": "Follow up on aging A/R claim",
            "priority": priority,
            "assigned_team": "AR Follow-up Team",
            "reason": (f"Rule 2 — ${rec['outstanding_amount']:,.2f} outstanding "
                       f"at {rec['claim_age_days']} days"),
        })

    # ---- Rule 3: Missing documentation ------------------------------------
    r3 = denials[(denials["denial_category"] == "Missing documentation")
                 & (denials["is_open"])]
    for rec in r3.to_dict("records"):
        candidates.append({
            "claim_id": rec["claim_id"],
            "task_type": "Request missing documentation",
            "priority": "Medium",
            "assigned_team": "Documentation Team",
            "reason": "Rule 3 — denial category is Missing documentation",
        })

    # ---- Rule 5: Appeal deadline approaching -------------------------------
    # Denials older than 20 days with no appeal filed risk losing appeal
    # rights entirely (typical payer windows are 30–90 days).
    denial_age = (pd.Timestamp(config.AS_OF_DATE)
                  - pd.to_datetime(denials["denial_date"])).dt.days
    r5 = denials[(denials["appeal_status"] == "Not Appealed")
                 & (denial_age > APPEAL_DEADLINE_DAYS)
                 & (denials["is_open"])]
    for rec in r5.to_dict("records"):
        candidates.append({
            "claim_id": rec["claim_id"],
            "task_type": "Appeal deadline approaching",
            "priority": "Urgent",
            "assigned_team": "Appeals Team",
            "reason": (f"Rule 5 — denied "
                       f"{(config.AS_OF_DATE - pd.Timestamp(rec['denial_date']).date()).days} "
                       f"days ago with no appeal filed"),
        })

    # ---- Dedupe + finalize --------------------------------------------------
    tasks = pd.DataFrame(candidates)
    before = len(tasks)
    tasks = tasks.drop_duplicates(subset=["claim_id", "task_type"], keep="first")
    log.info("Deduped %s candidate tasks to %s (one per claim per rule)",
             before, len(tasks))

    # Deterministic ordering, then assign IDs / dates / workflow status
    tasks = tasks.sort_values(
        ["priority", "claim_id", "task_type"],
        key=lambda s: s.map({"Urgent": 0, "High": 1, "Medium": 2, "Low": 3})
        if s.name == "priority" else s,
    ).reset_index(drop=True)

    rng = random.Random(config.RANDOM_SEED + AUTOMATION_SEED_OFFSET)
    rows = []
    for i, rec in enumerate(tasks.to_dict("records"), start=1):
        created = config.AS_OF_DATE - timedelta(days=rng.randint(0, 21))
        due = created + timedelta(days=DUE_DAYS[rec["priority"]])
        roll = rng.random()
        if roll < 0.55:
            status, closed = "Open", None
        elif roll < 0.75:
            status, closed = "In Progress", None
        elif roll < 0.97:
            status = "Completed"
            closed = created + timedelta(days=rng.randint(1, DUE_DAYS[rec["priority"]] + 5))
            closed = min(closed, config.AS_OF_DATE)
        else:
            status, closed = "Cancelled", None
        rows.append({
            "task_id": f"TSK-{i:06d}",
            "claim_id": rec["claim_id"],
            "task_type": rec["task_type"],
            "priority": rec["priority"],
            "assigned_team": rec["assigned_team"],
            "created_date": created,
            "due_date": due,
            "status": status,
            "closed_date": closed,
            "reason": rec["reason"],
        })
    return pd.DataFrame(rows)


def build_payer_alerts(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Rule 4: payer-level denial-rate escalation alerts."""
    claims = tables["fact_claims"]
    payers = tables["dim_payer"]

    stats = (claims.groupby("payer_id")
             .agg(total_claims=("claim_id", "count"),
                  denied_claims=("is_denied", "sum"),
                  denied_outstanding=("outstanding_amount",
                                      lambda s: s[claims.loc[s.index, "is_denied"]].sum()))
             .reset_index())
    stats["denial_rate"] = stats["denied_claims"] / stats["total_claims"]
    stats = stats.merge(payers[["payer_id", "payer_name", "payer_type"]], on="payer_id")

    breaches = stats[stats["denial_rate"] > PAYER_DENIAL_RATE_THRESHOLD].copy()
    breaches = breaches.sort_values("denial_rate", ascending=False)
    alerts = pd.DataFrame({
        "alert_id": [f"ALT-{i:04d}" for i in range(1, len(breaches) + 1)],
        "alert_date": config.AS_OF_DATE.isoformat(),
        "alert_type": "Payer denial rate above threshold",
        "payer_id": breaches["payer_id"].values,
        "payer_name": breaches["payer_name"].values,
        "payer_type": breaches["payer_type"].values,
        "total_claims": breaches["total_claims"].values,
        "denied_claims": breaches["denied_claims"].values,
        "denial_rate_pct": (breaches["denial_rate"] * 100).round(2).values,
        "threshold_pct": PAYER_DENIAL_RATE_THRESHOLD * 100,
        "denied_outstanding_amount": breaches["denied_outstanding"].round(2).values,
        "recommended_action": "Escalate to payer relations; schedule joint operating review",
    })
    return alerts


def main() -> int:
    tables = load_inputs()
    tasks = build_tasks(tables)
    alerts = build_payer_alerts(tables)

    task_path = config.PROCESSED_DIR / "fact_followup_tasks.csv"
    tasks.to_csv(task_path, index=False)
    tasks.head(config.SAMPLE_ROWS).to_csv(
        config.SAMPLE_DIR / "fact_followup_tasks.csv", index=False)

    alert_path = config.PROJECT_ROOT / "automation" / "sample_alert_output.csv"
    alerts.to_csv(alert_path, index=False)

    print(f"Tasks written: {len(tasks):,} -> {task_path}")
    print(tasks.groupby(['priority', 'status']).size().to_string())
    print(f"\nPayer alerts written: {len(alerts)} -> {alert_path}")
    if len(alerts):
        print(alerts[["payer_name", "denial_rate_pct"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())
