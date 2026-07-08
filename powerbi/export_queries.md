# Power BI Export Queries & Data Sources

The processed CSVs are the primary Power BI source — **no transformation needed**. This file documents what each extract contains and provides the PostgreSQL source queries for a database-backed deployment.

## CSV Extracts (Power BI-ready)

All in `data/processed/` (small samples of the same shape in `data/sample/`):

| File | Grain | Rows (seed 42) | Loads as |
|---|---|---|---|
| dim_patient.csv | patient | 1,200 | Dimension |
| dim_provider.csv | provider | 110 | Dimension |
| dim_facility.csv | facility | 8 | Dimension |
| dim_payer.csv | payer | 9 | Dimension |
| dim_denial_reason.csv | denial reason | 8 | Dimension |
| dim_service_line.csv | service line | 7 | Dimension |
| dim_date.csv | day | 546 | Date table (mark as Date table) |
| fact_claims.csv | claim | 6,000 | Hub fact |
| fact_denials.csv | denial | ~845 | Fact |
| fact_payments.csv | payment | ~5,200 | Fact |
| fact_ar_snapshot.csv | claim × month-end | ~5,700 | Fact |
| fact_followup_tasks.csv | task | ~430 | Fact |

Conventions: ISO dates (`YYYY-MM-DD`), booleans as `True`/`False`, amounts as plain decimals, no thousands separators, UTF-8.

## Power Query (M) — folder load pattern

One query per file, or parameterize the folder:

```m
let
    Source = Csv.Document(
        File.Contents("C:\<repo>\data\processed\fact_claims.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(
        Promoted,
        {
            {"claim_id", type text}, {"patient_id", Int64.Type},
            {"provider_id", Int64.Type}, {"facility_id", Int64.Type},
            {"payer_id", Int64.Type}, {"service_line_id", Int64.Type},
            {"date_of_service", type date}, {"claim_submission_date", type date},
            {"claim_status", type text}, {"billed_amount", type number},
            {"allowed_amount", type number}, {"paid_amount", type number},
            {"patient_responsibility", type number},
            {"outstanding_amount", type number}, {"claim_age_days", Int64.Type},
            {"is_denied", type logical}, {"is_paid", type logical},
            {"is_open", type logical}, {"is_high_value", type logical}
        }
    )
in
    Typed
```

## PostgreSQL Source Queries (database deployment)

Straight table pulls are sufficient — the model does the analytics:

```sql
SELECT * FROM dim_patient;
SELECT * FROM dim_provider;
SELECT * FROM dim_facility;
SELECT * FROM dim_payer;
SELECT * FROM dim_denial_reason;
SELECT * FROM dim_service_line;
SELECT * FROM dim_date;
SELECT * FROM fact_claims;
SELECT * FROM fact_denials;
SELECT * FROM fact_payments;
SELECT * FROM fact_ar_snapshot;
SELECT * FROM fact_followup_tasks;
```

Optional pre-aggregated view for very large deployments (not needed at this volume):

```sql
-- Monthly claim rollup to reduce refresh cost on 10M+ row claim tables
SELECT
    d.year,
    d.month,
    c.payer_id,
    c.facility_id,
    c.service_line_id,
    COUNT(*)                                  AS claims,
    COUNT(*) FILTER (WHERE c.is_denied)       AS denied_claims,
    SUM(c.billed_amount)                      AS billed_amount,
    SUM(c.paid_amount)                        AS paid_amount,
    SUM(c.outstanding_amount) FILTER (WHERE c.is_open) AS outstanding_amount
FROM fact_claims c
JOIN dim_date d ON d.date = c.claim_submission_date
GROUP BY d.year, d.month, c.payer_id, c.facility_id, c.service_line_id;
```

## Refresh Strategy (documented for a real deployment)

1. Nightly: ETL pipeline regenerates `data/processed/` (or loads PostgreSQL).
2. Automation engine reruns, updating tasks and alerts (idempotent).
3. Power BI scheduled refresh follows at a fixed offset (e.g., pipeline 02:00, refresh 04:00).
4. `dim_date` regenerates with the activity window, so time intelligence never breaks.
