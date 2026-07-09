"""Decision-support endpoints built on the explainable priority score.

  GET /api/priority-insights    portfolio view of the priority queue
  GET /api/recovery-simulator   "work the top N claims" revenue estimate

Both operate on OPEN claims (the actionable A/R), ranked by the transparent
priority score computed in automation.priority_scoring.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd
from fastapi import APIRouter, Depends, Query

from api.database import DataStore, get_store
from api.models.schemas import (DriverCount, PriorityInsights,
                                RecoverySimulatorResponse, SelectedClaimPreview,
                                TierCount)

router = APIRouter(tags=["Decision Support"])

TIER_ORDER = ["Critical", "High", "Medium", "Low", "Monitor"]


def _open_claims(store: DataStore) -> pd.DataFrame:
    df = store.claims_view
    return df[df["is_open"]].copy()


def _tier_breakdown(df: pd.DataFrame) -> list[TierCount]:
    rows = []
    for tier in TIER_ORDER:
        seg = df[df["priority_tier"] == tier]
        rows.append(TierCount(
            tier=tier,
            count=len(seg),
            outstanding_amount=round(float(seg["outstanding_amount"].sum()), 2),
        ))
    return rows


def _driver_breakdown(df: pd.DataFrame, top_n: int = 6) -> list[DriverCount]:
    """Count how many claims each driver category touches, with the most
    representative human label for that category."""
    cat_claims: Counter = Counter()
    cat_labels: dict[str, Counter] = {}
    for drivers in df["priority_drivers"]:
        if not isinstance(drivers, list):
            continue
        seen_cats = set()
        for d in drivers:
            cat = d["category"]
            cat_labels.setdefault(cat, Counter())[d["label"]] += 1
            if cat not in seen_cats:  # count each category once per claim
                cat_claims[cat] += 1
                seen_cats.add(cat)
    out = []
    for cat, claims in cat_claims.most_common(top_n):
        label = cat_labels[cat].most_common(1)[0][0]
        out.append(DriverCount(category=cat, label=label, claims=claims))
    return out


@router.get("/api/priority-insights", response_model=PriorityInsights,
            summary="Portfolio-level view of the explainable priority queue")
def priority_insights(store: DataStore = Depends(get_store)) -> PriorityInsights:
    df = _open_claims(store)
    counts = df["priority_tier"].value_counts()
    ch = df[df["priority_tier"].isin(["Critical", "High"])]
    return PriorityInsights(
        scored_open_claims=len(df),
        critical_count=int(counts.get("Critical", 0)),
        high_count=int(counts.get("High", 0)),
        medium_count=int(counts.get("Medium", 0)),
        low_count=int(counts.get("Low", 0)),
        monitor_count=int(counts.get("Monitor", 0)),
        critical_high_outstanding=round(float(ch["outstanding_amount"].sum()), 2),
        average_priority_score=round(float(df["priority_score"].mean()), 1) if len(df) else 0.0,
        tier_breakdown=_tier_breakdown(df),
        top_drivers=_driver_breakdown(df),
    )


@router.get("/api/recovery-simulator", response_model=RecoverySimulatorResponse,
            summary="Estimate recoverable revenue from working the top-priority claims")
def recovery_simulator(
    store: DataStore = Depends(get_store),
    claim_count: int = Query(50, ge=1, le=1000, description="How many top-priority claims to work"),
    recovery_rate: float = Query(0.40, ge=0.0, le=1.0, description="Assumed recovery rate (0-1)"),
) -> RecoverySimulatorResponse:
    df = _open_claims(store).sort_values(
        ["priority_score", "outstanding_amount"], ascending=[False, False])
    selected = df.head(claim_count).copy()

    # Per-claim exposure without double-counting: the larger of the open
    # balance and the still-unrecovered denied amount.
    denied_amt = selected["denied_amount"].fillna(0.0)
    recovered = selected["recovered_amount"].fillna(0.0)
    denied_unrecovered = (denied_amt - recovered).clip(lower=0.0)
    outstanding = selected["outstanding_amount"].fillna(0.0)
    recovery_base_per_claim = pd.concat([outstanding, denied_unrecovered], axis=1).max(axis=1)

    potential_base = round(float(recovery_base_per_claim.sum()), 2)
    estimated = round(potential_base * recovery_rate, 2)
    avg_score = round(float(selected["priority_score"].mean()), 1) if len(selected) else 0.0

    preview = [
        SelectedClaimPreview(
            claim_id=r["claim_id"],
            payer_name=r["payer_name"],
            facility_name=r["facility_name"],
            claim_status=r["claim_status"],
            outstanding_amount=round(float(r["outstanding_amount"]), 2),
            denied_amount=round(float(r["denied_amount"]), 2) if pd.notna(r["denied_amount"]) else 0.0,
            priority_score=int(r["priority_score"]),
            priority_tier=r["priority_tier"],
            top_driver=r["priority_top_driver"] if isinstance(r["priority_top_driver"], str) else None,
        )
        for r in selected.head(15).to_dict("records")
    ]

    interpretation = (
        f"If the team works the top {len(selected)} priority claims at a "
        f"{recovery_rate:.0%} recovery assumption, the estimated recoverable "
        f"revenue is ${estimated:,.0f} from a ${potential_base:,.0f} at-risk base."
    )

    return RecoverySimulatorResponse(
        claim_count=claim_count,
        recovery_rate=recovery_rate,
        selected_claim_count=len(selected),
        total_billed_amount=round(float(selected["billed_amount"].sum()), 2),
        total_outstanding_amount=round(float(outstanding.sum()), 2),
        total_denied_amount=round(float(denied_amt.sum()), 2),
        potential_recovery_base=potential_base,
        estimated_recoverable_revenue=estimated,
        average_priority_score=avg_score,
        priority_tier_breakdown=_tier_breakdown(selected),
        top_driver_breakdown=_driver_breakdown(selected),
        interpretation=interpretation,
        selected_claims_preview=preview,
    )
