# Tariff, Period Close and Invoicing Design

**Status:** awaiting approval

**Date:** 30 August 2026

**Problem frame:** [../../product/problem-frame.md](../../product/problem-frame.md)

**PRD:** [../../product/prd.md](../../product/prd.md) (0.4)

**Tech spec:** [../../technical/ev-chargeops-architecture.md](../../technical/ev-chargeops-architecture.md) (0.2)

**Previous increment:** [2026-08-30-recurring-close-and-session-assignment-design.md](2026-08-30-recurring-close-and-session-assignment-design.md)

## 1. Purpose

The previous increment made charging sessions canonical, auditable and assignable to a
condominium unit. It stops at "who consumed how much". This increment carries the same data the
rest of the way: versioned tariff, transparent apportionment, an explainable opinion, an
approved close, an immutable invoice per unit, a downloadable PDF, and the resident's own view
of that invoice.

It replaces the `Custos por responsável` panel, which multiplies energy by a hardcoded
`R$ 0,94/kWh` constant in the frontend and is not a bill.

## 2. Decisions requiring approval

These six shape everything downstream.

### 2.1 The apportionment model is the Sprint 1 formula, verbatim

```text
invoice(unit, period) = energy_value + infra_fee + loss_share
```

Sprint 1 defined it, delivered it and had it graded, with a worked example covering three
exceptional cases. It reproduces `data/exemplos/faturas.csv` to the cent. Adopting it as the
implementation contract gives the increment a golden test for free and demonstrates continuity
between the two sprints.

### 2.2 Rounding happens once per charging session

Each `InvoiceItem` corresponds to exactly one charging session and carries its own rounded
value in integer cents. Subtotals and the invoice total are sums of already-rounded items.

Both candidate strategies — rounding per session and rounding once over the period sum —
reproduce the Sprint 1 example exactly, so the fixture does not decide. Per-session rounding
wins because every printed line is independently verifiable and the total is the visible sum of
the lines. A resident contesting a bill can check it with a finger on the screen. That property
is the product.

### 2.3 A session's tariff band is resolved by its start time

A session that crosses band boundaries is billed entirely in the band where it started.

The alternative — splitting energy across bands proportionally to elapsed time — is more
precise in appearance and less honest in substance. The source gives one total energy figure
per session, not an energy curve, so any split would be an assumption presented as a
measurement. Start-time resolution is explainable to a resident in one sentence and matches the
Sprint 1 fixture, which keeps the golden test valid.

This supersedes the earlier wording in the tech spec about identifying every band that
intersects a session. When per-interval telemetry exists (`activePower` from the GoodWe API),
proportional allocation becomes measurable and can be revisited as a versioned policy change.

### 2.4 The infrastructure fee is a flat amount per active unit

`BillingPolicy.infraFeeCents` is charged once to each unit that charged in the period. It is not
a monthly total divided among active units.

Dividing a pooled total would make a unit's bill change because a neighbour did or did not
charge that month. That is contestable in an assembly and hard to explain. A flat per-unit fee
is stable, predictable and reproduces the Sprint 1 example.

### 2.5 A unit with no charging in the period is not billed

No energy, no infrastructure fee, no losses, total zero. Strictly pay-per-use, as Sprint 1
established. The invoice is still issued, with zero value, so the period has complete coverage
and the absence is auditable rather than silent.

### 2.6 Reconciliation is dual and never silent

Internal reconciliation compares eligible energy against invoiced energy and must be
`0,00 kWh`. External reconciliation compares invoiced energy against the charger's own
aggregate for the period.

An external difference is displayed with its value and never absorbed into any invoice. This is
the strongest auditability claim the product can make: the numbers are checked against the
manufacturer, not only against themselves.

## 3. Domain model

### 3.1 Tariff

`TariffSnapshot` is immutable once created.

| Field | Rule |
|---|---|
| `id` | UUID |
| `organizationId` | Tenant scope |
| `name` | Human label |
| `source` | `manual`, `aneel` or `sprint1_reference` |
| `sourceReference` | URL or document reference |
| `capturedAt` | When the values were obtained |
| `validFrom`, `validTo` | Effective period; `validTo` nullable |
| `bands` | Ordered list of bands |

