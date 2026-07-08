# Data Model — Star Schema

Kimball star schema: `fact_claims` is the hub; four child facts carry `claim_id` and inherit dimensional context through it. Full column definitions in [database/data_dictionary.md](../database/data_dictionary.md).

```mermaid
erDiagram
    dim_patient ||--o{ fact_claims : "patient_id"
    dim_provider ||--o{ fact_claims : "provider_id"
    dim_facility ||--o{ fact_claims : "facility_id"
    dim_facility ||--o{ dim_provider : "facility_id"
    dim_payer ||--o{ fact_claims : "payer_id"
    dim_service_line ||--o{ fact_claims : "service_line_id"
    dim_date ||--o{ fact_claims : "submission date"
    fact_claims ||--o| fact_denials : "claim_id"
    dim_denial_reason ||--o{ fact_denials : "denial_reason_id"
    fact_claims ||--o{ fact_payments : "claim_id"
    dim_payer ||--o{ fact_payments : "payer_id"
    fact_claims ||--o{ fact_ar_snapshot : "claim_id"
    fact_claims ||--o{ fact_followup_tasks : "claim_id"

    fact_claims {
        varchar claim_id PK
        int patient_id FK
        int provider_id FK
        int facility_id FK
        int payer_id FK
        int service_line_id FK
        date date_of_service
        date claim_submission_date
        varchar claim_status
        numeric billed_amount
        numeric allowed_amount
        numeric paid_amount
        numeric patient_responsibility
        numeric outstanding_amount
        int claim_age_days
        bool is_denied
        bool is_paid
        bool is_open
        bool is_high_value
    }

    fact_denials {
        varchar denial_id PK
        varchar claim_id FK
        int denial_reason_id FK
        date denial_date
        numeric denied_amount
        varchar appeal_status
        date appeal_submitted_date
        varchar appeal_outcome
        numeric recovered_amount
        int days_to_appeal
    }

    fact_payments {
        varchar payment_id PK
        varchar claim_id FK
        date payment_date
        int payer_id FK
        numeric paid_amount
        varchar payment_method
        int days_to_payment
    }

    fact_ar_snapshot {
        varchar snapshot_id PK
        varchar claim_id FK
        date snapshot_date
        numeric outstanding_amount
        varchar aging_bucket
    }

    fact_followup_tasks {
        varchar task_id PK
        varchar claim_id FK
        varchar task_type
        varchar priority
        varchar assigned_team
        date created_date
        date due_date
        varchar status
        date closed_date
        varchar reason
    }

    dim_patient {
        int patient_id PK
        varchar synthetic_patient_key
        varchar gender
        int birth_year
        varchar age_group
        varchar city
        varchar state
        varchar insurance_type
        varchar risk_segment
    }

    dim_payer {
        int payer_id PK
        varchar payer_name
        varchar payer_type
        varchar contract_type
        varchar state
        varchar risk_category
    }

    dim_provider {
        int provider_id PK
        varchar provider_name
        varchar specialty
        int facility_id FK
        varchar city
        varchar state
        varchar npi_fake
    }

    dim_facility {
        int facility_id PK
        varchar facility_name
        varchar facility_type
        varchar region
        varchar state
    }

    dim_denial_reason {
        int denial_reason_id PK
        varchar denial_code
        varchar denial_category
        varchar denial_description
        bool preventable_flag
    }

    dim_service_line {
        int service_line_id PK
        varchar service_line_name
    }

    dim_date {
        int date_id PK
        date date
        int month
        varchar month_name
        int quarter
        int year
        int week_of_year
    }
```

## Grain Statements

| Table | Grain |
|---|---|
| fact_claims | One row per claim |
| fact_denials | One row per denial event (0..1 per claim in this model) |
| fact_payments | One row per remittance transaction |
| fact_ar_snapshot | One row per open claim per month-end |
| fact_followup_tasks | One row per claim per automation rule |

## Design Notes

- **Surrogate integer keys** on all dimensions; business-style string keys (`CLM-`, `DEN-`, `PMT-`) on facts for readability in worklists.
- **Conformed dimensions:** `dim_payer` and `dim_date` are shared by multiple facts, making denial, payment, and A/R analyses directly comparable.
- **`dim_provider` → `dim_facility`** is a snowflake edge, kept because facility is both a claim attribute and a provider attribute (provider home facility).
- **Flags over joins:** `is_denied`, `is_open`, `is_high_value` are precomputed on `fact_claims` so BI tools and the API filter without subqueries.
- **No PHI by construction:** patients carry only demographic segments and generated keys; provider NPIs are `FAKE`-prefixed.
