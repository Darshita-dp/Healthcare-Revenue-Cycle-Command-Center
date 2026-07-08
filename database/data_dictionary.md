# Data Dictionary — Healthcare Revenue Cycle Command Center

> All data is synthetic. Patients are demographic segments with generated keys — no names, no real identifiers, no PHI. Provider NPIs are prefixed `FAKE`.

## Star Schema Overview

The model follows the Kimball star-schema pattern: **fact tables** hold measurable business events (claims, denials, payments, A/R snapshots, tasks) at a declared grain, and **dimension tables** hold the descriptive context used to slice them (who, where, which payer, why denied, when). Facts reference dimensions by surrogate integer keys; every analytical question in the project resolves to *fact measure grouped by dimension attribute* — e.g., "denial rate by payer" is `fact_claims.is_denied` grouped by `dim_payer.payer_name`.

Why a star schema here:

- **Query simplicity** — every KPI is a short join between one fact and one or two dimensions.
- **BI compatibility** — Power BI and most semantic layers auto-detect star relationships.
- **Conformed dimensions** — `dim_payer` and `dim_date` are shared across all five facts, so denial, payment, and A/R analyses are directly comparable.

```
        dim_patient   dim_provider   dim_facility
              \            |            /
               \           |           /
dim_date ───────────  fact_claims  ─────────── dim_payer
               /           |           \
              /            |            \
   dim_service_line        |        (1:N to facts below)
                           |
      fact_denials   fact_payments   fact_ar_snapshot   fact_followup_tasks
           |                                     
   dim_denial_reason                             
```

`fact_claims` is the hub: the four other facts each carry `claim_id` and inherit claim context (payer, facility, provider, service line) through it.

---

## Dimension Tables

### dim_patient — synthetic patients (1,200 rows)

| Column | Type | Description |
|---|---|---|
| patient_id | INTEGER PK | Surrogate key |
| synthetic_patient_key | VARCHAR(20) | Generated key like `PAT-000123`; used instead of any name |
| gender | VARCHAR(10) | Female / Male / Other |
| birth_year | INTEGER | Year of birth (1930–2015) |
| age_group | VARCHAR(10) | 0-17, 18-34, 35-49, 50-64, 65+ |
| city | VARCHAR(60) | Synthetic US city |
| state | CHAR(2) | US state code |
| insurance_type | VARCHAR(20) | Commercial / Medicare / Medicaid / Self-pay / Other |
| risk_segment | VARCHAR(10) | Low / Medium / High clinical-financial risk segment |

### dim_provider — rendering providers (110 rows)

| Column | Type | Description |
|---|---|---|
| provider_id | INTEGER PK | Surrogate key |
| provider_name | VARCHAR(100) | Synthetic name ("Dr. A. Reynolds" style) |
| specialty | VARCHAR(50) | Clinical specialty, aligned with service lines |
| facility_id | INTEGER FK → dim_facility | Primary facility |
| city / state | VARCHAR / CHAR(2) | Practice location |
| npi_fake | VARCHAR(12) | Clearly fake NPI, `FAKE`-prefixed |

### dim_facility — care sites (8 rows)

| Column | Type | Description |
|---|---|---|
| facility_id | INTEGER PK | Surrogate key |
| facility_name | VARCHAR(100) | Synthetic facility name |
| facility_type | VARCHAR(50) | Hospital / Clinic / Ambulatory Surgery Center / Urgent Care |
| region | VARCHAR(30) | North / South / East / West |
| state | CHAR(2) | US state code |

### dim_payer — insurance payers (9 rows)

| Column | Type | Description |
|---|---|---|
| payer_id | INTEGER PK | Surrogate key |
| payer_name | VARCHAR(100) | Synthetic payer name |
| payer_type | VARCHAR(20) | Commercial / Medicare / Medicaid / Self-pay / Other |
| contract_type | VARCHAR(30) | In-Network / Out-of-Network / Government |
| state | CHAR(2) | Primary operating state |
| risk_category | VARCHAR(10) | Low / Medium / High — payer behavioral risk (denial propensity, payment speed) |

### dim_denial_reason — denial vocabulary (8 rows)

| Column | Type | Description |
|---|---|---|
| denial_reason_id | INTEGER PK | Surrogate key |
| denial_code | VARCHAR(10) | Synthetic CARC-style code (e.g., `D-197`) |
| denial_category | VARCHAR(50) | One of the 8 denial categories |
| denial_description | VARCHAR(200) | Human-readable explanation |
| preventable_flag | BOOLEAN | TRUE if a front-end process fix (auth, eligibility check, documentation) could prevent it |

### dim_service_line — clinical service lines (7 rows)

| Column | Type | Description |
|---|---|---|
| service_line_id | INTEGER PK | Surrogate key |
| service_line_name | VARCHAR(50) | Primary Care, Emergency, Cardiology, Orthopedics, Imaging, Laboratory, Behavioral Health |

### dim_date — calendar (one row per day of activity window)

| Column | Type | Description |
|---|---|---|
| date_id | INTEGER PK | `YYYYMMDD` smart key |
| date | DATE | Calendar date |
| month | INTEGER | 1–12 |
| month_name | VARCHAR(12) | January … December |
| quarter | INTEGER | 1–4 |
| year | INTEGER | Calendar year |
| week_of_year | INTEGER | ISO week 1–53 |

