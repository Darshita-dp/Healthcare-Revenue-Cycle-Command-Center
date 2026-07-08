import { Link, useParams } from "react-router-dom";
import { api, fmtDate, fmtMoneyFull } from "../api/client";
import {
  AgingBadge, ErrorState, Field, Loading, PriorityBadge, SectionCard, StatusBadge,
  TaskStatusBadge, useFetch,
} from "../components/ui";
import { IconArrowRight, IconTarget } from "../components/Icons";
import type { ClaimDetail as ClaimDetailType } from "../api/types";

type DotTone = "blue" | "green" | "red" | "amber" | "purple" | "gray";

interface TimelineEvent {
  date: string;
  title: string;
  desc: string;
  tone: DotTone;
}

function buildTimeline(d: ClaimDetailType): TimelineEvent[] {
  const events: TimelineEvent[] = [
    {
      date: d.claim.date_of_service,
      title: "Service rendered",
      desc: `${d.claim.service_line_name} — ${d.claim.provider_name} at ${d.claim.facility_name}`,
      tone: "gray",
    },
    {
      date: d.claim.claim_submission_date,
      title: "Claim submitted",
      desc: `Billed ${fmtMoneyFull(d.claim.billed_amount)} to ${d.claim.payer_name}`,
      tone: "blue",
    },
  ];
  if (d.denial) {
    events.push({
      date: d.denial.denial_date,
      title: `Denied — ${d.denial.denial_category}`,
      desc: `${d.denial.denial_code}: ${d.denial.denial_description} (${fmtMoneyFull(d.denial.denied_amount)})`,
      tone: "red",
    });
    if (d.denial.appeal_submitted_date) {
      events.push({
        date: d.denial.appeal_submitted_date,
        title: "Appeal submitted",
        desc: `${d.denial.days_to_appeal} days after denial`,
        tone: "purple",
      });
    }
    if (d.denial.appeal_outcome) {
      events.push({
        date: d.denial.appeal_submitted_date ?? d.denial.denial_date,
        title: `Appeal resolved — ${d.denial.appeal_outcome}`,
        desc:
          d.denial.recovered_amount > 0
            ? `Recovered ${fmtMoneyFull(d.denial.recovered_amount)}`
            : "No recovery",
        tone: d.denial.recovered_amount > 0 ? "green" : "amber",
      });
    }
  }
  for (const p of d.payments) {
    events.push({
      date: p.payment_date,
      title: `Payment received — ${fmtMoneyFull(p.paid_amount)}`,
      desc: `${p.payment_method}, ${p.days_to_payment} days after submission`,
      tone: "green",
    });
  }
  for (const t of d.tasks) {
    events.push({
      date: t.created_date,
      title: `Task created — ${t.task_type}`,
      desc: `${t.priority} priority · ${t.assigned_team}`,
      tone: t.priority === "Urgent" ? "red" : "amber",
    });
  }
  return events.sort((a, b) => a.date.localeCompare(b.date));
}

