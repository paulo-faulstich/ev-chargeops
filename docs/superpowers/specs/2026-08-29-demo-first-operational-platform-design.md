# EV ChargeOps Demo-First Operational Platform Design

**Status:** proposed for implementation

**Date:** 29 August 2026

**Problem frame:** [../../product/problem-frame.md](../../product/problem-frame.md)

**PRD:** [../../product/prd.md](../../product/prd.md)

**Technical specification:** [../../technical/ev-chargeops-architecture.md](../../technical/ev-chargeops-architecture.md)

## 1. Purpose

This design turns the approved product direction into a demonstrable vertical slice. The product is not an upload utility. It is an operational, intelligence and billing layer for shared EV charging in condominiums and corporate buildings.

The CSV workflow exists only because the GoodWe EV Charger API is unavailable to challenge participants. It is an infrastructure adapter behind the product experience and must remain replaceable by a future GoodWe API or another charging-session source.

## 2. Problem statement

Managers and users of shared charging infrastructure do not have an integrated and auditable way to assign charging sessions to units, calculate individual consumption, apply cost-allocation rules and follow payment collection. Operational records exist in SEMS+, but they are not connected to the condominium context and are not available through an EV Charger API for the challenge.

The primary job to be done is:

> Close a monthly EV-charging period with confidence, explain what each resident owes and trace every charge back to the session, rule and source that produced it.

## 3. Product promise

EV ChargeOps transforms technical charging sessions into attributed consumption, explainable cost allocation, auditable billing and actionable operational intelligence.

The demonstration must prove this promise through a complete monthly close. A successful demo is not a collection of disconnected screens; it is a traceable state transition from open period to resident-visible payment.

## 4. Demonstration narrative

The default landing page is the manager dashboard for the LAB FIAP site and the selected billing period. It opens with data already available so the audience sees the problem being solved before seeing how data entered the system.

1. The manager sees total energy, estimated cost, assignment coverage, anomalies and billing readiness for the period.
2. The dashboard identifies sessions that cannot yet be charged because identity is unknown or a critical anomaly needs review.
3. The manager opens the action queue, assigns an unknown session to a demonstration unit and records a justification.
4. The dashboard recalculates energy and estimated cost by resident without changing the real session measurements.
5. The manager reviews the tariff and allocation policy, then confirms that eligible imported energy reconciles to invoice items with a difference of `0.00 kWh`.
6. The manager reviews explainable anomaly, forecast and usage-segmentation results.
7. The manager closes the period and issues resident invoices from an immutable tariff and policy snapshot.
8. An eligible invoice creates a Pix order through Mercado Pago sandbox, and a test webhook updates its status idempotently.
9. The resident view shows only that resident's unit, sessions, cost composition, recommendations and payment state.
10. From any amount, the presenter can navigate back to invoice item, session, assignment, import batch and raw source record.

The data-source screen is shown only as supporting evidence that the current CSV adapter is temporary and the domain is source-independent.

## 5. Information architecture

### 5.1 Manager dashboard

Route: `/dashboard`

This is the product home and the main demonstration surface. It contains:

- period and site selector;
- period status: `open`, `ready_to_close`, `closed` or `issued`;
- total energy, allocated energy, estimated cost and assignment coverage;
- count of sessions requiring action and critical anomaly count;
- ranked resident-cost table with unit, resident, kWh, session count, estimated or issued amount and payment status;
- consumption and cost evolution over the period;
- action queue for unknown identity, rejected records and anomaly review;
- concise insight cards for forecast, peak-use window and usage segments;
- readiness checklist and the primary `Close period` action.

Dashboard metrics are decision-oriented. Each card links to the records that explain it. Decorative metrics without a management action are excluded.

### 5.2 Residents and costs

Routes: `/residents` and `/residents/:id`

The list prioritizes cost accountability:

- unit and resident;
- attributed kWh and percentage of period consumption;
- session count;
- energy charge, shared-infrastructure allocation and losses;
- total due;
- invoice and payment status.

