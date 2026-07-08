-- ============================================================================
-- Executive KPI Queries — Healthcare Revenue Cycle Command Center
-- ============================================================================
-- Runs against the PostgreSQL star schema (database/schema.sql).
-- Each query is standalone. Business definitions match
-- database/data_dictionary.md and the API's CSV-mode logic.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- KPI 1 · Total billed amount
-- Gross charges submitted across all claims.
-- ----------------------------------------------------------------------------
SELECT SUM(billed_amount) AS total_billed_amount
FROM fact_claims;

-- ----------------------------------------------------------------------------
-- KPI 2 · Total paid amount
-- All payer payments received (net of nothing — patient responsibility is
-- tracked separately).
-- ----------------------------------------------------------------------------
SELECT SUM(paid_amount) AS total_paid_amount
FROM fact_claims;

-- ----------------------------------------------------------------------------
-- KPI 3 · Outstanding A/R
-- Unresolved balance on open claims: allowed − paid − patient responsibility.
-- ----------------------------------------------------------------------------
SELECT SUM(outstanding_amount) AS outstanding_ar
FROM fact_claims
WHERE is_open;

-- ----------------------------------------------------------------------------
-- KPI 4 · Revenue at risk
-- Money most likely to be lost without intervention: outstanding balances on
-- denied/appealed claims, plus open claims aged past 60 days.
-- ----------------------------------------------------------------------------
SELECT SUM(outstanding_amount) AS revenue_at_risk
FROM fact_claims
WHERE is_open
  AND (is_denied OR claim_age_days > 60);

-- ----------------------------------------------------------------------------
-- KPI 5 · Denial rate
-- Share of all claims that were denied at least once.
-- ----------------------------------------------------------------------------
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE is_denied) / COUNT(*), 2)
           AS denial_rate_pct
FROM fact_claims;

-- ----------------------------------------------------------------------------
-- KPI 6 · Clean claim rate
-- Claims that were paid without denial or partial-payment rework —
-- a proxy for first-pass yield.
-- ----------------------------------------------------------------------------
SELECT ROUND(
         100.0 * COUNT(*) FILTER (
             WHERE NOT is_denied
               AND claim_status IN ('Paid', 'Closed')
               AND is_paid
         ) / COUNT(*), 2) AS clean_claim_rate_pct
FROM fact_claims;

-- ----------------------------------------------------------------------------
-- KPI 7 · Average days to payment
-- Mean payment lag weighted per remittance.
-- ----------------------------------------------------------------------------
SELECT ROUND(AVG(days_to_payment), 1) AS avg_days_to_payment
FROM fact_payments;

-- ----------------------------------------------------------------------------
-- KPI 8 · A/R over 90 days
-- Outstanding balance sitting in the 90+ aging bucket right now
-- (age measured from submission date on currently open claims).
-- ----------------------------------------------------------------------------
SELECT SUM(outstanding_amount) AS ar_over_90_days
FROM fact_claims
WHERE is_open
  AND claim_age_days > 90;

-- ----------------------------------------------------------------------------
-- KPI 9 · Executive summary in one row
-- Convenient single-row snapshot for dashboards / API.
-- ----------------------------------------------------------------------------
SELECT
    COUNT(*)                                                        AS total_claims,
    SUM(billed_amount)                                              AS total_billed,
    SUM(paid_amount)                                                AS total_paid,
    SUM(outstanding_amount) FILTER (WHERE is_open)                  AS outstanding_ar,
    SUM(outstanding_amount) FILTER (WHERE is_open AND (is_denied OR claim_age_days > 60))
                                                                    AS revenue_at_risk,
    SUM(outstanding_amount) FILTER (WHERE is_open AND claim_age_days > 90)
                                                                    AS ar_over_90,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_denied) / COUNT(*), 2)  AS denial_rate_pct,
    ROUND(100.0 * COUNT(*) FILTER (
        WHERE NOT is_denied AND claim_status IN ('Paid','Closed') AND is_paid
    ) / COUNT(*), 2)                                                AS clean_claim_rate_pct
FROM fact_claims;

-- ----------------------------------------------------------------------------
-- KPI 10 · Monthly denial rate trend
-- Is the denial rate improving or getting worse? Grouped by submission month.
-- ----------------------------------------------------------------------------
SELECT
    d.year,
    d.month,
    d.month_name,
    COUNT(*)                                                        AS claims,
    COUNT(*) FILTER (WHERE c.is_denied)                             AS denied,
    ROUND(100.0 * COUNT(*) FILTER (WHERE c.is_denied) / COUNT(*), 2) AS denial_rate_pct
FROM fact_claims c
JOIN dim_date d ON d.date = c.claim_submission_date
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;

-- ----------------------------------------------------------------------------
-- KPI 11 · Monthly billed vs paid trend
-- ----------------------------------------------------------------------------
SELECT
    d.year,
    d.month,
    d.month_name,
    SUM(c.billed_amount) AS billed,
    SUM(c.paid_amount)   AS paid
FROM fact_claims c
JOIN dim_date d ON d.date = c.claim_submission_date
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;

-- ============================================================================
-- WORK QUEUE KPIs (fact_followup_tasks is produced by the automation engine)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- KPI 12 · Open follow-up tasks by priority
-- ----------------------------------------------------------------------------
SELECT priority, COUNT(*) AS open_tasks
FROM fact_followup_tasks
WHERE status IN ('Open', 'In Progress')
GROUP BY priority
ORDER BY CASE priority
    WHEN 'Urgent' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END;

-- ----------------------------------------------------------------------------
-- KPI 13 · Overdue follow-ups
-- Open tasks whose due date has passed.
-- ----------------------------------------------------------------------------
SELECT COUNT(*)             AS overdue_tasks,
       SUM(c.outstanding_amount) AS overdue_outstanding
FROM fact_followup_tasks t
JOIN fact_claims c ON c.claim_id = t.claim_id
WHERE t.status IN ('Open', 'In Progress')
  AND t.due_date < CURRENT_DATE;

-- ----------------------------------------------------------------------------
-- KPI 14 · High-priority claims needing action
-- ----------------------------------------------------------------------------
SELECT
    t.claim_id,
    t.task_type,
    t.priority,
    t.assigned_team,
    t.due_date,
    c.outstanding_amount
FROM fact_followup_tasks t
JOIN fact_claims c ON c.claim_id = t.claim_id
WHERE t.status IN ('Open', 'In Progress')
  AND t.priority IN ('High', 'Urgent')
ORDER BY t.priority DESC, c.outstanding_amount DESC;

-- ----------------------------------------------------------------------------
-- KPI 15 · Tasks completed and average time to close
-- ----------------------------------------------------------------------------
SELECT
    COUNT(*) FILTER (WHERE status = 'Completed')                 AS tasks_completed,
    ROUND(AVG(closed_date - created_date) FILTER (WHERE status = 'Completed'), 1)
                                                                 AS avg_days_to_close
FROM fact_followup_tasks;