A band carries `code` (`ponta`, `intermediario`, `fora_ponta`), `rateCentsPerKwh` (integer),
and the weekday/time windows it covers. Windows are expressed in the site's timezone.

Reference values from Sprint 1: `ponta` 125, `intermediario` 95, `fora_ponta` 78 cents per kWh.

Bands must tile the whole week without gaps or overlaps. A tariff failing that validation cannot
be saved.

### 3.2 Policy

`BillingPolicy` is immutable once created.

| Field | Rule |
|---|---|
| `infraFeeCents` | Flat fee per active unit per period |
| `lossPercentBasisPoints` | Loss share, in basis points, applied to energy value |
| `validFrom`, `validTo` | Effective period |

Sprint 1 reference: `infraFeeCents = 2500`, `lossPercentBasisPoints = 400`.

Basis points avoid float. Four percent is `400`.

### 3.3 Period

| Field | Rule |
|---|---|
| `id` | UUID |
| `organizationId`, `siteId` | Scope |
| `periodValue` | `YYYY-MM` |
| `status` | `open`, `closing`, `closed` |
| `tariffSnapshotId`, `billingPolicyId` | Null until closed; frozen at close |
| `approvedBy`, `approvedAt` | Null until closed |
| `closingOpinionId` | The opinion reviewed at approval |
| `eligibleEnergyKwh`, `invoicedEnergyKwh`, `aggregateEnergyKwh` | Frozen at close |

A session belongs to the period containing its `startedAt`, evaluated in the site's timezone. A
session crossing month-end belongs to the month it started in.

Freezing the snapshot identifiers on the period, rather than copying values onto every invoice,
keeps one source of truth per close while remaining immutable: both referenced records are
themselves immutable.

### 3.4 Invoice

| Field | Rule |
|---|---|
| `id` | UUID |
| `number` | Human-readable auditable identifier, unique per organization |
| `billingPeriodId`, `unitId` | Scope |
| `contactLabel` | Resident or billing contact, denormalized at issue time |
| `energyKwh` | Sum of item energies |
| `energyValueCents`, `infraFeeCents`, `lossShareCents`, `totalCents` | Integer cents |
| `issuedAt` | Immutable |

`contactLabel` is denormalized deliberately. A resident who moves out must not change a bill
already issued in their name.

### 3.5 Invoice item

One item per charging session.

| Field | Rule |
|---|---|
| `chargingSessionId` | The session billed |
| `startedAt`, `endedAt`, `energyKwh` | Copied from the session at issue time |
| `bandCode`, `rateCentsPerKwh` | The band resolved and the rate applied |
| `valueCents` | `round(energyKwh × rateCentsPerKwh)`, half-up |

Copying the observed measurements makes the invoice self-contained: it can be rendered and
defended without re-reading the session, and it cannot drift.

## 4. Calculation

A pure function over integers. No database access, no clock, no randomness.

```text
calculate(eligible_sessions, tariff, policy, units) -> list[InvoiceDraft]

for each session:
    band  = tariff.resolve_band(session.startedAt)
    value = round_half_up(session.energyKwh * band.rateCentsPerKwh)

for each unit:
    energy_value = sum(item.valueCents for its items)
    infra        = policy.infraFeeCents if the unit has at least one item else 0
    losses       = round_half_up(energy_value * policy.lossPercentBasisPoints / 10000)
    total        = energy_value + infra + losses
```

Rounding is half-up and defined once, in a single domain helper. Energy stays decimal with
explicit precision; money is integer cents from the first multiplication onward.

Re-running with the same inputs always yields byte-identical output.

## 5. Eligibility and blockers

A session is eligible when it is inside the period, belongs to the organization and site, has
status `ready`, and has an assignment to a unit.

Blocking conditions, all of which prevent close:

| Blocker | Resolution |
|---|---|
| Session with `identityConfidence = unknown` | Assign it to a unit |
| Session with a critical analytical finding | Record a decision on the finding |
| No effective tariff covering the period | Register or extend a tariff |
| No effective policy covering the period | Register or extend a policy |
| Internal reconciliation different from zero | Investigate; this indicates a defect |

