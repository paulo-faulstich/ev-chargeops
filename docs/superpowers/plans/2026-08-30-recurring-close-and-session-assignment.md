# Recurring Close and Session Assignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the monthly operation repeatable by adding an actionable post-import handoff, permanent navigation and an audited workflow for assigning pending charging sessions to condominium units.

**Architecture:** Add a `sessions` module to the FastAPI modular monolith. Ingestion continues to own immutable source capture; Sessions owns canonical operational queries and unit assignment. The dashboard and new Sessions UI consume generated API-client functions rather than inferring identity from raw SEMS+ fields.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy async, Alembic, PostgreSQL/SQLite, Next.js 16 App Router, React 19, TypeScript, generated OpenAPI types, pytest, Vitest and Playwright.

**Spec:** `docs/superpowers/specs/2026-08-30-recurring-close-and-session-assignment-design.md`

## Global Constraints

- Follow strict RED-GREEN-REFACTOR: every production behavior starts with a failing test that fails for the expected reason.
- Keep observed session energy, timestamps, charger, source, import batch and raw-record references immutable.
- Never use raw SEMS+ `Card ID` as a confirmed person or condominium unit.
- Assign financial responsibility to `unit_id`; resident labels are presentation context only.
- Scope every read and write by authenticated `organization_id`; cross-tenant identifiers return `404`.
- Require the `manager` role for session review and assignment.
- Keep FastAPI as the only component accessing operational tables.
- Generate TypeScript types from OpenAPI; do not duplicate response contracts by hand.
- Keep unfinished Residents, Insights and Invoices destinations out of interactive navigation.
- Preserve idempotent CSV import and organization-scoped session deduplication.
- End each task with focused verification, `git diff --check` and a dedicated commit.

## File Map

API additions live under `apps/api/app/modules/sessions/`: focused domain models/errors, query and command use cases with a repository port, SQLAlchemy assignment persistence, and FastAPI schemas/router. Migration `20260830_0002_session_assignments.py` adds the current assignment record while `audit_events` preserves change history.

Web additions are `apps/web/src/app/(app)/sessions/page.tsx`, a focused `components/sessions/` review component and E2E coverage. Existing dashboard, import and shell components are modified only for their respective handoffs. Generated files remain `packages/api-client/openapi.json` and `packages/api-client/src/schema.ts`.

---

### Task 1: Session Assignment Domain and Persistence

**Files:**
- Create: `apps/api/app/modules/sessions/domain/models.py`
- Create: `apps/api/app/modules/sessions/domain/errors.py`
- Create: `apps/api/app/modules/sessions/infrastructure/models.py`
- Create: `apps/api/alembic/versions/20260830_0002_session_assignments.py`
- Create: `apps/api/tests/modules/sessions/domain/test_assignment.py`
- Modify: `apps/api/alembic/env.py`
- Modify: `apps/api/tests/integration/test_migrations.py`

**Interfaces:**
- Consumes: existing `OrganizationScope`, `ChargingSessionModel`, `UnitModel`, `ProfileModel`, `AuditEventModel` and SQLAlchemy base mixins.
- Produces: `SessionView`, `AssignmentUnitView`, `SessionAssignment`, `AssignmentResult`, assignment errors and `SessionAssignmentModel`.

- [ ] **Step 1: Write failing domain tests**

```python
import pytest

from app.modules.sessions.domain.errors import InvalidJustification
from app.modules.sessions.domain.models import normalize_justification


def test_normalize_justification_strips_a_valid_reason() -> None:
    assert normalize_justification("  Confirmado pelo síndico  ") == (
        "Confirmado pelo síndico"
    )


@pytest.mark.parametrize("value", ["", "   ", "\n\t"])
def test_normalize_justification_rejects_blank_reason(value: str) -> None:
    with pytest.raises(InvalidJustification):
        normalize_justification(value)
```

- [ ] **Step 2: Run RED**

```bash
uv run --project apps/api pytest apps/api/tests/modules/sessions/domain/test_assignment.py -q
```

Expected: collection fails because `app.modules.sessions` does not exist.

- [ ] **Step 3: Implement domain types**

Create frozen, slotted dataclasses with these exact fields:

