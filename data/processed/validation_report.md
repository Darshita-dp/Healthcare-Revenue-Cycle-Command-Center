# Data Validation Report

- Generated against: `data/processed/` (as-of date 2026-06-30)
- Result: **PASS** (46 passed, 0 failed)

## Failed checks

_None._

## Passed checks

- ✅ Row count dim_patient — 1,200 rows (min 1,000)
- ✅ Row count dim_provider — 110 rows (min 100)
- ✅ Row count dim_facility — 8 rows (min 8)
- ✅ Row count dim_payer — 9 rows (min 8)
- ✅ Row count dim_denial_reason — 8 rows (min 8)
- ✅ Row count dim_service_line — 7 rows (min 7)
- ✅ Row count dim_date — 546 rows (min 300)
- ✅ Row count fact_claims — 6,000 rows (min 5,000)
- ✅ Row count fact_denials — 845 rows (min 300)
- ✅ Row count fact_payments — 5,218 rows (min 3,000)
- ✅ Row count fact_ar_snapshot — 5,732 rows (min 1,000)
- ✅ No null keys in dim_patient — 0 nulls
- ✅ No null keys in dim_provider — 0 nulls
- ✅ No null keys in dim_payer — 0 nulls
- ✅ No null keys in fact_claims — 0 nulls
- ✅ No null keys in fact_denials — 0 nulls
- ✅ No null keys in fact_payments — 0 nulls
- ✅ No null keys in fact_ar_snapshot — 0 nulls
- ✅ No negative amounts in fact_claims — 0 negative values
- ✅ No negative amounts in fact_denials — 0 negative values
- ✅ No negative amounts in fact_payments — 0 negative values
- ✅ No negative amounts in fact_ar_snapshot — 0 negative values
- ✅ FK fact_claims.patient_id -> dim_patient.patient_id — 0 orphans
- ✅ FK fact_claims.provider_id -> dim_provider.provider_id — 0 orphans
- ✅ FK fact_claims.facility_id -> dim_facility.facility_id — 0 orphans
- ✅ FK fact_claims.payer_id -> dim_payer.payer_id — 0 orphans
- ✅ FK fact_claims.service_line_id -> dim_service_line.service_line_id — 0 orphans
- ✅ FK fact_denials.claim_id -> fact_claims.claim_id — 0 orphans
- ✅ FK fact_denials.denial_reason_id -> dim_denial_reason.denial_reason_id — 0 orphans
- ✅ FK fact_payments.claim_id -> fact_claims.claim_id — 0 orphans
- ✅ FK fact_payments.payer_id -> dim_payer.payer_id — 0 orphans
- ✅ FK fact_ar_snapshot.claim_id -> fact_claims.claim_id — 0 orphans
- ✅ FK dim_provider.facility_id -> dim_facility.facility_id — 0 orphans
- ✅ FK fact_followup_tasks.claim_id -> fact_claims.claim_id — 0 orphans
- ✅ Claim statuses within vocabulary — all valid
- ✅ Denial rows only for denied claims — 0 extras
- ✅ Every denied claim has a denial row — 0 missing
- ✅ Appealed claims have denial records
- ✅ All payment amounts > 0
- ✅ Payments reconcile to claim paid_amount — max diff $0.00
- ✅ Payment records only where claim paid_amount > 0 — 0 violations
- ✅ A/R aging buckets match day math — 0 mismatches
- ✅ Aging bucket vocabulary valid
- ✅ All four aging buckets represented
- ✅ Submission date >= date of service
- ✅ No activity dated after AS_OF_DATE