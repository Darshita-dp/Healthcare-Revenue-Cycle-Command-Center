-- ============================================================================
-- Denial Analysis — Healthcare Revenue Cycle Command Center
-- ============================================================================
-- Which claims get denied, why, by whom, and how much comes back on appeal.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1 · Top denial reasons by volume and dollars
-- The classic denials pareto: a few categories usually drive most of the loss.
-- ----------------------------------------------------------------------------
SELECT
    r.denial_category,
    r.denial_code,
    COUNT(*)                    AS denial_count,
    SUM(f.denied_amount)        AS denied_amount,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_denials
FROM fact_denials f
JOIN dim_denial_reason r ON r.denial_reason_id = f.denial_reason_id
GROUP BY r.denial_category, r.denial_code
ORDER BY denial_count DESC;

-- ----------------------------------------------------------------------------
-- 2 · Denial rate by payer
-- Which payers deny the most claims — the escalation shortlist.
-- ----------------------------------------------------------------------------
SELECT
    p.payer_name,
    p.payer_type,
    COUNT(*)                                                        AS total_claims,
    COUNT(*) FILTER (WHERE c.is_denied)                             AS denied_claims,
    ROUND(100.0 * COUNT(*) FILTER (WHERE c.is_denied) / COUNT(*), 2) AS denial_rate_pct
FROM fact_claims c
JOIN dim_payer p ON p.payer_id = c.payer_id
GROUP BY p.payer_name, p.payer_type
ORDER BY denial_rate_pct DESC;

-- ----------------------------------------------------------------------------
-- 3 · Denial rate by facility
-- Facility-level process quality comparison.
-- ----------------------------------------------------------------------------
SELECT
    f.facility_name,
    f.facility_type,
    f.region,
    COUNT(*)                                                        AS total_claims,
    COUNT(*) FILTER (WHERE c.is_denied)                             AS denied_claims,
    ROUND(100.0 * COUNT(*) FILTER (WHERE c.is_denied) / COUNT(*), 2) AS denial_rate_pct
FROM fact_claims c
JOIN dim_facility f ON f.facility_id = c.facility_id
GROUP BY f.facility_name, f.facility_type, f.region
ORDER BY denial_rate_pct DESC;

-- ----------------------------------------------------------------------------
-- 4 · Denial rate by provider (top 15 highest, min 20 claims)
-- Minimum-volume filter avoids small-sample noise.
-- ----------------------------------------------------------------------------
SELECT
    pr.provider_name,
    pr.specialty,
    f.facility_name,
    COUNT(*)                                                        AS total_claims,
    ROUND(100.0 * COUNT(*) FILTER (WHERE c.is_denied) / COUNT(*), 2) AS denial_rate_pct
FROM fact_claims c
JOIN dim_provider pr ON pr.provider_id = c.provider_id
JOIN dim_facility f  ON f.facility_id = pr.facility_id
GROUP BY pr.provider_name, pr.specialty, f.facility_name
HAVING COUNT(*) >= 20
ORDER BY denial_rate_pct DESC
LIMIT 15;

-- ----------------------------------------------------------------------------
-- 5 · Denied amount by category
-- ----------------------------------------------------------------------------
SELECT
    r.denial_category,
    SUM(f.denied_amount)     AS denied_amount,
    SUM(f.recovered_amount)  AS recovered_amount,
    SUM(f.denied_amount) - SUM(f.recovered_amount) AS net_at_risk
FROM fact_denials f
JOIN dim_denial_reason r ON r.denial_reason_id = f.denial_reason_id
GROUP BY r.denial_category
ORDER BY denied_amount DESC;

-- ----------------------------------------------------------------------------
-- 6 · Preventable denial rate
-- Share of denials a front-end process fix could have avoided —
-- the strongest argument for upstream investment.
-- ----------------------------------------------------------------------------
SELECT
    ROUND(100.0 * COUNT(*) FILTER (WHERE r.preventable_flag) / COUNT(*), 2)
        AS preventable_denial_rate_pct,
    SUM(f.denied_amount) FILTER (WHERE r.preventable_flag)
        AS preventable_denied_amount
FROM fact_denials f
JOIN dim_denial_reason r ON r.denial_reason_id = f.denial_reason_id;

-- ----------------------------------------------------------------------------
-- 7 · Appeal funnel and success rate
-- Success = resolved appeals that were fully or partially overturned.
-- ----------------------------------------------------------------------------
SELECT
    COUNT(*)                                                       AS total_denials,
    COUNT(*) FILTER (WHERE appeal_status <> 'Not Appealed')        AS appeals_submitted,
    COUNT(*) FILTER (WHERE appeal_status = 'Appeal Resolved')      AS appeals_resolved,
    COUNT(*) FILTER (WHERE appeal_outcome IN ('Overturned','Partially Overturned'))
                                                                   AS appeals_won,
    ROUND(100.0 * COUNT(*) FILTER (WHERE appeal_outcome IN ('Overturned','Partially Overturned'))
        / NULLIF(COUNT(*) FILTER (WHERE appeal_status = 'Appeal Resolved'), 0), 2)
                                                                   AS appeal_success_rate_pct
FROM fact_denials;

-- ----------------------------------------------------------------------------
-- 8 · Recovered amount after appeal (total and by payer)
-- "How much money did follow-up actually bring back?"
-- ----------------------------------------------------------------------------
SELECT SUM(recovered_amount) AS total_recovered
FROM fact_denials;

SELECT
    p.payer_name,
    SUM(d.denied_amount)    AS denied_amount,
    SUM(d.recovered_amount) AS recovered_amount,
    ROUND(100.0 * SUM(d.recovered_amount) / NULLIF(SUM(d.denied_amount), 0), 2)
        AS recovery_rate_pct
FROM fact_denials d
JOIN fact_claims c ON c.claim_id = d.claim_id
JOIN dim_payer p   ON p.payer_id = c.payer_id
GROUP BY p.payer_name
ORDER BY recovered_amount DESC;

-- ----------------------------------------------------------------------------
-- 9 · Monthly denial trend by category
-- Detects emerging denial patterns (e.g., a payer tightening auth rules).
-- ----------------------------------------------------------------------------
SELECT
    dd.year,
    dd.month,
    r.denial_category,
    COUNT(*)             AS denials,
    SUM(f.denied_amount) AS denied_amount
FROM fact_denials f
JOIN dim_date dd          ON dd.date = f.denial_date
JOIN dim_denial_reason r  ON r.denial_reason_id = f.denial_reason_id
GROUP BY dd.year, dd.month, r.denial_category
ORDER BY dd.year, dd.month, denied_amount DESC;

-- ----------------------------------------------------------------------------
-- 10 · Unappealed denials approaching the appeal deadline
-- Feed for the automation engine's Rule 5 (deadline typically 30–90 days;
-- we flag anything unappealed after 20 days).
-- ----------------------------------------------------------------------------
SELECT
    d.denial_id,
    d.claim_id,
    p.payer_name,
    r.denial_category,
    d.denied_amount,
    d.denial_date,
    CURRENT_DATE - d.denial_date AS days_since_denial
FROM fact_denials d
JOIN fact_claims c        ON c.claim_id = d.claim_id
JOIN dim_payer p          ON p.payer_id = c.payer_id
JOIN dim_denial_reason r  ON r.denial_reason_id = d.denial_reason_id
WHERE d.appeal_status = 'Not Appealed'
  AND CURRENT_DATE - d.denial_date > 20
ORDER BY d.denied_amount DESC;
