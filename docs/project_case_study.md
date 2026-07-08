# Case Study — Healthcare Revenue Cycle Command Center

## Business Problem

US providers write off billions of dollars a year to claim denials and stalled accounts receivable. The mechanics are mundane and brutal: a claim gets denied for missing documentation and nobody works it; an appeal window quietly expires; a payer's denial rate creeps from 12% to 22% and nobody notices until quarter-end; the A/R report is a spreadsheet emailed weekly, already stale on arrival.

The gap is rarely analytical sophistication — it's **operationalization**. Teams have data; they lack a system that turns that data into a prioritized queue of actions and puts payer behavior on a scoreboard.

## Objective

Build a working, end-to-end system that:

1. Models the revenue cycle correctly (claims → denials → appeals → payments → A/R → follow-up).
2. Computes the KPIs leadership actually asks for (denial rate, revenue at risk, A/R over 90, appeal recovery).
3. **Converts analytics into work**: rule-generated, priority-ranked follow-up tasks routed to the right team.
4. Serves operations staff (React work queue) and executives (Power BI layer) from one governed model.

## Dataset

No public claims dataset ships with denial lifecycles and appeal outcomes, and real data is off-limits (PHI). So the project includes a **deterministic synthetic generator** (fixed seed 42, zero external downloads):

- 1,200 patients (demographic segments only — no names, no PHI), 110 providers, 8 facilities
- 9 payers with **parameterized behavior**: each has its own denial propensity (8–24%), payment-lag distribution (21–60 days), and allowed-amount ratio — so payer analytics show real contrast instead of uniform noise
- 6,000 claims across 7 service lines with lognormal charge distributions per line
- ~845 denials with a full appeal lifecycle (appealed → resolved → overturned/partial/upheld → recovered dollars)
- ~5,200 payments that reconcile to claim paid amounts to the cent
- Month-end A/R snapshots with aging buckets; stale claims resolve/write off over time so the aging curve stays realistic

## Architecture

```
generator (seed 42) → ETL pipeline → CSV star schema ⇄ PostgreSQL (optional, Docker)
                                   → validation suite (46 checks, gating)
                                   → automation rules engine → tasks + payer alerts
                                   → FastAPI (10 endpoints) → React Command Center (6 pages)
                                   → Power BI semantic layer (documented DAX + 5 pages)
```

CSV-first was a deliberate choice: a reviewer can run the entire system with `pip install` and `npm install` — no Docker, no database. The identical schema exists as PostgreSQL DDL with FKs, checks, and indexes for the database-backed path.

## Data Model

Kimball star schema — 7 dimensions, 5 facts, with `fact_claims` as the hub (grain: one row per claim) and child facts for denials, payments, A/R snapshots, and follow-up tasks. Conformed `dim_payer` and `dim_date` make denial, payment, and aging analyses directly comparable. Details: [data_model_diagram.md](data_model_diagram.md) and [database/data_dictionary.md](../database/data_dictionary.md).

## ETL Process

Modular Python pipeline (`etl/`): generate dimensions → transform claims (status, adjudication financials, aging) → generate denials + appeal outcomes (recoveries flow back onto claim financials so tables agree) → generate payments (payer-specific lags, split remittances) → month-end A/R snapshots. Logging throughout; every module seeds deterministically so reruns are byte-identical.

A separate **validation suite** gates the output with 46 checks: volumes, null keys, negative amounts, referential integrity on 12 FK paths, status vocabulary, denial↔claim consistency in both directions, payment reconciliation to the cent, aging-bucket math, and date sanity. It writes a markdown report and fails loudly on any violation.

## KPI Logic

Every KPI exists in three synchronized implementations — SQL (`analytics/*.sql`, 40 queries), API (pandas), and DAX (`powerbi/measures.md`) — with one definition documented in the data dictionary. Highlights:

- **Revenue at Risk** = outstanding on denied claims + open claims aged > 60 days
- **Clean Claim Rate** = paid without denial or rework ÷ all claims (first-pass yield)
- **Payer Risk Score** = 0.5·normalized denial rate + 0.3·normalized payment lag + 0.2·normalized share of A/R past 90 days — one number that ranks payers for escalation

## Automation Logic

Five rules turn the model into a work system (full spec: [automation/alert_rules.md](../automation/alert_rules.md)):

| Rule | Trigger | Output |
|---|---|---|
| High-value denial | denied > $5,000, unresolved | High task → Denials Team |
| A/R aging risk | > $1,000 outstanding, > 60 days | Medium/High task → AR Follow-up |
| Missing documentation | denial category match | Task → Documentation Team |
| Payer escalation | payer denial rate > 20% | Alert → payer relations |
| Appeal deadline | unappealed 20+ days post-denial | **Urgent** task → Appeals Team |

Tasks are deduplicated per (claim, rule), carry SLA due dates by priority (Urgent = 2 days … Low = 15), and regeneration is idempotent. On the seed-42 dataset the engine produces ~430 tasks and a payer escalation alert for State Medicaid at a 25.0% denial rate — exactly the payer configured with the worst behavior, which validates the pipeline end to end.

## Dashboards

**React Command Center (operations):** executive KPI wall with escalation banner, a claims work queue with seven filters and priority sorting, claim detail with a full event timeline and a recommended next action, payer scorecards with composite risk ranking, and a task queue with overdue flags. Every page has loading, error, and empty states; connection failures show run instructions instead of a blank screen.

**Power BI (executives):** five fully specified pages (Executive Overview, Denial Analysis, A/R Aging, Payer Performance, Work Queue) with 20+ production-ready DAX measures. Documented honestly as a design layer — no fake `.pbix`, no fake screenshots.

## Business Impact (what this would do in production)

- **Stop high-value leakage:** the day a $19k orthopedics claim is denied, it's a High task in a named team's queue — not a row 4,000 deep in a spreadsheet.
- **Never miss an appeal window:** the deadline rule converts silent write-offs into urgent, dated work items.
- **Negotiate with evidence:** payer scorecards and alert history turn "this payer feels slow" into "43-day average payment lag and a 22% denial rate, trending worse since March."
- **Focus scarce staff:** priority + dollars-at-stake sorting works the queue in value order.

## Future Improvements

- Predictive denial-risk scoring on claim attributes before submission
- Write-back workflow (assign, note, close tasks from the UI)
- dbt transformation layer with tests and lineage
- 835/837 EDI ingestion for realistic sourcing
- Role-based access, audit logging, and facility-level row security

## Disclaimer

This project uses synthetic/public-style healthcare data only and does not contain real patient information. All identifiers are generated; NPIs are fake by construction.
