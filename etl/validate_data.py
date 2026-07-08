"""Data quality validation suite for the processed revenue cycle dataset.

Checks (each is a named gate; the run fails if any gate fails):
  1. Row counts meet minimum volumes
  2. Key columns contain no nulls
  3. No negative financial amounts anywhere
  4. Referential integrity: every fact FK resolves to a dimension row
  5. Claim status values are within the allowed vocabulary
  6. Denial rows exist only for denied claims (and vice versa)
  7. Payment rows only where paid_amount > 0; payments reconcile to claims
  8. A/R aging buckets match days-outstanding math
  9. Date sanity: submission >= date of service; no future dates past AS_OF

Writes a human-readable report to data/processed/validation_report.md and
exits non-zero on failure so it can gate CI or a Makefile target.

Usage:
    python etl/validate_data.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from etl import config  # noqa: E402

VALID_STATUSES = {"Submitted", "Paid", "Denied", "Partially Paid",
                  "Under Review", "Appealed", "Closed"}
VALID_BUCKETS = {"0-30", "31-60", "61-90", "90+"}

MIN_ROWS = {
    "dim_patient": 1000, "dim_provider": 100, "dim_facility": 8,
    "dim_payer": 8, "dim_denial_reason": 8, "dim_service_line": 7,
    "dim_date": 300, "fact_claims": 5000, "fact_denials": 300,
    "fact_payments": 3000, "fact_ar_snapshot": 1000,
}

AMOUNT_COLUMNS = {
    "fact_claims": ["billed_amount", "allowed_amount", "paid_amount",
                    "patient_responsibility", "outstanding_amount"],
    "fact_denials": ["denied_amount", "recovered_amount"],
    "fact_payments": ["paid_amount"],
    "fact_ar_snapshot": ["outstanding_amount"],
}

KEY_COLUMNS = {
    "dim_patient": ["patient_id", "synthetic_patient_key"],
    "dim_provider": ["provider_id", "facility_id"],
    "dim_payer": ["payer_id", "payer_name"],
    "fact_claims": ["claim_id", "patient_id", "provider_id", "facility_id",
                    "payer_id", "service_line_id", "claim_status"],
    "fact_denials": ["denial_id", "claim_id", "denial_reason_id"],
    "fact_payments": ["payment_id", "claim_id", "payer_id"],
    "fact_ar_snapshot": ["snapshot_id", "claim_id", "aging_bucket"],
}


@dataclass
class Report:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def check(self, ok: bool, name: str, detail: str = "") -> None:
        line = f"{name}" + (f" — {detail}" if detail else "")
        (self.passed if ok else self.failed).append(line)


def load_tables() -> dict[str, pd.DataFrame]:
    tables = {}
    for name in MIN_ROWS:
        path = config.PROCESSED_DIR / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} missing — run `python etl/run_pipeline.py` first")
        tables[name] = pd.read_csv(path)
    # follow-up tasks are optional until the automation engine has run
    task_path = config.PROCESSED_DIR / "fact_followup_tasks.csv"
    if task_path.exists():
        tables["fact_followup_tasks"] = pd.read_csv(task_path)
    return tables


def validate(tables: dict[str, pd.DataFrame]) -> Report:
    r = Report()
    claims = tables["fact_claims"]
    denials = tables["fact_denials"]
    payments = tables["fact_payments"]
    snapshots = tables["fact_ar_snapshot"]

    # 1 — row counts
    for name, minimum in MIN_ROWS.items():
        n = len(tables[name])
        r.check(n >= minimum, f"Row count {name}", f"{n:,} rows (min {minimum:,})")

    # 2 — null keys
    for name, cols in KEY_COLUMNS.items():
        nulls = int(tables[name][cols].isna().sum().sum())
        r.check(nulls == 0, f"No null keys in {name}", f"{nulls} nulls")

    # 3 — negative amounts
    for name, cols in AMOUNT_COLUMNS.items():
        neg = int((tables[name][cols] < 0).sum().sum())
        r.check(neg == 0, f"No negative amounts in {name}", f"{neg} negative values")

    # 4 — referential integrity
    fk_map = [
        ("fact_claims", "patient_id", "dim_patient", "patient_id"),
        ("fact_claims", "provider_id", "dim_provider", "provider_id"),
        ("fact_claims", "facility_id", "dim_facility", "facility_id"),
        ("fact_claims", "payer_id", "dim_payer", "payer_id"),
        ("fact_claims", "service_line_id", "dim_service_line", "service_line_id"),
        ("fact_denials", "claim_id", "fact_claims", "claim_id"),
        ("fact_denials", "denial_reason_id", "dim_denial_reason", "denial_reason_id"),
        ("fact_payments", "claim_id", "fact_claims", "claim_id"),
        ("fact_payments", "payer_id", "dim_payer", "payer_id"),
        ("fact_ar_snapshot", "claim_id", "fact_claims", "claim_id"),
        ("dim_provider", "facility_id", "dim_facility", "facility_id"),
    ]
    if "fact_followup_tasks" in tables:
        fk_map.append(("fact_followup_tasks", "claim_id", "fact_claims", "claim_id"))
    for fact, fk, dim, pk in fk_map:
        orphans = int((~tables[fact][fk].isin(tables[dim][pk])).sum())
        r.check(orphans == 0, f"FK {fact}.{fk} -> {dim}.{pk}", f"{orphans} orphans")

    # 5 — status vocabulary
    bad_status = set(claims["claim_status"].unique()) - VALID_STATUSES
    r.check(not bad_status, "Claim statuses within vocabulary",
            f"unexpected: {sorted(bad_status)}" if bad_status else "all valid")

    # 6 — denial consistency (both directions)
    denied_ids = set(claims.loc[claims["is_denied"], "claim_id"])
    extra = int((~denials["claim_id"].isin(denied_ids)).sum())
    missing = len(denied_ids - set(denials["claim_id"]))
    r.check(extra == 0, "Denial rows only for denied claims", f"{extra} extras")
    r.check(missing == 0, "Every denied claim has a denial row", f"{missing} missing")
    appealed = claims.loc[claims["claim_status"] == "Appealed", "claim_id"]
    r.check(bool(appealed.isin(denials["claim_id"]).all()),
            "Appealed claims have denial records")

    # 7 — payments
    r.check(bool((payments["paid_amount"] > 0).all()),
            "All payment amounts > 0")
    recon = (payments.groupby("claim_id")["paid_amount"].sum()
             .reindex(claims["claim_id"]).fillna(0).round(2))
    diff = float((recon.values - claims["paid_amount"].round(2).values).max())
    r.check(abs(diff) < 0.02, "Payments reconcile to claim paid_amount",
            f"max diff ${abs(diff):.2f}")
    zero_paid_with_payment = int(
        claims.loc[claims["paid_amount"] <= 0, "claim_id"]
        .isin(payments["claim_id"]).sum())
    r.check(zero_paid_with_payment == 0,
            "Payment records only where claim paid_amount > 0",
            f"{zero_paid_with_payment} violations")

    # 8 — aging bucket math
    snap = snapshots.merge(
        claims[["claim_id", "claim_submission_date"]], on="claim_id", how="left")
    days = (pd.to_datetime(snap["snapshot_date"])
            - pd.to_datetime(snap["claim_submission_date"])).dt.days

    def bucket(d: int) -> str:
        return "0-30" if d <= 30 else "31-60" if d <= 60 else "61-90" if d <= 90 else "90+"

    mismatches = int((snap["aging_bucket"] != days.map(bucket)).sum())
    r.check(mismatches == 0, "A/R aging buckets match day math", f"{mismatches} mismatches")
    bad_bucket = set(snapshots["aging_bucket"].unique()) - VALID_BUCKETS
    r.check(not bad_bucket, "Aging bucket vocabulary valid")
    r.check(len(VALID_BUCKETS - set(snapshots["aging_bucket"].unique())) == 0,
            "All four aging buckets represented")

    # 9 — date sanity
    dos = pd.to_datetime(claims["date_of_service"])
    sub = pd.to_datetime(claims["claim_submission_date"])
    r.check(bool((sub >= dos).all()), "Submission date >= date of service")
    as_of = pd.Timestamp(config.AS_OF_DATE)
    r.check(bool((sub <= as_of).all()) and bool((pd.to_datetime(payments["payment_date"]) <= as_of).all()),
            "No activity dated after AS_OF_DATE")

    return r


def write_report(r: Report) -> Path:
    path = config.PROCESSED_DIR / "validation_report.md"
    lines = [
        "# Data Validation Report",
        "",
        f"- Generated against: `data/processed/` (as-of date {config.AS_OF_DATE})",
        f"- Result: **{'PASS' if not r.failed else 'FAIL'}** "
        f"({len(r.passed)} passed, {len(r.failed)} failed)",
        "",
        "## Failed checks" if r.failed else "## Failed checks\n\n_None._",
    ]
    lines += [f"- ❌ {f}" for f in r.failed]
    lines += ["", "## Passed checks", ""]
    lines += [f"- ✅ {p}" for p in r.passed]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    tables = load_tables()
    report = validate(tables)
    path = write_report(report)
    print(f"Validation: {len(report.passed)} passed, {len(report.failed)} failed")
    for f in report.failed:
        print(f"  FAIL: {f}")
    print(f"Report written to {path}")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
