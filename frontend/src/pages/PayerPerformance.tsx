import { api, fmtMoney } from "../api/client";
import { ErrorState, Loading, useFetch } from "../components/ui";
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

  return (
    <>
      <div className="page-header">
        <h1>Payer Performance</h1>
        <div className="desc">
          Scorecards ranked by composite risk — 50% denial rate, 30% payment speed, 20% aged A/R share.
        </div>
      </div>

      {alerts.data && alerts.data.length > 0 && (
        <div className="callout warn" style={{ marginBottom: 16 }}>
          <strong>Escalation alerts:</strong>{" "}
          {alerts.data.map((a) => (
            <span key={a.alert_id}>
              {a.payer_name} is denying {a.denial_rate_pct}% of claims ({fmtMoney(a.denied_outstanding_amount)}{" "}
              denied balance outstanding). {a.recommended_action}.{" "}
            </span>
          ))}
        </div>
      )}

      <div className="table-wrap" style={{ marginBottom: 20 }}>
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
                  <td>
                    <strong>#{p.risk_rank}</strong>
                  </td>
                  <td>
                    <strong>{p.payer_name}</strong>
                    <div style={{ fontSize: 11.5, color: "var(--text-faint)" }}>{p.contract_type}</div>
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

      <div className="section-title">Denial Profiles</div>
      <div className="grid cards-row">
        {list.map((p) => (
          <div className="card" key={p.payer_id}>
            <h3 style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              {p.payer_name}
              <span className={`badge ${riskBadge(p.risk_rank, list.length).tone}`}>#{p.risk_rank}</span>
            </h3>
            <div className="card-sub">
              {p.denied_claims} denials · {fmtMoney(p.denied_amount)} denied · {fmtMoney(p.recovered_amount)}{" "}
              recovered
            </div>
            {p.top_denial_reasons.length === 0 ? (
              <p style={{ fontSize: 12.5, color: "var(--text-dim)" }}>No denials recorded.</p>
            ) : (
              <table>
                <tbody>
                  {p.top_denial_reasons.map((r) => (
                    <tr key={r.denial_category}>
                      <td style={{ padding: "6px 4px", fontSize: 12.5 }}>{r.denial_category}</td>
                      <td className="num" style={{ padding: "6px 4px", fontSize: 12.5 }}>
                        {r.denials}× · {fmtMoney(r.denied_amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
