// API response types — mirror api/models/schemas.py

export interface Health {
  status: string;
  mode: string;
  tables_loaded: number;
}

export interface MonthlyDenialPoint {
  year: number;
  month: number;
  label: string;
  claims: number;
  denied: number;
  denial_rate_pct: number;
}

export interface MonthlyBilledPaid {
  year: number;
  month: number;
  label: string;
  billed: number;
  paid: number;
}

export interface Kpis {
  total_claims: number;
  total_billed: number;
  total_paid: number;
  outstanding_ar: number;
  revenue_at_risk: number;
  ar_over_90: number;
  denial_rate_pct: number;
  clean_claim_rate_pct: number;
  avg_days_to_payment: number;
  open_tasks: number;
  overdue_tasks: number;
  preventable_denial_rate_pct: number;
  appeal_success_rate_pct: number;
  total_recovered: number;
  denial_trend: MonthlyDenialPoint[];
  monthly_billed_paid: MonthlyBilledPaid[];
}

export interface ClaimSummary {
  claim_id: string;
  payer_name: string;
  payer_type: string;
  facility_name: string;
  provider_name: string;
  service_line_name: string;
  claim_status: string;
  billed_amount: number;
  outstanding_amount: number;
  claim_age_days: number;
  aging_bucket: string;
  is_denied: boolean;
  is_high_value: boolean;
  denial_category: string | null;
  action_needed: string | null;
  task_priority: string | null;
  priority_score: number;
  priority_tier: string;
  priority_top_driver: string | null;
  date_of_service: string;
  claim_submission_date: string;
}

export interface PriorityDriver {
  label: string;
  points: number;
  category: string;
}

export interface ClaimList {
  total: number;
  limit: number;
  offset: number;
  items: ClaimSummary[];
}

export interface ClaimFilters {
  payers: string[];
  statuses: string[];
  aging_buckets: string[];
  denial_reasons: string[];
  priorities: string[];
  tiers: string[];
  facilities: string[];
}

export interface PaymentRecord {
  payment_id: string;
  payment_date: string;
  paid_amount: number;
  payment_method: string;
  days_to_payment: number;
}

export interface TaskRecord {
  task_id: string;
  claim_id: string;
  task_type: string;
  priority: string;
  assigned_team: string;
  created_date: string;
  due_date: string;
  status: string;
  closed_date: string | null;
  reason: string;
  is_overdue: boolean;
  outstanding_amount: number | null;
  payer_name: string | null;
}

export interface TaskList {
  total: number;
  limit: number;
  offset: number;
  summary: {
    open: number;
    in_progress: number;
    completed: number;
    overdue: number;
    avg_days_to_close: number | null;
  };
  items: TaskRecord[];
}

export interface DenialDetail {
  denial_id: string;
  denial_date: string;
  denial_code: string | null;
  denial_category: string | null;
  denial_description: string | null;
  preventable: boolean | null;
  denied_amount: number;
  appeal_status: string;
  appeal_submitted_date: string | null;
  appeal_outcome: string | null;
  recovered_amount: number;
  days_to_appeal: number | null;
}

export interface PatientSegment {
  synthetic_patient_key: string;
  gender: string;
  age_group: string;
  state: string;
  insurance_type: string;
  risk_segment: string;
}

export interface ClaimDetail {
  claim: ClaimSummary;
  allowed_amount: number;
  paid_amount: number;
  patient_responsibility: number;
  patient_segment: PatientSegment;
  denial: DenialDetail | null;
  payments: PaymentRecord[];
  tasks: TaskRecord[];
  recommended_action: string;
  priority_score: number;
  priority_tier: string;
  priority_summary: string;
  priority_drivers: PriorityDriver[];
}

export interface TopDenialReason {
  denial_category: string;
  denials: number;
  denied_amount: number;
}

export interface PayerScorecard {
  payer_id: number;
  payer_name: string;
  payer_type: string;
  contract_type: string;
  risk_category: string;
  total_claims: number;
  denied_claims: number;
  denial_rate_pct: number;
  avg_days_to_payment: number | null;
  billed_amount: number;
  paid_amount: number;
  outstanding_ar: number;
  ar_over_90: number;
  denied_amount: number;
  recovered_amount: number;
  risk_score: number;
  risk_rank: number;
  top_denial_reasons: TopDenialReason[];
}

export interface AgingBucketRow {
  aging_bucket: string;
  open_claims: number;
  outstanding_amount: number;
  pct_of_ar: number;
}

export interface AgingByPayer {
  payer_name: string;
  "0-30": number;
  "31-60": number;
  "61-90": number;
  "90+": number;
  total: number;
}

export interface Aging {
  as_of: string;
  buckets: AgingBucketRow[];
  by_payer: AgingByPayer[];
  trend: { snapshot: string; aging_bucket: string; outstanding_amount: number }[];
}

export interface Alert {
  alert_id: string;
  alert_date: string;
  alert_type: string;
  payer_name: string;
  payer_type: string;
  total_claims: number;
  denied_claims: number;
  denial_rate_pct: number;
  threshold_pct: number;
  denied_outstanding_amount: number;
  recommended_action: string;
}

export interface TierCount {
  tier: string;
  count: number;
  outstanding_amount: number;
}

export interface DriverCount {
  category: string;
  label: string;
  claims: number;
}

export interface PriorityInsights {
  scored_open_claims: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  monitor_count: number;
  critical_high_outstanding: number;
  average_priority_score: number;
  tier_breakdown: TierCount[];
  top_drivers: DriverCount[];
}

export interface SelectedClaimPreview {
  claim_id: string;
  payer_name: string;
  facility_name: string;
  claim_status: string;
  outstanding_amount: number;
  denied_amount: number;
  priority_score: number;
  priority_tier: string;
  top_driver: string | null;
}

export interface RecoverySimulator {
  claim_count: number;
  recovery_rate: number;
  selected_claim_count: number;
  total_billed_amount: number;
  total_outstanding_amount: number;
  total_denied_amount: number;
  potential_recovery_base: number;
  estimated_recoverable_revenue: number;
  average_priority_score: number;
  priority_tier_breakdown: TierCount[];
  top_driver_breakdown: DriverCount[];
  interpretation: string;
  selected_claims_preview: SelectedClaimPreview[];
}
