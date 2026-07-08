"""Deterministic synthetic dimension + base-claim generator.

Builds all dimension tables and the raw claim skeleton (who/where/when/how
much was billed). Downstream steps (transform_claims, generate_denials,
generate_payments) turn the skeleton into a full revenue cycle dataset.

Everything derives from a single seeded random.Random instance, so the
output is identical on every run.
"""

from __future__ import annotations

import logging
import math
import random
from datetime import date, timedelta

import pandas as pd

from etl import config

log = logging.getLogger(__name__)

FIRST_INITIALS = list("ABCDEFGHJKLMNPRSTVW")
LAST_NAMES = [
    "Reynolds", "Okafor", "Nguyen", "Patel", "Kowalski", "Ramirez", "Chen",
    "Fitzgerald", "Andersson", "Delgado", "Haywood", "Iqbal", "Jefferson",
    "Kaminski", "Lindqvist", "Moreau", "Novak", "Osei", "Petrov", "Quintana",
    "Rossi", "Silva", "Takahashi", "Ueda", "Varga", "Whitfield", "Yamada", "Zieliński",
]


def _random_date(rng: random.Random, start: date, end: date) -> date:
    """Uniform random date in [start, end]."""
    return start + timedelta(days=rng.randint(0, (end - start).days))


def build_dim_date() -> pd.DataFrame:
    """Calendar covering the full activity window plus payment/appeal tail."""
    start, end = config.SERVICE_START, config.AS_OF_DATE
    rows = []
    d = start
    while d <= end:
        rows.append({
            "date_id": int(d.strftime("%Y%m%d")),
            "date": d.isoformat(),
            "month": d.month,
            "month_name": d.strftime("%B"),
            "quarter": (d.month - 1) // 3 + 1,
            "year": d.year,
            "week_of_year": int(d.strftime("%V")),
        })
        d += timedelta(days=1)
    return pd.DataFrame(rows)


def build_dim_facility() -> pd.DataFrame:
    return pd.DataFrame(
        config.FACILITIES,
        columns=["facility_id", "facility_name", "facility_type", "region", "state"],
    )


def build_dim_payer() -> pd.DataFrame:
    return pd.DataFrame(
        [p[:6] for p in config.PAYERS],
        columns=["payer_id", "payer_name", "payer_type", "contract_type", "state", "risk_category"],
    )


def build_dim_service_line() -> pd.DataFrame:
    return pd.DataFrame(
        [(s[0], s[1]) for s in config.SERVICE_LINES],
        columns=["service_line_id", "service_line_name"],
    )


def build_dim_denial_reason() -> pd.DataFrame:
    return pd.DataFrame(
        [r[:5] for r in config.DENIAL_REASONS],
        columns=["denial_reason_id", "denial_code", "denial_category",
                 "denial_description", "preventable_flag"],
    )


def build_dim_patient(rng: random.Random) -> pd.DataFrame:
    payer_types = ["Commercial", "Medicare", "Medicaid", "Self-pay", "Other"]
    type_weights = [0.48, 0.26, 0.14, 0.07, 0.05]
    rows = []
    for pid in range(1, config.N_PATIENTS + 1):
        insurance = rng.choices(payer_types, weights=type_weights)[0]
        # Medicare patients skew old; Medicaid skews younger
        if insurance == "Medicare":
            birth_year = rng.randint(1935, 1961)
        elif insurance == "Medicaid":
            birth_year = rng.randint(1975, 2015)
        else:
            birth_year = rng.randint(1940, 2010)
        age = config.AS_OF_DATE.year - birth_year
        if age < 18:
            age_group = "0-17"
        elif age < 35:
            age_group = "18-34"
        elif age < 50:
            age_group = "35-49"
        elif age < 65:
            age_group = "50-64"
        else:
            age_group = "65+"
        city, state = rng.choice(config.CITIES)
        rows.append({
            "patient_id": pid,
            "synthetic_patient_key": f"PAT-{pid:06d}",
            "gender": rng.choices(["Female", "Male", "Other"], weights=[0.51, 0.47, 0.02])[0],
            "birth_year": birth_year,
            "age_group": age_group,
            "city": city,
            "state": state,
            "insurance_type": insurance,
            "risk_segment": rng.choices(config.RISK_SEGMENTS, weights=[0.55, 0.30, 0.15])[0],
        })
    return pd.DataFrame(rows)