```python
@dataclass(frozen=True, slots=True)
class SessionView:
    id: UUID
    started_at: datetime
    ended_at: datetime
    energy_kwh: Decimal
    charger_serial: str
    source: str
    provenance: str
    identity_confidence: str
    status: str
    unit_id: UUID | None
    unit_code: str | None
    unit_name: str | None
    resident_name: str | None


@dataclass(frozen=True, slots=True)
class AssignmentUnitView:
    id: UUID
    code: str
    display_name: str
    resident_name: str | None


@dataclass(frozen=True, slots=True)
class SessionAssignment:
    id: UUID
    session_id: UUID
    unit_id: UUID
    assigned_by: UUID
    justification: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AssignmentResult:
    assignment: SessionAssignment
    session: SessionView
    created: bool
```

`normalize_justification(value)` strips the input and raises `InvalidJustification(field="justification")` when empty. Define separate `SessionNotFound`, `UnitNotFound`, `AssignmentForbidden` and `InvalidPeriod` exceptions.

- [ ] **Step 4: Run domain GREEN**

Run Step 2. Expected: all tests pass.

- [ ] **Step 5: Write failing migration tests**

Extend `test_migrations.py` to assert the head revision creates `session_assignments` with `organization_id`, `charging_session_id`, `unit_id`, `assigned_by`, `justification` and named unique constraint `uq_session_assignments_organization_id_charging_session_id`. Assert downgrade to `20260829_0001` removes only the assignment table.

- [ ] **Step 6: Run migration RED**

```bash
uv run --project apps/api pytest apps/api/tests/integration/test_migrations.py -q
```

Expected: failure because revision `20260830_0002` does not exist.

- [ ] **Step 7: Add model and migration**

```python
class SessionAssignmentModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "session_assignments"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    charging_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("charging_sessions.id"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id"), index=True)
    assigned_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    justification: Mapped[str] = mapped_column(Text(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "charging_session_id",
            name="uq_session_assignments_organization_id_charging_session_id",
        ),
        Index(
            "ix_session_assignments_organization_id_unit_id",
            "organization_id",
            "unit_id",
        ),
    )
```

Set `down_revision = "20260829_0001"`, create matching foreign keys/indexes and import the new metadata module in `alembic/env.py`.

- [ ] **Step 8: Verify persistence GREEN**

```bash
uv run --project apps/api pytest apps/api/tests/modules/sessions/domain/test_assignment.py apps/api/tests/integration/test_migrations.py -q
uv run --project apps/api alembic -c apps/api/alembic.ini check
```

- [ ] **Step 9: Commit**

```bash
git add apps/api/app/modules/sessions apps/api/alembic apps/api/tests/modules/sessions apps/api/tests/integration/test_migrations.py
git diff --check
git commit -m "feat: add session assignment persistence"
```

---

### Task 2: Organization-Scoped Session and Unit Queries

**Files:**
- Create: `apps/api/app/modules/sessions/application/ports.py`
- Create: `apps/api/app/modules/sessions/application/list_sessions.py`
- Create: `apps/api/app/modules/sessions/application/list_assignment_units.py`
- Create: `apps/api/app/modules/sessions/infrastructure/repository.py`
- Create: `apps/api/tests/modules/sessions/application/fakes.py`
- Create: `apps/api/tests/modules/sessions/application/test_list_sessions.py`
- Create: `apps/api/tests/modules/sessions/application/test_list_assignment_units.py`
- Create: `apps/api/tests/modules/sessions/infrastructure/test_session_repository.py`

**Interfaces:**
- Consumes: Task 1 types and assignment model; existing organization, membership, profile, charger and charging-session models.
- Produces: `SessionRepository`, `ListSessions`, `ListAssignmentUnits` and `SqlAlchemySessionRepository`.

- [ ] **Step 1: Write failing use-case tests and port contract**

```python
class SessionRepository(Protocol):
    async def list_sessions(
        self,
        organization_id: UUID,
        *,
        period: str | None,
        status: str | None,
    ) -> tuple[SessionView, ...]: ...

    async def list_assignment_units(
        self,
        organization_id: UUID,
    ) -> tuple[AssignmentUnitView, ...]: ...

    async def assign_session(
        self,
        scope: OrganizationScope,
        session_id: UUID,
        unit_id: UUID,
        justification: str,
        occurred_at: datetime,
    ) -> AssignmentResult: ...
```

Assert the recording fake receives `(scope.organization_id, "2026-08", "pending_review")`, that unit queries receive only `organization_id`, and that malformed values such as `2026-13` raise `InvalidPeriod`.

- [ ] **Step 2: Run application RED**