The resident detail contains session history, cost composition, consumption trend, relevant recommendations and provenance labels. A manager can inspect every resident; a resident can inspect only authorized units.

### 5.3 Sessions and review queue

Routes: `/sessions` and `/sessions/:id`

The session list supports filters by period, resident, identity confidence, status and anomaly. The detail shows:

- observed energy and timestamps;
- charger and port;
- derived average power;
- current user and unit assignment;
- identity confidence: `confirmed`, `assigned` or `unknown`;
- anomaly flags and review decisions;
- source, batch and original-record reference;
- assignment and audit history.

Assignment never overwrites measured data. It creates a `SessionAssignment` and an `AuditEvent` with actor, timestamp, previous value, new value and justification.

### 5.4 Insights

Route: `/insights`

The insights area makes the three required analytical modules operational:

- anomaly detection identifies sessions that need review before billing;
- forecasting estimates next-period consumption or returns an explicitly inconclusive result;
- segmentation explains usage profiles and supports communication or operating decisions.

Every result exposes algorithm version, dataset reference, parameters, sample size, evaluation metric and provenance. Results are presented as decision support, never as unquestionable facts.

### 5.5 Billing and payments

Routes: `/billing`, `/billing/:periodId` and `/invoices/:id`

The billing-period view shows:

- applicable tariff snapshot and source;
- allocation policy and its version;
- reconciliation between eligible session energy and invoice-item energy;
- blockers that prevent closing;
- invoices and payment states after closing.

The invoice view explains energy charge, infrastructure fee, losses and total. Mercado Pago is used only in sandbox. Payment events are idempotent and auditable.

### 5.6 Data sources

Routes: `/settings/data-sources` and `/settings/imports/:id`

The existing CSV preview is moved under settings and extended with confirmation, history and errors. This screen communicates:

- current adapter: `SEMS+ CSV`;
- future adapter capability: `GoodWe API` when credentials and EV Charger coverage exist;
- last successful import and source health;
- batch checksum, counts and status;
- raw-record and rejection evidence.

Upload is not present in the primary navigation hierarchy above operational dashboards. It is an administrative source-management capability.

## 6. Data and provenance strategy

The demo uses two clearly separated data classes:

1. **Observed operational data:** energy, timestamps, charger serial and available session fields obtained from the SEMS+ history or its faithful fixture. These values are labeled `real`.
2. **Demonstration context:** resident identities, unit relationships and any additional history needed to demonstrate forecasting or clustering. These values are labeled `assigned` or `simulated`.

Calculated power, cost and model output are labeled `derived`; tariff and payment states obtained from third parties are labeled `external`.

Simulated identity is never injected into a raw SEMS+ record. Provenance travels independently with each entity and remains visible in the manager and resident interfaces.

## 7. Persistent model

Supabase project `lgjohsxipfctgooiuqnv` provides managed PostgreSQL, Auth and Storage. The project is in East US (Ohio) and was verified healthy before implementation. No credential is committed or embedded in generated clients.

The FastAPI backend is the only application component that accesses operational tables. SQLAlchemy repositories implement application ports, and Alembic owns schema migrations.

### 7.1 Organization and identity

- `organizations`
- `sites`
- `chargers`
- `units`
- `profiles`
- `memberships`

The demonstration seeds one organization, the LAB FIAP site, one manager account and multiple resident accounts. All operational rows carry `organization_id`. FastAPI derives organization and role from the validated Supabase JWT; client-provided organization identifiers never override this scope.

### 7.2 Ingestion and sessions

- `import_batches`
- `raw_import_records`
- `charging_sessions`
- `session_assignments`

`import_batches.checksum` prevents accidental repetition of an identical file. `charging_sessions.deduplication_key` is unique per organization and prevents the same session from being inserted through another batch. Invalid rows remain attached to the batch without creating sessions.

### 7.3 Tariffs, billing and payments