export default function ClaimDetail() {
  const { claimId } = useParams<{ claimId: string }>();
  const detail = useFetch<ClaimDetailType>(() => api.claim(claimId!), [claimId]);

  if (detail.loading) return <Loading label="Loading claim record…" />;
  if (detail.error) return <ErrorState message={detail.error} />;
  const d = detail.data!;
  const c = d.claim;

  return (
    <>
      <Link to="/claims" className="back-link">
        <span style={{ transform: "rotate(180deg)", display: "inline-flex" }}>
          <IconArrowRight size={13} />
        </span>
        Back to work queue
      </Link>

      <div className="hero-card">
        <div className="hero-top">
          <div>
            <div className="hero-id">
              {c.claim_id}
              <StatusBadge status={c.claim_status} />
              {c.is_high_value && <span className="badge purple">High value</span>}
              <AgingBadge bucket={c.aging_bucket} />
            </div>
            <div className="hero-sub">
              {c.service_line_name} · service {fmtDate(c.date_of_service)} · submitted{" "}
              {fmtDate(c.claim_submission_date)} · {c.claim_age_days} days old
            </div>
          </div>
          {c.task_priority && (
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.8, textTransform: "uppercase", color: "#7e93b8" }}>
                Queue priority
              </div>
              <div style={{ marginTop: 4 }}>
                <PriorityBadge priority={c.task_priority} />
              </div>
            </div>
          )}
        </div>
        <div className="hero-stats">
          <div className="hero-stat">
            <div className="h-label">Billed</div>
            <div className="h-value">{fmtMoneyFull(c.billed_amount)}</div>
          </div>
          <div className="hero-stat">
            <div className="h-label">Allowed</div>
            <div className="h-value">{fmtMoneyFull(d.allowed_amount)}</div>
          </div>
          <div className="hero-stat">
            <div className="h-label">Paid</div>
            <div className="h-value pos">{fmtMoneyFull(d.paid_amount)}</div>
          </div>
          <div className="hero-stat">
            <div className="h-label">Patient Resp.</div>
            <div className="h-value">{fmtMoneyFull(d.patient_responsibility)}</div>
          </div>
          <div className="hero-stat">
            <div className="h-label">Outstanding</div>
            <div className={`h-value ${c.outstanding_amount > 0 ? "neg" : "pos"}`}>
              {fmtMoneyFull(c.outstanding_amount)}
            </div>
          </div>
          <div className="hero-stat">
            <div className="h-label">Payer</div>
            <div className="h-value" style={{ fontSize: 14 }}>{c.payer_name}</div>
          </div>
          <div className="hero-stat">
            <div className="h-label">Facility</div>
            <div className="h-value" style={{ fontSize: 14 }}>{c.facility_name}</div>
          </div>
        </div>
      </div>

      <div className="action-panel" style={{ marginBottom: 16 }}>
        <span className="ap-icon">
          <IconTarget size={18} />
        </span>
        <div>
          <div className="ap-label">Recommended next action</div>
          <div className="ap-text">{d.recommended_action}</div>
        </div>
      </div>

      <div className="grid two-col">
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <SectionCard title="Claim Overview" sub="Parties and coverage on this claim">
            <div className="field-grid">
              <Field label="Provider" value={c.provider_name} />
              <Field label="Facility" value={c.facility_name} />
              <Field label="Payer" value={`${c.payer_name} (${c.payer_type})`} />
              <Field label="Service Line" value={c.service_line_name} />
              <Field
                label="Patient Segment"
                value={
                  <>
                    <span className="mono">{d.patient_segment.synthetic_patient_key}</span>
                    {" · "}
                    {d.patient_segment.age_group} · {d.patient_segment.gender}
                  </>
                }
              />
              <Field
                label="Coverage / Risk"
                value={`${d.patient_segment.insurance_type} · ${d.patient_segment.risk_segment} risk · ${d.patient_segment.state}`}
              />
            </div>
            <p style={{ fontSize: 11.5, color: "var(--text-faint)", margin: "12px 0 0" }}>
              Patient shown as a demographic segment only — synthetic data, no identifying details.
            </p>
          </SectionCard>

          {d.denial && (
            <SectionCard title="Denial Details" sub="Why the payer denied, and where the appeal stands">
              <div className="field-grid">
                <Field label="Category" value={<span className="badge red">{d.denial.denial_category}</span>} />
                <Field label="Code" value={<span className="mono">{d.denial.denial_code}</span>} />
                <Field label="Denied Amount" value={<strong>{fmtMoneyFull(d.denial.denied_amount)}</strong>} />
                <Field label="Denial Date" value={fmtDate(d.denial.denial_date)} />
                <Field label="Appeal Status" value={d.denial.appeal_status} />
                <Field label="Appeal Outcome" value={d.denial.appeal_outcome ?? "—"} />
                <Field
                  label="Recovered"
                  value={
                    <span style={{ color: d.denial.recovered_amount > 0 ? "var(--green)" : undefined, fontWeight: 650 }}>
                      {fmtMoneyFull(d.denial.recovered_amount)}
                    </span>
                  }
                />
                <Field
                  label="Preventable?"
                  value={d.denial.preventable ? <span className="badge amber">Yes — process fix</span> : "No"}
                />
              </div>
              <p style={{ fontSize: 12.5, color: "var(--text-dim)", margin: "12px 0 0" }}>
                {d.denial.denial_description}
              </p>
            </SectionCard>
          )}

          <SectionCard title="Payment History" sub="Remittances applied to this claim">
            {d.payments.length === 0 ? (
              <p style={{ color: "var(--text-dim)", fontSize: 13, margin: 0 }}>
                No payments received on this claim.
              </p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Payment</th>
                    <th>Date</th>
                    <th className="num">Amount</th>
                    <th>Method</th>
                    <th className="num">Days to Pay</th>
                  </tr>
                </thead>
                <tbody>
                  {d.payments.map((p) => (
                    <tr key={p.payment_id}>
                      <td className="mono">{p.payment_id}</td>
                      <td>{fmtDate(p.payment_date)}</td>
                      <td className="num"><strong>{fmtMoneyFull(p.paid_amount)}</strong></td>
                      <td>{p.payment_method}</td>
                      <td className="num">{p.days_to_payment}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </SectionCard>

          <SectionCard title="Follow-Up Tasks" sub="Automation-generated work on this claim">
            {d.tasks.length === 0 ? (
              <p style={{ color: "var(--text-dim)", fontSize: 13, margin: 0 }}>
                No automation rules fired for this claim.
              </p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Task</th>
                    <th>Priority</th>
                    <th>Team</th>
                    <th>Due</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {d.tasks.map((t) => (
                    <tr key={t.task_id}>
                      <td>
                        <span className="cell-main">{t.task_type}</span>
                        <div className="cell-sub">{t.reason}</div>
                      </td>
                      <td><PriorityBadge priority={t.priority} /></td>
                      <td>{t.assigned_team}</td>
                      <td>
                        {fmtDate(t.due_date)}
                        {t.is_overdue && <span className="badge red" style={{ marginLeft: 6 }}>Overdue</span>}
                      </td>
                      <td><TaskStatusBadge status={t.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </SectionCard>
        </div>

        <SectionCard
          title="Claim Timeline"
          sub="Every event on this claim, oldest first"
          style={{ alignSelf: "start" }}
        >
          <ul className="timeline">
            {buildTimeline(d).map((e, i) => (
              <li key={i}>
                <span className={`t-dot ${e.tone}`} />
                <div className="t-date">{fmtDate(e.date)}</div>
                <div className="t-title">{e.title}</div>
                <div className="t-desc">{e.desc}</div>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
    </>
  );
}