An external reconciliation difference is a warning, not a blocker. The charger aggregate and the
session list are different measurements and may legitimately diverge; the product's job is to
show the number, not to hide it or to refuse work because of it.

Discarded sessions are excluded and listed with their reason.

## 6. Closing opinion

Produced before approval, over the period's dataset, by `RuleBasedClosingOpinionAnalyzer`.

Deterministic rules:

| Code | Condition | Severity |
|---|---|---|
| `INVALID_INTERVAL` | End not after start | critical |
| `NON_POSITIVE_ENERGY` | Energy ≤ 0 | critical |
| `POWER_EXCEEDS_RATED` | Derived average power exceeds charger rated power by a margin | critical |
| `DUPLICATE_SUSPECT` | Same charger and overlapping interval | critical |
| `ENERGY_OUTLIER` | Energy far from the unit's own distribution | warning |
| `AGGREGATE_MISMATCH` | Invoiced energy differs from charger aggregate | warning |
| `UNASSIGNED_ENERGY` | Eligible energy without a unit | critical |

Each finding carries code, severity, evidence (the values that triggered it), a plain-language
explanation and a confidence. The consolidated opinion carries conclusion, highest severity,
confidence, the evidence list and a recommendation.

When the sample is too small for a distribution-based rule, that rule returns
`inconclusive` explicitly rather than a fabricated verdict. An opinion composed entirely of
inconclusive results says so.

The opinion is persisted as an `InsightRun` with algorithm version, parameters, dataset checksum
and timestamp, so the approval references exactly what the manager saw.

The opinion never changes a monetary value. It gates the close; it does not compute the bill.

## 7. Close transaction

One transaction:

1. Re-evaluate blockers. Any blocker aborts with `409`.
2. Freeze `tariffSnapshotId`, `billingPolicyId`, `closingOpinionId` on the period.
3. Run the calculation.
4. Persist invoices and items.
5. Mark eligible sessions `billed`.
6. Freeze the three energy totals.
7. Set status `closed`, `approvedBy`, `approvedAt`.
8. Append an `AuditEvent`.

Closing an already-closed period returns `409` and changes nothing.

## 8. PDF

`PdfInvoiceRenderer` implements `InvoiceRenderer`, server-side, from the persisted invoice
alone.

The document contains the condominium and unit, the contact, the period, the itemized sessions
with band and rate, the three subtotals, the total, the tariff source and validity, the policy
version, the provenance of the data, and the invoice number.

It is generated on demand and streamed. The stored `InvoiceDocument` records checksum and
generation timestamp so that two downloads of the same invoice are provably identical.

The rendered figures come from stored integers, never recalculated at render time. The PDF and
the screen cannot disagree.

## 9. Resident view

The invoice page is one artifact with two doors.

The manager reaches it from the invoice list. The resident context reaches the same route,
scoped. There is no second layout and no resident dashboard.

Page structure, in reading order:

1. **How much and why** — total, decomposed into energy, infrastructure and losses, visibly
   summing to the total.
2. **Where it came from** — the session list with date, start, end, duration, energy, band, rate
   and value. Each line traceable to its import batch.
3. **Why this rate** — the versioned tariff with source and validity, and the band applied to
   each session.
4. **What to do with it** — what the same energy would have cost in the cheaper bands. Derived
   from the versioned tariff only; no invented baseline, no imagined savings.

Plus provenance labels, the invoice number and the PDF download.

Item 4 is the first thing to cut if time runs short. The other three are the invoice explaining
itself; item 4 is advice.

### Resident context mechanics

`POST /v1/resident-context` with a `unitId` returns a short-lived scoped context. It resolves
through the same authorization dependency a real resident session would use, and repositories
apply the unit filter alongside the organization filter. Every write is rejected while it is
active. Entering the context appends an `AuditEvent`.

The UI shows a permanent, unmistakable banner naming the unit and stating read-only, with
one-click exit.

This is the only door to the `resident` role in this increment. Adding a resident login later
adds a door; it does not change the model.

## 10. Persistence

Migrations add: `tariff_snapshots`, `tariff_bands`, `billing_policies`, `billing_periods`,
`invoices`, `invoice_items`, `invoice_documents`, `charger_energy_readings`, `closing_opinions`
and `analytical_findings`.

