# Resume Bullets

## Primary block

**Healthcare Revenue Cycle Command Center | SQL, Python, Power BI, React, FastAPI**

- Built an end-to-end healthcare revenue cycle analytics system using synthetic claims data, SQL data modeling, Python ETL, Power BI dashboard planning, and a React operational interface
- Designed a PostgreSQL star schema for claims, denials, payments, payers, providers, facilities, A/R aging, and follow-up tasks to support KPI reporting and operational analysis
- Created analytics logic to track denial rate, revenue at risk, payer performance, A/R aging, appeal outcomes, and high-priority follow-up queues
- Developed automation rules to generate follow-up tasks for high-value denials, aging claims, payer spikes, and approaching appeal deadlines

## Alternate bullets (pick by target role)

**Data engineering emphasis**
- Engineered a deterministic Python ETL pipeline (fixed-seed, fully reproducible) generating 12 star-schema tables with 6,000+ claims, gated by a 46-check validation suite covering referential integrity, financial reconciliation to the cent, and aging-bucket logic

**Analytics emphasis**
- Authored 40 documented PostgreSQL queries (window functions, CTEs, FILTER aggregates) implementing executive, denial, A/R aging, and payer-performance KPIs, including a composite payer risk score used for escalation ranking

**BI emphasis**
- Specified a 5-page Power BI executive dashboard with 20+ production-ready DAX measures (time intelligence, normalized composite scoring) over a conformed-dimension star schema

**Full-stack emphasis**
- Shipped a FastAPI backend (10 endpoints, Pydantic models, 7-parameter filtered work queue) and a React 18 + TypeScript dashboard with six views, priority-ranked worklists, and claim-level event timelines

**Automation emphasis**
- Implemented an idempotent rules engine converting claims analytics into prioritized, SLA-dated follow-up tasks routed to four teams, plus automatic payer escalation alerts at a 20% denial-rate threshold

## One-liner (for a projects section with tight space)

- Built an end-to-end revenue cycle analytics platform (PostgreSQL star schema, Python ETL + validation, FastAPI, React, documented Power BI/DAX layer) that converts claims and denial data into prioritized follow-up work queues
