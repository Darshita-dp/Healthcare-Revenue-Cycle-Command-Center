-- ============================================================================
-- Healthcare Revenue Cycle Command Center — PostgreSQL Star Schema
-- ============================================================================
-- Kimball-style star schema: 7 conformed dimensions, 5 fact tables.
-- Synthetic data only — no PHI. Compatible with PostgreSQL 13+.
--
-- Execute:  psql -U rcm_user -d revenue_cycle -f database/schema.sql
-- (Docker Compose runs this automatically on first container start.)
-- ============================================================================

-- Drop in dependency order so the script is rerunnable
DROP TABLE IF EXISTS fact_followup_tasks CASCADE;
DROP TABLE IF EXISTS fact_ar_snapshot CASCADE;
DROP TABLE IF EXISTS fact_payments CASCADE;
DROP TABLE IF EXISTS fact_denials CASCADE;
DROP TABLE IF EXISTS fact_claims CASCADE;
DROP TABLE IF EXISTS dim_provider CASCADE;
DROP TABLE IF EXISTS dim_patient CASCADE;
DROP TABLE IF EXISTS dim_facility CASCADE;
DROP TABLE IF EXISTS dim_payer CASCADE;
DROP TABLE IF EXISTS dim_denial_reason CASCADE;
DROP TABLE IF EXISTS dim_service_line CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;

-- ============================================================================
-- DIMENSIONS
-- ============================================================================

CREATE TABLE dim_date (
    date_id        INTEGER PRIMARY KEY,          -- surrogate key YYYYMMDD
    date           DATE NOT NULL UNIQUE,
    month          INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name     VARCHAR(12) NOT NULL,
    quarter        INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    year           INTEGER NOT NULL,
    week_of_year   INTEGER NOT NULL CHECK (week_of_year BETWEEN 1 AND 53)
);
COMMENT ON TABLE dim_date IS 'Calendar dimension covering the full claim activity window';

CREATE TABLE dim_facility (
    facility_id    INTEGER PRIMARY KEY,
    facility_name  VARCHAR(100) NOT NULL,
    facility_type  VARCHAR(50) NOT NULL,         -- Hospital / Clinic / ASC / Urgent Care
    region         VARCHAR(30) NOT NULL,
    state          CHAR(2) NOT NULL
);

CREATE TABLE dim_patient (
    patient_id            INTEGER PRIMARY KEY,
    synthetic_patient_key VARCHAR(20) NOT NULL UNIQUE,  -- e.g. PAT-000123, never a name
    gender                VARCHAR(10) NOT NULL,
    birth_year            INTEGER NOT NULL,
    age_group             VARCHAR(10) NOT NULL,          -- 0-17 / 18-34 / 35-49 / 50-64 / 65+
    city                  VARCHAR(60) NOT NULL,
    state                 CHAR(2) NOT NULL,
    insurance_type        VARCHAR(20) NOT NULL,          -- mirrors payer_type of primary payer
    risk_segment          VARCHAR(10) NOT NULL           -- Low / Medium / High
);
COMMENT ON TABLE dim_patient IS 'Synthetic patients — demographic segments only, no PHI';

CREATE TABLE dim_provider (
    provider_id    INTEGER PRIMARY KEY,
    provider_name  VARCHAR(100) NOT NULL,        -- synthetic "Dr. <Lastname>" style
    specialty      VARCHAR(50) NOT NULL,
    facility_id    INTEGER NOT NULL REFERENCES dim_facility(facility_id),
    city           VARCHAR(60) NOT NULL,
    state          CHAR(2) NOT NULL,
    npi_fake       VARCHAR(12) NOT NULL UNIQUE   -- clearly fake 'FAKE'-prefixed NPI
);

CREATE TABLE dim_payer (
    payer_id       INTEGER PRIMARY KEY,
    payer_name     VARCHAR(100) NOT NULL,
    payer_type     VARCHAR(20) NOT NULL,         -- Commercial / Medicare / Medicaid / Self-pay / Other
    contract_type  VARCHAR(30) NOT NULL,         -- In-Network / Out-of-Network / Government
    state          CHAR(2) NOT NULL,
    risk_category  VARCHAR(10) NOT NULL          -- Low / Medium / High (behavioral risk)
);

