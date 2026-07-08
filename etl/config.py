"""Shared configuration for the synthetic data generator and ETL pipeline.

Every tunable knob lives here so the dataset can be resized or re-shaped
without touching generator logic. RANDOM_SEED makes every run reproducible.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
SAMPLE_DIR = DATA_DIR / "sample"
SAMPLE_ROWS = 50  # rows per table copied into data/sample/

# ---------------------------------------------------------------------------
# Time window — all activity happens in this window; AS_OF_DATE is "today"
# for age calculations so the dataset never goes stale.
# ---------------------------------------------------------------------------
AS_OF_DATE = date(2026, 6, 30)
SERVICE_START = date(2025, 1, 1)
SERVICE_END = date(2026, 6, 15)

# ---------------------------------------------------------------------------
# Volumes
# ---------------------------------------------------------------------------
N_PATIENTS = 1200
N_PROVIDERS = 110
N_CLAIMS = 6000

# ---------------------------------------------------------------------------
# Financial thresholds
# ---------------------------------------------------------------------------
HIGH_VALUE_THRESHOLD = 10_000.00   # is_high_value flag on claims

# ---------------------------------------------------------------------------
# Facilities (8)
# ---------------------------------------------------------------------------
FACILITIES = [
    # facility_id, name, type, region, state
    (1, "St. Meridian Medical Center",   "Hospital",                  "North", "IL"),
    (2, "Lakeview Community Hospital",   "Hospital",                  "North", "WI"),
    (3, "Cedar Grove Clinic",            "Clinic",                    "South", "TX"),
    (4, "Riverbend Family Practice",     "Clinic",                    "South", "TX"),
    (5, "Summit Orthopedic Surgery Center", "Ambulatory Surgery Center", "West", "CO"),
    (6, "Pacific Heights Imaging Center", "Ambulatory Surgery Center", "West", "CA"),
    (7, "Eastgate Urgent Care",          "Urgent Care",               "East", "NY"),
    (8, "Harbor Point Behavioral Health", "Clinic",                   "East", "MA"),
]

# ---------------------------------------------------------------------------
# Payers (9) — behavior parameters drive realistic analytics:
#   denial_rate: probability a claim is denied
#   pay_lag_mean/sd: days from submission to payment (lognormal-ish)
#   allowed_ratio: allowed_amount as a share of billed_amount
# ---------------------------------------------------------------------------
PAYERS = [
    # id, name, payer_type, contract_type, state, risk_category, denial_rate, pay_lag_mean, pay_lag_sd, allowed_ratio
    # Payer names are fictional — deliberately NOT real insurance brands,
    # since synthetic denial rates are attributed to them.
    (1, "Blue Summit National",     "Commercial", "In-Network",     "IL", "Low",    0.09, 24, 8,  0.72),
    (2, "Northwind Health Plans",   "Commercial", "In-Network",     "TX", "Medium", 0.14, 32, 12, 0.68),
    (3, "Granite Peak Health",      "Commercial", "In-Network",     "NY", "Low",    0.10, 27, 9,  0.70),
    (4, "Silverline Select",        "Commercial", "Out-of-Network", "CA", "High",   0.22, 45, 15, 0.55),
    (5, "Medicare Part B",          "Medicare",   "Government",     "US", "Low",    0.08, 21, 6,  0.62),
    (6, "Medicare Advantage Plus",  "Medicare",   "Government",     "US", "Medium", 0.16, 35, 12, 0.60),
    (7, "State Medicaid Program",   "Medicaid",   "Government",     "IL", "High",   0.24, 52, 18, 0.48),
    (8, "Self-Pay",                 "Self-pay",   "Out-of-Network", "US", "High",   0.05, 60, 25, 1.00),
    (9, "TriState Workers Comp",    "Other",      "Out-of-Network", "NY", "Medium", 0.18, 48, 16, 0.65),
]
# Share of claim volume by payer (sums to 1.0)
PAYER_MIX = [0.20, 0.16, 0.12, 0.08, 0.16, 0.10, 0.10, 0.04, 0.04]

# ---------------------------------------------------------------------------
# Service lines — billed-amount ranges (lognormal parameters per line)
# ---------------------------------------------------------------------------
SERVICE_LINES = [
    # id, name, billed_median, billed_sigma, volume_weight
    (1, "Primary Care",      260,   0.55, 0.28),
    (2, "Emergency",         2400,  0.85, 0.14),
    (3, "Cardiology",        3800,  0.90, 0.10),
    (4, "Orthopedics",       6500,  0.95, 0.09),
    (5, "Imaging",           1200,  0.70, 0.15),
    (6, "Laboratory",        340,   0.60, 0.16),
    (7, "Behavioral Health", 420,   0.50, 0.08),
]

# Specialties mapped to service lines (for provider generation)
SPECIALTIES = {
    1: ["Family Medicine", "Internal Medicine", "Pediatrics"],
    2: ["Emergency Medicine"],
    3: ["Cardiology", "Interventional Cardiology"],
    4: ["Orthopedic Surgery", "Sports Medicine"],
    5: ["Radiology"],
    6: ["Pathology"],
    7: ["Psychiatry", "Clinical Psychology"],
}

# ---------------------------------------------------------------------------
# Denial reasons — must match database/seed_reference_data.sql exactly.
# weight = relative frequency among denials.
# ---------------------------------------------------------------------------
DENIAL_REASONS = [
    # id, code, category, description, preventable, weight
    (1, "D-16",  "Missing documentation",        "Claim lacks required documentation or attachments",      True,  0.20),
    (2, "D-27",  "Eligibility issue",            "Patient not eligible on date of service",                True,  0.16),
    (3, "D-197", "Prior authorization required", "Service performed without required prior authorization", True,  0.15),
    (4, "D-11",  "Coding issue",                 "Diagnosis or procedure coding inconsistent or invalid",  True,  0.14),
    (5, "D-18",  "Duplicate claim",              "Exact duplicate of a previously submitted claim",        True,  0.07),
    (6, "D-29",  "Timely filing",                "Claim submitted after the payer filing deadline",        True,  0.08),
    (7, "D-50",  "Medical necessity",            "Service not deemed medically necessary by payer policy", False, 0.12),
    (8, "D-26",  "Coverage terminated",          "Patient coverage terminated before date of service",     False, 0.08),
]

# ---------------------------------------------------------------------------
# Appeal behavior
# ---------------------------------------------------------------------------
APPEAL_RATE = 0.55            # share of denials that get appealed
APPEAL_RESOLVED_RATE = 0.75   # share of submitted appeals resolved by AS_OF_DATE
APPEAL_OVERTURN = 0.40        # resolved appeals fully overturned
APPEAL_PARTIAL = 0.20         # resolved appeals partially overturned

# ---------------------------------------------------------------------------
# Demographics vocabulary
# ---------------------------------------------------------------------------
CITIES = [
    ("Chicago", "IL"), ("Springfield", "IL"), ("Milwaukee", "WI"), ("Madison", "WI"),
    ("Houston", "TX"), ("Austin", "TX"), ("Dallas", "TX"), ("Denver", "CO"),
    ("Boulder", "CO"), ("San Diego", "CA"), ("Sacramento", "CA"), ("Albany", "NY"),
    ("Buffalo", "NY"), ("Boston", "MA"), ("Worcester", "MA"),
]
AGE_GROUPS = ["0-17", "18-34", "35-49", "50-64", "65+"]
RISK_SEGMENTS = ["Low", "Medium", "High"]
PAYMENT_METHODS = ["EFT", "Check", "Card", "Lockbox"]
PAYMENT_METHOD_WEIGHTS = [0.62, 0.20, 0.06, 0.12]
