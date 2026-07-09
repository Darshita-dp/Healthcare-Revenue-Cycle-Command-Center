"""Claims work-queue endpoints: filterable list + full claim detail."""

from __future__ import annotations

from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from api.database import DataStore, get_store
from api.models.schemas import (ClaimDetail, ClaimListResponse, ClaimSummary,
                                DenialDetail, PaymentRecord, TaskRecord)
from automation.priority_scoring import summarize

router = APIRouter(tags=["Claims"])

CLAIM_SUMMARY_COLS = [
    "claim_id", "payer_name", "payer_type", "facility_name", "provider_name",
    "service_line_name", "claim_status", "billed_amount", "outstanding_amount",
    "claim_age_days", "aging_bucket", "is_denied", "is_high_value",
    "denial_category", "action_needed", "task_priority",
    "priority_score", "priority_tier", "priority_top_driver",
    "date_of_service", "claim_submission_date",
]


def _to_summaries(df: pd.DataFrame) -> list[ClaimSummary]:
    recs = df[CLAIM_SUMMARY_COLS].to_dict("records")
    out = []
    for r in recs:
        for k, v in list(r.items()):
            if pd.isna(v):
                r[k] = None
        out.append(ClaimSummary(**r))
    return out


@router.get("/api/claims", response_model=ClaimListResponse,
            summary="Filterable, prioritized claims work queue")
