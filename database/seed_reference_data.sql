-- ============================================================================
-- seed_reference_data.sql — static reference dimensions
-- ============================================================================
-- Seeds the two dimensions whose contents are fixed business vocabulary:
-- denial reasons and service lines. All other tables are populated by the
-- ETL pipeline (etl/load_to_postgres.py), which loads the same values from
-- data/processed/ — the loader upserts, so running both is safe.
--
--   psql -U rcm_user -d revenue_cycle -f database/seed_reference_data.sql
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Denial reasons (synthetic CARC-style codes)
-- preventable_flag = true when a front-end process fix could avoid the denial
-- ---------------------------------------------------------------------------
INSERT INTO dim_denial_reason (denial_reason_id, denial_code, denial_category, denial_description, preventable_flag) VALUES
    (1, 'D-16',  'Missing documentation',        'Claim lacks required documentation or attachments',           TRUE),
    (2, 'D-27',  'Eligibility issue',            'Patient not eligible on date of service',                     TRUE),
    (3, 'D-197', 'Prior authorization required', 'Service performed without required prior authorization',      TRUE),
    (4, 'D-11',  'Coding issue',                 'Diagnosis or procedure coding inconsistent or invalid',       TRUE),
    (5, 'D-18',  'Duplicate claim',              'Exact duplicate of a previously submitted claim',             TRUE),
    (6, 'D-29',  'Timely filing',                'Claim submitted after the payer filing deadline',             TRUE),
    (7, 'D-50',  'Medical necessity',            'Service not deemed medically necessary by payer policy',      FALSE),
    (8, 'D-26',  'Coverage terminated',          'Patient coverage terminated before date of service',          FALSE)
ON CONFLICT (denial_reason_id) DO UPDATE SET
    denial_code        = EXCLUDED.denial_code,
    denial_category    = EXCLUDED.denial_category,
    denial_description = EXCLUDED.denial_description,
    preventable_flag   = EXCLUDED.preventable_flag;

-- ---------------------------------------------------------------------------
-- Service lines
-- ---------------------------------------------------------------------------
INSERT INTO dim_service_line (service_line_id, service_line_name) VALUES
    (1, 'Primary Care'),
    (2, 'Emergency'),
    (3, 'Cardiology'),
    (4, 'Orthopedics'),
    (5, 'Imaging'),
    (6, 'Laboratory'),
    (7, 'Behavioral Health')
ON CONFLICT (service_line_id) DO UPDATE SET
    service_line_name = EXCLUDED.service_line_name;
