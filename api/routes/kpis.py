"""Executive KPI endpoint — mirrors analytics/kpi_queries.sql in pandas."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends

from api.database import DataStore, get_store
from api.models.schemas import KpiResponse

router = APIRouter(tags=["KPIs"])


@router.get("/api/kpis", response_model=KpiResponse,
            summary="Executive KPI snapshot with monthly trends")
def get_kpis(store: DataStore = Depends(get_store)) -> KpiResponse:
    claims = store.tables["fact_claims"]
    denials = store.tables["fact_denials"]
    payments = store.tables["fact_payments"]
    tasks = store.tables["fact_followup_tasks"]
    reasons = store.tables["dim_denial_reason"]

    open_claims = claims[claims["is_open"]]
    at_risk = open_claims[(open_claims["is_denied"]) | (open_claims["claim_age_days"] > 60)]
    clean = claims[(~claims["is_denied"])
                   & (claims["claim_status"].isin(["Paid", "Closed"]))
                   & (claims["is_paid"])]

    d = denials.merge(reasons[["denial_reason_id", "preventable_flag"]],
                      on="denial_reason_id")
    resolved = d[d["appeal_status"] == "Appeal Resolved"]
    won = resolved[resolved["appeal_outcome"].isin(["Overturned", "Partially Overturned"])]

    open_tasks = tasks[tasks["status"].isin(["Open", "In Progress"])]
    as_of = claims["claim_submission_date"].max()  # dataset build horizon
    overdue = open_tasks[open_tasks["due_date"] < as_of]

    # Monthly trends keyed on submission month
    m = claims.assign(
        year=claims["claim_submission_date"].dt.year,
        month=claims["claim_submission_date"].dt.month,
        label=claims["claim_submission_date"].dt.strftime("%b %Y"),
    )
    grp = m.groupby(["year", "month", "label"], sort=True)
    denial_trend = [
        {"year": int(y), "month": int(mo), "label": lbl,
         "claims": int(g["claim_id"].count()),
         "denied": int(g["is_denied"].sum()),
         "denial_rate_pct": round(100 * g["is_denied"].mean(), 2)}
        for (y, mo, lbl), g in grp
    ]
    billed_paid = [
        {"year": int(y), "month": int(mo), "label": lbl,
         "billed": round(float(g["billed_amount"].sum()), 2),
         "paid": round(float(g["paid_amount"].sum()), 2)}
        for (y, mo, lbl), g in grp
    ]

    return KpiResponse(
        total_claims=len(claims),
        total_billed=round(float(claims["billed_amount"].sum()), 2),
        total_paid=round(float(claims["paid_amount"].sum()), 2),
        outstanding_ar=round(float(open_claims["outstanding_amount"].sum()), 2),
        revenue_at_risk=round(float(at_risk["outstanding_amount"].sum()), 2),
        ar_over_90=round(float(
            open_claims.loc[open_claims["claim_age_days"] > 90,
                            "outstanding_amount"].sum()), 2),
        denial_rate_pct=round(100 * claims["is_denied"].mean(), 2),
        clean_claim_rate_pct=round(100 * len(clean) / len(claims), 2),
        avg_days_to_payment=round(float(payments["days_to_payment"].mean()), 1),
        open_tasks=len(open_tasks),
        overdue_tasks=len(overdue),
        preventable_denial_rate_pct=round(100 * d["preventable_flag"].mean(), 2),
        appeal_success_rate_pct=round(100 * len(won) / len(resolved), 2)
        if len(resolved) else 0.0,
        total_recovered=round(float(denials["recovered_amount"].sum()), 2),
        denial_trend=denial_trend,
        monthly_billed_paid=billed_paid,
    )