- `tariff_snapshots`
- `billing_policies`
- `billing_periods`
- `invoices`
- `invoice_items`
- `payment_orders`
- `payment_events`

Money is stored as integer cents. Energy and power use explicit PostgreSQL `numeric` precision. Closing a period snapshots tariff and policy inputs so later edits cannot change an issued invoice.

The first tariff is a versioned demonstration snapshot derived from an official source and stores source URL, reference date and capture date. A live tariff adapter may replace it later without changing billing rules. The demo does not depend on live ANEEL availability.

### 7.4 Insights and audit

- `insight_runs`
- `anomaly_flags`
- `forecast_snapshots`
- `usage_segment_snapshots`
- `audit_events`

`insight_runs` stores dataset checksum, algorithm identifier and version, parameters, seed, sample size, evaluation metrics, execution time and provenance summary. Domain modules receive canonical datasets and do not query SQLAlchemy directly.

## 8. Analytical modules

### 8.1 Anomaly detection

The first implementation combines deterministic rules with a robust statistical comparison. It flags at least:

- non-positive or impossible energy and duration;
- end time before start time;
- derived average power incompatible with charger nominal power;
- energy or duration outliers relative to the available period history.

A flag has code, severity, explanation, evidence, model or rule version and review status. Critical flags block billing until reviewed.

### 8.2 Consumption forecast

The first forecaster uses a simple reproducible regression or time-series baseline appropriate to the data volume. It reports:

- forecast horizon;
- training and validation window;
- sample size;
- error metric;
- uncertainty range;
- dataset provenance.

If the observed history is insufficient, the real-data result is `inconclusive`. A separate demonstration dataset may produce a simulated forecast, but the interface must never merge the two conclusions.

### 8.3 Usage segmentation

The first segmenter aggregates per-resident features such as session frequency, average energy, average duration and predominant charging hour. It standardizes features and runs K-Means with a fixed seed. The execution records cluster count, parameters and an evaluation metric such as silhouette score when mathematically valid.

Segment names are product interpretations, not raw model facts. The UI identifies when resident assignments or source sessions are simulated.

## 9. Billing rules for the demonstrable slice

The billing policy has three explicit components:

1. energy charge: session kWh multiplied by the applicable tariff snapshot;
2. shared infrastructure fee: fixed amount per active unit or another versioned demonstration rule;
3. technical-loss allocation: documented percentage applied consistently across eligible consumption.

Every invoice item stores the quantity, unit value, rule version and source session. Rounding occurs once at the item boundary using a documented mode. Re-running the same closed-period calculation returns identical values.

The exact demonstration values are fixtures, not hidden constants in domain code.

## 10. API and application boundaries

The initial REST surface extends the approved API with:

- authentication context and current profile;
- manager dashboard query;
- resident list and detail;
- session list, detail and assignment;
- persisted import confirmation and batch history;
- tariff and billing-period lifecycle;
- invoice and payment lifecycle;
- insight execution and result queries;
- resident dashboard query.

Read models may join data for screen efficiency, but writes remain use cases with explicit ports. The Next.js application consumes only the generated OpenAPI client; it does not import Supabase database SDKs for operational queries.

## 11. External integrations

### Supabase

Supabase is the primary real integration for persistence, authentication and original-file storage. Local and automated tests use replaceable repositories or an isolated database; domain tests do not require network access.

### Mercado Pago sandbox

The sandbox adapter creates one real test Pix order and processes an idempotent test webhook. Secrets remain in environment variables. A sanitized contract fixture protects automated tests from sandbox availability, but the final demo evidence must include one successful sandbox transaction when credentials are supplied.

### GoodWe

No GoodWe API credential is assumed. No command reaches the charger. The CSV adapter implements the same `ChargingSessionSource` port a future API adapter will use.

## 12. Delivery checkpoints

The implementation is divided into four independently demonstrable checkpoints while preserving the single product narrative.

### Checkpoint A: operational data foundation

