# Automation Rules — Follow-Up Task & Alert Engine

The rules engine ([generate_followup_tasks.py](generate_followup_tasks.py)) reads the processed dataset and converts analytics into **work**: claim-level follow-up tasks routed to the right team, and payer-level escalation alerts. It is the piece that turns a dashboard into an operations tool.

**Idempotency:** tasks are deduplicated on `(claim_id, task_type)` — one task per rule per claim, no matter how many times the engine runs. The run is fully deterministic (seeded), so outputs are reproducible.

**Due-date SLAs by priority:** Urgent = 2 days, High = 5, Medium = 10, Low = 15 (from task creation).

---

## Rule 1 — High-Value Denial

| | |
|---|---|
| **Condition** | Claim is denied, still unresolved, and denied amount > **$5,000** |
| **Action** | Create task **"Review high-value denied claim"** |
| **Priority** | High |
| **Assigned team** | Denials Team |
| **Why** | A small number of high-dollar denials usually carries most of the recoverable money. These must never sit in a generic queue. |

## Rule 2 — A/R Aging Risk

| | |
|---|---|
| **Condition** | Claim is open, outstanding amount > **$1,000**, claim age > **60 days** |
| **Action** | Create task **"Follow up on aging A/R claim"** |
| **Priority** | Medium; escalates to **High** past 90 days |
| **Assigned team** | AR Follow-up Team |
| **Why** | Collectability decays sharply with age — industry rule of thumb is that claims older than 120 days collect at less than half the rate of fresh claims. |

## Rule 3 — Missing Documentation

| | |
|---|---|
| **Condition** | Open denial with denial category = **Missing documentation** |
| **Action** | Create task **"Request missing documentation"** |
| **Priority** | Medium |
| **Assigned team** | Documentation Team |
| **Why** | These denials are highly recoverable — the service was payable; only paperwork is missing. Fast turnaround converts them at a high rate. |

## Rule 4 — Payer Escalation (alert, not a task)

| | |
|---|---|
| **Condition** | Payer's overall denial rate > **20%** |
| **Action** | Create alert **"Payer denial rate above threshold"** in [sample_alert_output.csv](sample_alert_output.csv) |
| **Audience** | Payer relations / managed care leadership |
| **Why** | A payer denying one in five claims is a contract-level problem, not a claim-level one. The alert includes claim counts, denial rate, and denied outstanding dollars to support the escalation conversation. |

## Rule 5 — Appeal Deadline Approaching

| | |
|---|---|
| **Condition** | Denial older than **20 days**, appeal status = Not Appealed, claim still open |
| **Action** | Create task **"Appeal deadline approaching"** |
| **Priority** | **Urgent** |
| **Assigned team** | Appeals Team |
| **Why** | Most payers enforce 30–90 day appeal windows. A missed window converts a recoverable denial into a guaranteed write-off — this is the most time-critical rule in the engine. |

---

## Outputs

| File | Contents |
|---|---|
| `data/processed/fact_followup_tasks.csv` | Claim-level tasks (task_id, claim_id, type, priority, team, created/due dates, status, reason) |
| `automation/sample_alert_output.csv` | Payer-level escalation alerts with supporting metrics |

## Running

```bash
python automation/generate_followup_tasks.py
```

Requires `data/processed/` to exist (`python etl/run_pipeline.py` first).

## Extending

Each rule is a self-contained block in `build_tasks()`. To add a rule: filter the relevant dataframe, append candidate dicts with `claim_id`, `task_type`, `priority`, `assigned_team`, `reason` — dedup, ID assignment, and SLA due dates are handled centrally. Thresholds live as module constants so they can be tuned (or externalized to config) without touching rule logic.
