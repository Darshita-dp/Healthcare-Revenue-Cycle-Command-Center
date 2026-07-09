# Power BI Dashboard — Design & Build Notes

> **Honest note:** Power BI Desktop was not available in the build environment, so this repository ships the complete *design and semantic layer* (pages, visuals, DAX in [measures.md](measures.md), source queries in [export_queries.md](export_queries.md)) rather than a `.pbix` binary or fake screenshots. Building the actual file from these notes takes roughly 1–2 hours in Power BI Desktop — steps below.

## Data Connection

**Option A — CSV (fastest):** Get Data → Text/CSV → load all 12 files from `data/processed/`. Every file is Power BI-ready (headers, ISO dates, no nested structures).

**Option B — PostgreSQL:** `docker compose up -d`, run `python etl/load_to_postgres.py`, then Get Data → PostgreSQL (`localhost:5432`, db `revenue_cycle`).

**Model setup:**
1. Confirm star relationships: each `fact_*` table → its `dim_*` tables by surrogate key; `fact_denials`/`fact_payments`/`fact_ar_snapshot`/`fact_followup_tasks` → `fact_claims` by `claim_id` (many-to-one, single direction).
2. Mark `dim_date` as the Date table; relate `dim_date[date]` → `fact_claims[claim_submission_date]`.
3. Create a `_Measures` table and add all measures from [measures.md](measures.md).
4. Theme: dark navy headers (#0E1A30), primary blue (#1E5EFF), red for risk (#D92D20), green for recovery (#0E9F6E) — matches the React UI.

---

## Page 1 — Executive Overview

*Audience: CFO / VP Revenue Cycle. Question: "Are we healthy, and where is the money?"*

| Zone | Visual | Fields / Measures |
|---|---|---|
| Top band | 7 KPI cards | Total Billed, Total Paid, Outstanding A/R, Revenue at Risk, Denial Rate, Clean Claim Rate, Average Days to Payment |
| Left mid | Line chart — Monthly revenue trend | dim_date[month] × Total Billed, Total Paid |
| Right mid | Line chart — Denial rate trend | dim_date[month] × Denial Rate, with MoM change tooltip |
| Left low | Stacked bar — A/R aging | Aging bucket (from fact_ar_snapshot or claim_age_days bins) × Outstanding A/R |
| Center low | Bar — Top 5 payers by denied amount | dim_payer[payer_name] × Total Denied Amount, Top N filter = 5 |
| Right low | Bar — Revenue at risk by facility | dim_facility[facility_name] × Revenue at Risk |
| Corner | Donut — Claim status distribution | fact_claims[claim_status] × Total Claims |

Slicers: date range, facility, payer type.

## Page 2 — Denial Analysis

*Audience: Denials manager. Question: "Why are we losing money and is it preventable?"*

| Zone | Visual | Fields / Measures |
|---|---|---|
| Top | KPI cards | Denial Rate, Total Denied Amount, Preventable Denial Rate, Appeal Success Rate, Recovered Amount |
| Left | Bar — Top denial categories | dim_denial_reason[denial_category] × count of denials |
| Center | Table — Denial reason detail | category, code, description, denials, denied $, recovered $, net exposure |
| Right | Bar — Denied amount by payer | dim_payer[payer_name] × Total Denied Amount |
| Low left | 100% stacked column — Preventable vs not, by month | dim_date[month] × denial count, legend = preventable_flag |
| Low right | Line — Denial trend by month | dim_date[month] × denial count, legend = denial_category (top 4) |

**Drill-through page:** "Claims for this denial category" — table of claim_id, payer, facility, denied amount, appeal status; drill-through filter on denial_category.

## Page 3 — A/R Aging

*Audience: A/R follow-up supervisor. Question: "What's aging and who owes it?"*

| Zone | Visual | Fields / Measures |
|---|---|---|
| Top | KPI cards | Outstanding A/R, A/R Over 90 Days, % of A/R over 90 (A/R Over 90 ÷ Outstanding A/R), open claim count |
| Left | Column — A/R by aging bucket | bucket × Outstanding A/R |
| Center | Stacked bar — Outstanding by payer and bucket | dim_payer[payer_name] × Outstanding A/R, legend = bucket |
| Right | Area — Aging trend | fact_ar_snapshot[snapshot_date] × outstanding, legend = aging_bucket |
| Bottom | Table — High-value aging claims | claim_id, payer, facility, status, age days, outstanding; filter age > 90 & outstanding > 5000, sorted desc |
| Side | Clustered bar — Facility aging comparison | facility × % of A/R over 90 days |

## Page 4 — Payer Performance

*Audience: Managed care / payer relations. Question: "Which payer needs escalation?"*

| Zone | Visual | Fields / Measures |
|---|---|---|
| Top | Matrix — Payer scorecard | payer × claims, Denial Rate, Average Days to Payment, Paid to Billed %, Outstanding A/R, Payer Risk Score; conditional formatting on rate and score |
| Left | Scatter — Denial rate vs payment speed | x = Average Days to Payment, y = Denial Rate, size = Total Billed, detail = payer |
| Right | Bar — Outstanding balance by payer | payer × Outstanding A/R |
| Low | Bar — Paid vs billed by payer | payer × Total Billed, Total Paid |
| Callout | Card + alert table | payers with Denial Rate > 20% (matches automation Rule 4) |

## Page 5 — Work Queue

*Audience: Team leads. Question: "What must be worked today?"*

| Zone | Visual | Fields / Measures |
|---|---|---|
| Top | KPI cards | Open Follow-Up Tasks, Overdue Follow-Ups, Tasks Completed, Average Time to Close Task |
| Left | Table — High-priority tasks | task_type, claim_id, priority, team, due_date, status; filter priority ∈ {Urgent, High}, conditional red on overdue |
| Center | Column — Task status by team | assigned_team × task count, legend = status |
| Right | Bar — Claims needing appeal | fact_denials filtered appeal_status = "Not Appealed" × denied amount by payer |
| Low | Matrix — Team performance | team × Tasks Completed, Average Time to Close Task, Overdue Follow-Ups |

---

## Optional Page 6: Priority & Recovery (decision support)

The application layer adds an **explainable claim priority score** (0–100, tiered Critical/High/Medium/Low/Monitor) and a **revenue recovery simulator**. The score is computed in Python ([automation/priority_scoring.py](../automation/priority_scoring.py)) because it blends per-claim facts with a payer-level denial rate; the transparent rule sum can be mirrored in Power BI two ways:

1. **Export the scored claims** from the API (`GET /api/claims?sort=score`) or persist `priority_score` / `priority_tier` into a `fact_claims` extract, then treat them as ordinary columns. This is the recommended path — the rules stay in one place.
2. **Replicate the rule sum in DAX** for a self-contained model (see the "Explainable Priority Score (optional)" measures in [measures.md](measures.md)).

Suggested layout once `priority_score` / `priority_tier` are present:

| Zone | Visual | Fields / notes |
|---|---|---|
| Top | KPI cards | Critical Claims, High-Priority Claims, Critical+High Outstanding, Average Priority Score |
| Left | Bar — Claims by tier | priority_tier × claim count, ordered Critical→Monitor |
| Center | Table — Top-priority queue | claim_id, payer, outstanding, priority_score, priority_tier; sort desc by score |
| Right | Card + what-if | Recovery simulator: a `Claims to Work` (25/50/100) and `Recovery Rate` (30/40/50%) what-if parameter feeding an Estimated Recoverable Revenue measure |

Because the driver-level breakdown ("why +30") is inherently row-level and textual, it is best shown in the React app or a Power BI tooltip/drill-through; the Power BI page focuses on the tier distribution and the recovery estimate. Keep the honest framing: recovery rate is a planning assumption, not a guaranteed collection.

---

## Interactions & Polish Checklist

- [ ] Sync date slicer across pages 1–4
- [ ] Drill-through from every payer visual to Page 4, every denial visual to Page 2's claim list
- [ ] Tooltips: add Recovered Amount to all denial visuals
- [ ] Conditional formatting: Denial Rate red > 15%, amber 10–15%; risk score data bars
- [ ] Bookmark: "Escalation view" — Page 4 pre-filtered to Denial Rate > 20%
- [ ] Row-level security placeholder role by facility (demo talking point)
- [ ] Performance: all measures are simple aggregates over a ~6k-row fact — no optimization needed