def build_dim_provider(rng: random.Random, facilities: pd.DataFrame) -> pd.DataFrame:
    fac_lookup = facilities.set_index("facility_id")[["state"]].to_dict("index")
    rows = []
    used_names: set[str] = set()
    for prov_id in range(1, config.N_PROVIDERS + 1):
        service_line_id = rng.choices(
            [s[0] for s in config.SERVICE_LINES],
            weights=[s[4] for s in config.SERVICE_LINES],
        )[0]
        specialty = rng.choice(config.SPECIALTIES[service_line_id])
        facility_id = rng.randint(1, len(config.FACILITIES))
        state = fac_lookup[facility_id]["state"]
        city = next((c for c, s in config.CITIES if s == state), config.CITIES[0][0])
        while True:
            name = f"Dr. {rng.choice(FIRST_INITIALS)}. {rng.choice(LAST_NAMES)}"
            if name not in used_names:
                used_names.add(name)
                break
        rows.append({
            "provider_id": prov_id,
            "provider_name": name,
            "specialty": specialty,
            "facility_id": facility_id,
            "city": city,
            "state": state,
            "npi_fake": f"FAKE{prov_id:07d}",
            # helper for claim generation; dropped before export
            "_service_line_id": service_line_id,
        })
    return pd.DataFrame(rows)


def build_base_claims(rng: random.Random, patients: pd.DataFrame,
                      providers: pd.DataFrame) -> pd.DataFrame:
    """Claim skeleton: parties, dates, billed amount. Status/financials are
    assigned in transform_claims.py."""
    payer_ids = [p[0] for p in config.PAYERS]
    payer_by_type: dict[str, list[int]] = {}
    for p in config.PAYERS:
        payer_by_type.setdefault(p[2], []).append(p[0])

    line_params = {s[0]: (s[2], s[3]) for s in config.SERVICE_LINES}
    providers_by_line: dict[int, list[dict]] = {}
    for rec in providers.to_dict("records"):
        providers_by_line.setdefault(rec["_service_line_id"], []).append(rec)

    patient_recs = patients.to_dict("records")
    rows = []
    for i in range(1, config.N_CLAIMS + 1):
        patient = rng.choice(patient_recs)
        # payer follows the patient's insurance type ~90% of the time
        if rng.random() < 0.9 and patient["insurance_type"] in payer_by_type:
            payer_id = rng.choice(payer_by_type[patient["insurance_type"]])
        else:
            payer_id = rng.choices(payer_ids, weights=config.PAYER_MIX)[0]

        service_line_id = rng.choices(
            [s[0] for s in config.SERVICE_LINES],
            weights=[s[4] for s in config.SERVICE_LINES],
        )[0]
        provider = rng.choice(providers_by_line[service_line_id])

        dos = _random_date(rng, config.SERVICE_START, config.SERVICE_END)
        submission = dos + timedelta(days=rng.randint(1, 14))

        median, sigma = line_params[service_line_id]
        billed = round(median * math.exp(rng.gauss(0, sigma)), 2)
        billed = max(billed, 45.0)

        rows.append({
            "claim_id": f"CLM-{i:06d}",
            "patient_id": patient["patient_id"],
            "provider_id": provider["provider_id"],
            "facility_id": provider["facility_id"],
            "payer_id": payer_id,
            "service_line_id": service_line_id,
            "date_of_service": dos,
            "claim_submission_date": submission,
            "billed_amount": billed,
        })
    return pd.DataFrame(rows)


def generate_all() -> dict[str, pd.DataFrame]:
    """Build every dimension plus the base-claim skeleton. Deterministic."""
    rng = random.Random(config.RANDOM_SEED)
    log.info("Generating dimensions (seed=%s)", config.RANDOM_SEED)

    dims = {
        "dim_date": build_dim_date(),
        "dim_facility": build_dim_facility(),
        "dim_payer": build_dim_payer(),
        "dim_service_line": build_dim_service_line(),
        "dim_denial_reason": build_dim_denial_reason(),
    }
    dims["dim_patient"] = build_dim_patient(rng)
    providers = build_dim_provider(rng, dims["dim_facility"])
    dims["dim_provider"] = providers.drop(columns=["_service_line_id"])

    log.info("Generating %s base claims", config.N_CLAIMS)
    base_claims = build_base_claims(rng, dims["dim_patient"], providers)

    return {**dims, "base_claims": base_claims}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    out = generate_all()
    for name, df in out.items():
        print(f"{name}: {len(df):,} rows")