```bash
uv run --project apps/api pytest apps/api/tests/modules/sessions/application/test_list_sessions.py apps/api/tests/modules/sessions/application/test_list_assignment_units.py -q
```

- [ ] **Step 3: Implement minimal query use cases**

`ListSessions.execute(scope, period, status)` validates an optional `YYYY-MM` with `datetime.strptime` and forwards immutable filters. `ListAssignmentUnits.execute(scope)` forwards the scoped organization.

- [ ] **Step 4: Run application GREEN**

Run Step 2. Expected: all tests pass.

- [ ] **Step 5: Write failing repository isolation tests**

Seed two organizations, sessions with populated `card_id_raw`, units and memberships. Assert the first tenant sees only its own rows, raw card content creates no unit assignment, and a unit without a resident returns `resident_name is None`.

```python
items = await repository.list_sessions(
    first_scope.organization_id,
    period="2026-08",
    status="pending_review",
)
assert [item.id for item in items] == [first_session.id]
assert items[0].identity_confidence == "unknown"
assert items[0].unit_id is None
```

- [ ] **Step 6: Run repository RED**

```bash
uv run --project apps/api pytest apps/api/tests/modules/sessions/infrastructure/test_session_repository.py -q
```

- [ ] **Step 7: Implement canonical joins**

Query sessions by organization with an outer join to assignment, unit, resident membership/profile and charger. Convert `YYYY-MM` to an inclusive UTC start and exclusive next-month boundary. Order by `started_at DESC, id DESC`. Query assignment units by organization and code, exposing no email. Because the current schema has no active-membership interval, select at most one resident label per unit deterministically by membership `created_at, id`; a unit with no resident remains assignable.

- [ ] **Step 8: Verify queries GREEN**

```bash
uv run --project apps/api pytest apps/api/tests/modules/sessions/application apps/api/tests/modules/sessions/infrastructure/test_session_repository.py -q
uv run --project apps/api ruff check apps/api/app/modules/sessions apps/api/tests/modules/sessions
uv run --project apps/api mypy apps/api/app/modules/sessions
```

- [ ] **Step 9: Commit**

```bash
git add apps/api/app/modules/sessions apps/api/tests/modules/sessions
git diff --check
git commit -m "feat: query canonical charging sessions"
```

---

### Task 3: Audited Assignment Command

**Files:**
- Create: `apps/api/app/modules/sessions/application/assign_session.py`
- Create: `apps/api/tests/modules/sessions/application/test_assign_session.py`
- Modify: `apps/api/app/modules/sessions/infrastructure/repository.py`
- Modify: `apps/api/tests/modules/sessions/infrastructure/test_session_repository.py`

**Interfaces:**
- Consumes: Task 2 repository port and Task 1 types/errors.
- Produces: `AssignSession.execute(scope, session_id, unit_id, justification) -> AssignmentResult`.

- [ ] **Step 1: Write failing role and validation tests**

```python
result = await AssignSession(repository, clock=lambda: NOW).execute(
    manager_scope,
    SESSION_ID,
    UNIT_ID,
    "  Confirmado pelo síndico  ",
)
assert repository.assignment_call == (
    manager_scope,
    SESSION_ID,
    UNIT_ID,
    "Confirmado pelo síndico",
    NOW,
)
assert result == repository.assignment_result
```

Assert resident scope raises `AssignmentForbidden` and blank justification raises `InvalidJustification` without a repository call.

- [ ] **Step 2: Run command RED**

```bash
uv run --project apps/api pytest apps/api/tests/modules/sessions/application/test_assign_session.py -q
```

- [ ] **Step 3: Implement the use case**

Inject a UTC clock defaulting to `lambda: datetime.now(UTC)`, require `OrganizationRole.MANAGER`, normalize justification and call the repository once.

- [ ] **Step 4: Run command GREEN**

Run Step 2. Expected: all tests pass.

- [ ] **Step 5: Write failing atomic persistence tests**

Assert first assignment creates one row and one audit event, changes confidence to `assigned` and status to `ready`; exact replay creates neither another row nor another audit; reassignment updates the current row and appends an audit with literal previous/new unit UUIDs; cross-tenant IDs raise typed not-found errors; forced audit failure rolls back all changes.

```python
assert latest_audit.metadata_json == {
    "previous_unit_id": str(unit_a.id),
    "new_unit_id": str(unit_b.id),
    "justification": "Correção",
}
```