CREATE TABLE dim_denial_reason (
    denial_reason_id   INTEGER PRIMARY KEY,
    denial_code        VARCHAR(10) NOT NULL UNIQUE,   -- CARC-style synthetic code
    denial_category    VARCHAR(50) NOT NULL,
    denial_description VARCHAR(200) NOT NULL,
    preventable_flag   BOOLEAN NOT NULL               -- true if front-end process could prevent it
);

CREATE TABLE dim_service_line (
    service_line_id    INTEGER PRIMARY KEY,
    service_line_name  VARCHAR(50) NOT NULL UNIQUE
);

-- ============================================================================
-- FACTS
-- ============================================================================

CREATE TABLE fact_claims (
    claim_id                VARCHAR(20) PRIMARY KEY,      -- CLM-000001
    patient_id              INTEGER NOT NULL REFERENCES dim_patient(patient_id),
    provider_id             INTEGER NOT NULL REFERENCES dim_provider(provider_id),
    facility_id             INTEGER NOT NULL REFERENCES dim_facility(facility_id),
    payer_id                INTEGER NOT NULL REFERENCES dim_payer(payer_id),
    service_line_id         INTEGER NOT NULL REFERENCES dim_service_line(service_line_id),
    date_of_service         DATE NOT NULL,
    claim_submission_date   DATE NOT NULL,
    claim_status            VARCHAR(20) NOT NULL CHECK (claim_status IN
                              ('Submitted','Paid','Denied','Partially Paid',
                               'Under Review','Appealed','Closed')),
    billed_amount           NUMERIC(12,2) NOT NULL CHECK (billed_amount >= 0),
    allowed_amount          NUMERIC(12,2) NOT NULL CHECK (allowed_amount >= 0),
    paid_amount             NUMERIC(12,2) NOT NULL CHECK (paid_amount >= 0),
    patient_responsibility  NUMERIC(12,2) NOT NULL CHECK (patient_responsibility >= 0),
    outstanding_amount      NUMERIC(12,2) NOT NULL CHECK (outstanding_amount >= 0),
    claim_age_days          INTEGER NOT NULL CHECK (claim_age_days >= 0),
    is_denied               BOOLEAN NOT NULL,
    is_paid                 BOOLEAN NOT NULL,
    is_open                 BOOLEAN NOT NULL,
    is_high_value           BOOLEAN NOT NULL,             -- billed_amount above high-value threshold
    CHECK (claim_submission_date >= date_of_service)
);
COMMENT ON TABLE fact_claims IS 'One row per claim — grain: claim';

CREATE TABLE fact_denials (
    denial_id             VARCHAR(20) PRIMARY KEY,        -- DEN-000001
    claim_id              VARCHAR(20) NOT NULL REFERENCES fact_claims(claim_id),
    denial_reason_id      INTEGER NOT NULL REFERENCES dim_denial_reason(denial_reason_id),
    denial_date           DATE NOT NULL,
    denied_amount         NUMERIC(12,2) NOT NULL CHECK (denied_amount >= 0),
    appeal_status         VARCHAR(20) NOT NULL CHECK (appeal_status IN
                            ('Not Appealed','Appeal Submitted','Appeal Resolved')),
    appeal_submitted_date DATE,
    appeal_outcome        VARCHAR(20) CHECK (appeal_outcome IN
                            ('Overturned','Partially Overturned','Upheld')),
    recovered_amount      NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (recovered_amount >= 0),
    days_to_appeal        INTEGER CHECK (days_to_appeal >= 0)
);
COMMENT ON TABLE fact_denials IS 'One row per denial event — grain: denial (claims may have one denial in this model)';

