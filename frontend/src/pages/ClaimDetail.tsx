import { Link, useParams } from "react-router-dom";
import { api, fmtDate, fmtMoneyFull } from "../api/client";
import {
  AgingBadge, ErrorState, Loading, PriorityBadge, StatusBadge, TaskStatusBadge, useFetch,
} from "../components/ui";
import type { ClaimDetail as ClaimDetailType } from "../api/types";

interface TimelineEvent {
  date: string;
  title: string;
  desc: string;
}

function buildTimeline(d: ClaimDetailType): TimelineEvent[] {
  const events: TimelineEvent[] = [
    {
      date: d.claim.date_of_service,
      title: "Service rendered",
      desc: `${d.claim.service_line_name} — ${d.claim.provider_name} at ${d.claim.facility_name}`,
    },
    {
      date: d.claim.claim_submission_date,
      title: "Claim submitted",
      desc: `Billed ${fmtMoneyFull(d.claim.billed_amount)} to ${d.claim.payer_name}`,
    },
  ];
  if (d.denial) {
    events.push({
      date: d.denial.denial_date,
      title: `Denied — ${d.denial.denial_category}`,
      desc: `${d.denial.denial_code}: ${d.denial.denial_description} (${fmtMoneyFull(d.denial.denied_amount)})`,
    });
    if (d.denial.appeal_submitted_date) {
      events.push({
        date: d.denial.appeal_submitted_date,
        title: "Appeal submitted",
        desc: `${d.denial.days_to_appeal} days after denial`,
      });
    }
    if (d.denial.appeal_outcome) {
      events.push({
        date: d.denial.appeal_submitted_date ?? d.denial.denial_date,
        title: `Appeal resolved — ${d.denial.appeal_outcome}`,
        desc: d.denial.recovered_amount > 0
          ? `Recovered ${fmtMoneyFull(d.denial.recovered_amount)}`
          : "No recovery",
      });
    }
  }
  for (const p of d.payments) {
    events.push({
      date: p.payment_date,
      title: `Payment received — ${fmtMoneyFull(p.paid_amount)}`,
      desc: `${p.payment_method}, ${p.days_to_payment} days after submission`,
    });
  }
  for (const t of d.tasks) {
    events.push({
      date: t.created_date,
      title: `Task created — ${t.task_type}`,
      desc: `${t.priority} priority · ${t.assigned_team}`,
    });
  }
  return events.sort((a, b) => a.date.localeCompare(b.date));
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 0.4 }}>
        {label}
      </div>
      <div style={{ fontSize: 13.5, marginTop: 2 }}>{value}</div>
    </div>
  );
}