- [ ] **Step 6: Run repository mutation RED**

```bash
uv run --project apps/api pytest apps/api/tests/modules/sessions/infrastructure/test_session_repository.py -q
```

- [ ] **Step 7: Implement atomic assignment**

Select both session and unit with `organization_id`; insert or update the single assignment row; make exact unit/reason replay idempotent; update only session identity/status metadata; append a sanitized `session_assigned` audit event; commit once. Catch `SQLAlchemyError`, roll back and re-raise. Never copy `card_id_raw` into assignment.

- [ ] **Step 8: Verify mutation GREEN**

```bash
uv run --project apps/api pytest apps/api/tests/modules/sessions/application/test_assign_session.py apps/api/tests/modules/sessions/infrastructure/test_session_repository.py -q
uv run --project apps/api ruff check apps/api/app/modules/sessions apps/api/tests/modules/sessions
uv run --project apps/api mypy apps/api/app/modules/sessions
```

- [ ] **Step 9: Commit**

```bash
git add apps/api/app/modules/sessions apps/api/tests/modules/sessions
git diff --check
git commit -m "feat: assign sessions to condominium units"
```

---

### Task 4: Sessions HTTP Contract and Generated Client

**Files:**
- Create: `apps/api/app/modules/sessions/presentation/schemas.py`
- Create: `apps/api/app/modules/sessions/presentation/dependencies.py`
- Create: `apps/api/app/modules/sessions/presentation/router.py`
- Create: `apps/api/tests/modules/sessions/presentation/conftest.py`
- Create: `apps/api/tests/modules/sessions/presentation/test_sessions_endpoints.py`
- Modify: `apps/api/app/main.py`
- Modify generated: `packages/api-client/openapi.json`
- Modify generated: `packages/api-client/src/schema.ts`
- Modify: `packages/api-client/src/index.ts`
- Modify: `packages/api-client/src/index.test.ts`

**Interfaces:**
- Consumes: Tasks 2-3 use cases, `current_scope`, existing camel-case schemas and authenticated `apiRequest`.
- Produces: `GET /v1/sessions`, `GET /v1/assignment-units`, `PUT /v1/sessions/{id}/assignment`, plus `listSessions`, `listAssignmentUnits` and `assignSession`.

- [ ] **Step 1: Write failing endpoint tests**

Import the fixture through the real import route. Assert filtered Sessions returns two unknown items even when raw Card ID is populated, assignment units return four seeded units without email, and PUT returns an assigned/ready session. Add explicit `401`, resident-role `403`, malformed period and blank justification `422`, and cross-tenant `404` cases.

```python
response = api_client.get(
    "/v1/sessions?period=2026-08&status=pending_review",
    headers=auth_headers,
)
assert response.status_code == 200
assert len(response.json()["items"]) == 2
assert {item["identityConfidence"] for item in response.json()["items"]} == {
    "unknown"
}
```

- [ ] **Step 2: Run endpoint RED**

```bash
uv run --project apps/api pytest apps/api/tests/modules/sessions/presentation/test_sessions_endpoints.py -q
```

Expected: `404` because the routes do not exist.

- [ ] **Step 3: Implement schemas, dependencies and router**

Use `SessionListResponse`, `AssignmentUnitListResponse`, `SessionAssignmentRequest(unit_id: UUID, justification: str)` and `SessionAssignmentResponse`. Map role to `403`, lookup to `404`, validation to `422`, and declare every runtime response in OpenAPI. Register the router in `app/main.py`.

- [ ] **Step 4: Verify API GREEN**

```bash
uv run --project apps/api pytest apps/api/tests/modules/sessions/presentation/test_sessions_endpoints.py -q
uv run --project apps/api ruff check apps/api/app apps/api/tests/modules/sessions
uv run --project apps/api mypy apps/api/app
```

- [ ] **Step 5: Regenerate and write failing Vitest cases**

```bash
pnpm generate:api
```

Require literal query encoding and JSON mutation behavior:

```typescript
await listSessions(
  "signed-token",
  { period: "2026-08", status: "pending_review" },
  "http://api.test",
);
expect(fetchMock).toHaveBeenCalledWith(
  "http://api.test/v1/sessions?period=2026-08&status=pending_review",
  expect.objectContaining({ headers: { Authorization: "Bearer signed-token" } }),
);
```