def list_claims(
    store: DataStore = Depends(get_store),
    payer: Optional[str] = Query(None, description="Payer name (exact match)"),
    status: Optional[str] = Query(None, description="Claim status"),
    aging_bucket: Optional[str] = Query(None, description="0-30 | 31-60 | 61-90 | 90+"),
    denial_reason: Optional[str] = Query(None, description="Denial category"),
    priority: Optional[str] = Query(None, description="Open-task priority on the claim"),
    facility: Optional[str] = Query(None, description="Facility name (exact match)"),
    search: Optional[str] = Query(None, description="Substring match on claim ID"),
    open_only: bool = Query(False, description="Only claims still open in A/R"),
    tier: Optional[str] = Query(None, description="Priority tier: Critical | High | Medium | Low | Monitor"),
    sort: str = Query("priority", description="priority | score | age | amount"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ClaimListResponse:
    df = store.claims_view

    if open_only:
        df = df[df["is_open"]]
    if payer:
        df = df[df["payer_name"] == payer]
    if status:
        df = df[df["claim_status"] == status]
    if aging_bucket:
        df = df[df["aging_bucket"] == aging_bucket]
    if denial_reason:
        df = df[df["denial_category"] == denial_reason]
    if priority:
        df = df[df["task_priority"] == priority]
    if facility:
        df = df[df["facility_name"] == facility]
    if tier:
        df = df[df["priority_tier"] == tier]
    if search:
        df = df[df["claim_id"].str.contains(search, case=False, na=False)]

    if sort == "age":
        df = df.sort_values("claim_age_days", ascending=False)
    elif sort == "amount":
        df = df.sort_values("outstanding_amount", ascending=False)
    elif sort == "score":
        df = df.sort_values(["priority_score", "outstanding_amount"], ascending=[False, False])
    else:  # priority: explainable score first, then dollars at stake
        df = df.sort_values(["priority_score", "outstanding_amount"], ascending=[False, False])

    total = len(df)
    page = df.iloc[offset:offset + limit]
    return ClaimListResponse(total=total, limit=limit, offset=offset,
                             items=_to_summaries(page))


@router.get("/api/claims/filters",
            summary="Distinct values for the work-queue filter dropdowns")
def claim_filters(store: DataStore = Depends(get_store)) -> dict:
    df = store.claims_view
    return {
        "payers": sorted(df["payer_name"].unique().tolist()),
        "statuses": sorted(df["claim_status"].unique().tolist()),
        "aging_buckets": ["0-30", "31-60", "61-90", "90+"],
        "denial_reasons": sorted(df["denial_category"].dropna().unique().tolist()),
        "priorities": ["Urgent", "High", "Medium", "Low"],
        "tiers": ["Critical", "High", "Medium", "Low", "Monitor"],
        "facilities": sorted(df["facility_name"].unique().tolist()),
    }


def _recommend(row: pd.Series, denial: Optional[DenialDetail]) -> str:
    """Next-best-action heuristic shown on the claim detail page."""
    if denial and denial.appeal_status == "Not Appealed":
        return ("File an appeal immediately — no appeal is on record and payer "
                "appeal windows are typically 30–90 days from the denial date.")
    if denial and denial.appeal_status == "Appeal Submitted":
        return "Appeal is pending — follow up with the payer on appeal status."
    if row["claim_status"] == "Partially Paid":
        return ("Reconcile the partial payment against the allowed amount and "
                "bill the remaining balance or post the adjustment.")
    if row["is_open"] and row["claim_age_days"] > 90:
        return ("Escalate with the payer — claim has aged past 90 days. "
                "Verify claim status telephonically or via the payer portal.")
    if row["is_open"] and row["claim_age_days"] > 60:
        return "Contact the payer for adjudication status before the claim ages further."
    if row["is_open"]:
        return "Monitor — claim is within normal adjudication timelines."
    return "No action needed — claim is resolved."


@router.get("/api/claims/{claim_id}", response_model=ClaimDetail,
            summary="Full claim detail: parties, financials, timeline, tasks")
def get_claim(claim_id: str, store: DataStore = Depends(get_store)) -> ClaimDetail:
    view = store.claims_view
    match = view[view["claim_id"] == claim_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    row = match.iloc[0]

    base = store.tables["fact_claims"]
    base_row = base[base["claim_id"] == claim_id].iloc[0]

    patients = store.tables["dim_patient"]
    patient = patients[patients["patient_id"] == base_row["patient_id"]].iloc[0]
    patient_segment = {
        "synthetic_patient_key": patient["synthetic_patient_key"],
        "gender": patient["gender"],
        "age_group": patient["age_group"],
        "state": patient["state"],
        "insurance_type": patient["insurance_type"],
        "risk_segment": patient["risk_segment"],
    }

    denial_detail = None
    denials = store.tables["fact_denials"]
    drow = denials[denials["claim_id"] == claim_id]
    if not drow.empty:
        d = drow.iloc[0]
        reasons = store.tables["dim_denial_reason"]
        reason = reasons[reasons["denial_reason_id"] == d["denial_reason_id"]].iloc[0]
        denial_detail = DenialDetail(
            denial_id=d["denial_id"],
            denial_date=d["denial_date"].date(),
            denial_code=reason["denial_code"],
            denial_category=reason["denial_category"],
            denial_description=reason["denial_description"],
            preventable=bool(reason["preventable_flag"]),
            denied_amount=float(d["denied_amount"]),
            appeal_status=d["appeal_status"],
            appeal_submitted_date=d["appeal_submitted_date"].date()
            if pd.notna(d["appeal_submitted_date"]) else None,
            appeal_outcome=d["appeal_outcome"] if pd.notna(d["appeal_outcome"]) else None,
            recovered_amount=float(d["recovered_amount"]),
            days_to_appeal=int(d["days_to_appeal"]) if pd.notna(d["days_to_appeal"]) else None,
        )

    pay = store.tables["fact_payments"]
    payments = [
        PaymentRecord(
            payment_id=p["payment_id"], payment_date=p["payment_date"].date(),
            paid_amount=float(p["paid_amount"]), payment_method=p["payment_method"],
            days_to_payment=int(p["days_to_payment"]),
        )
        for p in pay[pay["claim_id"] == claim_id]
        .sort_values("payment_date").to_dict("records")
    ]

    tasks_df = store.tables["fact_followup_tasks"]
    as_of = base["claim_submission_date"].max()
    tasks = [
        TaskRecord(
            task_id=t["task_id"], claim_id=t["claim_id"], task_type=t["task_type"],
            priority=t["priority"], assigned_team=t["assigned_team"],
            created_date=t["created_date"].date(), due_date=t["due_date"].date(),
            status=t["status"],
            closed_date=t["closed_date"].date() if pd.notna(t["closed_date"]) else None,
            reason=t["reason"],
            is_overdue=bool(t["status"] in ("Open", "In Progress")
                            and t["due_date"] < as_of),
        )
        for t in tasks_df[tasks_df["claim_id"] == claim_id].to_dict("records")
    ]

    drivers = row["priority_drivers"] if isinstance(row["priority_drivers"], list) else []
    return ClaimDetail(
        claim=_to_summaries(match)[0],
        allowed_amount=float(base_row["allowed_amount"]),
        paid_amount=float(base_row["paid_amount"]),
        patient_responsibility=float(base_row["patient_responsibility"]),
        patient_segment=patient_segment,
        denial=denial_detail,
        payments=payments,
        tasks=tasks,
        recommended_action=_recommend(row, denial_detail),
        priority_score=int(row["priority_score"]),
        priority_tier=row["priority_tier"],
        priority_summary=summarize(row["priority_tier"], drivers),
        priority_drivers=drivers,
    )