export default function ClaimDetail() {
  const { claimId } = useParams<{ claimId: string }>();
  const detail = useFetch<ClaimDetailType>(() => api.claim(claimId!), [claimId]);

  if (detail.loading) return <Loading label="Loading claim…" />;
  if (detail.error) return <ErrorState message={detail.error} />;
  const d = detail.data!;
  const c = d.claim;

  return (
    <>
      <div className="page-header">
        <div style={{ fontSize: 12.5, marginBottom: 6 }}>
          <Link to="/claims">← Back to work queue</Link>
        </div>
        <h1 style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="mono" style={{ fontSize: 19 }}>{c.claim_id}</span>
          <StatusBadge status={c.claim_status} />
          {c.is_high_value && <span className="badge purple">High value</span>}
          <AgingBadge bucket={c.aging_bucket} />
        </h1>
        <div className="desc">
          {c.service_line_name} · {fmtDate(c.date_of_service)} · {c.payer_name}
        </div>
      </div>

      <div className="callout" style={{ marginBottom: 16 }}>
        <strong>Recommended action:</strong> {d.recommended_action}
      </div>

      <div className="grid two-col">
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="card">
            <h3>Claim Summary</h3>
            <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
              <Field label="Billed" value={<strong>{fmtMoneyFull(c.billed_amount)}</strong>} />
              <Field label="Allowed" value={fmtMoneyFull(d.allowed_amount)} />
              <Field label="Paid" value={fmtMoneyFull(d.paid_amount)} />
              <Field label="Patient Resp." value={fmtMoneyFull(d.patient_responsibility)} />
              <Field
                label="Outstanding"
                value={
                  <strong style={{ color: c.outstanding_amount > 0 ? "var(--red)" : "var(--green)" }}>
                    {fmtMoneyFull(c.outstanding_amount)}
                  </strong>
                }
              />
              <Field label="Claim Age" value={`${c.claim_age_days} days`} />
            </div>
          </div>

          <div className="card">
            <h3>Parties</h3>
            <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
              <Field label="Provider" value={c.provider_name} />
              <Field label="Facility" value={c.facility_name} />
              <Field label="Payer" value={`${c.payer_name} (${c.payer_type})`} />
              <Field label="Service Line" value={c.service_line_name} />
            </div>
          </div>

          <div className="card">
            <h3>Patient Segment</h3>
            <div className="card-sub">Demographic segment only — synthetic data, no identifying details.</div>
            <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 12 }}>
              <Field label="Key" value={<span className="mono">{d.patient_segment.synthetic_patient_key}</span>} />
              <Field label="Age Group" value={d.patient_segment.age_group} />
              <Field label="Gender" value={d.patient_segment.gender} />
              <Field label="State" value={d.patient_segment.state} />
              <Field label="Insurance" value={d.patient_segment.insurance_type} />
              <Field label="Risk Segment" value={d.patient_segment.risk_segment} />
            </div>
          </div>

          {d.denial && (
            <div className="card">
              <h3>Denial</h3>
              <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
                <Field label="Category" value={<span className="badge red">{d.denial.denial_category}</span>} />
                <Field label="Code" value={<span className="mono">{d.denial.denial_code}</span>} />
                <Field label="Denied Amount" value={fmtMoneyFull(d.denial.denied_amount)} />
                <Field label="Denial Date" value={fmtDate(d.denial.denial_date)} />
                <Field label="Appeal Status" value={d.denial.appeal_status} />
                <Field label="Appeal Outcome" value={d.denial.appeal_outcome ?? "—"} />
                <Field
                  label="Recovered"
                  value={
                    <span style={{ color: d.denial.recovered_amount > 0 ? "var(--green)" : undefined }}>
                      {fmtMoneyFull(d.denial.recovered_amount)}
                    </span>
                  }
                />
                <Field
                  label="Preventable?"
                  value={d.denial.preventable ? <span className="badge amber">Yes</span> : "No"}
                />
              </div>
              <p style={{ fontSize: 12.5, color: "var(--text-dim)", marginBottom: 0 }}>
                {d.denial.denial_description}
              </p>
            </div>
          )}

          <div className="card">
            <h3>Payment History</h3>
            {d.payments.length === 0 ? (
              <p style={{ color: "var(--text-dim)", fontSize: 13 }}>No payments received on this claim.</p>
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
                      <td className="num">{fmtMoneyFull(p.paid_amount)}</td>
                      <td>{p.payment_method}</td>
                      <td className="num">{p.days_to_payment}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="card">
            <h3>Follow-Up Tasks</h3>
            {d.tasks.length === 0 ? (
              <p style={{ color: "var(--text-dim)", fontSize: 13 }}>
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
                        {t.task_type}
                        <div style={{ fontSize: 11.5, color: "var(--text-faint)" }}>{t.reason}</div>
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
          </div>
        </div>

        <div className="card" style={{ alignSelf: "start" }}>
          <h3>Claim Timeline</h3>
          <ul className="timeline">
            {buildTimeline(d).map((e, i) => (
              <li key={i}>
                <span className="t-dot" />
                <div className="t-date">{fmtDate(e.date)}</div>
                <div className="t-title">{e.title}</div>
                <div className="t-desc">{e.desc}</div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </>
  );
}
