-- ============================================================================
-- Payer Performance — Healthcare Revenue Cycle Command Center
-- ============================================================================
-- Payer scorecards: volume, payment behavior, denial behavior, outstanding
-- balances, and a composite risk ranking used for escalation decisions.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1 · Claims and dollars by payer
-- ----------------------------------------------------------------------------
SELECT
    p.payer_name,
    p.payer_type,
    p.contract_type,
    COUNT(*)              AS total_claims,
    SUM(c.billed_amount)  AS billed_amount,
    SUM(c.paid_amount)    AS paid_amount,
    ROUND(100.0 * SUM(c.paid_amount) / NULLIF(SUM(c.billed_amount), 0), 2)
                          AS paid_to_billed_pct
FROM fact_claims c
JOIN dim_payer p ON p.payer_id = c.payer_id
GROUP BY p.payer_name, p.payer_type, p.contract_type
ORDER BY billed_amount DESC;

-- ----------------------------------------------------------------------------
-- 2 · Payment speed by payer
-- Median is more robust than mean for lag distributions.
-- ----------------------------------------------------------------------------
SELECT
    p.payer_name,
    COUNT(*)                                              AS payments,
    ROUND(AVG(pm.days_to_payment), 1)                     AS avg_days_to_payment,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pm.days_to_payment)
                                                          AS median_days_to_payment,
    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY pm.days_to_payment)
                                                          AS p90_days_to_payment
FROM fact_payments pm
JOIN dim_payer p ON p.payer_id = pm.payer_id
GROUP BY p.payer_name
ORDER BY avg_days_to_payment DESC;

-- ----------------------------------------------------------------------------
-- 3 · Denial behavior by payer
-- ----------------------------------------------------------------------------
SELECT
    p.payer_name,
    COUNT(*)                                                         AS total_claims,
    COUNT(*) FILTER (WHERE c.is_denied)                              AS denied_claims,
    ROUND(100.0 * COUNT(*) FILTER (WHERE c.is_denied) / COUNT(*), 2) AS denial_rate_pct,
    SUM(d.denied_amount)                                             AS denied_amount,
    SUM(d.recovered_amount)                                          AS recovered_amount
FROM fact_claims c
JOIN dim_payer p ON p.payer_id = c.payer_id
LEFT JOIN fact_denials d ON d.claim_id = c.claim_id
GROUP BY p.payer_name
ORDER BY denial_rate_pct DESC;

-- ----------------------------------------------------------------------------
-- 4 · Outstanding A/R by payer
-- ----------------------------------------------------------------------------
SELECT
    p.payer_name,
    COUNT(*) FILTER (WHERE c.is_open)                       AS open_claims,
    SUM(c.outstanding_amount) FILTER (WHERE c.is_open)      AS outstanding_ar,
    SUM(c.outstanding_amount) FILTER (WHERE c.is_open AND c.claim_age_days > 90)
                                                            AS ar_over_90
FROM fact_claims c
JOIN dim_payer p ON p.payer_id = c.payer_id
GROUP BY p.payer_name
ORDER BY outstanding_ar DESC NULLS LAST;

-- ----------------------------------------------------------------------------
-- 5 · Payer risk ranking (composite score)
-- Normalizes three behaviors to 0–1 and weights them:
--   50% denial rate, 30% payment speed, 20% share of A/R stuck past 90 days.
-- Score near 1 = escalate; near 0 = healthy relationship.
-- ----------------------------------------------------------------------------
WITH payer_stats AS (
    SELECT
        p.payer_id,
        p.payer_name,
        p.risk_category,
        1.0 * COUNT(*) FILTER (WHERE c.is_denied) / COUNT(*)             AS denial_rate,
        COALESCE(AVG(pm.days_to_payment), 60)                            AS avg_lag,
        COALESCE(
            SUM(c.outstanding_amount) FILTER (WHERE c.is_open AND c.claim_age_days > 90)
            / NULLIF(SUM(c.outstanding_amount) FILTER (WHERE c.is_open), 0), 0)
                                                                         AS pct_ar_over_90
    FROM fact_claims c
    JOIN dim_payer p ON p.payer_id = c.payer_id
    LEFT JOIN fact_payments pm ON pm.payer_id = p.payer_id
    GROUP BY p.payer_id, p.payer_name, p.risk_category
),
normalized AS (
    SELECT *,
        denial_rate    / NULLIF(MAX(denial_rate)    OVER (), 0) AS denial_norm,
        avg_lag        / NULLIF(MAX(avg_lag)        OVER (), 0) AS lag_norm,
        pct_ar_over_90 / NULLIF(MAX(pct_ar_over_90) OVER (), 0) AS aging_norm
    FROM payer_stats
)
SELECT
    payer_name,
    risk_category,
    ROUND(100.0 * denial_rate, 2)                              AS denial_rate_pct,
    ROUND(avg_lag, 1)                                          AS avg_days_to_payment,
    ROUND(100.0 * pct_ar_over_90, 2)                           AS pct_ar_over_90,
    ROUND(0.5 * denial_norm + 0.3 * lag_norm + 0.2 * aging_norm, 3) AS risk_score,
    RANK() OVER (ORDER BY 0.5 * denial_norm + 0.3 * lag_norm + 0.2 * aging_norm DESC)
                                                               AS risk_rank
FROM normalized
ORDER BY risk_rank;

-- ----------------------------------------------------------------------------
-- 6 · Payers breaching the 20% denial-rate escalation threshold
-- Feed for automation Rule 4.
-- ----------------------------------------------------------------------------
SELECT
    p.payer_name,
    ROUND(100.0 * COUNT(*) FILTER (WHERE c.is_denied) / COUNT(*), 2) AS denial_rate_pct
FROM fact_claims c
JOIN dim_payer p ON p.payer_id = c.payer_id
GROUP BY p.payer_name
HAVING 100.0 * COUNT(*) FILTER (WHERE c.is_denied) / COUNT(*) > 20
ORDER BY denial_rate_pct DESC;

-- ----------------------------------------------------------------------------
-- 7 · Top denial reasons per payer (top 3 each, window-ranked)
-- ----------------------------------------------------------------------------
SELECT payer_name, denial_category, denials, denied_amount
FROM (
    SELECT
        p.payer_name,
        r.denial_category,
        COUNT(*)             AS denials,
        SUM(d.denied_amount) AS denied_amount,
        ROW_NUMBER() OVER (PARTITION BY p.payer_name ORDER BY COUNT(*) DESC) AS rn
    FROM fact_denials d
    JOIN fact_claims c       ON c.claim_id = d.claim_id
    JOIN dim_payer p         ON p.payer_id = c.payer_id
    JOIN dim_denial_reason r ON r.denial_reason_id = d.denial_reason_id
    GROUP BY p.payer_name, r.denial_category
) ranked
WHERE rn <= 3
ORDER BY payer_name, denials DESC;
