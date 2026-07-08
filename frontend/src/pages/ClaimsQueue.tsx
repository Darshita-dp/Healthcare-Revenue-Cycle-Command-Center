import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtMoney, fmtNum } from "../api/client";
import {
  AgingBadge, EmptyState, ErrorState, Loading, PriorityBadge, StatusBadge, useFetch,
} from "../components/ui";
import type { ClaimFilters, ClaimList } from "../api/types";

const PAGE_SIZE = 25;

interface Filters {
  payer: string;
  status: string;
  aging_bucket: string;
  denial_reason: string;
  priority: string;
  facility: string;
  search: string;
  sort: string;
}

const EMPTY_FILTERS: Filters = {
  payer: "", status: "", aging_bucket: "", denial_reason: "",
  priority: "", facility: "", search: "", sort: "priority",
};

export default function ClaimsQueue() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(0);

  const options = useFetch<ClaimFilters>(() => api.claimFilters());
  const claims = useFetch<ClaimList>(
    () => api.claims({ ...filters, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    [filters, page],
  );

  const set = (key: keyof Filters) => (e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) => {
    setFilters((f) => ({ ...f, [key]: e.target.value }));
    setPage(0);
  };

  const activeFilters = Object.entries(filters).filter(
    ([k, v]) => v !== "" && !(k === "sort" && v === "priority"),
  ).length;

  return (
    <>
      <div className="page-header">
        <h1>Claims Work Queue</h1>
        <div className="desc">
          Priority-sorted worklist — urgent tasks and the largest dollars first. Click a row for full detail.
        </div>
      </div>

      <div className="filter-bar">
        <div className="filter">
          <label>Search claim ID</label>
          <input type="text" placeholder="CLM-000123" value={filters.search} onChange={set("search")} />
        </div>
        <div className="filter">
          <label>Payer</label>
          <select value={filters.payer} onChange={set("payer")}>
            <option value="">All payers</option>
            {options.data?.payers.map((p) => <option key={p}>{p}</option>)}
          </select>
        </div>
        <div className="filter">
          <label>Status</label>
          <select value={filters.status} onChange={set("status")}>
            <option value="">All statuses</option>
            {options.data?.statuses.map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div className="filter">
          <label>Aging</label>
          <select value={filters.aging_bucket} onChange={set("aging_bucket")}>
            <option value="">All ages</option>
            {options.data?.aging_buckets.map((b) => <option key={b}>{b}</option>)}
          </select>
        </div>
        <div className="filter">
          <label>Denial reason</label>
          <select value={filters.denial_reason} onChange={set("denial_reason")}>
            <option value="">All reasons</option>
            {options.data?.denial_reasons.map((r) => <option key={r}>{r}</option>)}
          </select>
        </div>
        <div className="filter">
          <label>Priority</label>
          <select value={filters.priority} onChange={set("priority")}>
            <option value="">All priorities</option>
            {options.data?.priorities.map((p) => <option key={p}>{p}</option>)}
          </select>
        </div>
        <div className="filter">
          <label>Facility</label>
          <select value={filters.facility} onChange={set("facility")}>
            <option value="">All facilities</option>
            {options.data?.facilities.map((f) => <option key={f}>{f}</option>)}
          </select>
        </div>
        <div className="filter">
          <label>Sort by</label>
          <select value={filters.sort} onChange={set("sort")}>
            <option value="priority">Priority</option>
            <option value="age">Claim age</option>
            <option value="amount">Outstanding $</option>
          </select>
        </div>
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
      </div>

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
                  <th>Facility</th>
                  <th className="num">Billed</th>
                  <th className="num">Outstanding</th>
                  <th>Status</th>
                  <th>Denial Reason</th>
                  <th>Age</th>
                  <th>Priority</th>
                  <th>Action Needed</th>
                </tr>
              </thead>
              <tbody>
                {claims.data.items.map((c) => {
                  const highRisk =
                    c.task_priority === "Urgent" || (c.aging_bucket === "90+" && c.outstanding_amount > 5000);
                  return (
                    <tr
                      key={c.claim_id}
                      className={`clickable${highRisk ? " risk-row" : ""}`}
                      onClick={() => navigate(`/claims/${c.claim_id}`)}
                    >
                      <td>
                        <span className="mono">{c.claim_id}</span>
                        {c.is_high_value && (
                          <span className="badge purple" style={{ marginLeft: 6 }}>
                            High value
                          </span>
                        )}
                      </td>
                      <td>{c.payer_name}</td>
                      <td style={{ maxWidth: 170, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {c.facility_name}
                      </td>
                      <td className="num">{fmtMoney(c.billed_amount)}</td>
                      <td className="num">
                        <strong>{fmtMoney(c.outstanding_amount)}</strong>
                      </td>
                      <td>
                        <StatusBadge status={c.claim_status} />
                      </td>
                      <td>{c.denial_category ?? "—"}</td>
                      <td>
                        <AgingBadge bucket={c.aging_bucket} />
                      </td>
                      <td>
                        <PriorityBadge priority={c.task_priority} />
                      </td>
                      <td style={{ fontSize: 12.5, color: "var(--text-dim)" }}>{c.action_needed ?? "—"}</td>
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
