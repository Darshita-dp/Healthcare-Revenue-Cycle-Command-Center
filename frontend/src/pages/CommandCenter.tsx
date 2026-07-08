import { Link } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, fmtMoney, fmtNum } from "../api/client";
import { ErrorState, KpiCard, Loading, useFetch } from "../components/ui";
import type { Aging, Alert, Kpis, PayerScorecard } from "../api/types";

function riskTone(rank: number): "red" | "amber" | "green" {
  return rank <= 2 ? "red" : rank <= 4 ? "amber" : "green";
}

export default function CommandCenter() {
  const kpis = useFetch<Kpis>(() => api.kpis());
  const payers = useFetch<PayerScorecard[]>(() => api.payers());
  const alerts = useFetch<Alert[]>(() => api.alerts());
  const aging = useFetch<Aging>(() => api.aging());

  if (kpis.loading) return <Loading label="Loading command center…" />;
  if (kpis.error) return <ErrorState message={kpis.error} />;
  const k = kpis.data!;

  return (
    <>
      <div className="page-header">
        <h1>Command Center</h1>
        <div className="desc">
          Revenue cycle health at a glance — synthetic dataset, {fmtNum(k.total_claims)} claims.
        </div>
      </div>

      {alerts.data && alerts.data.length > 0 && (
        <div className="callout danger" style={{ marginBottom: 16 }}>
          <strong>⚠ {alerts.data.length} payer escalation{alerts.data.length > 1 ? "s" : ""}:</strong>{" "}
          {alerts.data
            .map((a) => `${a.payer_name} denial rate ${a.denial_rate_pct}% (threshold ${a.threshold_pct}%)`)
            .join(" · ")}{" "}
          — <Link to="/payers">review payer scorecards</Link>
        </div>
      )}

      <div className="grid kpi-grid">
        <KpiCard label="Total Billed" value={fmtMoney(k.total_billed)} hint="Gross charges submitted" />
        <KpiCard label="Total Paid" value={fmtMoney(k.total_paid)} hint="Payer payments received" tone="green" />
        <KpiCard label="Outstanding A/R" value={fmtMoney(k.outstanding_ar)} hint="Open claim balances" />
        <KpiCard
          label="Revenue at Risk"
          value={fmtMoney(k.revenue_at_risk)}
          hint="Denied + aged > 60 days"
          tone="red"
        />
        <KpiCard
          label="A/R Over 90 Days"
          value={fmtMoney(k.ar_over_90)}
          hint="Oldest, hardest to collect"
          tone="amber"
        />
        <KpiCard label="Denial Rate" value={`${k.denial_rate_pct}%`} hint="Of all claims" tone="red" />
        <KpiCard
          label="Clean Claim Rate"
          value={`${k.clean_claim_rate_pct}%`}
          hint="Paid without rework"
          tone="green"
        />
        <KpiCard label="Avg Days to Payment" value={String(k.avg_days_to_payment)} hint="Submission → remit" />
        <KpiCard
          label="Open Tasks"
          value={fmtNum(k.open_tasks)}
          hint={`${fmtNum(k.overdue_tasks)} overdue`}
          tone={k.overdue_tasks > 0 ? "amber" : undefined}
        />
        <KpiCard
          label="Recovered on Appeal"
          value={fmtMoney(k.total_recovered)}
          hint={`${k.appeal_success_rate_pct}% appeal success`}
          tone="green"
        />
      </div>

      <div className="grid two-col" style={{ marginTop: 16 }}>
        <div className="card">
          <h3>Denial Rate Trend</h3>
          <div className="card-sub">Monthly denial rate — is it improving or getting worse?</div>
          <ResponsiveContainer width="100%" height={230}>
            <LineChart data={k.denial_trend} margin={{ top: 5, right: 12, left: -18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e9edf4" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} unit="%" />
              <Tooltip formatter={(v: number) => [`${v}%`, "Denial rate"]} />
              <Line
                type="monotone"
                dataKey="denial_rate_pct"
                stroke="#d92d20"
                strokeWidth={2}
                dot={false}
                name="Denial rate"
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3>Billed vs Paid by Month</h3>
          <div className="card-sub">Charge volume against cash actually received</div>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={k.monthly_billed_paid} margin={{ top: 5, right: 12, left: -8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e9edf4" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `$${Math.round(v / 1000)}k`} />
              <Tooltip formatter={(v: number) => fmtMoney(v)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="billed" fill="#94a9d1" name="Billed" radius={[3, 3, 0, 0]} isAnimationActive={false} />
              <Bar dataKey="paid" fill="#1e5eff" name="Paid" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid two-col" style={{ marginTop: 16 }}>
        <div className="card">
          <h3>A/R by Aging Bucket</h3>
          <div className="card-sub">
            {aging.data ? `As of ${aging.data.as_of}` : "Where the outstanding money sits"}
          </div>
          {aging.loading && <Loading label="Loading aging…" />}
          {aging.error && <ErrorState message={aging.error} />}
          {aging.data && (
            <table>
              <thead>
                <tr>
                  <th>Bucket</th>
                  <th className="num">Open Claims</th>
                  <th className="num">Outstanding</th>
                  <th style={{ width: "34%" }}>Share of A/R</th>
                </tr>
              </thead>
              <tbody>
                {aging.data.buckets.map((b) => (
                  <tr key={b.aging_bucket}>
                    <td>
                      <strong>{b.aging_bucket} days</strong>
                    </td>
                    <td className="num">{fmtNum(b.open_claims)}</td>
                    <td className="num">{fmtMoney(b.outstanding_amount)}</td>
                    <td>
                      <div className="progress-track">
                        <div
                          className="progress-fill"
                          style={{
                            width: `${b.pct_of_ar}%`,
                            background:
                              b.aging_bucket === "90+"
                                ? "var(--red)"
                                : b.aging_bucket === "61-90"
                                  ? "var(--amber)"
                                  : "var(--primary)",
                          }}
                        />
                      </div>
                      <span style={{ fontSize: 11.5, color: "var(--text-faint)" }}>{b.pct_of_ar}%</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card">
          <h3>Payer Risk Cards</h3>
          <div className="card-sub">Composite of denial rate, payment speed, and aged A/R</div>
          {payers.loading && <Loading label="Loading payers…" />}
          {payers.error && <ErrorState message={payers.error} />}
          {payers.data && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {payers.data.slice(0, 5).map((p) => (
                <Link
                  key={p.payer_id}
                  to="/payers"
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "8px 12px",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    color: "inherit",
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>
                      #{p.risk_rank} {p.payer_name}
                    </div>
                    <div style={{ fontSize: 11.5, color: "var(--text-faint)" }}>
                      {p.denial_rate_pct}% denials · {p.avg_days_to_payment ?? "—"} days to pay ·{" "}
                      {fmtMoney(p.outstanding_ar)} A/R
                    </div>
                  </div>
                  <span className={`badge ${riskTone(p.risk_rank)}`}>risk {p.risk_score.toFixed(2)}</span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