For assignment, assert method `PUT`, `Content-Type: application/json`, bearer authorization and exact `JSON.stringify({ unitId, justification })` body.

- [ ] **Step 6: Run client RED**

```bash
pnpm --filter @ev-chargeops/api-client test
```

- [ ] **Step 7: Implement typed client functions**

Alias generated schema types, build optional filters with `URLSearchParams`, encode session IDs and reuse `apiRequest`. Do not change multipart import headers.

- [ ] **Step 8: Verify contract/client GREEN**

```bash
pnpm check:api-contract
pnpm --filter @ev-chargeops/api-client test
pnpm --filter @ev-chargeops/api-client typecheck
```

- [ ] **Step 9: Commit**

```bash
git add apps/api/app/main.py apps/api/app/modules/sessions/presentation apps/api/tests/modules/sessions/presentation packages/api-client
git diff --check
git commit -m "feat: publish session assignment API"
```

---

### Task 5: Session Review Queue UI

**Files:**
- Create: `apps/web/src/app/(app)/sessions/page.tsx`
- Create: `apps/web/src/components/sessions/session-formatters.ts`
- Create: `apps/web/src/components/sessions/session-review.tsx`
- Create: `apps/web/e2e/session-review.spec.ts`
- Modify: `apps/web/src/app/globals.css`

**Interfaces:**
- Consumes: Task 4 generated response types and `listSessions`, `listAssignmentUnits`, `assignSession`.
- Produces: authenticated `/sessions`, filter-aware pending queue and unit-assignment interaction.

- [ ] **Step 1: Write failing Playwright queue test with API routes**

Route the three APIs with complete literal payloads and assert:

```typescript
await page.goto("/sessions?status=pending_review&period=2026-08");
await expect(page.getByRole("heading", { name: "Sessões" })).toBeVisible();
await expect(page.getByText("2 pendências no período")).toBeVisible();
await page.getByRole("row", { name: /7,00 kWh/ }).click();
await page.getByLabel("Unidade responsável").selectOption(UNIT_A_ID);
await page.getByLabel("Justificativa").fill("Confirmado pela portaria");
await page.getByRole("button", { name: "Atribuir e revisar próxima" }).click();
await expect(page.getByRole("status")).toContainText("Unidade A-101");
await expect(page.getByText("1 pendência no período")).toBeVisible();
```

Assert the exact PUT body and verify observed energy, date, charger and provenance remain visible throughout assignment.

- [ ] **Step 2: Run UI RED**

```bash
pnpm --dir apps/web exec playwright test e2e/session-review.spec.ts
```

Expected: `/sessions` returns `404`.

- [ ] **Step 3: Implement authenticated route and formatters**

`page.tsx` reads `getAccessToken()`, redirects to `/login` when absent and renders `<SessionReview accessToken={accessToken} />`. Keep São Paulo date, duration and decimal-energy formatting in pure functions.

- [ ] **Step 4: Implement queue and assignment states**

Load sessions and units in parallel. Support loading, recoverable load error, no imported sessions, all matching sessions assigned, selected pending session, submission error and success. After a successful PUT, remove the item from the pending filter, select the next row, reset justification and report remaining count. Keep `Voltar para visão geral` visible.

- [ ] **Step 5: Add accessible responsive styling**

Use a desktop master-detail grid and mobile list-to-detail flow. Associate labels and controls, add visible keyboard focus, keep immutable evidence beside the assignment form and never use color as the only status signal.

- [ ] **Step 6: Verify UI GREEN**