Constraints that matter:

- unique invoice per `(billingPeriodId, unitId)`;
- unique invoice `number` per organization;
- unique `(organizationId, siteId, periodValue)` per billing period;
- unique `(organizationId, chargerId, periodType, periodValue)` per charger reading;
- every monetary column is `integer` cents, never float;
- foreign keys carry `organizationId` so cross-tenant rows behave as not found.

## 11. API

```text
GET    /v1/tariffs
POST   /v1/tariffs
GET    /v1/billing-policies
POST   /v1/billing-policies
GET    /v1/billing-periods
POST   /v1/billing-periods
GET    /v1/billing-periods/:id
GET    /v1/billing-periods/:id/readiness
POST   /v1/billing-periods/:id/close
GET    /v1/invoices
GET    /v1/invoices/:id
GET    /v1/invoices/:id/document
POST   /v1/insight-runs/closing-opinion
POST   /v1/charger-readings/import
POST   /v1/resident-context
DELETE /v1/resident-context
```

`readiness` is the dashboard's source for coverage, blockers and both reconciliations.

## 12. Errors and concurrency

- Close with unresolved blockers: `409` listing them.
- Close an already-closed period: `409`, no state change.
- Period with no effective tariff or policy: `409` naming which is missing.
- Resident context requesting another unit: `404`, no cross-tenant disclosure.
- Any write attempt under resident context: `403`.
- Concurrent close attempts: the transaction takes a row lock on the period; the loser gets
  `409`.
- PDF generation failure: the invoice remains valid and issued; the download can be retried.

## 13. Testing

**Golden.** The calculation reproduces the Sprint 1 worked example per unit, to the cent,
including the interrupted session and the unit without consumption. This test is the acceptance
gate for the whole calculation layer.

One deliberate divergence is asserted rather than hidden. Sprint 1 billed per RFID user, so the
two-vehicle unit U102 paid the infrastructure fee twice; the unit-level model charges it once.
Energy and losses for that unit still reproduce exactly, so the difference has a single cause
and a single line. `test_two_vehicle_unit_diverges_from_sprint1_only_on_the_fee` pins it, and
[PRD 0.4 section 4.4](../../product/prd.md) records the reasoning.

**Domain.** Band resolution at boundaries and across midnight; rounding half-up at exact halves;
losses on zero energy; infrastructure fee suppressed for inactive units; a tariff with a gap in
its band coverage rejected.

**Immutability.** Issue an invoice, change the tariff and the policy, re-read the invoice: every
value identical. Re-run the calculation for a closed period: rejected.

**Reconciliation.** A known fixture closes at `0,00 kWh` internal. A fixture whose aggregate
deliberately diverges reports the external difference with the exact value and does not alter
any invoice.

**Opinion.** Each rule fires on its prepared fixture and stays silent otherwise. A dataset too
small for the distribution rule returns inconclusive rather than a verdict.

**Authorization.** Resident context cannot read another unit's invoice, cannot list the
period's other invoices, and cannot write. Entering the context produces an audit event.

**E2E.** Import, assign, review the opinion, resolve a blocker, approve the close, open an
invoice, download the PDF, enter resident context, see the same figures, exit.

## 14. Acceptance criteria

- The apportionment reproduces the Sprint 1 worked example to the cent.
- Every invoice line is independently verifiable and the lines sum to the printed total.
- No invoice exists without an explicit approval carrying actor and timestamp.
- A tariff or policy change after issue alters no issued invoice.
- Internal reconciliation is `0,00 kWh`; external reconciliation is displayed with its value.
- The opinion presents conclusion, severity, confidence, evidence and recommendation, and
  critical findings block the close.
- The PDF renders from stored values and matches the screen.
- The resident context shows one unit, writes nothing, and is audited.
- No hardcoded tariff constant remains anywhere in the frontend.

## 15. Non-goals

- Payments of any kind, including sandbox.
- Consumption forecasting and usage segmentation.
- Correcting or reopening a closed period.
- A resident login.
- Proportional energy allocation across tariff bands.
- Editing residents and units from the invoice screen.