CREATE TABLE fact_payments (
    payment_id      VARCHAR(20) PRIMARY KEY,              -- PMT-000001
    claim_id        VARCHAR(20) NOT NULL REFERENCES fact_claims(claim_id),
    payment_date    DATE NOT NULL,
    payer_id        INTEGER NOT NULL REFERENCES dim_payer(payer_id),
    paid_amount     NUMERIC(12,2) NOT NULL CHECK (paid_amount > 0),
    payment_method  VARCHAR(20) NOT NULL,                 -- EFT / Check / Card / Lockbox
    days_to_payment INTEGER NOT NULL CHECK (days_to_payment >= 0)
);
COMMENT ON TABLE fact_payments IS 'One row per remittance — grain: payment transaction';

CREATE TABLE fact_ar_snapshot (
    snapshot_id        VARCHAR(24) PRIMARY KEY,           -- SNP-000001
    claim_id           VARCHAR(20) NOT NULL REFERENCES fact_claims(claim_id),
    snapshot_date      DATE NOT NULL,
    outstanding_amount NUMERIC(12,2) NOT NULL CHECK (outstanding_amount >= 0),
    aging_bucket       VARCHAR(10) NOT NULL CHECK (aging_bucket IN
                         ('0-30','31-60','61-90','90+')),
    UNIQUE (claim_id, snapshot_date)
);
COMMENT ON TABLE fact_ar_snapshot IS 'Periodic A/R snapshots — grain: open claim per snapshot date';

CREATE TABLE fact_followup_tasks (
    task_id       VARCHAR(20) PRIMARY KEY,                -- TSK-000001
    claim_id      VARCHAR(20) NOT NULL REFERENCES fact_claims(claim_id),
    task_type     VARCHAR(60) NOT NULL,
    priority      VARCHAR(10) NOT NULL CHECK (priority IN ('Low','Medium','High','Urgent')),
    assigned_team VARCHAR(40) NOT NULL,
    created_date  DATE NOT NULL,
    due_date      DATE NOT NULL,
    status        VARCHAR(15) NOT NULL CHECK (status IN ('Open','In Progress','Completed','Cancelled')),
    closed_date   DATE,
    reason        VARCHAR(200) NOT NULL,
    UNIQUE (claim_id, task_type)                          -- idempotency: one task per rule per claim
);
COMMENT ON TABLE fact_followup_tasks IS 'Rule-engine output — grain: one task per claim per rule';

-- ============================================================================
-- INDEXES (FK columns + common filter/join paths)
-- ============================================================================

CREATE INDEX idx_claims_payer          ON fact_claims(payer_id);
CREATE INDEX idx_claims_facility       ON fact_claims(facility_id);
CREATE INDEX idx_claims_provider       ON fact_claims(provider_id);
CREATE INDEX idx_claims_patient        ON fact_claims(patient_id);
CREATE INDEX idx_claims_service_line   ON fact_claims(service_line_id);
CREATE INDEX idx_claims_status         ON fact_claims(claim_status);
CREATE INDEX idx_claims_submission     ON fact_claims(claim_submission_date);
CREATE INDEX idx_claims_open_outstanding ON fact_claims(is_open, outstanding_amount);

CREATE INDEX idx_denials_claim         ON fact_denials(claim_id);
CREATE INDEX idx_denials_reason        ON fact_denials(denial_reason_id);
CREATE INDEX idx_denials_date          ON fact_denials(denial_date);

CREATE INDEX idx_payments_claim        ON fact_payments(claim_id);
CREATE INDEX idx_payments_payer        ON fact_payments(payer_id);
CREATE INDEX idx_payments_date         ON fact_payments(payment_date);

CREATE INDEX idx_ar_claim              ON fact_ar_snapshot(claim_id);
CREATE INDEX idx_ar_snapshot_date      ON fact_ar_snapshot(snapshot_date);
CREATE INDEX idx_ar_bucket             ON fact_ar_snapshot(aging_bucket);

CREATE INDEX idx_tasks_claim           ON fact_followup_tasks(claim_id);
CREATE INDEX idx_tasks_status_priority ON fact_followup_tasks(status, priority);
CREATE INDEX idx_tasks_due             ON fact_followup_tasks(due_date);

CREATE INDEX idx_provider_facility     ON dim_provider(facility_id);
