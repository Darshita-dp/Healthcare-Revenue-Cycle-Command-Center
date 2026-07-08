"""Denial + appeal lifecycle generation.

For every denied claim, creates a fact_denials row with a weighted denial
reason and a realistic appeal lifecycle (appealed or not, resolved or
pending, overturned/partial/upheld, recovered dollars). Also finalizes the
claim status for appealed claims and applies recovered money back onto the
claim's financials so fact_claims and fact_denials stay consistent.
"""

from __future__ import annotations

import logging
import random
from datetime import timedelta

import pandas as pd

from etl import config

log = logging.getLogger(__name__)

_DENIAL_SEED_OFFSET = 2


def generate_denials(claims: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (denials_df, updated_claims_df)."""
    rng = random.Random(config.RANDOM_SEED + _DENIAL_SEED_OFFSET)

    reason_ids = [r[0] for r in config.DENIAL_REASONS]
    reason_weights = [r[5] for r in config.DENIAL_REASONS]

    denied = claims[claims["is_denied"]].copy()
    denial_rows = []
    claim_updates: dict[str, dict] = {}

    for i, rec in enumerate(denied.to_dict("records"), start=1):
        submission = rec["claim_submission_date"]
        denial_date = submission + timedelta(days=rng.randint(10, 40))
        if denial_date > config.AS_OF_DATE:
            denial_date = config.AS_OF_DATE
        denied_amount = rec["allowed_amount"] if rec["allowed_amount"] > 0 else rec["billed_amount"]

        appeal_status = "Not Appealed"
        appeal_submitted = None
        appeal_outcome = None
        recovered = 0.0
        days_to_appeal = None
        claim_status = "Denied"
        paid_delta = 0.0

        days_since_denial = (config.AS_OF_DATE - denial_date).days
        appealed = rng.random() < config.APPEAL_RATE and days_since_denial > 5
        if not appealed and days_since_denial > 120 and rng.random() < 0.65:
            # Old unappealed denials eventually get written off and closed
            claim_status = "Closed"
        if appealed:
            days_to_appeal = rng.randint(5, 30)
            appeal_submitted = denial_date + timedelta(days=days_to_appeal)
            if appeal_submitted > config.AS_OF_DATE:
                appeal_submitted = config.AS_OF_DATE
                days_to_appeal = (appeal_submitted - denial_date).days
            appeal_status = "Appeal Submitted"
            claim_status = "Appealed"

            resolution_lag = rng.randint(15, 60)
            if (appeal_submitted + timedelta(days=resolution_lag) <= config.AS_OF_DATE
                    and rng.random() < config.APPEAL_RESOLVED_RATE):
                appeal_status = "Appeal Resolved"
                roll = rng.random()
                if roll < config.APPEAL_OVERTURN:
                    appeal_outcome = "Overturned"
                    recovered = denied_amount
                elif roll < config.APPEAL_OVERTURN + config.APPEAL_PARTIAL:
                    appeal_outcome = "Partially Overturned"
                    recovered = round(denied_amount * rng.uniform(0.3, 0.7), 2)
                else:
                    appeal_outcome = "Upheld"
                    recovered = 0.0

                if appeal_outcome == "Overturned":
                    claim_status = "Paid" if rng.random() < 0.5 else "Closed"
                    paid_delta = recovered
                elif appeal_outcome == "Partially Overturned":
                    claim_status = "Partially Paid"
                    paid_delta = recovered
                else:
                    # Upheld — claim is written off / closed
                    claim_status = "Closed"

        denial_rows.append({
            "denial_id": f"DEN-{i:06d}",
            "claim_id": rec["claim_id"],
            "denial_reason_id": rng.choices(reason_ids, weights=reason_weights)[0],
            "denial_date": denial_date,
            "denied_amount": denied_amount,
            "appeal_status": appeal_status,
            "appeal_submitted_date": appeal_submitted,
            "appeal_outcome": appeal_outcome,
            "recovered_amount": recovered,
            "days_to_appeal": days_to_appeal,
        })
        claim_updates[rec["claim_id"]] = {
            "claim_status": claim_status,
            "paid_delta": paid_delta,
        }

    denials = pd.DataFrame(denial_rows)

    # Apply lifecycle outcomes back to fact_claims so both tables agree
    claims = claims.copy()
    idx = claims.set_index("claim_id").index
    status_map = {cid: u["claim_status"] for cid, u in claim_updates.items()}
    paid_map = {cid: u["paid_delta"] for cid, u in claim_updates.items()}

    mask = claims["claim_id"].isin(claim_updates)
    claims.loc[mask, "claim_status"] = claims.loc[mask, "claim_id"].map(status_map)
    claims.loc[mask, "paid_amount"] = (
        claims.loc[mask, "paid_amount"] + claims.loc[mask, "claim_id"].map(paid_map)
    ).round(2)

    resolved_closed = claims["claim_status"].isin(["Closed", "Paid"])
    claims["is_paid"] = claims["paid_amount"] > 0
    claims["is_open"] = ~resolved_closed & claims["claim_status"].ne("Cancelled")
    claims["outstanding_amount"] = (
        (claims["allowed_amount"] - claims["paid_amount"] - claims["patient_responsibility"])
        .clip(lower=0.0)
        .where(claims["is_open"], 0.0)
        .round(2)
    )

    log.info(
        "Generated %s denials — appealed %.0f%%, resolved appeals %s, recovered $%.0f",
        len(denials),
        denials["appeal_status"].ne("Not Appealed").mean() * 100,
        (denials["appeal_status"] == "Appeal Resolved").sum(),
        denials["recovered_amount"].sum(),
    )
    return denials, claims
