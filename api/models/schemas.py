"""Pydantic response models — documented shapes for the Swagger UI."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    mode: str = Field(description="Data source: 'csv' or 'postgres'")
    tables_loaded: int


class KpiResponse(BaseModel):
    total_claims: int
    total_billed: float
    total_paid: float
    outstanding_ar: float
    revenue_at_risk: float
    ar_over_90: float
    denial_rate_pct: float
    clean_claim_rate_pct: float
    avg_days_to_payment: float
    open_tasks: int
    overdue_tasks: int
    preventable_denial_rate_pct: float
    appeal_success_rate_pct: float
    total_recovered: float
    denial_trend: list["MonthlyDenialPoint"]
    monthly_billed_paid: list["MonthlyBilledPaid"]


class MonthlyDenialPoint(BaseModel):
    year: int
    month: int
    label: str
    claims: int
    denied: int
    denial_rate_pct: float


class MonthlyBilledPaid(BaseModel):
    year: int
    month: int
    label: str
    billed: float
    paid: float


class ClaimSummary(BaseModel):
    claim_id: str
    payer_name: str
    payer_type: str
    facility_name: str
    provider_name: str
    service_line_name: str
    claim_status: str
    billed_amount: float
    outstanding_amount: float
    claim_age_days: int
    aging_bucket: str
    is_denied: bool
    is_high_value: bool
    denial_category: Optional[str] = None
    action_needed: Optional[str] = None
    task_priority: Optional[str] = None
    date_of_service: date
    claim_submission_date: date


class ClaimListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ClaimSummary]


class PaymentRecord(BaseModel):
    payment_id: str
    payment_date: date
    paid_amount: float
    payment_method: str
    days_to_payment: int


class TaskRecord(BaseModel):
    task_id: str
    claim_id: str
    task_type: str
    priority: str
    assigned_team: str
    created_date: date
    due_date: date
    status: str
    closed_date: Optional[date] = None
    reason: str
    is_overdue: bool
    outstanding_amount: Optional[float] = None
    payer_name: Optional[str] = None


class DenialDetail(BaseModel):
    denial_id: str
    denial_date: date
    denial_code: Optional[str] = None
    denial_category: Optional[str] = None
    denial_description: Optional[str] = None
    preventable: Optional[bool] = None
    denied_amount: float
    appeal_status: str
    appeal_submitted_date: Optional[date] = None
    appeal_outcome: Optional[str] = None
    recovered_amount: float
    days_to_appeal: Optional[int] = None


class ClaimDetail(BaseModel):
    claim: ClaimSummary
    allowed_amount: float
    paid_amount: float
    patient_responsibility: float
    patient_segment: dict
    denial: Optional[DenialDetail] = None
    payments: list[PaymentRecord]
    tasks: list[TaskRecord]
    recommended_action: str


class PayerScorecard(BaseModel):
    payer_id: int
    payer_name: str
    payer_type: str
    contract_type: str
    risk_category: str
    total_claims: int
    denied_claims: int
    denial_rate_pct: float
    avg_days_to_payment: Optional[float] = None
    billed_amount: float
    paid_amount: float
    outstanding_ar: float
    ar_over_90: float
    denied_amount: float
    recovered_amount: float
    risk_score: float
    risk_rank: int
    top_denial_reasons: list[dict]


class AgingBucketRow(BaseModel):
    aging_bucket: str
    open_claims: int
    outstanding_amount: float
    pct_of_ar: float


class AgingResponse(BaseModel):
    as_of: str
    buckets: list[AgingBucketRow]
    by_payer: list[dict]
    trend: list[dict]


class Alert(BaseModel):
    alert_id: str
    alert_date: str
    alert_type: str
    payer_name: str
    payer_type: str
    total_claims: int
    denied_claims: int
    denial_rate_pct: float
    threshold_pct: float
    denied_outstanding_amount: float
    recommended_action: str