---

## Fact Tables

### fact_claims — grain: one row per claim (6,000 rows)

| Column | Type | Description |
|---|---|---|
| claim_id | VARCHAR(20) PK | `CLM-000001` |
| patient_id | FK → dim_patient | Patient on the claim |
| provider_id | FK → dim_provider | Rendering provider |
| facility_id | FK → dim_facility | Site of service |
| payer_id | FK → dim_payer | Billed payer |
| service_line_id | FK → dim_service_line | Clinical service line |
| date_of_service | DATE | When care was delivered |
| claim_submission_date | DATE | When the claim was billed (≥ date_of_service) |
| claim_status | VARCHAR(20) | Submitted / Paid / Denied / Partially Paid / Under Review / Appealed / Closed |
| billed_amount | NUMERIC(12,2) | Gross charges |
| allowed_amount | NUMERIC(12,2) | Contractually allowed amount |
| paid_amount | NUMERIC(12,2) | Total payer payments received |
| patient_responsibility | NUMERIC(12,2) | Copay/coinsurance/deductible portion |
| outstanding_amount | NUMERIC(12,2) | allowed − paid − patient_responsibility (floored at 0) on unresolved claims |
| claim_age_days | INTEGER | Days since submission (as of the data build date) |
| is_denied | BOOLEAN | Claim was denied (including later appealed) |
| is_paid | BOOLEAN | Claim received payer payment |
| is_open | BOOLEAN | Balance unresolved — still in A/R |
| is_high_value | BOOLEAN | billed_amount ≥ $10,000 |

### fact_denials — grain: one row per denial (≈15% of claims)

| Column | Type | Description |
|---|---|---|
| denial_id | VARCHAR(20) PK | `DEN-000001` |
| claim_id | FK → fact_claims | Denied claim |
| denial_reason_id | FK → dim_denial_reason | Why it was denied |
| denial_date | DATE | Payer denial date |
| denied_amount | NUMERIC(12,2) | Amount denied |
| appeal_status | VARCHAR(20) | Not Appealed / Appeal Submitted / Appeal Resolved |
| appeal_submitted_date | DATE, nullable | When the appeal was filed |
| appeal_outcome | VARCHAR(20), nullable | Overturned / Partially Overturned / Upheld (resolved appeals only) |
| recovered_amount | NUMERIC(12,2) | Dollars recovered from the appeal |
| days_to_appeal | INTEGER, nullable | denial_date → appeal_submitted_date |

### fact_payments — grain: one row per remittance

| Column | Type | Description |
|---|---|---|
| payment_id | VARCHAR(20) PK | `PMT-000001` |
| claim_id | FK → fact_claims | Paid claim |
| payment_date | DATE | Remittance date |
| payer_id | FK → dim_payer | Paying payer |
| paid_amount | NUMERIC(12,2) | Payment amount (> 0 by constraint) |
| payment_method | VARCHAR(20) | EFT / Check / Card / Lockbox |
| days_to_payment | INTEGER | claim_submission_date → payment_date |

### fact_ar_snapshot — grain: one row per open claim per snapshot date

| Column | Type | Description |
|---|---|---|
| snapshot_id | VARCHAR(24) PK | `SNP-000001` |
| claim_id | FK → fact_claims | Open claim |
| snapshot_date | DATE | Month-end snapshot date |
| outstanding_amount | NUMERIC(12,2) | Balance as of snapshot |
| aging_bucket | VARCHAR(10) | 0-30 / 31-60 / 61-90 / 90+ (days since submission at snapshot) |

### fact_followup_tasks — grain: one task per claim per automation rule

| Column | Type | Description |
|---|---|---|
| task_id | VARCHAR(20) PK | `TSK-000001` |
| claim_id | FK → fact_claims | Claim to work |
| task_type | VARCHAR(60) | e.g., "Review high-value denied claim" |
| priority | VARCHAR(10) | Low / Medium / High / Urgent |
| assigned_team | VARCHAR(40) | Denials Team / AR Follow-up Team / Documentation Team / Appeals Team |
| created_date | DATE | When the rule fired |
| due_date | DATE | SLA-based due date (priority-dependent) |
| status | VARCHAR(15) | Open / In Progress / Completed / Cancelled |
| closed_date | DATE, nullable | Completion date |
| reason | VARCHAR(200) | Which rule fired and why |

---

## Key Business Definitions

| Term | Definition in this model |
|---|---|
| Denial rate | `COUNT(is_denied) / COUNT(*)` on fact_claims |
| Clean claim rate | Claims paid with no denial and no rework ÷ all claims |
| Outstanding A/R | `SUM(outstanding_amount) WHERE is_open` |
| Revenue at risk | Outstanding on denied claims + outstanding on open claims aged > 60 days |
| Aging bucket | Days from `claim_submission_date` to snapshot/build date: 0-30, 31-60, 61-90, 90+ |
| Preventable denial | Denial whose `dim_denial_reason.preventable_flag` is TRUE |
| Appeal success | Resolved appeal with outcome Overturned or Partially Overturned |
