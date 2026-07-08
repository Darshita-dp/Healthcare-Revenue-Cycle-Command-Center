// Thin fetch wrapper + typed endpoint functions.
// In dev, Vite proxies /api and /health to FastAPI on :8000 (vite.config.ts).
// Set VITE_API_URL to point somewhere else (e.g. a deployed API).

import type {
  Aging, Alert, ClaimDetail, ClaimFilters, ClaimList, Health, Kpis,
  PayerScorecard, TaskList,
} from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

async function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
    }
  }
  let resp: Response;
  try {
    resp = await fetch(url.toString());
  } catch {
    throw new ApiError(
      "Cannot reach the API. Start it with `uvicorn api.main:app --reload` from the repository root.",
    );
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      detail = (await resp.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, resp.status);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  health: () => get<Health>("/health"),
  kpis: () => get<Kpis>("/api/kpis"),
  claims: (params?: Record<string, string | number | undefined>) =>
    get<ClaimList>("/api/claims", params),
  claimFilters: () => get<ClaimFilters>("/api/claims/filters"),
  claim: (id: string) => get<ClaimDetail>(`/api/claims/${id}`),
  payers: () => get<PayerScorecard[]>("/api/payers"),
  payer: (id: number) => get<PayerScorecard>(`/api/payers/${id}`),
  tasks: (params?: Record<string, string | number | boolean | undefined>) =>
    get<TaskList>("/api/tasks", params),
  aging: () => get<Aging>("/api/aging"),
  alerts: () => get<Alert[]>("/api/alerts"),
};

export const fmtMoney = (n: number | null | undefined): string =>
  n == null
    ? "—"
    : n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export const fmtMoneyFull = (n: number | null | undefined): string =>
  n == null
    ? "—"
    : n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

export const fmtNum = (n: number | null | undefined): string =>
  n == null ? "—" : n.toLocaleString("en-US");

export const fmtDate = (d: string | null | undefined): string =>
  d ? new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" }) : "—";
