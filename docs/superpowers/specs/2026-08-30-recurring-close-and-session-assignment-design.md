# Recurring Close and Session Assignment Design

**Status:** approved for planning

**Date:** 30 August 2026

**Problem frame:** [../../product/problem-frame.md](../../product/problem-frame.md)

**PRD:** [../../product/prd.md](../../product/prd.md)

**Parent design:** [2026-08-29-demo-first-operational-platform-design.md](2026-08-29-demo-first-operational-platform-design.md)

## 1. Purpose

This increment turns the current import-to-dashboard demonstration into a reusable monthly operation. It removes two false signals from the product:

1. importing a file currently ends without a clear next action; and
2. the sidebar currently looks like a one-time stepper even though managers repeat imports and monthly closes.

It also replaces the broken `Review pending item` destination with a real, auditable session-assignment workflow. The manager will be able to identify the condominium unit responsible for an imported charging session, record why the assignment was made and continue the monthly close.

## 2. Product decisions

### 2.1 Navigation is permanent; progress is period-scoped

The sidebar is application navigation, not progress. It will no longer use a vertical connector, circular step nodes or completed-step semantics.

The first implemented navigation contains only working destinations:

- `Overview` at `/dashboard`;
- `Sessions` at `/sessions`;
- `Data sources` at `/settings/data-sources`.

`Residents and costs`, `Insights` and `Invoices` will appear when their routes support a usable product flow. The primary navigation section is labeled `Operation`; `Data sources` remains under `Settings`.

Monthly-close progress belongs inside the dashboard and is scoped to the selected site and period. Importing another file does not restart global navigation. It adds a batch, updates the open period and recomputes its readiness. A new period receives its own state.

### 2.2 Post-import success has a next action

After a successful confirmation, the confirmation panel is replaced rather than relabeled. The success state shows:

- imported filename;
- number of sessions created;
- invalid and duplicate counts;
- selected or inferred period;
- a concise explanation of what still requires attention.

The primary action is `Continue close` and routes to `/dashboard`. The dashboard determines the next unresolved action. The secondary action is `Import another file` and resets only the upload workflow. Import history remains visible as provenance evidence.

The stale `Confirmation required` copy and the `Import again` action are never shown after a successful confirmation.

### 2.3 The dashboard routes pending work to Sessions

The dashboard attention card links to `/sessions?status=pending_review&period=<period>`. It never sends an identity or anomaly task back to `Data sources`.

The action copy is contextual:

- unknown assignments: `Review N pending sessions`;
- critical analytical flags: `Review AI opinion`;
- no blockers: `Review costs`.

Only the assignment route is delivered by this increment. Analytical and cost destinations retain their approved future behavior and will be enabled when those capabilities exist.

### 2.4 Financial responsibility belongs to a unit

An assignment links a charging session to a condominium unit. The resident or billing contact is displayed through the unit's active membership, but the durable financial relationship remains the unit.

This avoids rewriting historical billing attribution when residents change. The interface may display both unit and resident, but `unit_id` is the required assignment target.

The raw SEMS+ `Card ID` is evidence only. It must not be interpreted as a confirmed person or unit because the observed value can repeat the charger serial. A session remains `unknown` until an explicit assignment exists or a future trusted identity adapter provides confirmed evidence.

## 3. Manager workflow

### 3.1 Import completion

1. The manager confirms a valid SEMS+ preview.
2. The API persists the batch, raw rows and canonical sessions idempotently.
3. The page presents `Import complete` with the batch result.
4. The manager chooses `Continue close` or `Import another file`.
5. `Continue close` returns to the dashboard, where the imported data and blockers are visible.

### 3.2 Resolve a pending assignment

1. The manager chooses `Review N pending sessions` on the dashboard.
2. `/sessions` opens with the current period and `pending_review` filter.
3. Each row shows observed start and end times, duration, energy, charger, source provenance and identity status.
4. The manager selects a session.
5. The assignment panel shows the immutable observed data and a unit selector with the current resident or billing contact.
6. The manager selects a unit and enters a short justification.
7. `Assign and review next` creates the assignment and audit event in one transaction.
8. The queue advances to the next pending session. The manager may return to the dashboard at any time.
9. The dashboard reads canonical assignment state, recalculates coverage and costs, and changes its next action when the queue is empty.

### 3.3 Repeat the operation

- A different file creates another import batch and contributes new sessions to the appropriate open period.
- Reimporting the same file remains idempotent and creates no duplicate sessions.
- Resolving one assignment does not hide other unresolved sessions.
- A new calendar period starts with independent readiness and assignment coverage.
- A future closed-period policy will prevent late data from silently changing issued invoices. Reopening or correction is outside this increment.

## 4. Application and domain boundaries

The new `sessions` module follows the existing modular-monolith and ports-and-adapters conventions:

```text
modules/sessions/
├── domain/
│   ├── session_assignment.py
│   └── errors.py
├── application/
│   ├── list_sessions.py
│   ├── list_assignment_units.py
│   ├── assign_session.py
│   └── ports.py
├── infrastructure/
│   └── repository.py
└── presentation/
    ├── router.py
    └── schemas.py
```

The ingestion module remains responsible for creating canonical sessions. The sessions module owns operational review and assignment. Dashboard queries consume canonical sessions and assignments rather than deriving identity from raw import payloads.

The domain operation accepts:

- scoped organization and actor;
- session identifier;
- unit identifier;
- non-empty justification;
- current time supplied by the application boundary.

It produces the current assignment and an audit description. It cannot alter observed energy, time, charger, source, batch or raw record.

## 5. Persistent model

A migration adds `session_assignments`:

| Field | Rule |
|---|---|
| `id` | UUID primary key |
| `organization_id` | Required tenant scope |
| `charging_session_id` | Required and unique per organization |
| `unit_id` | Required assignment target |
| `assigned_by` | Required manager profile |
| `justification` | Required explanatory text |
| `created_at`, `updated_at` | Auditable timestamps |

The table stores the current assignment. A reassignment updates this operational record inside a transaction and appends an immutable `audit_events` row containing the previous unit, new unit and justification. This avoids multiple active assignments while preserving change history.

Foreign keys and repository queries enforce organization scope. A session or unit from another organization behaves as not found.

When an assignment is created:

- `charging_sessions.identity_confidence` changes from `unknown` to `assigned`;
- `charging_sessions.status` changes from `pending_review` to `ready`, unless another blocking status applies;
- an `AuditEvent` with type `session_assigned` is appended.

Measured columns remain immutable.

## 6. API contract

The initial REST surface is:

### `GET /v1/sessions`

Filters:

- `period` as `YYYY-MM`;
- `status` such as `pending_review` or `ready`;
- optional `siteId`.

Each item includes canonical measurements, provenance, identity confidence, current unit and display contact when assigned. Raw import payloads are not returned as the session model.

### `GET /v1/assignment-units`

Returns units in the current organization with code, display name and active resident or billing-contact label. It does not expose unrelated profile data.

### `PUT /v1/sessions/{sessionId}/assignment`

Request:

```json
{
  "unitId": "uuid",
  "justification": "Confirmed by the condominium manager"
}
```

The operation is organization-scoped, requires the manager role and returns the updated assignment view. Repeating the same unit and justification is idempotent. Changing the unit records an audited reassignment.

All endpoints use the existing structured error envelope and generated TypeScript client.

## 7. Web experience

### 7.1 Sessions list and review

`/sessions` is a real navigation destination. Its default view uses the latest active period and shows a visible filter summary. The empty state distinguishes:

- no imported sessions;
- no sessions matching the filter;
- all sessions assigned.

The assignment interaction is a master-detail layout on desktop and a list-to-detail flow on mobile. The selected session keeps its observed evidence visible while the manager chooses the unit.

Primary action: `Assign and review next`.

Secondary actions: `Save assignment` and `Return to overview`.

Success feedback states which unit received the session and how many pending sessions remain.

### 7.2 Dashboard and import handoff

The import page returns the manager to the dashboard after confirmation. The dashboard is the orchestration surface; it routes the manager to the first unresolved operational task. The sessions page performs the assignment. This keeps upload subordinate to the product problem.

### 7.3 Navigation styling

The sidebar removes connector lines and progress dots. The active route uses a compact cyan rail or background treatment. Disabled pseudo-links are removed. Navigation remains stable after a period is closed.

## 8. Error and concurrency behavior

- Missing or unauthorized session or unit: `404` without revealing cross-tenant existence.
- Empty justification: `422` with a field-level error.
- Session already billed or period closed: `409` with an actionable message; enforcement becomes active with billing-period persistence.
- Concurrent reassignment: repository update uses the current row transactionally and returns the committed assignment.
- Import success followed by dashboard-load failure: import remains committed; the success state offers a retry link without reconfirming the file.
- No active resident on a unit: the unit remains assignable and displays `No active resident`; billing responsibility still belongs to the unit.

## 9. AI handoff

This increment does not pretend that assignment itself is AI. It creates the trustworthy identity input required by the approved hybrid and explainable closing opinion.

After assignments and analytical modules exist, the dashboard opinion will combine deterministic billing facts with anomaly, forecast and segmentation results. The AI produces evidence and a recommendation; the manager resolves exceptions and approves the close.

## 10. Testing strategy

### Domain and application

- assigning a session to a unit produces `assigned` confidence and `ready` status;
- observed measurement fields cannot be changed by assignment;
- justification is required;
- reassignment records previous and new units;
- same assignment request is idempotent;
- cross-organization session and unit are rejected as not found.

### Persistence and migration

- migration upgrades and downgrades on SQLite and PostgreSQL-compatible metadata;
- foreign keys and unique session assignment hold;
- assignment and audit event commit atomically;
- repository queries never return another organization's sessions or units.

### API and generated client

- manager can list and assign;
- unauthenticated, unauthorized, malformed and conflict responses match OpenAPI;
- generated client covers filters and assignment request without hand-written drift.

### Web end to end

- successful import replaces confirmation with `Continue close` and `Import another file`;
- `Continue close` shows imported dashboard data;
- dashboard pending CTA opens filtered Sessions;
- manager assigns a pending session and sees the count decrease;
- final assignment clears the pending blocker;
- reimport remains available and idempotent;
- sidebar behaves as navigation, not completion state, on desktop and mobile.

## 11. Acceptance criteria

This increment is complete when:

- the post-import state presents a clear next action and no stale confirmation language;
- the sidebar no longer visually represents a one-time sequence;
- only implemented destinations are interactive;
- pending review never routes to data-source configuration;
- the manager can resolve a pending session by assigning it to a unit;
- every assignment is organization-scoped and auditable;
- raw `Card ID` is never treated as a confirmed resident or unit;
- dashboard coverage and cost grouping use canonical assignment state;
- multiple import batches can contribute to the same open period without duplicate sessions;
- automated tests cover the complete import-to-assignment-to-dashboard flow.

## 12. Non-goals

- creating or editing residents and units from the assignment screen;
- invoice issuance or closed-period correction;
- automatic identity inference from untrusted `Card ID` values;
- AI-generated assignments;
- bulk assignment without per-session evidence;
- enabling unfinished Insights or Invoices routes.
