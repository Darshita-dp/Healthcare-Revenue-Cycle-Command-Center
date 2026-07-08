// Shared UI primitives: badges, KPI cards, loading / error / empty states,
// and a data-fetching hook used by every page.

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";

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
      <div className="big">⚠️</div>
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
      <div className="big">🗂️</div>
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
  return <span className={`badge ${STATUS_TONE[status] ?? "gray"}`}>{status}</span>;
}

const PRIORITY_TONE: Record<string, string> = {
  Urgent: "red",
  High: "amber",
  Medium: "blue",
  Low: "gray",
};

export function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return <span className="badge gray">—</span>;
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
  const tone = bucket === "90+" ? "red" : bucket === "61-90" ? "amber" : bucket === "31-60" ? "blue" : "gray";
  return <span className={`badge ${tone}`}>{bucket} days</span>;
}

// ---------------------------------------------------------------- KPI card
export function KpiCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "red" | "amber" | "green";
}) {
  return (
    <div className={`kpi-card${tone ? ` tone-${tone}` : ""}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}
