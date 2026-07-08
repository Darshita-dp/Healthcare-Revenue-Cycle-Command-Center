"""Payer performance endpoints — scorecards with composite risk ranking."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from api.database import DataStore, get_store
from api.models.schemas import PayerScorecard

router = APIRouter(tags=["Payers"])

# Composite risk weights (must match analytics/payer_performance.sql query 5)
W_DENIAL, W_LAG, W_AGING = 0.5, 0.3, 0.2


def _scorecards(store: DataStore) -> list[PayerScorecard]:
    claims = store.tables["fact_claims"]
    payments = store.tables["fact_payments"]
    payers = store.tables["dim_payer"]
    denials = store.tables["fact_denials"].merge(
        claims[["claim_id", "payer_id"]], on="claim_id")
    reasons = store.tables["dim_denial_reason"]
    denials = denials.merge(reasons[["denial_reason_id", "denial_category"]],
                            on="denial_reason_id")

    rows = []
    for p in payers.to_dict("records"):
        pc = claims[claims["payer_id"] == p["payer_id"]]
        if pc.empty:
            continue
        pp = payments[payments["payer_id"] == p["payer_id"]]
        pd_ = denials[denials["payer_id"] == p["payer_id"]]
        open_c = pc[pc["is_open"]]
        outstanding = float(open_c["outstanding_amount"].sum())
        over90 = float(open_c.loc[open_c["claim_age_days"] > 90,
                                  "outstanding_amount"].sum())
        top_reasons = (pd_.groupby("denial_category")
                       .agg(denials=("denial_id", "count"),
                            denied_amount=("denied_amount", "sum"))
                       .sort_values("denials", ascending=False)
                       .head(3).reset_index())
        rows.append({
            "payer_id": int(p["payer_id"]),
            "payer_name": p["payer_name"],
            "payer_type": p["payer_type"],
            "contract_type": p["contract_type"],
            "risk_category": p["risk_category"],
            "total_claims": len(pc),
            "denied_claims": int(pc["is_denied"].sum()),
            "denial_rate": float(pc["is_denied"].mean()),
            "avg_lag": float(pp["days_to_payment"].mean()) if len(pp) else None,
            "billed_amount": round(float(pc["billed_amount"].sum()), 2),
            "paid_amount": round(float(pc["paid_amount"].sum()), 2),
            "outstanding_ar": round(outstanding, 2),
            "ar_over_90": round(over90, 2),
            "pct_ar_over_90": over90 / outstanding if outstanding else 0.0,
            "denied_amount": round(float(pd_["denied_amount"].sum()), 2),
            "recovered_amount": round(float(pd_["recovered_amount"].sum()), 2),
            "top_denial_reasons": [
                {"denial_category": r["denial_category"],
                 "denials": int(r["denials"]),
                 "denied_amount": round(float(r["denied_amount"]), 2)}
                for r in top_reasons.to_dict("records")],
        })

    df = pd.DataFrame(rows)
    # Normalize to the worst performer, then weight (same math as the SQL)
    lag_filled = df["avg_lag"].fillna(60.0)
    df["risk_score"] = (
        W_DENIAL * df["denial_rate"] / df["denial_rate"].max()
        + W_LAG * lag_filled / lag_filled.max()
        + W_AGING * df["pct_ar_over_90"] / max(df["pct_ar_over_90"].max(), 1e-9)
    ).round(3)
    df["risk_rank"] = df["risk_score"].rank(ascending=False, method="min").astype(int)

    return [
        PayerScorecard(
            **{k: r[k] for k in [
                "payer_id", "payer_name", "payer_type", "contract_type",
                "risk_category", "total_claims", "denied_claims", "billed_amount",
                "paid_amount", "outstanding_ar", "ar_over_90", "denied_amount",
                "recovered_amount", "top_denial_reasons"]},
            denial_rate_pct=round(100 * r["denial_rate"], 2),
            avg_days_to_payment=round(r["avg_lag"], 1) if pd.notna(r["avg_lag"]) else None,
            risk_score=float(r["risk_score"]),
            risk_rank=int(r["risk_rank"]),
        )
        for r in df.sort_values("risk_rank").to_dict("records")
    ]


@router.get("/api/payers", response_model=list[PayerScorecard],
            summary="Payer scorecards ranked by composite risk score")
def list_payers(store: DataStore = Depends(get_store)) -> list[PayerScorecard]:
    return _scorecards(store)


@router.get("/api/payers/{payer_id}", response_model=PayerScorecard,
            summary="Single payer scorecard")
def get_payer(payer_id: int, store: DataStore = Depends(get_store)) -> PayerScorecard:
    for card in _scorecards(store):
        if card.payer_id == payer_id:
            return card
    raise HTTPException(status_code=404, detail=f"Payer {payer_id} not found")
