import { Link } from "react-router-dom";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, fmtMoney, fmtNum } from "../api/client";
import {
  ErrorState, InsightPanel, Loading, MetricCard, PageHeader, SectionCard, useFetch,
} from "../components/ui";
import RecoverySimulator from "../components/RecoverySimulator";
import {
  IconAlert, IconCalendar, IconCheckSquare, IconClock, IconDollar, IconLightning,
  IconScale, IconShield, IconTarget, IconTrendDown, IconWallet,
} from "../components/Icons";
import type { Aging, Alert, Kpis, PayerScorecard, PriorityInsights, TaskList } from "../api/types";

// Ordinal single-hue ramp for the aging buckets (light -> dark = young -> old)
const AGING_RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#184f95"];

function riskClass(rank: number): string {
  return rank <= 2 ? "hot" : rank <= 4 ? "warm" : "";
}

export default function CommandCenter() {
  const kpis = useFetch<Kpis>(() => api.kpis());
  const payers = useFetch<PayerScorecard[]>(() => api.payers());
  const alerts = useFetch<Alert[]>(() => api.alerts());
  const aging = useFetch<Aging>(() => api.aging());
  const tasks = useFetch<TaskList>(() => api.tasks({ limit: 1 }));
  const insights = useFetch<PriorityInsights>(() => api.priorityInsights());

  if (kpis.loading) return <Loading label="Loading command center…" />;
  if (kpis.error) return <ErrorState message={kpis.error} />;
  const k = kpis.data!;

  const collectionRate = k.total_billed > 0 ? (100 * k.total_paid) / k.total_billed : 0;
  const firstMonth = k.denial_trend[0];
  const lastMonth = k.denial_trend[k.denial_trend.length - 1];
  const denialDirection =
    lastMonth && firstMonth
      ? lastMonth.denial_rate_pct <= firstMonth.denial_rate_pct
        ? "improving"
        : "worsening"
      : null;

  return (
    <>
      <PageHeader
        title="Revenue Cycle Command Center"
        subtitle="Live operational view of claims, denials, payer behavior, and accounts receivable across the health system — built on a fully synthetic dataset."
        meta={
          <>
            <span className="meta-chip">
              <IconCalendar size={13} />
              Data as of {aging.data?.as_of ?? "…"}
            </span>
            <span className="meta-chip">
              <IconShield size={13} />
              Synthetic Data · No PHI
            </span>
          </>
        }
      />

      {alerts.data && alerts.data.length > 0 && (
        <div className="callout danger" style={{ marginBottom: 18 }}>
          <span className="co-icon">
            <IconAlert size={17} />
          </span>
          <div>
            <strong>
              {alerts.data.length} payer escalation{alerts.data.length > 1 ? "s" : ""} active:
            </strong>{" "}
            {alerts.data
              .map((a) => `${a.payer_name} is denying ${a.denial_rate_pct}% of claims (threshold ${a.threshold_pct}%)`)
              .join(" · ")}
            {" — "}
            <Link to="/payers">review payer scorecards</Link>
          </div>
        </div>
      )}

      <div className="grid kpi-grid">
        <MetricCard
          label="Total Billed"
          value={fmtMoney(k.total_billed)}
          context="Gross charges submitted"
          icon={<IconDollar size={16} />}
          tone="blue"
        />
        <MetricCard
          label="Total Paid"
          value={fmtMoney(k.total_paid)}
          context={`${collectionRate.toFixed(1)}% of billed collected`}
          icon={<IconWallet size={16} />}
          tone="green"
        />
        <MetricCard
          label="Outstanding A/R"
          value={fmtMoney(k.outstanding_ar)}
          context="Unresolved balances on open claims"
          icon={<IconClock size={16} />}
          tone="teal"
        />
        <MetricCard
          label="Revenue at Risk"
          value={fmtMoney(k.revenue_at_risk)}
          context="Denied or aged past 60 days"
          icon={<IconAlert size={16} />}
          tone="red"
        />
        <MetricCard
          label="Denial Rate"
          value={`${k.denial_rate_pct}%`}
          context={denialDirection ? `Trend ${denialDirection} vs. start of window` : "Share of all claims denied"}
          icon={<IconTrendDown size={16} />}
          tone="red"
        />
        <MetricCard
          label="A/R Over 90 Days"
          value={fmtMoney(k.ar_over_90)}
          context="Oldest, hardest money to collect"
          icon={<IconClock size={16} />}
          tone="amber"
        />
        <MetricCard
          label="Clean Claim Rate"
          value={`${k.clean_claim_rate_pct}%`}
          context="Paid first-pass, no rework"
          icon={<IconCheckSquare size={16} />}
          tone="green"
        />
        <MetricCard
          label="Open Tasks"
          value={fmtNum(k.open_tasks)}
          context={`${fmtNum(k.overdue_tasks)} overdue · rules engine`}
          icon={<IconCheckSquare size={16} />}
          tone={k.overdue_tasks > 0 ? "amber" : "blue"}
        />
      </div>

      <div className="section-title">
        <IconTarget size={17} />
        Explainable Priority &amp; Recovery
      </div>

      {insights.data && (
        <SectionCard
          title="Priority Queue Snapshot"
          sub={`Rule-based priority score across ${fmtNum(insights.data.scored_open_claims)} open claims — transparent, not a black-box model`}
          action={<Link to="/claims?tier=Critical">Work Critical queue →</Link>}
          style={{ marginBottom: 16 }}
        >
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
            <MetricCard
              label="Critical Claims"
              value={fmtNum(insights.data.critical_count)}
              context="Score 80–100 · immediate action"
              icon={<IconAlert size={16} />}
              tone="red"
            />
            <MetricCard
              label="High Priority"
              value={fmtNum(insights.data.high_count)}
              context="Score 60–79 · work this week"
              icon={<IconTrendDown size={16} />}
              tone="amber"
            />
            <MetricCard
              label="Critical + High A/R"
              value={fmtMoney(insights.data.critical_high_outstanding)}
              context="Outstanding tied to top tiers"
              icon={<IconDollar size={16} />}
              tone="teal"
            />
            <MetricCard
              label="Avg Priority Score"
              value={insights.data.average_priority_score}
              context="Across open claims"
              icon={<IconScale size={16} />}
              tone="blue"
            />
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, marginTop: 14 }}>
            <span style={{ fontSize: 11.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--text-faint)", display: "inline-flex", alignItems: "center", gap: 6 }}>
              <IconLightning size={13} /> Top drivers
            </span>
            {insights.data.top_drivers.slice(0, 4).map((d) => (
              <span key={d.category} className="badge gray">
                {d.label} · {fmtNum(d.claims)}
              </span>
            ))}
          </div>
        </SectionCard>
      )}

      <div style={{ marginBottom: 16 }}>
        <RecoverySimulator />
      </div>

      <div className="grid two-col" style={{ marginTop: 16 }}>
        <SectionCard
          title="Revenue Trend"
          sub="Monthly billed charges vs. payments received"
        >
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={k.monthly_billed_paid} margin={{ top: 6, right: 10, left: -6, bottom: 0 }}>
              <defs>
                <linearGradient id="gBilled" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2a78d6" stopOpacity={0.18} />
                  <stop offset="100%" stopColor="#2a78d6" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="gPaid" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#1baf7a" stopOpacity={0.22} />
                  <stop offset="100%" stopColor="#1baf7a" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--ch-grid)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#8593a9" }} tickLine={false}
                     axisLine={{ stroke: "#d4dbe7" }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11, fill: "#8593a9" }} tickLine={false} axisLine={false}
                     tickFormatter={(v: number) => `$${Math.round(v / 1000)}k`} />
              <Tooltip formatter={(v: number) => fmtMoney(v)} />
              <Legend wrapperStyle={{ fontSize: 12 }} iconType="plainline" />
              <Area type="monotone" dataKey="billed" name="Billed" stroke="#2a78d6" strokeWidth={2}
                    fill="url(#gBilled)" dot={false} isAnimationActive={false} />
              <Area type="monotone" dataKey="paid" name="Paid" stroke="#1baf7a" strokeWidth={2}
                    fill="url(#gPaid)" dot={false} isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
          <div className="chart-note">
            The gap between the lines is contractual adjustment, patient responsibility, denial loss, and A/R still in flight.
          </div>
        </SectionCard>

        <SectionCard
          title="Denial Rate Trend"
          sub="Monthly denial rate — is performance improving or slipping?"
        >
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={k.denial_trend} margin={{ top: 6, right: 10, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="var(--ch-grid)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#8593a9" }} tickLine={false}
                     axisLine={{ stroke: "#d4dbe7" }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11, fill: "#8593a9" }} tickLine={false} axisLine={false} unit="%" />
              <Tooltip formatter={(v: number) => [`${v}%`, "Denial rate"]} />
              <Line type="monotone" dataKey="denial_rate_pct" name="Denial rate" stroke="#e34948"
                    strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
          <div className="chart-note">
            Portfolio average {k.denial_rate_pct}% · {k.preventable_denial_rate_pct}% of denials are process-preventable.
          </div>
        </SectionCard>
      </div>

      <div className="grid two-col" style={{ marginTop: 16 }}>
        <SectionCard
          title="A/R by Aging Bucket"
          sub={aging.data ? `Outstanding balance by claim age — as of ${aging.data.as_of}` : "Where the outstanding money sits"}
          action={<Link to="/claims?aging=90%2B">Work 90+ queue →</Link>}
        >
          {aging.loading && <Loading label="Loading aging…" />}
          {aging.error && <ErrorState message={aging.error} />}
          {aging.data && (
            <ResponsiveContainer width="100%" height={210}>
              <BarChart data={aging.data.buckets} layout="vertical"
                        margin={{ top: 0, right: 70, left: 8, bottom: 0 }}>
                <CartesianGrid stroke="var(--ch-grid)" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: "#8593a9" }} tickLine={false}
                       axisLine={false} tickFormatter={(v: number) => `$${Math.round(v / 1000)}k`} />
                <YAxis type="category" dataKey="aging_bucket" width={52}
                       tick={{ fontSize: 12, fill: "#55627a", fontWeight: 600 }} tickLine={false}
                       axisLine={{ stroke: "#d4dbe7" }} tickFormatter={(v: string) => `${v} d`} />
                <Tooltip formatter={(v: number, _n, item) =>
                  [`${fmtMoney(v)} · ${item?.payload?.open_claims} claims`, "Outstanding"]} />
                <Bar dataKey="outstanding_amount" name="Outstanding" barSize={18}
                     radius={[0, 4, 4, 0]} isAnimationActive={false}>
                  {aging.data.buckets.map((b, i) => (
                    <Cell key={b.aging_bucket} fill={AGING_RAMP[i] ?? AGING_RAMP[3]} />
                  ))}
                  <LabelList dataKey="pct_of_ar" position="right"
                             formatter={(v: unknown) => `${v}%`}
                             style={{ fontSize: 11, fill: "#55627a", fontWeight: 600 }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
          <div className="chart-note">Darker = older. Collectability decays sharply past 90 days.</div>
        </SectionCard>

        <SectionCard
          title="Payer Risk Leaderboard"
          sub="Composite of denial rate, payment speed, and aged A/R"
          action={<Link to="/payers">Full scorecards →</Link>}
        >
          {payers.loading && <Loading label="Loading payers…" />}
          {payers.error && <ErrorState message={payers.error} />}
          {payers.data && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {payers.data.slice(0, 5).map((p) => (
                <Link key={p.payer_id} to="/payers" className="rank-row">
                  <span className={`rank-num ${riskClass(p.risk_rank)}`}>{p.risk_rank}</span>
                  <span className="rank-body">
                    <span className="rank-title">{p.payer_name}</span>
                    <div className="rank-sub">
                      {p.denial_rate_pct}% denial rate · {p.avg_days_to_payment ?? "—"} days to pay ·{" "}
                      {fmtMoney(p.outstanding_ar)} outstanding
                    </div>
                  </span>
                  <span className={`badge ${p.risk_rank <= 2 ? "red" : p.risk_rank <= 4 ? "amber" : "green"}`}>
                    {p.risk_rank <= 2 ? "Escalate" : p.risk_rank <= 4 ? "Watch" : "Healthy"} · {p.risk_score.toFixed(2)}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </SectionCard>
      </div>

      <div className="grid two-col" style={{ marginTop: 16 }}>
        <SectionCard
          title="Work Queue Summary"
          sub="Follow-up work generated by the automation rules engine"
          action={<Link to="/tasks">Open task board →</Link>}
        >
          {tasks.data ? (
            <div className="summary-strip" style={{ marginBottom: 0, boxShadow: "none" }}>
              <div className="summary-cell">
                <div className="s-label">Open</div>
                <div className="s-value">{fmtNum(tasks.data.summary.open)}</div>
              </div>
              <div className="summary-cell">
                <div className="s-label">In Progress</div>
                <div className="s-value">{fmtNum(tasks.data.summary.in_progress)}</div>
              </div>
              <div className="summary-cell">
                <div className="s-label">Overdue</div>
                <div className="s-value red">{fmtNum(tasks.data.summary.overdue)}</div>
              </div>
              <div className="summary-cell">
                <div className="s-label">Completed</div>
                <div className="s-value green">{fmtNum(tasks.data.summary.completed)}</div>
              </div>
              <div className="summary-cell">
                <div className="s-label">Avg Close</div>
                <div className="s-value">{tasks.data.summary.avg_days_to_close ?? "—"} d</div>
              </div>
            </div>
          ) : (
            <Loading label="Loading tasks…" />
          )}
        </SectionCard>

        <InsightPanel
          items={[
            <>
              <strong>{fmtMoney(k.revenue_at_risk)}</strong> is at risk right now — denied balances plus open
              claims past 60 days. The work queue orders it by recoverable value.
            </>,
            <>
              Appeals are working: <strong>{fmtMoney(k.total_recovered)}</strong> recovered at a{" "}
              <strong>{k.appeal_success_rate_pct}%</strong> success rate — unappealed denials are the leak.
            </>,
            <>
              <strong>{k.preventable_denial_rate_pct}%</strong> of denials are preventable (auth, eligibility,
              documentation) — the strongest case for front-end process fixes.
            </>,
          ]}
        />
      </div>
    </>
  );
}