- Supabase configuration, Alembic and repositories;
- Supabase Auth and organization scoping;
- persisted idempotent import batches, raw records and sessions;
- seeded site, charger, units and demonstration profiles;
- source management moved out of the main product path.

### Checkpoint B: manager dashboard and monthly close

- manager dashboard and action queue;
- session assignment and audit history;
- resident cost table and details;
- tariff snapshot, billing policy, reconciliation and deterministic invoices.

### Checkpoint C: actionable intelligence

- anomaly detection and review;
- forecast with validation and uncertainty;
- reproducible usage segmentation;
- dashboard integration and `InsightRun` evidence.

### Checkpoint D: payment and presentation hardening

- Mercado Pago sandbox Pix and webhook;
- resident-authorized view;
- provenance navigation and evidence export;
- final seed, demonstration script, responsive QA and acceptance evidence.

## 13. Acceptance criteria

The slice is complete when:

- the default experience begins at the manager dashboard, not upload;
- the monthly-close demonstration narrative works end to end;
- reimporting an identical file creates zero new sessions;
- every persisted session references its batch and raw record;
- every session exposes `confirmed`, `assigned` or `unknown` identity confidence;
- the manager can resolve an unknown session through an audited assignment;
- eligible imported energy reconciles to invoiced energy with `0.00 kWh` difference;
- the same closed-period inputs always produce the same invoice values;
- one prepared anomaly is explained and reviewed;
- one forecast reports sample, error and uncertainty or is explicitly inconclusive;
- one segmentation run records features, parameters, seed, evaluation and dataset provenance;
- one Mercado Pago sandbox order is created and updated idempotently;
- the resident view cannot access another unit;
- all mixed real, assigned, simulated, derived and external data is labeled;
- every criterion has an automated test or a traceable demonstration step;
- no command or configuration change is sent to the GoodWe equipment.

## 14. Non-goals

- GoodWe API integration without official credentials and EV Charger coverage;
- browser automation of SEMS+ as a permanent source;
- OCPP or Modbus simulation presented as the LAB FIAP charger;
- remote charger control;
- production payments;
- generic condominium administration beyond what the demo flow needs;
- complex machine-learning models that imply confidence unsupported by the dataset;
- production-scale availability, multi-region deployment or microservices;
- hiding demonstration data behind realistic-looking but false provenance.

## 15. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Upload dominates the product narrative | Dashboard is the landing page; data source lives under settings and is omitted from the primary demo until supporting evidence is needed. |
| Too little real history for ML | Show inconclusive real result and a separate, visibly simulated demonstration dataset. |
| Identity is absent from SEMS+ | Use audited manual assignment and keep measured fields immutable. |
| External sandbox is unavailable during presentation | Persist sanitized successful evidence and provide a controlled retry, while keeping the live sandbox integration as the target. |
| Scope expands into a production platform | Implement only entities, roles and flows required by the demonstration and acceptance criteria. |
| Financial values become difficult to defend | Version every rule, preserve snapshots and expose reconciliation and item-level calculation. |

## 16. Testing and evidence strategy

- domain tests cover session invariants, billing determinism, anomaly rules and insight reproducibility;
- repository integration tests cover migrations, organization isolation and idempotency;
- adapter contracts ensure current CSV and future session sources produce canonical candidates;
- API tests cover auth, role enforcement, error envelopes and state transitions;
- generated OpenAPI drift remains part of the repository gate;
- Playwright covers the manager close flow and resident authorization boundary;
- contract fixtures cover Mercado Pago without requiring network for every test;
- the final demonstration checklist maps every product claim to a screen, test or persisted audit record.

## 17. Definition of success

The product succeeds when an evaluator can answer all of the following from the running application:

- how much energy was consumed in the period;
- which resident is responsible for each eligible session;
- how much each resident owes and how that amount was calculated;
- which records require management attention;
- what the analytical modules concluded and how reproducible those conclusions are;
- whether invoices were issued and paid;
- where every important value came from.

If the evaluator only remembers that a CSV was uploaded, this design has failed even if the importer works correctly.
