# DAX Measures — Revenue Cycle Command Center

Production-ready DAX for the Power BI model built on the CSVs in `data/processed/` (or the PostgreSQL star schema). Model assumptions:

- Each fact table relates to its dimensions by the surrogate keys (auto-detected star relationships).
- `dim_date[date]` is marked as the model's Date table and relates to `fact_claims[claim_submission_date]` (active) and `fact_claims[date_of_service]` (inactive; activate with `USERELATIONSHIP` where noted).
- Boolean CSV columns (`is_denied`, `is_open`, `preventable_flag`, …) load as True/False.

> Organize these in a dedicated `_Measures` table for a clean field list.

## Financial Core

```dax
Total Billed Amount =
SUM ( fact_claims[billed_amount] )
```

```dax
Total Paid Amount =
SUM ( fact_claims[paid_amount] )
```

```dax
Outstanding A/R =
CALCULATE (
    SUM ( fact_claims[outstanding_amount] ),
    fact_claims[is_open] = TRUE ()
)
```

```dax
Revenue at Risk =
CALCULATE (
    SUM ( fact_claims[outstanding_amount] ),
    fact_claims[is_open] = TRUE (),
    FILTER (
        fact_claims,
        fact_claims[is_denied] = TRUE ()
            || fact_claims[claim_age_days] > 60
    )
)
```

```dax
A/R Over 90 Days =
CALCULATE (
    SUM ( fact_claims[outstanding_amount] ),
    fact_claims[is_open] = TRUE (),
    fact_claims[claim_age_days] > 90
)
```

## Rates & Quality

```dax
Total Claims =
COUNTROWS ( fact_claims )
```

```dax
Denial Rate =
DIVIDE (
    CALCULATE ( COUNTROWS ( fact_claims ), fact_claims[is_denied] = TRUE () ),
    [Total Claims]
)
-- Format: percentage, 1 decimal
```

```dax
Clean Claim Rate =
DIVIDE (
    CALCULATE (
        COUNTROWS ( fact_claims ),
        fact_claims[is_denied] = FALSE (),
        fact_claims[is_paid] = TRUE (),
        fact_claims[claim_status] IN { "Paid", "Closed" }
    ),
    [Total Claims]
)
```

```dax
Average Days to Payment =
AVERAGE ( fact_payments[days_to_payment] )
```

## Denials & Appeals

```dax
Total Denied Amount =
SUM ( fact_denials[denied_amount] )
```

```dax
Preventable Denial Rate =
-- Uses the fact_denials → dim_denial_reason relationship
DIVIDE (
    CALCULATE (
        COUNTROWS ( fact_denials ),
        dim_denial_reason[preventable_flag] = TRUE ()
    ),
    COUNTROWS ( fact_denials )
)
```

```dax
Appeals Resolved =
CALCULATE (
    COUNTROWS ( fact_denials ),
    fact_denials[appeal_status] = "Appeal Resolved"
)
```

```dax
Appeal Success Rate =
DIVIDE (
    CALCULATE (
        COUNTROWS ( fact_denials ),
        fact_denials[appeal_outcome] IN { "Overturned", "Partially Overturned" }
    ),
    [Appeals Resolved]
)
```

```dax
Recovered Amount =
SUM ( fact_denials[recovered_amount] )
```

```dax
Net Denial Exposure =
[Total Denied Amount] - [Recovered Amount]
```

## Work Queue

```dax
Open Follow-Up Tasks =
CALCULATE (
    COUNTROWS ( fact_followup_tasks ),
    fact_followup_tasks[status] IN { "Open", "In Progress" }
)
```

```dax
Overdue Follow-Ups =
VAR AsOf = MAX ( dim_date[date] )   -- or TODAY() in a live deployment
RETURN
CALCULATE (
    COUNTROWS ( fact_followup_tasks ),
    fact_followup_tasks[status] IN { "Open", "In Progress" },
    fact_followup_tasks[due_date] < AsOf
)
```

```dax
Tasks Completed =
CALCULATE (
    COUNTROWS ( fact_followup_tasks ),
    fact_followup_tasks[status] = "Completed"
)
```

```dax
Average Time to Close Task =
AVERAGEX (
    FILTER (
        fact_followup_tasks,
        fact_followup_tasks[status] = "Completed"
            && NOT ISBLANK ( fact_followup_tasks[closed_date] )
    ),
    DATEDIFF (
        fact_followup_tasks[created_date],
        fact_followup_tasks[closed_date],
        DAY
    )
)
```

## Trend / Time Intelligence

```dax
Denial Rate (Prior Month) =
CALCULATE ( [Denial Rate], DATEADD ( dim_date[date], -1, MONTH ) )
```

```dax
Denial Rate MoM Change =
[Denial Rate] - [Denial Rate (Prior Month)]
-- Conditional formatting: red when positive (worsening), green when negative
```

```dax
Paid to Billed % =
DIVIDE ( [Total Paid Amount], [Total Billed Amount] )
```

## Payer Risk (composite, matches SQL & API logic)

```dax
Payer Risk Score =
VAR MaxDenial = MAXX ( ALL ( dim_payer ), CALCULATE ( [Denial Rate] ) )
VAR MaxLag    = MAXX ( ALL ( dim_payer ), CALCULATE ( [Average Days to Payment] ) )
VAR MaxAged   =
    MAXX (
        ALL ( dim_payer ),
        CALCULATE ( DIVIDE ( [A/R Over 90 Days], [Outstanding A/R] ) )
    )
RETURN
    0.5 * DIVIDE ( [Denial Rate], MaxDenial )
    + 0.3 * DIVIDE ( [Average Days to Payment], MaxLag )
    + 0.2 * DIVIDE ( DIVIDE ( [A/R Over 90 Days], [Outstanding A/R] ), MaxAged )
```

## Formatting Guide

| Measure | Format |
|---|---|
| All $ measures | Currency, 0 decimals ($ #,##0) |
| Denial Rate, Clean Claim Rate, Preventable Denial Rate, Appeal Success Rate, Paid to Billed % | Percentage, 1 decimal |
| Days measures | Decimal, 1 decimal |
| Counts | Whole number, thousands separator |
| Payer Risk Score | Decimal, 2 decimals |
