// Shared UI system: data hook, page scaffolding, cards, badges, states.

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { IconAlert, IconArrowRight, IconFolder, IconLightning } from "./Icons";

// ---------------------------------------------------------------- useFetch
export function useFetch<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fn().then(
      (d) => {
        if (!cancelled) {
          setData(d);
          setLoading(false);
        }
      },
      (e: unknown) => {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : "Unexpected error loading data.");
          setLoading(false);
        }
      },
    );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => load(), [load]);
  return { data, error, loading, reload: load };
}

// -------------------------------------------------------------- PageHeader
export function PageHeader({
  title,
  subtitle,
  meta,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  meta?: React.ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <div className="desc">{subtitle}</div>}
      </div>
      {meta && <div className="header-meta">{meta}</div>}
    </div>
  );
}

// ------------------------------------------------------------- SectionCard
export function SectionCard({
  title,
  sub,
  action,
  children,
  style,
}: {
  title: React.ReactNode;
  sub?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div className="card" style={style}>
      <div className="card-head">
        <div>
          <h3>{title}</h3>
          {sub && <div className="card-sub">{sub}</div>}
        </div>
        {action && <div className="card-action">{action}</div>}
      </div>
      {children}
    </div>
  );
}

// -------------------------------------------------------------- MetricCard
export type Tone = "blue" | "green" | "amber" | "red" | "teal";

export function MetricCard({
  label,
  value,
  context,
  icon,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  context?: React.ReactNode;
  icon?: React.ReactNode;
  tone?: Tone;
}) {
  return (
    <div className={`metric-card${tone ? ` tone-${tone}` : ""}`}>
      <div className="metric-top">
        <div className="metric-label">{label}</div>
        {icon && <div className="metric-icon">{icon}</div>}
      </div>
      <div className="metric-value">{value}</div>
      {context && <div className="metric-context">{context}</div>}
    </div>
  );
}

// ------------------------------------------------------------ InsightPanel
export function InsightPanel({
  title = "What the data says",
  items,
}: {
  title?: string;
  items: React.ReactNode[];
}) {
  return (
    <div className="insight-panel">
      <h3>
        <IconLightning size={14} />
        {title}
      </h3>
      <ul className="insight-list">
        {items.map((item, i) => (
          <li key={i}>
            <span className="i-icon" style={{ color: "var(--primary)" }}>
              <IconArrowRight size={13} />
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// --------------------------------------------------------------- FilterBar
export function FilterBar({ sticky = true, children }: { sticky?: boolean; children: React.ReactNode }) {
  return (
    <div className="filter-panel" style={sticky ? undefined : { position: "static" }}>
      <div className="filter-bar">{children}</div>
    </div>
  );
}

export function Filter({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="filter">
      <label>{label}</label>
      {children}
    </div>
  );
}

// ------------------------------------------------------------ SummaryStrip
export function SummaryStrip({
  cells,
}: {
  cells: { label: string; value: React.ReactNode; tone?: "red" | "amber" | "green" }[];
}) {
  return (
    <div className="summary-strip">
      {cells.map((c) => (
        <div className="summary-cell" key={c.label}>
          <div className="s-label">{c.label}</div>
          <div className={`s-value${c.tone ? ` ${c.tone}` : ""}`}>{c.value}</div>
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ states
export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="state-box">
      <div className="spinner" />
      {label}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  const isConn = message.includes("Cannot reach");
  return (
    <div className="state-box">
      <div className="state-icon" style={{ background: "var(--red-soft)", color: "var(--red)" }}>
        <IconAlert size={24} />
      </div>
      <h3>{isConn ? "API not reachable" : "Something went wrong"}</h3>
      <p>{message}</p>
      {isConn && (
        <p>
          From the repository root run <code>uvicorn api.main:app --reload</code>, then refresh.
        </p>
      )}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="state-box">
      <div className="state-icon">
        <IconFolder size={24} />
      </div>
      <h3>{title}</h3>
      {hint && <p>{hint}</p>}
    </div>
  );
}

// ------------------------------------------------------------------ badges
const STATUS_TONE: Record<string, string> = {
  Paid: "green",
  Closed: "gray",
  Denied: "red",
  Appealed: "purple",
  "Partially Paid": "amber",
  "Under Review": "blue",
  Submitted: "blue",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${STATUS_TONE[status] ?? "gray"}`}>
      <span className="dot" />
      {status}
    </span>
  );
}

const PRIORITY_TONE: Record<string, string> = {
  Urgent: "red",
  High: "amber",
  Medium: "blue",
  Low: "gray",
};

export function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return <span style={{ color: "var(--text-faint)" }}>—</span>;
  return (
    <span className={`badge ${PRIORITY_TONE[priority] ?? "gray"}`}>
      <span className="dot" />
      {priority}
    </span>
  );
}

const TASK_STATUS_TONE: Record<string, string> = {
  Open: "blue",
  "In Progress": "amber",
  Completed: "green",
  Cancelled: "gray",
};

export function TaskStatusBadge({ status }: { status: string }) {
  return <span className={`badge ${TASK_STATUS_TONE[status] ?? "gray"}`}>{status}</span>;
}

export function AgingBadge({ bucket }: { bucket: string }) {
  const tone =
    bucket === "90+" ? "red" : bucket === "61-90" ? "amber" : bucket === "31-60" ? "blue" : "gray";
  return <span className={`badge ${tone}`}>{bucket} d</span>;
}

// ------------------------------------------------------------------ fields
export function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="field">
      <div className="f-label">{label}</div>
      <div className="f-value">{value}</div>
    </div>
  );
}

// --------------------------------------------------------------- priority UI
const TIER_TONE: Record<string, string> = {
  Critical: "red",
  High: "amber",
  Medium: "blue",
  Low: "gray",
  Monitor: "gray",
};

export function tierTone(tier: string): string {
  return TIER_TONE[tier] ?? "gray";
}

export function TierBadge({ tier }: { tier: string }) {
  return (
    <span className={`badge ${tierTone(tier)}`}>
      <span className="dot" />
      {tier}
    </span>
  );
}

/** Compact score chip with a fill bar — used in table cells. */
export function ScorePill({ score, tier }: { score: number; tier: string }) {
  const tone = tierTone(tier);
  return (
    <div className="score-pill" title={`${tier} · ${score}/100`}>
      <span className={`score-num tone-${tone}`}>{score}</span>
      <span className="score-track">
        <span className={`score-fill tone-${tone}`} style={{ width: `${score}%` }} />
      </span>
    </div>
  );
}

/** Large score meter for the claim detail page. */
export function ScoreMeter({ score, tier }: { score: number; tier: string }) {
  const tone = tierTone(tier);
  return (
    <div className="score-meter">
      <div className={`score-meter-value tone-${tone}`}>
        {score}
        <span className="score-meter-max">/100</span>
      </div>
      <div className="score-meter-track">
        <span className={`score-fill tone-${tone}`} style={{ width: `${score}%` }} />
      </div>
      <div style={{ marginTop: 8 }}>
        <TierBadge tier={tier} />
      </div>
    </div>
  );
}

export function DriverList({ drivers }: { drivers: { label: string; points: number }[] }) {
  if (drivers.length === 0) {
    return (
      <p style={{ color: "var(--text-dim)", fontSize: 13, margin: 0 }}>
        No active risk factors — this claim is resolved or within normal timelines.
      </p>
    );
  }
  return (
    <ul className="driver-list">
      {drivers.map((d, i) => (
        <li key={i}>
          <span className="driver-label">{d.label}</span>
          <span className="driver-points">+{d.points}</span>
        </li>
      ))}
    </ul>
  );
}