```bash
pnpm --dir apps/web exec playwright test e2e/session-review.spec.ts
pnpm --dir apps/web lint
pnpm --dir apps/web exec next build --webpack
```

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/app/'(app)'/sessions apps/web/src/components/sessions apps/web/src/app/globals.css apps/web/e2e/session-review.spec.ts
git diff --check
git commit -m "feat: add pending session review queue"
```

---

### Task 6: Canonical Dashboard and Correct Pending Handoff

**Files:**
- Modify: `apps/web/src/components/dashboard/dashboard-summary.ts`
- Modify: `apps/web/src/components/dashboard/dashboard-overview.tsx`
- Modify: `apps/web/e2e/dashboard.spec.ts`

**Interfaces:**
- Consumes: Task 4 `listSessions` and Task 5 `/sessions` route.
- Produces: dashboard aggregation based only on canonical assignment state and a correctly filtered pending-review link.

- [ ] **Step 1: Change dashboard tests first**

Replace raw import-detail mocks with `GET /api/v1/sessions` payloads. Include a session whose raw Card ID would equal the charger serial but whose canonical identity is unknown. Assert:

```typescript
await expect(page.getByText("0 de 2", { exact: true })).toBeVisible();
await expect(
  page.getByText("2 sessões ainda não podem ser cobradas porque falta identificar o responsável."),
).toBeVisible();
await expect(
  page.getByRole("link", { name: "Revisar 2 pendências" }),
).toHaveAttribute("href", "/sessions?status=pending_review&period=2026-08");
```

Add an assigned canonical payload and assert the cost table groups under `Unidade A-101`, never raw Card ID.

- [ ] **Step 2: Run dashboard RED**

```bash
pnpm --dir apps/web exec playwright test e2e/dashboard.spec.ts
```

Expected: the dashboard still requests import batches and links to Data sources.

- [ ] **Step 3: Refactor summary input**

Change the signature to:

```typescript
export function buildDashboardSummary(
  sessions: SessionResponse[],
): DashboardSummary | null;
```

Use canonical `startedAt`, `energyKwh`, `unitId`, `unitCode`, `unitName`, `identityConfidence` and `status`. Delete raw CSV key/Card ID parsing. Add `periodKey: string` to `DashboardSummary` so URLs use `YYYY-MM` without reverse-parsing a localized label.

- [ ] **Step 4: Fetch canonical sessions and fix CTA**

Call `listSessions(accessToken, {}, apiUrl)`. Render:

```tsx
<Link
  href={`/sessions?status=pending_review&period=${summary.periodKey}`}
  className="primary-dashboard-action compact"
>
  Revisar {summary.pendingCount}{" "}
  {summary.pendingCount === 1 ? "pendência" : "pendências"}
</Link>
```

- [ ] **Step 5: Verify dashboard GREEN**

```bash
pnpm --dir apps/web exec playwright test e2e/dashboard.spec.ts
pnpm --dir apps/web lint
pnpm --filter @ev-chargeops/api-client typecheck
```

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/dashboard apps/web/e2e/dashboard.spec.ts
git diff --check
git commit -m "fix: drive dashboard from canonical assignments"
```

---

### Task 7: Actionable Post-Import Handoff

**Files:**
- Modify: `apps/web/src/components/imports/import-dropzone.tsx`
- Modify: `apps/web/src/app/globals.css`
- Modify: `apps/web/e2e/import-confirmation.spec.ts`

**Interfaces:**
- Consumes: existing import preview/confirmation response and `/dashboard`.
- Produces: mutually exclusive confirmation and confirmed-success states with `Continuar fechamento` and `Importar outro arquivo`.

- [ ] **Step 1: Update import E2E first**

After the `201`, assert:

```typescript
await expect(page.getByText("Importação concluída", { exact: true })).toBeVisible();
await expect(page.getByText("2 sessões adicionadas")).toBeVisible();
await expect(page.getByText("Agosto 2026", { exact: true })).toBeVisible();
await expect(page.getByText("0 inválidos · 0 duplicados")).toBeVisible();
await expect(
  page.getByRole("link", { name: "Continuar fechamento" }),
).toHaveAttribute("href", "/dashboard");
await expect(
  page.getByRole("button", { name: "Importar outro arquivo" }),
).toBeVisible();
await expect(page.getByText("Confirmação necessária")).toBeHidden();
await expect(
  page.getByRole("button", { name: "Importar novamente" }),
).toBeHidden();
```

Click `Importar outro arquivo` and assert the file input returns. Preserve replay idempotency by uploading the same file again through the reset flow.

- [ ] **Step 2: Run import RED**

```bash
pnpm --dir apps/web exec playwright test e2e/import-confirmation.spec.ts
```

- [ ] **Step 3: Implement exclusive success markup**

When `confirmation` exists, replace `.confirmation-panel` with a success panel. Use `confirmation.created` to distinguish `N sessões adicionadas` from `Lote já existente; nenhuma sessão duplicada`. Derive the localized latest period from valid `preview.records[].session.startedAt` values with a pure helper and show invalid/duplicate counts from the confirmation response. Keep preview ledger/history visible. `Continuar fechamento` is a Next.js `Link`; `Importar outro arquivo` calls `reset()`.

- [ ] **Step 4: Verify handoff GREEN**

