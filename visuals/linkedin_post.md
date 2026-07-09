# LinkedIn Post Draft

---

Hospitals don't usually lose revenue in one dramatic moment. They lose it $4,000 at a time — a denial nobody worked, an appeal window that quietly expired, a payer whose denial rate drifted up for three months before anyone pulled the report.

I wanted to understand that problem end to end, so I built a **Healthcare Revenue Cycle Command Center** from scratch:

🔹 A deterministic synthetic claims dataset — 6,000 claims, 9 payers with distinct denial and payment behavior, full appeal lifecycles. Zero PHI by construction.
🔹 A PostgreSQL star schema (7 dimensions, 5 facts) with a 46-check Python validation suite
🔹 40 documented SQL queries for the KPIs that matter: denial rate, revenue at risk, A/R over 90 days, appeal recovery
🔹 An automation rules engine that converts analytics into *work* — prioritized follow-up tasks routed to the right team, and alerts when a payer crosses a 20% denial rate
🔹 An **explainable claim priority score** (0–100) — every claim shows *why* it's a priority, point by point, no black box
🔹 A **revenue recovery simulator** — "work the top 50 claims at a 40% recovery rate → ~$130K estimated recoverable"
🔹 A FastAPI backend + React operational dashboard: claims work queue, claim-level timelines, payer risk scorecards
🔹 A fully documented Power BI executive layer with production-ready DAX

The design idea I kept coming back to: **a dashboard tells you there's a problem; a command center tells you what to do first — and why.** Every metric in this system ends in a queue, a priority, and an owner. I kept the prioritization deliberately rule-based and transparent, because in revenue cycle work a person has to be able to defend why a claim was worked.

The whole thing runs locally with pip + npm — no external data, no infrastructure required.

Repo: https://github.com/Darshita-dp/Healthcare-Revenue-Cycle-Command-Center

I'd genuinely love feedback from people who live in revenue cycle operations — what would you add to the rules engine first?

#HealthcareAnalytics #RevenueCycle #DataEngineering #SQL #Python #React #FastAPI #PowerBI #DataAnalytics

---

**Posting notes:** attach 2–3 real screenshots (command center, work queue, claim detail). Post mid-week, morning.
