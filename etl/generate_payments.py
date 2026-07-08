"""Payment and A/R snapshot generation.

fact_payments: one or more remittances per paying claim, with payer-specific
payment lag distributions. Payment totals reconcile exactly to
fact_claims.paid_amount.

fact_ar_snapshot: month-end outstanding balances with aging buckets for
every claim that was open (unpaid balance) as of each snapshot date.
"""

from __future__ import annotations

import logging
import random
from datetime import date, timedelta

import pandas as pd

from etl import config

log = logging.getLogger(__name__)

_PAYMENT_SEED_OFFSET = 3
_SNAPSHOT_SEED_OFFSET = 4


def _aging_bucket(days: int) -> str:
    if days <= 30:
        return "0-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "90+"


def generate_payments(claims: pd.DataFrame) -> pd.DataFrame:
    """One or two payment transactions per claim with paid_amount > 0."""
    rng = random.Random(config.RANDOM_SEED + _PAYMENT_SEED_OFFSET)
    lag_params = {p[0]: (p[7], p[8]) for p in config.PAYERS}

    rows = []
    pid = 0
    payers = claims[claims["paid_amount"] > 0]
    for rec in payers.to_dict("records"):
        mean, sd = lag_params[rec["payer_id"]]
        lag = max(3, int(rng.gauss(mean, sd)))
        first_date = rec["claim_submission_date"] + timedelta(days=lag)
        if first_date > config.AS_OF_DATE:
            first_date = config.AS_OF_DATE
            lag = (first_date - rec["claim_submission_date"]).days

        total = rec["paid_amount"]
        # Partially-paid and appealed-recovery claims often pay in two remits
        split = rec["claim_status"] in ("Partially Paid",) and total > 500 and rng.random() < 0.5
        amounts = []
        if split:
            first = round(total * rng.uniform(0.4, 0.7), 2)
            amounts.append((first, first_date, lag))
            second_lag = lag + rng.randint(10, 45)
            second_date = min(rec["claim_submission_date"] + timedelta(days=second_lag),
                              config.AS_OF_DATE)
            amounts.append((round(total - first, 2),
                            second_date,
                            (second_date - rec["claim_submission_date"]).days))
        else:
            amounts.append((round(total, 2), first_date, lag))

        method = rng.choices(config.PAYMENT_METHODS, weights=config.PAYMENT_METHOD_WEIGHTS)[0]
        for amount, pay_date, pay_lag in amounts:
            if amount <= 0:
                continue
            pid += 1
            rows.append({
                "payment_id": f"PMT-{pid:06d}",
                "claim_id": rec["claim_id"],
                "payment_date": pay_date,
                "payer_id": rec["payer_id"],
                "paid_amount": amount,
                "payment_method": method,
                "days_to_payment": pay_lag,
            })

    payments = pd.DataFrame(rows)
    log.info("Generated %s payments totaling $%s",
             len(payments), f"{payments['paid_amount'].sum():,.0f}")
    return payments


def generate_ar_snapshots(claims: pd.DataFrame) -> pd.DataFrame:
    """Month-end A/R snapshots.

    Simplification: a claim appears in a snapshot if it was submitted on or
    before the snapshot date and is still open as of AS_OF_DATE (we don't
    reconstruct historical balance movement — the snapshot carries the
    current outstanding amount with the aging bucket as of that date).
    """
    snapshot_dates: list[date] = []
    d = config.SERVICE_START.replace(day=28)
    while d <= config.AS_OF_DATE:
        # roll to actual month end
        nxt = (d.replace(day=1) + timedelta(days=32)).replace(day=1)
        month_end = nxt - timedelta(days=1)
        if month_end <= config.AS_OF_DATE:
            snapshot_dates.append(month_end)
        d = nxt.replace(day=28)

    open_claims = claims[(claims["is_open"]) & (claims["outstanding_amount"] > 0)]
    rows = []
    sid = 0
    for snap in snapshot_dates:
        eligible = open_claims[open_claims["claim_submission_date"] <= snap]
        for rec in eligible.to_dict("records"):
            sid += 1
            age = (snap - rec["claim_submission_date"]).days
            rows.append({
                "snapshot_id": f"SNP-{sid:07d}",
                "claim_id": rec["claim_id"],
                "snapshot_date": snap,
                "outstanding_amount": rec["outstanding_amount"],
                "aging_bucket": _aging_bucket(age),
            })

    snapshots = pd.DataFrame(rows)
    log.info("Generated %s A/R snapshot rows across %s month-ends",
             len(snapshots), len(snapshot_dates))
    return snapshots
