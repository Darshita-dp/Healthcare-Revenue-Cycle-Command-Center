"""Claim transformation: assign status, adjudication financials, and flags.

Takes the base-claim skeleton and produces the final fact_claims shape.
Payer behavior parameters (denial rate, allowed ratio) come from etl.config,
so each payer produces a distinct, analyzable footprint.
"""

from __future__ import annotations

import logging
import random

import pandas as pd

from etl import config

log = logging.getLogger(__name__)

# Seeded independently of the generator so module order can't shift results
_TRANSFORM_SEED_OFFSET = 1


def transform_claims(base_claims: pd.DataFrame) -> pd.DataFrame:
    """Assign claim_status, allowed/paid/outstanding amounts, and flags.

    Status model (per claim):
      - denied (payer-specific probability) -> Denied, or Appealed if the
        denial went to appeal (finalized against fact_denials later)
      - otherwise adjudicated: Paid / Partially Paid / Under Review /
        Submitted (recent claims not yet adjudicated) / Closed
    """
    rng = random.Random(config.RANDOM_SEED + _TRANSFORM_SEED_OFFSET)
    payer_params = {p[0]: {"denial_rate": p[6], "allowed_ratio": p[9]} for p in config.PAYERS}

    rows = []
    for rec in base_claims.to_dict("records"):
        params = payer_params[rec["payer_id"]]
        billed = rec["billed_amount"]
        allowed = round(billed * min(1.0, params["allowed_ratio"] * rng.uniform(0.9, 1.1)), 2)
        age_days = (config.AS_OF_DATE - rec["claim_submission_date"]).days

        is_denied = rng.random() < params["denial_rate"]
        paid = 0.0
        patient_resp = 0.0
        status: str

        if is_denied:
            # Appeal lifecycle is decided in generate_denials; mark provisional
            status = "Denied"
        elif age_days < 25 and rng.random() < 0.65:
            # Recent claims often not adjudicated yet
            status = "Submitted" if rng.random() < 0.7 else "Under Review"
        elif age_days <= 120 and rng.random() < 0.06:
            # Pended claims resolve within ~4 months; older ones adjudicate
            status = "Under Review"
        else:
            # Adjudicated and payable
            patient_resp = round(allowed * rng.uniform(0.05, 0.25), 2)
            payer_portion = round(allowed - patient_resp, 2)
            if rng.random() < 0.12:
                # Partially paid: payer paid less than its full portion.
                # Old partial balances usually get adjusted/written off.
                paid = round(payer_portion * rng.uniform(0.35, 0.85), 2)
                if age_days > 120 and rng.random() < 0.7:
                    status = "Closed"
                else:
                    status = "Partially Paid"
            else:
                paid = payer_portion
                # Most fully-paid claims eventually close
                status = "Closed" if rng.random() < 0.55 else "Paid"

        outstanding = round(max(0.0, allowed - paid - patient_resp), 2)
        if status == "Closed":
            outstanding = 0.0
        is_open = status in ("Submitted", "Under Review", "Denied", "Appealed", "Partially Paid")

        rows.append({
            **rec,
            "claim_status": status,
            "allowed_amount": allowed,
            "paid_amount": paid,
            "patient_responsibility": patient_resp,
            "outstanding_amount": outstanding if is_open else 0.0,
            "claim_age_days": age_days,
            "is_denied": is_denied,
            "is_paid": paid > 0,
            "is_open": is_open,
            "is_high_value": billed >= config.HIGH_VALUE_THRESHOLD,
        })

    claims = pd.DataFrame(rows)
    log.info(
        "Transformed %s claims — denial rate %.1f%%, open %.1f%%",
        len(claims), claims["is_denied"].mean() * 100, claims["is_open"].mean() * 100,
    )
    return claims
