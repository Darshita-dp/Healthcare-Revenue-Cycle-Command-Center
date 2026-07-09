"""Explainable claim priority scoring.

A single, transparent, rule-based model that scores each claim from 0-100 and
records the exact business reason behind every point it awarded. There is no
black-box ML here — the score is a sum of documented rules, so a revenue cycle
analyst can always answer "why is this claim a priority?".

The module is deliberately dependency-light (standard library only) so it can
be reused by the ETL/automation layer and the FastAPI backend without pulling
in pandas or pydantic. Callers pass plain values; they get back a
``PriorityResult`` with the score, the tier, and the ordered list of drivers.

Scoring model (all thresholds are module constants so they are easy to audit):

  High-value denial      denied & > $5,000                 +30
                         denied & $2,500-$5,000            +20
  A/R aging (balance>$1k) age > 90 days                    +25
                         age 61-90 days                    +18
                         age 31-60 days                    +10
  Payer risk             payer denial rate > 20%           +15
                         payer denial rate 15-20%          +10
  Appeal urgency         not appealed & denied > 20 days   +20
                         not appealed & denied 10-20 days  +15
  Denial category        Timely filing                     +15
                         Medical necessity                 +12
                         Prior authorization required      +10
                         Missing documentation             +8
                         Eligibility issue                 +8
                         Coding issue                      +6
  Open financial         outstanding > $10,000             +15
   exposure              outstanding $5,000-$10,000        +10
                         outstanding $1,000-$5,000         +5

Score is capped at 100. Tiers: 80-100 Critical, 60-79 High, 40-59 Medium,
1-39 Low, 0 Monitor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------- #
# Thresholds (single source of truth — audited against automation/alert_rules) #
# --------------------------------------------------------------------------- #
HIGH_VALUE_DENIAL_HIGH = 5_000.0
HIGH_VALUE_DENIAL_MID = 2_500.0

AGING_BALANCE_FLOOR = 1_000.0
AGING_90 = 90
AGING_60 = 60
AGING_30 = 30

PAYER_RATE_HIGH = 0.20
PAYER_RATE_MID = 0.15

APPEAL_OVERDUE_DAYS = 20
APPEAL_APPROACHING_DAYS = 10

EXPOSURE_HIGH = 10_000.0
EXPOSURE_MID = 5_000.0
EXPOSURE_LOW = 1_000.0

# Points awarded per denial category (business preventability / recovery upside)
DENIAL_CATEGORY_POINTS = {
    "Timely filing": 15,
    "Medical necessity": 12,
    "Prior authorization required": 10,
    "Missing documentation": 8,
    "Eligibility issue": 8,
    "Coding issue": 6,
    # Duplicate claim / Coverage terminated carry no priority uplift on their own
}

SCORE_CAP = 100

TIER_BANDS = [
    (80, "Critical"),
    (60, "High"),
    (40, "Medium"),
    (1, "Low"),
    (0, "Monitor"),
]


@dataclass
class Driver:
    """One scored contribution, with a human-readable explanation."""

    label: str
    points: int
    category: str  # grouping key for portfolio-level aggregation

    def as_dict(self) -> dict:
        return {"label": self.label, "points": self.points, "category": self.category}


@dataclass
class PriorityResult:
    score: int
    tier: str
    drivers: list[Driver] = field(default_factory=list)

    @property
    def top_driver(self) -> Optional[str]:
        return self.drivers[0].label if self.drivers else None

    def drivers_as_dicts(self) -> list[dict]:
        return [d.as_dict() for d in self.drivers]

    def summary(self) -> str:
        """One-sentence, business-friendly explanation of the tier."""
        if self.score == 0 or not self.drivers:
            return "No active risk factors — this claim is resolved or within normal timelines."
        reasons = _humanize_reasons([d.category for d in self.drivers[:4]])
        return f"This claim is {self.tier} priority because it combines {reasons}."


def tier_for(score: int) -> str:
    for floor, name in TIER_BANDS:
        if score >= floor:
            return name
    return "Monitor"


def summarize(tier: str, driver_dicts: list[dict]) -> str:
    """Business-friendly one-liner from an already-scored claim's drivers.

    Lets callers that persisted only the driver dicts (e.g. a dataframe cell)
    rebuild the same sentence PriorityResult.summary() produces."""
    if not driver_dicts:
        return "No active risk factors — this claim is resolved or within normal timelines."
    reasons = _humanize_reasons([d["category"] for d in driver_dicts[:4]])
    return f"This claim is {tier} priority because it combines {reasons}."


def _humanize_reasons(categories: list[str]) -> str:
    phrase = {
        "high_value_denial": "a high denied dollar amount",
        "aging": "aging accounts receivable",
        "payer_risk": "an elevated payer denial rate",
        "appeal_urgency": "appeal-deadline urgency",
        "denial_category": "a recoverable denial reason",
        "exposure": "significant open financial exposure",
    }
    seen: list[str] = []
    for c in categories:
        p = phrase.get(c, c)
        if p not in seen:
            seen.append(p)
    if len(seen) == 1:
        return seen[0]
    if len(seen) == 2:
        return f"{seen[0]} and {seen[1]}"
    return ", ".join(seen[:-1]) + f", and {seen[-1]}"


def score_claim(
    *,
    is_denied: bool,
    denied_amount: float = 0.0,
    claim_age_days: int = 0,
    outstanding_amount: float = 0.0,
    payer_denial_rate: float = 0.0,
    appeal_status: Optional[str] = None,
    days_since_denial: Optional[int] = None,
    denial_category: Optional[str] = None,
) -> PriorityResult:
    """Score a single claim. All inputs are plain values; see module docstring
    for the point schedule. Returns a :class:`PriorityResult`."""
    drivers: list[Driver] = []
    denied_amount = float(denied_amount or 0.0)
    outstanding_amount = float(outstanding_amount or 0.0)

    # --- High-value denial ---------------------------------------------------
    if is_denied:
        if denied_amount > HIGH_VALUE_DENIAL_HIGH:
            drivers.append(Driver(
                f"High-value denial above ${HIGH_VALUE_DENIAL_HIGH:,.0f}", 30, "high_value_denial"))
        elif denied_amount >= HIGH_VALUE_DENIAL_MID:
            drivers.append(Driver(
                f"Denial between ${HIGH_VALUE_DENIAL_MID:,.0f} and ${HIGH_VALUE_DENIAL_HIGH:,.0f}",
                20, "high_value_denial"))

    # --- A/R aging (only meaningful with a real outstanding balance) ---------
    if outstanding_amount > AGING_BALANCE_FLOOR:
        if claim_age_days > AGING_90:
            drivers.append(Driver("Aged over 90 days with an open balance", 25, "aging"))
        elif claim_age_days > AGING_60:
            drivers.append(Driver("Aged 61-90 days with an open balance", 18, "aging"))
        elif claim_age_days > AGING_30:
            drivers.append(Driver("Aged 31-60 days with an open balance", 10, "aging"))

    # --- Payer risk ----------------------------------------------------------
    if payer_denial_rate > PAYER_RATE_HIGH:
        drivers.append(Driver(
            f"Payer denial rate above {PAYER_RATE_HIGH:.0%}", 15, "payer_risk"))
    elif payer_denial_rate >= PAYER_RATE_MID:
        drivers.append(Driver(
            f"Payer denial rate {PAYER_RATE_MID:.0%}-{PAYER_RATE_HIGH:.0%}", 10, "payer_risk"))

    # --- Appeal urgency (denied, not yet appealed) ---------------------------
    if is_denied and (appeal_status == "Not Appealed") and days_since_denial is not None:
        if days_since_denial > APPEAL_OVERDUE_DAYS:
            drivers.append(Driver(
                "Appeal window at risk — denied 20+ days, no appeal filed", 20, "appeal_urgency"))
        elif days_since_denial >= APPEAL_APPROACHING_DAYS:
            drivers.append(Driver(
                "Appeal deadline approaching — no appeal filed yet", 15, "appeal_urgency"))

    # --- Denial category -----------------------------------------------------
    if is_denied and denial_category in DENIAL_CATEGORY_POINTS:
        pts = DENIAL_CATEGORY_POINTS[denial_category]
        drivers.append(Driver(f"{denial_category} denial", pts, "denial_category"))

    # --- Open financial exposure ---------------------------------------------
    if outstanding_amount > EXPOSURE_HIGH:
        drivers.append(Driver("Open exposure above $10,000", 15, "exposure"))
    elif outstanding_amount >= EXPOSURE_MID:
        drivers.append(Driver("Open exposure $5,000-$10,000", 10, "exposure"))
    elif outstanding_amount >= EXPOSURE_LOW:
        drivers.append(Driver("Open exposure $1,000-$5,000", 5, "exposure"))

    raw = sum(d.points for d in drivers)
    score = min(raw, SCORE_CAP)
    drivers.sort(key=lambda d: d.points, reverse=True)
    return PriorityResult(score=score, tier=tier_for(score), drivers=drivers)
