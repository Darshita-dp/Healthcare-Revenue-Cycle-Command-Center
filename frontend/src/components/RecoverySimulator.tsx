import { useState } from "react";
import { api, fmtMoney } from "../api/client";
import { useFetch } from "./ui";
import { IconLightning, IconTarget } from "./Icons";
import type { RecoverySimulator as SimData } from "../api/types";

const CLAIM_COUNTS = [25, 50, 100];
const RECOVERY_RATES = [0.3, 0.4, 0.5];

const TIER_TONE: Record<string, string> = {
  Critical: "#e66767",
  High: "#eda100",
  Medium: "#5598e7",
  Low: "#9fb0ca",
  Monitor: "#7e93b8",
};

export default function RecoverySimulator() {
  const [claimCount, setClaimCount] = useState(50);
  const [rate, setRate] = useState(0.4);

  const sim = useFetch<SimData>(
    () => api.recoverySimulator({ claim_count: claimCount, recovery_rate: rate }),
    [claimCount, rate],
  );

  const maxTier = sim.data
    ? Math.max(1, ...sim.data.priority_tier_breakdown.map((t) => t.count))
    : 1;

  return (
    <div className="simulator">
      <div className="sim-head">
        <div>
          <div className="sim-title">
            <IconTarget size={19} />
            Revenue Recovery Simulator
          </div>
          <div className="sim-sub">
            Estimate potential recovery from working the highest-priority claims first. Ranking uses
            the explainable priority score; recovery rate is an adjustable planning assumption.
          </div>
        </div>
        <div className="sim-controls">
          <div className="sim-control">
            <div className="sc-label">Work top</div>
            <div className="seg">
              {CLAIM_COUNTS.map((n) => (
                <button key={n} className={n === claimCount ? "on" : ""} onClick={() => setClaimCount(n)}>
                  {n}
                </button>
              ))}
            </div>
          </div>
          <div className="sim-control">
            <div className="sc-label">Recovery rate</div>
            <div className="seg">
              {RECOVERY_RATES.map((r) => (
                <button key={r} className={r === rate ? "on" : ""} onClick={() => setRate(r)}>
                  {Math.round(r * 100)}%
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {sim.error && <div className="sim-interpretation">Could not load the simulator: {sim.error}</div>}

      {sim.data && (
        <>
          <div className="sim-body">
            <div>
              <div className="sim-headline">
                <div className="sh-label">Estimated recoverable revenue</div>
                <div className="sh-value">{fmtMoney(sim.data.estimated_recoverable_revenue)}</div>
                <div className="sh-context">
                  {Math.round(sim.data.recovery_rate * 100)}% of a{" "}
                  {fmtMoney(sim.data.potential_recovery_base)} at-risk base across{" "}
                  {sim.data.selected_claim_count} claims
                </div>
              </div>
              <div className="sim-metrics">
                <div className="sim-metric">
                  <div className="sm-label">Potential recovery base</div>
                  <div className="sm-value">{fmtMoney(sim.data.potential_recovery_base)}</div>
                </div>
                <div className="sim-metric">
                  <div className="sm-label">Claims worked</div>
                  <div className="sm-value">{sim.data.selected_claim_count}</div>
                </div>
                <div className="sim-metric">
                  <div className="sm-label">Outstanding in set</div>
                  <div className="sm-value">{fmtMoney(sim.data.total_outstanding_amount)}</div>
                </div>
                <div className="sim-metric">
                  <div className="sm-label">Avg priority score</div>
                  <div className="sm-value">{sim.data.average_priority_score}</div>
                </div>
              </div>
            </div>

            <div>
              <div className="sim-panel" style={{ marginBottom: 12 }}>
                <h4>Workload by priority tier</h4>
                {sim.data.priority_tier_breakdown
                  .filter((t) => t.count > 0)
                  .map((t) => (
                    <div className="sim-tier-row" key={t.tier}>
                      <span className="st-name">{t.tier}</span>
                      <span className="st-track">
                        <span
                          className="score-fill"
                          style={{
                            width: `${(t.count / maxTier) * 100}%`,
                            background: TIER_TONE[t.tier],
                            display: "block",
                            height: "100%",
                          }}
                        />
                      </span>
                      <span className="st-count">{t.count}</span>
                    </div>
                  ))}
              </div>
              <div className="sim-panel">
                <h4>Top recovery drivers</h4>
                {sim.data.top_driver_breakdown.slice(0, 5).map((d) => (
                  <div className="sim-driver" key={d.category}>
                    <span>{d.label}</span>
                    <span className="sd-count">{d.claims}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="sim-interpretation">
            <IconLightning size={13} /> {sim.data.interpretation}
          </div>
          <div className="sim-note">
            Planning estimate only — recovery rate is a user-set assumption applied to at-risk balances,
            not a guaranteed collection. Built on synthetic data.
          </div>
        </>
      )}
    </div>
  );
}
