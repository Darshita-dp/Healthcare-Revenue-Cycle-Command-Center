-- ============================================================================
-- A/R Aging Analysis — Healthcare Revenue Cycle Command Center
-- ============================================================================
-- Where is the outstanding money, how old is it, and who owes it.
-- Current-state queries use fact_claims.claim_age_days; historical trend
-- queries use fact_ar_snapshot (month-end snapshots).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1 · Current A/R by aging bucket
-- The canonical aging waterfall: 0-30 / 31-60 / 61-90 / 90+.
-- ----------------------------------------------------------------------------
SELECT
    CASE
        WHEN claim_age_days <= 30 THEN '0-30'
        WHEN claim_age_days <= 60 THEN '31-60'
        WHEN claim_age_days <= 90 THEN '61-90'
        ELSE '90+'
    END                         AS aging_bucket,
    COUNT(*)                    AS open_claims,
    SUM(outstanding_amount)     AS outstanding_amount,
    ROUND(100.0 * SUM(outstanding_amount)
        / SUM(SUM(outstanding_amount)) OVER (), 2) AS pct_of_ar
FROM fact_claims
WHERE is_open AND outstanding_amount > 0
GROUP BY 1
ORDER BY MIN(claim_age_days);

-- ----------------------------------------------------------------------------
-- 2 · Outstanding A/R by payer and bucket (pivot-ready)
-- ----------------------------------------------------------------------------
SELECT
    p.payer_name,
    SUM(c.outstanding_amount) FILTER (WHERE c.claim_age_days <= 30)  AS bucket_0_30,
    SUM(c.outstanding_amount) FILTER (WHERE c.claim_age_days BETWEEN 31 AND 60) AS bucket_31_60,
    SUM(c.outstanding_amount) FILTER (WHERE c.claim_age_days BETWEEN 61 AND 90) AS bucket_61_90,
    SUM(c.outstanding_amount) FILTER (WHERE c.claim_age_days > 90)   AS bucket_90_plus,
    SUM(c.outstanding_amount)                                        AS total_outstanding
FROM fact_claims c
JOIN dim_payer p ON p.payer_id = c.payer_id
WHERE c.is_open AND c.outstanding_amount > 0
GROUP BY p.payer_name
ORDER BY total_outstanding DESC;

-- ----------------------------------------------------------------------------
-- 3 · Claims aging beyond 30 / 60 / 90 days (detail list)
-- Sorted so the most severe (oldest, largest) claims surface first.
-- ----------------------------------------------------------------------------
SELECT
    c.claim_id,
    p.payer_name,
    f.facility_name,
    c.claim_status,
    c.claim_age_days,
    c.outstanding_amount
FROM fact_claims c
JOIN dim_payer p    ON p.payer_id = c.payer_id
JOIN dim_facility f ON f.facility_id = c.facility_id
WHERE c.is_open
  AND c.outstanding_amount > 0
  AND c.claim_age_days > 30
ORDER BY c.claim_age_days DESC, c.outstanding_amount DESC;

-- ----------------------------------------------------------------------------
-- 4 · High-value claims over 90 days
-- The "walk into the CFO's office" list.
-- ----------------------------------------------------------------------------
SELECT
    c.claim_id,
    p.payer_name,
    f.facility_name,
    s.service_line_name,
    c.claim_status,
    c.claim_age_days,
    c.outstanding_amount
FROM fact_claims c
JOIN dim_payer p        ON p.payer_id = c.payer_id
JOIN dim_facility f     ON f.facility_id = c.facility_id
JOIN dim_service_line s ON s.service_line_id = c.service_line_id
WHERE c.is_open
  AND c.claim_age_days > 90
  AND c.outstanding_amount > 5000
ORDER BY c.outstanding_amount DESC
LIMIT 25;

-- ----------------------------------------------------------------------------
-- 5 · Facility-level aging comparison
-- Percent of each facility's A/R stuck past 90 days.
-- ----------------------------------------------------------------------------
SELECT
    f.facility_name,
    f.region,
    SUM(c.outstanding_amount)                                        AS total_ar,
    SUM(c.outstanding_amount) FILTER (WHERE c.claim_age_days > 90)   AS ar_over_90,
    ROUND(100.0 * SUM(c.outstanding_amount) FILTER (WHERE c.claim_age_days > 90)
        / NULLIF(SUM(c.outstanding_amount), 0), 2)                   AS pct_over_90
FROM fact_claims c
JOIN dim_facility f ON f.facility_id = c.facility_id
WHERE c.is_open AND c.outstanding_amount > 0
GROUP BY f.facility_name, f.region
ORDER BY pct_over_90 DESC;

-- ----------------------------------------------------------------------------
-- 6 · A/R trend from month-end snapshots
-- Is aging A/R growing? Uses fact_ar_snapshot for historical truth.
-- ----------------------------------------------------------------------------
SELECT
    s.snapshot_date,
    s.aging_bucket,
    COUNT(*)                  AS open_claims,
    SUM(s.outstanding_amount) AS outstanding_amount
FROM fact_ar_snapshot s
GROUP BY s.snapshot_date, s.aging_bucket
ORDER BY s.snapshot_date, s.aging_bucket;

-- ----------------------------------------------------------------------------
-- 7 · 90+ bucket share over time
-- Single-line health metric: the share of A/R older than 90 days.
-- ----------------------------------------------------------------------------
SELECT
    snapshot_date,
    ROUND(100.0 * SUM(outstanding_amount) FILTER (WHERE aging_bucket = '90+')
        / NULLIF(SUM(outstanding_amount), 0), 2) AS pct_ar_over_90
FROM fact_ar_snapshot
GROUP BY snapshot_date
ORDER BY snapshot_date;
