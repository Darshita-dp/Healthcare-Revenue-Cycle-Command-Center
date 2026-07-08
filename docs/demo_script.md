# Demo Script (90–120 seconds)

*Spoken walkthrough for interviews or a screen recording. Screens in [brackets].*

---

**[Command Center home]**

"This is the Healthcare Revenue Cycle Command Center — an end-to-end analytics and automation system I built on a synthetic claims dataset: six thousand claims, nine payers, a full denial and appeal lifecycle, all generated deterministically in Python so there's zero PHI.

Up top: the numbers a CFO asks for every Monday. Thirteen point seven million billed, about a million in outstanding A/R — and the red number, revenue at risk: outstanding money on denied claims and anything aging past sixty days. Notice the alert banner — State Medicaid just crossed a twenty-five percent denial rate. The system flagged it automatically."

**[Claims Work Queue]**

"Analytics are only useful if they change what someone does at 9 a.m. This is the work queue — every claim, filterable by payer, status, aging bucket, denial reason, priority, and facility, sorted so urgent tasks and the biggest dollars come first. The red-edged rows are high risk: urgent tasks or big balances past ninety days."

**[Click a claim → Claim Detail]**

"One click gives the full story: financials, the denial — here, coverage terminated, nineteen thousand dollars — the complete timeline, and a recommended action. Three automation rules fired on this claim, including an urgent one: the appeal window is closing. In a real shop, this is money that quietly dies in a spreadsheet. Here it's an assigned, dated task."

**[Payer Performance]**

"Payer scorecards, ranked by a composite risk score — half denial rate, thirty percent payment speed, twenty percent aged A/R. State Medicaid is rank one: twenty-three percent denials, fifty-two days to pay. That's the escalation conversation, with evidence."

**[About page, briefly]**

"Under the hood: a PostgreSQL star schema, a Python ETL pipeline with a forty-six-check validation suite, forty documented SQL queries, a FastAPI backend, this React front end, and a fully documented Power BI layer with production DAX.

Every number ties back to one governed data model — which is really the point: not a dashboard, but a system that turns claims data into prioritized work."

---

**Timing guide:** Command Center 25s · Work Queue 20s · Claim Detail 25s · Payers 20s · Close 20s.

**If asked "what was hardest?"** — making the synthetic data *behave*: payers needed distinct denial propensities and payment lags, appeal recoveries had to flow back onto claim financials so every table reconciles to the cent, and stale claims had to resolve over time or the aging curve looked absurd. The 46-check validation suite exists because the first version of that logic was wrong in three places.
