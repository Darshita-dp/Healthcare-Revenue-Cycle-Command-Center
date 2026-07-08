"""Operational endpoints: denials, follow-up tasks, A/R aging, payer alerts."""

from __future__ import annotations

from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, Query

from api.database import ALERTS_CSV, DataStore, get_store
from api.models.schemas import AgingResponse, Alert, TaskRecord

router = APIRouter(tags=["Operations"])


@router.get("/api/denials", summary="Denials with reason, appeal, and recovery detail")
def list_denials(
    store: DataStore = Depends(get_store),
    category: Optional[str] = Query(None, description="Denial category filter"),
    appeal_status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    d = store.tables["fact_denials"].merge(
        store.tables["dim_denial_reason"], on="denial_reason_id")
    d = d.merge(store.claims_view[["claim_id", "payer_name", "facility_name",
                                   "claim_status", "outstanding_amount"]],
                on="claim_id")
    if category:
        d = d[d["denial_category"] == category]
    if appeal_status:
        d = d[d["appeal_status"] == appeal_status]
    d = d.sort_values("denied_amount", ascending=False)

    total = len(d)
    page = d.iloc[offset:offset + limit].copy()
    for col in ["denial_date", "appeal_submitted_date"]:
        page[col] = page[col].dt.strftime("%Y-%m-%d")
    page = page.astype(object).where(page.notna(), None)
    return {"total": total, "limit": limit, "offset": offset,
            "items": page.to_dict("records")}


@router.get("/api/tasks", response_model=dict,
            summary="Follow-up task work queue")
def list_tasks(
    store: DataStore = Depends(get_store),
    status: Optional[str] = Query(None, description="Open | In Progress | Completed | Cancelled"),
    priority: Optional[str] = Query(None),
    team: Optional[str] = Query(None, description="Assigned team"),
    overdue_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    t = store.tables["fact_followup_tasks"].copy()
    claims = store.claims_view[["claim_id", "payer_name", "outstanding_amount"]]
    t = t.merge(claims, on="claim_id", how="left")

    as_of = store.tables["fact_claims"]["claim_submission_date"].max()
    t["is_overdue"] = t["status"].isin(["Open", "In Progress"]) & (t["due_date"] < as_of)

    if status:
        t = t[t["status"] == status]
    if priority:
        t = t[t["priority"] == priority]
    if team:
        t = t[t["assigned_team"] == team]
    if overdue_only:
        t = t[t["is_overdue"]]

    rank = t["priority"].map({"Urgent": 0, "High": 1, "Medium": 2, "Low": 3})
    t = t.assign(_rank=rank).sort_values(
        ["_rank", "due_date"], ascending=[True, True])

    completed = store.tables["fact_followup_tasks"]
    done = completed[completed["status"] == "Completed"]
    avg_close = ((done["closed_date"] - done["created_date"]).dt.days.mean()
                 if len(done) else None)

    total = len(t)
    items = [
        TaskRecord(
            task_id=r["task_id"], claim_id=r["claim_id"], task_type=r["task_type"],
            priority=r["priority"], assigned_team=r["assigned_team"],
            created_date=r["created_date"].date(), due_date=r["due_date"].date(),
            status=r["status"],
            closed_date=r["closed_date"].date() if pd.notna(r["closed_date"]) else None,
            reason=r["reason"], is_overdue=bool(r["is_overdue"]),
            outstanding_amount=float(r["outstanding_amount"])
            if pd.notna(r["outstanding_amount"]) else None,
            payer_name=r["payer_name"] if pd.notna(r["payer_name"]) else None,
        ).model_dump()
        for r in t.iloc[offset:offset + limit].to_dict("records")
    ]
    return {
        "total": total, "limit": limit, "offset": offset,
        "summary": {
            "open": int((store.tables["fact_followup_tasks"]["status"] == "Open").sum()),
            "in_progress": int((store.tables["fact_followup_tasks"]["status"] == "In Progress").sum()),
            "completed": int(len(done)),
            "overdue": int(t["is_overdue"].sum()) if not (status or priority or team or overdue_only)
            else int((store.tables["fact_followup_tasks"]["status"].isin(["Open", "In Progress"])
                      & (store.tables["fact_followup_tasks"]["due_date"] < as_of)).sum()),
            "avg_days_to_close": round(float(avg_close), 1) if avg_close is not None else None,
        },
        "items": items,
    }


@router.get("/api/aging", response_model=AgingResponse,
            summary="A/R aging buckets, by payer, and month-end trend")
def get_aging(store: DataStore = Depends(get_store)) -> AgingResponse:
    claims = store.claims_view
    open_c = claims[(claims["is_open"]) & (claims["outstanding_amount"] > 0)]
    total_ar = float(open_c["outstanding_amount"].sum())

    buckets = []
    for bucket in ["0-30", "31-60", "61-90", "90+"]:
        seg = open_c[open_c["aging_bucket"] == bucket]
        amt = float(seg["outstanding_amount"].sum())
        buckets.append({
            "aging_bucket": bucket,
            "open_claims": len(seg),
            "outstanding_amount": round(amt, 2),
            "pct_of_ar": round(100 * amt / total_ar, 2) if total_ar else 0.0,
        })

    by_payer = (open_c.pivot_table(index="payer_name", columns="aging_bucket",
                                   values="outstanding_amount", aggfunc="sum",
                                   fill_value=0.0)
                .reindex(columns=["0-30", "31-60", "61-90", "90+"], fill_value=0.0)
                .round(2))
    by_payer["total"] = by_payer.sum(axis=1).round(2)
    by_payer = by_payer.sort_values("total", ascending=False).reset_index()

    snap = store.tables["fact_ar_snapshot"]
    trend = (snap.groupby([snap["snapshot_date"].dt.strftime("%Y-%m-%d"), "aging_bucket"])
             ["outstanding_amount"].sum().round(2).reset_index()
             .rename(columns={"snapshot_date": "snapshot"}))

    as_of = store.tables["fact_claims"]["claim_submission_date"].max()
    return AgingResponse(
        as_of=as_of.strftime("%Y-%m-%d"),
        buckets=buckets,
        by_payer=by_payer.to_dict("records"),
        trend=trend.to_dict("records"),
    )


@router.get("/api/alerts", response_model=list[Alert],
            summary="Payer escalation alerts from the automation engine")
def list_alerts() -> list[Alert]:
    if not ALERTS_CSV.exists():
        return []
    df = pd.read_csv(ALERTS_CSV)
    return [Alert(**r) for r in df.to_dict("records")]
