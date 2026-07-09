import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, fmtMoney, fmtNum } from "../api/client";
import {
  AgingBadge, EmptyState, ErrorState, Filter, FilterBar, Loading, PageHeader, ScorePill,
  StatusBadge, SummaryStrip, TierBadge, useFetch,
} from "../components/ui";
import { IconSearch } from "../components/Icons";
import type { ClaimFilters, ClaimList } from "../api/types";

const PAGE_SIZE = 25;

interface Filters {
  payer: string;
  status: string;
  aging_bucket: string;
  denial_reason: string;
  priority: string;
  tier: string;
  facility: string;
  search: string;
  sort: string;
}

const EMPTY_FILTERS: Filters = {
  payer: "", status: "", aging_bucket: "", denial_reason: "",
  priority: "", tier: "", facility: "", search: "", sort: "priority",
};

export default function ClaimsQueue() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [filters, setFilters] = useState<Filters>({
    ...EMPTY_FILTERS,
    aging_bucket: params.get("aging") ?? "",
    status: params.get("status") ?? "",
    tier: params.get("tier") ?? "",
  });
  const [page, setPage] = useState(0);

  const options = useFetch<ClaimFilters>(() => api.claimFilters());
  const claims = useFetch<ClaimList>(
    () => api.claims({ ...filters, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    [filters, page],
  );

  // Companion counts within the same filter slice (cheap: limit=1 requests)
  const denied = useFetch<ClaimList>(
    () => api.claims({ ...filters, status: "Denied", limit: 1 }), [filters]);
  const over90 = useFetch<ClaimList>(
    () => api.claims({ ...filters, aging_bucket: "90+", open_only: "true", limit: 1 }), [filters]);
  const critical = useFetch<ClaimList>(
    () => api.claims({ ...filters, tier: "Critical", limit: 1 }), [filters]);
  const highTier = useFetch<ClaimList>(
    () => api.claims({ ...filters, tier: "High", limit: 1 }), [filters]);

  const set = (key: keyof Filters) => (e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) => {
    setFilters((f) => ({ ...f, [key]: e.target.value }));
    setPage(0);
  };

  const activeFilters = Object.entries(filters).filter(
    ([k, v]) => v !== "" && !(k === "sort" && v === "priority"),
  ).length;

  const criticalHigh =
    critical.data && highTier.data ? critical.data.total + highTier.data.total : null;

  return (
    <>
      <PageHeader
        title="Claims Work Queue"
        subtitle="The operational workbench — priority-sorted so urgent tasks and the largest recoverable dollars surface first. Click any row for the full case record."
      />

      <SummaryStrip
        cells={[
          { label: "Claims in view", value: claims.data ? fmtNum(claims.data.total) : "…" },
          {
            label: "Critical + High",
            value: criticalHigh === null ? "…" : fmtNum(criticalHigh),
            tone: "amber",
          },
          { label: "Denied", value: denied.data ? fmtNum(denied.data.total) : "…", tone: "red" },
          { label: "Open · aged 90+", value: over90.data ? fmtNum(over90.data.total) : "…", tone: "red" },
        ]}
      />

      <FilterBar>
        <Filter label="Search claim ID">
          <span className="search-box">
            <IconSearch size={14} />
            <input type="text" placeholder="CLM-000123" value={filters.search} onChange={set("search")} />
          </span>
        </Filter>
        <Filter label="Payer">
          <select value={filters.payer} onChange={set("payer")}>
            <option value="">All payers</option>
            {options.data?.payers.map((p) => <option key={p}>{p}</option>)}
          </select>
        </Filter>
        <Filter label="Status">
          <select value={filters.status} onChange={set("status")}>
            <option value="">All statuses</option>
            {options.data?.statuses.map((s) => <option key={s}>{s}</option>)}
          </select>
        </Filter>
        <Filter label="Aging">
          <select value={filters.aging_bucket} onChange={set("aging_bucket")}>
            <option value="">All ages</option>
            {options.data?.aging_buckets.map((b) => <option key={b}>{b}</option>)}
          </select>
        </Filter>
        <Filter label="Denial reason">
          <select value={filters.denial_reason} onChange={set("denial_reason")}>
            <option value="">All reasons</option>
            {options.data?.denial_reasons.map((r) => <option key={r}>{r}</option>)}
          </select>
        </Filter>
        <Filter label="Priority tier">
          <select value={filters.tier} onChange={set("tier")}>
            <option value="">All tiers</option>
            {options.data?.tiers.map((t) => <option key={t}>{t}</option>)}
          </select>
        </Filter>
        <Filter label="Queue priority">
          <select value={filters.priority} onChange={set("priority")}>
            <option value="">All priorities</option>
            {options.data?.priorities.map((p) => <option key={p}>{p}</option>)}
          </select>
        </Filter>
        <Filter label="Facility">
          <select value={filters.facility} onChange={set("facility")}>
            <option value="">All facilities</option>
            {options.data?.facilities.map((f) => <option key={f}>{f}</option>)}
          </select>
        </Filter>
        <Filter label="Sort by">
          <select value={filters.sort} onChange={set("sort")}>
            <option value="priority">Priority score</option>
            <option value="age">Claim age</option>
            <option value="amount">Outstanding $</option>
          </select>
        </Filter>
        {activeFilters > 0 && (
          <button
            className="btn"
            onClick={() => {
              setFilters(EMPTY_FILTERS);
              setPage(0);
            }}
          >
            Clear ({activeFilters})
          </button>
        )}
      </FilterBar>

      {claims.loading && <Loading label="Loading claims…" />}
      {claims.error && <ErrorState message={claims.error} />}
      {claims.data && claims.data.items.length === 0 && (
        <EmptyState
          title="No claims match these filters"
          hint="Try clearing a filter — or celebrate: this slice of the queue is clean."
        />
      )}

      {claims.data && claims.data.items.length > 0 && (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Claim</th>
                  <th>Payer</th>
                  <th className="num">Outstanding</th>
                  <th>Status</th>
                  <th>Age</th>
                  <th style={{ minWidth: 120 }}>Priority</th>
                  <th>Why / Action</th>
                </tr>
              </thead>
              <tbody>
                {claims.data.items.map((c) => {
                  const highRisk = c.priority_tier === "Critical";
                  const warn = c.priority_tier === "High";
                  return (
                    <tr
                      key={c.claim_id}
                      className={`clickable${highRisk ? " risk-row" : warn ? " warn-row" : ""}`}
                      onClick={() => navigate(`/claims/${c.claim_id}`)}
                    >
                      <td>
                        <span className="mono" style={{ fontWeight: 650, color: "var(--primary)" }}>
                          {c.claim_id}
                        </span>
                        {c.is_high_value && (
                          <span className="badge purple" style={{ marginLeft: 6 }}>
                            High value
                          </span>
                        )}
                        <div className="cell-sub">{c.service_line_name} · {c.facility_name}</div>
                      </td>
                      <td>
                        <div className="cell-main" style={{ fontWeight: 550 }}>{c.payer_name}</div>
                        <div className="cell-sub">{c.payer_type}</div>
                      </td>
                      <td className="num">
                        <strong>{fmtMoney(c.outstanding_amount)}</strong>
                      </td>
                      <td><StatusBadge status={c.claim_status} /></td>
                      <td><AgingBadge bucket={c.aging_bucket} /></td>
                      <td>
                        <ScorePill score={c.priority_score} tier={c.priority_tier} />
                        <div style={{ marginTop: 5 }}>
                          <TierBadge tier={c.priority_tier} />
                        </div>
                      </td>
                      <td style={{ fontSize: 12.5, color: "var(--text-dim)", maxWidth: 240 }}>
                        {c.priority_top_driver ? (
                          <span className="cell-main" style={{ fontWeight: 550, color: "var(--text)" }}>
                            {c.priority_top_driver}
                          </span>
                        ) : (
                          <span style={{ color: "var(--text-faint)" }}>No active risk factors</span>
                        )}
                        {c.action_needed && <div className="cell-sub">{c.action_needed}</div>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="pagination">
            <span>
              {fmtNum(page * PAGE_SIZE + 1)}–{fmtNum(Math.min((page + 1) * PAGE_SIZE, claims.data.total))} of{" "}
              {fmtNum(claims.data.total)} claims
            </span>
            <button className="btn" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              ← Prev
            </button>
            <button
              className="btn"
              disabled={(page + 1) * PAGE_SIZE >= claims.data.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next →
            </button>
          </div>
        </>
      )}
    </>
  );
}
