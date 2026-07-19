// Thin typed fetch wrapper for the FastAPI backend.
//
// API base URL resolution:
//   * In local dev the Vite proxy forwards /api and /health to the backend
//     (see vite.config.ts), so VITE_API_URL is left unset and requests use
//     same-origin relative paths.
//   * In a hosted deployment, set VITE_API_URL at build time to the
//     absolute URL of the deployed API (e.g. https://<name>.onrender.com).
//     Any trailing slash is stripped so that BASE + "/api/kpis" never
//     produces "//api/kpis".
//   * If VITE_API_URL is set but the fetch fails, we surface a stable
//     sentinel error code (API_UNREACHABLE) which the UI can translate
//     into a public-facing message.

import type {
  Aging, Alert, ClaimDetail, ClaimFilters, ClaimList, Health, Kpis,
  PayerScorecard, PriorityInsights, RecoverySimulator, TaskList,
} from "./types";

/** Sentinel error code for network-level failures — the UI keys off this
 *  to render a public-friendly message without leaking dev instructions. */
export const API_UNREACHABLE = "API_UNREACHABLE";

/** Normalize a configured API base:
 *   ""                           -> ""            (dev, same-origin proxy)
 *   "https://api.example.com"    -> as-is
 *   "https://api.example.com/"   -> trailing slash stripped
 *   "  https://x.com//  "        -> trimmed + normalized                */
function normalizeBase(raw: string | undefined): string {
  if (!raw) return "";
  return raw.trim().replace(/\/+$/, "");
}

const BASE = normalizeBase(import.meta.env.VITE_API_URL as string | undefined);

export class ApiError extends Error {
  constructor(message: string, public status?: number, public code?: string) {
    super(message);
  }
}

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
  // Ensure the path always starts with "/", so `BASE + path` never yields
  // "https://api.example.comapi/kpis" or "//api/kpis".
  const p = path.startsWith("/") ? path : `/${path}`;
  const target = BASE ? `${BASE}${p}` : p;
  const url = new URL(target, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

async function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const target = buildUrl(path, params);
  let resp: Response;
  try {
    resp = await fetch(target);
  } catch (netErr) {
    // Network layer failed — DNS, CORS, offline, backend cold-starting on
    // Render's free tier, etc. The UI decides how to word this; the client
    // only carries the sentinel code and (in dev only) the technical detail.
    const detail = netErr instanceof Error ? netErr.message : String(netErr);
    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      console.warn(`[api] fetch failed for ${target}:`, detail);
    }
    throw new ApiError("The demo API is temporarily unavailable.", undefined, API_UNREACHABLE);
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
  priorityInsights: () => get<PriorityInsights>("/api/priority-insights"),
  recoverySimulator: (params?: Record<string, number | undefined>) =>
    get<RecoverySimulator>("/api/recovery-simulator", params),
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