```bash
pnpm --dir apps/web exec playwright test e2e/import-confirmation.spec.ts
pnpm --dir apps/web lint
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/imports/import-dropzone.tsx apps/web/src/app/globals.css apps/web/e2e/import-confirmation.spec.ts
git diff --check
git commit -m "feat: guide managers after data import"
```

---

### Task 8: Permanent Navigation, Critical Flow and Documentation

**Files:**
- Modify: `apps/web/src/components/shell/app-shell.tsx`
- Modify: `apps/web/src/app/globals.css`
- Modify: `apps/web/e2e/auth-shell.spec.ts`
- Create: `apps/web/e2e/monthly-close-handoff.spec.ts`
- Modify: `README.md`
- Modify: `docs/product/prd.md`
- Modify: `docs/technical/ev-chargeops-architecture.md`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: permanent navigation, real import-to-assignment acceptance path and synchronized documentation.

- [ ] **Step 1: Write failing navigation tests**

Assert principal navigation label `Operação`, real links for `/dashboard` and `/sessions`, no `aria-disabled="true"`, and `aria-current="page"` for the selected route. Keep `Fontes de dados` under the separate `Configurações` navigation.

- [ ] **Step 2: Run navigation RED**

```bash
pnpm --dir apps/web exec playwright test e2e/auth-shell.spec.ts
```

- [ ] **Step 3: Implement permanent navigation**

```typescript
const operationalDestinations = [
  { href: "/dashboard", label: "Visão geral" },
  { href: "/sessions", label: "Sessões" },
];
```

Render both as links. Remove connector line, node markup and circular status CSS. Use a compact cyan left border/background for the active route. Ensure mobile focus and labels remain visible.

- [ ] **Step 4: Run navigation GREEN**

Run Step 2. Expected: all tests pass.

- [ ] **Step 5: Write failing real critical-flow E2E**

Read the committed CSV, replace source dates in memory with `29/09/2026`, and upload it as `sems_assignment.csv`. Use the real API; do not route/mock requests.

```typescript
await page.goto("/settings/data-sources");
await uploadUniqueSeptemberFixture(page);
await page.getByRole("button", { name: "Confirmar importação" }).click();
await page.getByRole("link", { name: "Continuar fechamento" }).click();
await expect(page.getByText("0 de 2", { exact: true })).toBeVisible();
await page.getByRole("link", { name: "Revisar 2 pendências" }).click();
await page.getByRole("row", { name: /7,00 kWh/ }).click();
await page.getByLabel("Unidade responsável").selectOption({ label: /A-101/ });
await page.getByLabel("Justificativa").fill("Confirmado pela portaria");
await page.getByRole("button", { name: "Atribuir e revisar próxima" }).click();
await page.getByRole("link", { name: "Voltar para visão geral" }).click();
await expect(page.getByText("1 de 2", { exact: true })).toBeVisible();
await expect(
  page.getByRole("table", { name: "Custos por responsável" }),
).toContainText("Unidade A-101");
```

- [ ] **Step 6: Run critical-flow RED and fix only integration seams**

```bash
pnpm --dir apps/web exec playwright test e2e/monthly-close-handoff.spec.ts
```

Expected first failure must identify a real seam such as stale refresh, route parsing or unit display. Fix the smallest production seam and rerun until GREEN; do not weaken assertions.

- [ ] **Step 7: Update documentation**

Record the working Sessions route, unit-based audited assignment, untrusted raw Card ID, recurring navigation, post-import dashboard handoff, new API endpoints and `session_assignments` table. Preserve Sprint 1 history and label these as Sprint 2 execution behavior.

- [ ] **Step 8: Run the full repository gate**

```bash
pnpm check
git diff --check
git status --short
```

Expected: Ruff, mypy, API unit/integration tests, Alembic check, OpenAPI drift check, Vitest, TypeScript, ESLint, Webpack build and all Playwright tests exit `0`; diff check is silent; status shows only intended Task 8 files.

- [ ] **Step 9: Commit**

```bash
git add apps/web/src/components/shell apps/web/src/app/globals.css apps/web/e2e README.md docs/product/prd.md docs/technical/ev-chargeops-architecture.md
git diff --check
git commit -m "feat: complete recurring session review flow"
```

- [ ] **Step 10: Post-commit verification**

```bash
pnpm check
git status --short --branch
git log --oneline -8
```

Expected: full gate exits `0`, the worktree is clean and task commits appear in dependency order.
