import { api, fmtMoney } from "../api/client";
import {
  ErrorState, InsightPanel, Loading, PageHeader, SectionCard, useFetch,
} from "../components/ui";
import { IconAlert } from "../components/Icons";
import type { Alert, PayerScorecard } from "../api/types";

function riskBadge(rank: number, total: number): { tone: string; label: string } {
  if (rank <= 2) return { tone: "red", label: "Escalate" };
  if (rank <= Math.ceil(total / 2)) return { tone: "amber", label: "Watch" };
  return { tone: "green", label: "Healthy" };
}

export default function PayerPerformance() {
  const payers = useFetch<PayerScorecard[]>(() => api.payers());
  const alerts = useFetch<Alert[]>(() => api.alerts());

  if (payers.loading) return <Loading label="Loading payer scorecards…" />;
  if (payers.error) return <ErrorState message={payers.error} />;
  const list = payers.data!;
  const alertPayers = new Set((alerts.data ?? []).map((a) => a.payer_name));

  const worstDenial = [...list].sort((a, b) => b.denial_rate_pct - a.denial_rate_pct)[0];
  const slowest = [...list]
    .filter((p) => p.avg_days_to_payment !== null)
    .sort((a, b) => (b.avg_days_to_payment ?? 0) - (a.avg_days_to_payment ?? 0))[0];
  const biggestAr = [...list].sort((a, b) => b.outstanding_ar - a.outstanding_ar)[0];

  return (
    <>
      <PageHeader
        title="Payer Performance"
        subtitle="Scorecards ranked by composite risk — 50% denial rate, 30% payment speed, 20% aged A/R share. Rank 1 is the payer costing the most operational effort."
      />

      {alerts.data && alerts.data.length > 0 && (
        <div className="callout danger" style={{ marginBottom: 16 }}>
          <span className="co-icon">
            <IconAlert size={17} />
          </span>
          <div>
            <strong>Escalation alerts:</strong>{" "}
            {alerts.data.map((a) => (
              <span key={a.alert_id}>
                {a.payer_name} is denying {a.denial_rate_pct}% of claims ({fmtMoney(a.denied_outstanding_amount)}{" "}
                denied balance outstanding). {a.recommended_action}.{" "}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid two-col" style={{ marginBottom: 16 }}>
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", alignContent: "start" }}>
          {list.slice(0, 3).map((p) => {
            const b = riskBadge(p.risk_rank, list.length);
            return (
              <div className="card" key={p.payer_id} style={{ padding: "16px 18px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className={`rank-num ${p.risk_rank <= 2 ? "hot" : "warm"}`}>{p.risk_rank}</span>
                  <span className={`badge ${b.tone}`}>{b.label}</span>
                </div>
                <div style={{ fontWeight: 750, fontSize: 14.5, marginTop: 10 }}>{p.payer_name}</div>
                <div style={{ fontSize: 12, color: "var(--text-faint)" }}>
                  {p.payer_type} · {p.contract_type}
                </div>
                <div className="field-grid" style={{ marginTop: 12, gridTemplateColumns: "1fr 1fr" }}>
                  <div className="field">
                    <div className="f-label">Denial rate</div>
                    <div className="f-value" style={{ color: p.denial_rate_pct > 20 ? "var(--red)" : undefined, fontWeight: 700 }}>
                      {p.denial_rate_pct}%
                    </div>
                  </div>
                  <div className="field">
                    <div className="f-label">Days to pay</div>
                    <div className="f-value" style={{ fontWeight: 700 }}>{p.avg_days_to_payment ?? "—"}</div>
                  </div>
                  <div className="field">
                    <div className="f-label">Outstanding</div>
                    <div className="f-value">{fmtMoney(p.outstanding_ar)}</div>
                  </div>
                  <div className="field">
                    <div className="f-label">Risk score</div>
                    <div className="f-value">{p.risk_score.toFixed(2)}</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <InsightPanel
          title="Where to focus"
          items={[
            <>
              <strong>{worstDenial.payer_name}</strong> has the highest denial rate at{" "}
              <strong>{worstDenial.denial_rate_pct}%</strong>
              {alertPayers.has(worstDenial.payer_name) ? " — above the 20% escalation threshold." : "."}
            </>,
            slowest ? (
              <>
                <strong>{slowest.payer_name}</strong> pays slowest at{" "}
                <strong>{slowest.avg_days_to_payment} days</strong> on average — a cash-flow drag worth a
                joint operating review.
              </>
            ) : (
              <>Payment lag data unavailable.</>
            ),
            <>
              <strong>{biggestAr.payer_name}</strong> holds the largest outstanding balance at{" "}
              <strong>{fmtMoney(biggestAr.outstanding_ar)}</strong>, including {fmtMoney(biggestAr.ar_over_90)}{" "}
              already past 90 days.
            </>,
          ]}
        />
      </div>

      <SectionCard title="Full Scorecard" sub="All payers, ranked by composite risk">
        <div style={{ overflowX: "auto", margin: "0 -22px -20px", padding: "0 22px 8px" }}>
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Payer</th>
                <th>Type</th>
                <th className="num">Claims</th>
                <th className="num">Denial Rate</th>
                <th className="num">Avg Days to Pay</th>
                <th className="num">Billed</th>
                <th className="num">Paid</th>
                <th className="num">Outstanding A/R</th>
                <th className="num">A/R &gt; 90d</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {list.map((p) => {
                const badge = riskBadge(p.risk_rank, list.length);
                return (
                  <tr key={p.payer_id} className={alertPayers.has(p.payer_name) ? "risk-row" : ""}>
                    <td><strong>#{p.risk_rank}</strong></td>
                    <td>
                      <span className="cell-main">{p.payer_name}</span>
                      <div className="cell-sub">{p.contract_type}</div>
                    </td>
                    <td>{p.payer_type}</td>
                    <td className="num">{p.total_claims.toLocaleString()}</td>
                    <td className="num">
                      <strong style={{ color: p.denial_rate_pct > 20 ? "var(--red)" : undefined }}>
                        {p.denial_rate_pct}%
                      </strong>
                    </td>
                    <td className="num">{p.avg_days_to_payment ?? "—"}</td>
                    <td className="num">{fmtMoney(p.billed_amount)}</td>
                    <td className="num">{fmtMoney(p.paid_amount)}</td>
                    <td className="num">{fmtMoney(p.outstanding_ar)}</td>
                    <td className="num">{fmtMoney(p.ar_over_90)}</td>
                    <td>
                      <span className={`badge ${badge.tone}`}>
                        {badge.label} · {p.risk_score.toFixed(2)}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </SectionCard>

      <div className="section-title">Denial Profiles by Payer</div>
      <div className="grid cards-row">
        {list.map((p) => (
          <SectionCard
            key={p.payer_id}
            title={p.payer_name}
            sub={`${p.denied_claims} denials · ${fmtMoney(p.denied_amount)} denied · ${fmtMoney(p.recovered_amount)} recovered`}
            action={<span className={`badge ${riskBadge(p.risk_rank, list.length).tone}`}>#{p.risk_rank}</span>}
          >
            {p.top_denial_reasons.length === 0 ? (
              <p style={{ fontSize: 12.5, color: "var(--text-dim)", margin: 0 }}>No denials recorded.</p>
            ) : (
              <table>
                <tbody>
                  {p.top_denial_reasons.map((r) => (
                    <tr key={r.denial_category}>
                      <td style={{ padding: "7px 4px", fontSize: 12.5 }}>{r.denial_category}</td>
                      <td className="num" style={{ padding: "7px 4px", fontSize: 12.5 }}>
                        {r.denials}× · {fmtMoney(r.denied_amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </SectionCard>
        ))}
      </div>
    </>
  );
}
