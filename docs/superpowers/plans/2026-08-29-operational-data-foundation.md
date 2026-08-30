# Operational Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Checkpoint A: authenticated, organization-scoped and idempotent persistence of SEMS+ import batches, raw records and canonical charging sessions in Supabase PostgreSQL, while moving CSV ingestion behind a secondary data-source experience.

**Architecture:** Keep the existing FastAPI ingestion domain independent from SQLAlchemy, Supabase and HTTP. Add application ports for authentication, organization scope and persistence; implement them with Supabase JWT verification and SQLAlchemy async repositories. Next.js uses Supabase SSR only for authentication, continues to consume operational data through the generated FastAPI client, and makes `/dashboard` the authenticated product home.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic Settings, SQLAlchemy 2 async, Psycopg 3, Alembic, Supabase PostgreSQL/Auth/Storage, PyJWT, Next.js 16.3.3 App Router, React 19.2.8, TypeScript 5, `@supabase/ssr`, generated OpenAPI client, pytest and Playwright.

**Spec:** `docs/superpowers/specs/2026-08-29-demo-first-operational-platform-design.md`

## Global Constraints

- Node.js must be `>=22.13.0 <23`; use the repository `.nvmrc` and pnpm `11.19.0`.
- Python remains `>=3.12`; application and test commands run through `uv --project apps/api`.
- Supabase project ref is `lgjohsxipfctgooiuqnv`; project URL is `https://lgjohsxipfctgooiuqnv.supabase.co`.
- The project's public JWKS currently publishes an ES256 P-256 verification key; FastAPI must verify `alg`, signature, `exp`, `iss` and `aud` and must never trust decoded-but-unverified claims.
- Supabase secrets, database passwords, user passwords and service-role keys never enter Git, generated clients, browser bundles, logs, fixtures or this plan.
- The FastAPI backend is the only application component that reads or writes operational tables.
- The domain cannot import FastAPI, Pydantic, PyJWT, Supabase SDKs, SQLAlchemy, Alembic or database drivers.
- Every operational repository query and uniqueness rule is scoped by `organization_id`.
- Fixture authentication is permitted only when `APP_ENV` is `local` or `test`; configuration must fail closed if fixture auth is enabled in `demo` or `production`.
- CSV remains a `ChargingSessionSource` adapter. No GoodWe API credential is assumed and no command reaches the LAB FIAP charger.
- Real energy and timestamps remain immutable and labeled `real`; demonstration identity is stored separately as `assigned` or `simulated`.
- Tests cannot require Supabase or any external network service unless they are explicitly marked as live smoke tests.
- Next.js 16 uses `proxy.ts`, not deprecated `middleware.ts`, and `cookies()` is awaited.
- The default authenticated route is `/dashboard`; CSV tooling lives under `/settings/data-sources`.
- Each task follows RED -> GREEN -> focused verification -> commit. Do not combine task commits.

---

## File and Responsibility Map

### Shared backend foundation

- `apps/api/app/shared/config.py`: validated environment configuration and environment safety checks.
- `apps/api/app/shared/database.py`: async engine, session factory and request-scoped session dependency.
- `apps/api/app/shared/sqlalchemy.py`: declarative base and cross-module timestamp/UUID helpers.
- `apps/api/alembic/`: schema migration environment and immutable migration revisions.

### Identity and organization

- `apps/api/app/modules/identity/domain/auth.py`: `AuthPrincipal`, `OrganizationScope` and role values.
- `apps/api/app/modules/identity/application/ports.py`: token-verifier and scope-repository ports.
- `apps/api/app/modules/identity/application/resolve_scope.py`: verified-token to authorized organization-scope use case.
- `apps/api/app/modules/identity/infrastructure/supabase_jwt.py`: ES256 JWKS verification adapter.
- `apps/api/app/modules/identity/infrastructure/fixture_jwt.py`: fail-closed local/test adapter.
- `apps/api/app/modules/identity/infrastructure/repository.py`: SQLAlchemy profile and membership resolution.
- `apps/api/app/modules/identity/presentation/dependencies.py`: FastAPI bearer-token and scope dependencies.
- `apps/api/app/modules/organizations/infrastructure/models.py`: organization, site, charger, unit, profile and membership mappings.

### Persisted ingestion

- `apps/api/app/modules/ingestion/domain/import_batch.py`: persistence-facing immutable batch and record values.
- `apps/api/app/modules/ingestion/application/import_ports.py`: import repository and original-file store ports.
- `apps/api/app/modules/ingestion/application/review_import.py`: preview enriched with cross-batch duplicate detection.
- `apps/api/app/modules/ingestion/application/confirm_import.py`: idempotent transaction orchestration.
- `apps/api/app/modules/ingestion/application/list_imports.py`: batch history and detail queries.
- `apps/api/app/modules/ingestion/infrastructure/models.py`: batch, raw-record and charging-session mappings.
- `apps/api/app/modules/ingestion/infrastructure/repository.py`: organization-scoped SQLAlchemy adapter.
- `apps/api/app/modules/ingestion/infrastructure/file_store.py`: local/test and Supabase Storage original-file adapters.
- `apps/api/app/modules/ingestion/presentation/router.py`: authenticated preview, confirm, list and detail endpoints.

### Web authentication and product shell

- `apps/web/src/lib/supabase/client.ts`: per-browser Supabase client.
- `apps/web/src/lib/supabase/server.ts`: per-request server client using async cookies.
- `apps/web/src/lib/supabase/proxy.ts`: session refresh and protected-route redirect logic.
- `apps/web/src/proxy.ts`: Next.js 16 proxy entrypoint and matcher.
- `apps/web/src/app/login/`: password sign-in page and server action.
- `apps/web/src/app/(app)/layout.tsx`: authenticated navigation shell.
- `apps/web/src/app/(app)/dashboard/page.tsx`: Checkpoint A product-home foundation.
- `apps/web/src/app/(app)/settings/data-sources/page.tsx`: SEMS+ source management.
- `apps/web/src/components/imports/`: preview, confirmation and history components.
- `packages/api-client/src/index.ts`: authenticated API wrapper and import-batch operations.

---

### Task 1: Validated Settings and Async Database Boundary

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/.env.example`
- Create: `apps/api/app/shared/__init__.py`
- Create: `apps/api/app/shared/config.py`
- Create: `apps/api/app/shared/sqlalchemy.py`
- Create: `apps/api/app/shared/database.py`
- Create: `apps/api/tests/shared/test_config.py`
- Create: `apps/api/tests/shared/test_database.py`
- Modify: `package.json`

**Interfaces:**
- Produces: `Settings`, `get_settings()`, `Base`, `TimestampMixin`, `UuidPrimaryKeyMixin`, `create_engine_from_settings(settings)`, `create_session_factory(engine)` and `get_db_session()`.
- Consumes: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_AUDIENCE`, `SUPABASE_SERVICE_ROLE_KEY`, `ORIGINAL_FILE_STORE`, `ORIGINAL_FILES_ROOT`, `APP_ENV`, `AUTH_MODE`, `FIXTURE_AUTH_TOKEN` and `DEMO_MANAGER_EMAIL`.

- [ ] **Step 1: Add failing configuration tests**

```python
# apps/api/tests/shared/test_config.py
import pytest
from pydantic import ValidationError

from app.shared.config import Settings


def test_fixture_auth_is_allowed_for_tests() -> None:
    settings = Settings(
        app_env="test",
        auth_mode="fixture",
        database_url="sqlite+aiosqlite:///:memory:",
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
    )

    assert settings.supabase_issuer == (
        "https://lgjohsxipfctgooiuqnv.supabase.co/auth/v1"
    )
    assert settings.supabase_jwks_url.endswith("/.well-known/jwks.json")


def test_fixture_auth_fails_closed_in_production() -> None:
    with pytest.raises(ValidationError, match="fixture auth"):
        Settings(
            app_env="production",
            auth_mode="fixture",
            database_url="postgresql+psycopg://example.invalid/postgres",
            supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
            fixture_auth_token="fixture-manager-token",
        )


def test_demo_requires_supabase_original_file_store_and_service_key() -> None:
    with pytest.raises(ValidationError, match="supabase original file store"):
        Settings(
            app_env="demo",
            auth_mode="supabase",
            database_url="postgresql://example.invalid/postgres",
            supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
            original_file_store="supabase",
        )
```

```python
# apps/api/tests/shared/test_database.py
from sqlalchemy import text

from app.shared.config import Settings
from app.shared.database import create_engine_from_settings, create_session_factory


async def test_async_session_executes_against_test_database() -> None:
    settings = Settings(
        app_env="test",
        auth_mode="fixture",
        database_url="sqlite+aiosqlite:///:memory:",
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
    )
    engine = create_engine_from_settings(settings)
    factory = create_session_factory(engine)

    async with factory() as session:
        assert await session.scalar(text("select 1")) == 1

    await engine.dispose()


async def test_plain_postgres_url_uses_async_psycopg_driver() -> None:
    settings = Settings(
        app_env="local",
        auth_mode="fixture",
        database_url="postgresql://postgres:secret@localhost/postgres",
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
    )

    engine = create_engine_from_settings(settings)

    assert engine.url.drivername == "postgresql+psycopg"
    await engine.dispose()
```

- [ ] **Step 2: Run the tests and observe RED**

Run:

```bash
uv run --project apps/api pytest apps/api/tests/shared/test_config.py apps/api/tests/shared/test_database.py -q
```

Expected: collection fails because `app.shared.config` and `app.shared.database` do not exist.

- [ ] **Step 3: Add database, migration and JWT dependencies**

Run:

```bash
uv add --project apps/api "sqlalchemy[asyncio]>=2.0,<2.1" "psycopg[binary]>=3.2,<4" "alembic>=1.19,<2" "PyJWT[crypto]>=2.10,<3" "httpx>=0.28,<1"
uv add --project apps/api --dev "aiosqlite>=0.22,<1"
```

Expected: `apps/api/pyproject.toml` and `apps/api/uv.lock` contain the locked dependencies.

- [ ] **Step 4: Implement settings with environment safety validation**

```python
# apps/api/app/shared/config.py
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


API_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=API_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["local", "test", "demo", "production"] = "local"
    auth_mode: Literal["supabase", "fixture"] = "supabase"
    database_url: str
    supabase_url: str
    supabase_jwt_audience: str = "authenticated"
    supabase_service_role_key: str | None = None
    original_file_store: Literal["local", "supabase"] = "local"
    original_files_root: Path = API_ROOT / ".data" / "original-imports"
    fixture_auth_token: str | None = None
    demo_manager_email: str | None = None

    @model_validator(mode="after")
    def validate_auth_mode(self) -> "Settings":
        if self.auth_mode == "fixture" and self.app_env not in {"local", "test"}:
            raise ValueError("fixture auth is allowed only in local or test")
        if self.auth_mode == "fixture" and not self.fixture_auth_token:
            raise ValueError("fixture auth requires FIXTURE_AUTH_TOKEN")
        if self.original_file_store == "supabase" and not self.supabase_service_role_key:
            raise ValueError(
                "supabase original file store requires SUPABASE_SERVICE_ROLE_KEY"
            )
        if self.app_env in {"demo", "production"} and self.original_file_store != "supabase":
            raise ValueError("demo and production require the supabase original file store")
        return self

    @property
    def supabase_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_issuer}/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 5: Implement the async SQLAlchemy boundary**

```python
# apps/api/app/shared/sqlalchemy.py
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UuidPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
```

```python
# apps/api/app/shared/database.py
from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.shared.config import Settings, get_settings


def create_engine_from_settings(settings: Settings) -> AsyncEngine:
    url: URL = make_url(settings.database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return create_async_engine(url, pool_pre_ping=True)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_engine_from_settings(settings)
        _session_factory = create_session_factory(_engine)
    return _session_factory


async def get_db_session(
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[AsyncSession]:
    async with session_factory(settings)() as session:
        yield session
```

- [ ] **Step 6: Document exact non-secret variables and add migration commands**

```dotenv
# apps/api/.env.example
APP_ENV=local
AUTH_MODE=fixture
DATABASE_URL=sqlite+aiosqlite:///./ev_chargeops_local.db
SUPABASE_URL=https://lgjohsxipfctgooiuqnv.supabase.co
SUPABASE_JWT_AUDIENCE=authenticated
ORIGINAL_FILE_STORE=local
ORIGINAL_FILES_ROOT=./apps/api/.data/original-imports
FIXTURE_AUTH_TOKEN=fixture-manager-token
DEMO_MANAGER_EMAIL=manager@example.test
# Demo only; keep the real value in this ignored file and never in the web app.
SUPABASE_SERVICE_ROLE_KEY=
```

Add root scripts:

```json
{
  "db:upgrade": "uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head",
  "db:check": "uv run --project apps/api alembic -c apps/api/alembic.ini check"
}
```

- [ ] **Step 7: Run focused verification**

Run:

```bash
uv run --project apps/api pytest apps/api/tests/shared/test_config.py apps/api/tests/shared/test_database.py -q
uv run --project apps/api ruff check apps/api/app/shared apps/api/tests/shared
uv run --project apps/api mypy apps/api/app/shared
```

Expected: tests pass, Ruff reports `All checks passed!`, and mypy reports success.

- [ ] **Step 8: Commit Task 1**

```bash
git add package.json apps/api/pyproject.toml apps/api/uv.lock apps/api/.env.example apps/api/app/shared apps/api/tests/shared
git commit -m "feat: add validated database foundation"
```

---

### Task 2: Operational Models, Alembic and Deterministic Seed

**Files:**
- Create: `apps/api/alembic.ini`
- Create: `apps/api/alembic/env.py`
- Create: `apps/api/alembic/script.py.mako`
- Create: `apps/api/alembic/versions/20260829_0001_operational_foundation.py`
- Create: `apps/api/app/modules/organizations/__init__.py`
- Create: `apps/api/app/modules/organizations/infrastructure/__init__.py`
- Create: `apps/api/app/modules/organizations/infrastructure/models.py`
- Create: `apps/api/app/modules/ingestion/infrastructure/models.py`
- Create: `apps/api/app/modules/audit/__init__.py`
- Create: `apps/api/app/modules/audit/infrastructure/__init__.py`
- Create: `apps/api/app/modules/audit/infrastructure/models.py`
- Create: `apps/api/scripts/__init__.py`
- Create: `apps/api/scripts/seed_operational_foundation.py`
- Create: `apps/api/tests/integration/conftest.py`
- Create: `apps/api/tests/integration/test_migrations.py`
- Create: `apps/api/tests/integration/test_operational_seed.py`

**Interfaces:**
- Consumes: `Base`, UUID/timestamp mixins and `DATABASE_URL` from Task 1.
- Produces: ORM models and schema for `organizations`, `sites`, `chargers`, `units`, `profiles`, `memberships`, `import_batches`, `raw_import_records`, `charging_sessions` and `audit_events`.
- Produces stable demo identifiers: organization `10000000-0000-0000-0000-000000000001`, site `20000000-0000-0000-0000-000000000001`, charger `30000000-0000-0000-0000-000000000001`, units `A-101` through `A-104`.

- [ ] **Step 1: Write the migration and seed contract tests**

```python
# apps/api/tests/integration/test_migrations.py
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_creates_operational_tables(tmp_path: Path) -> None:
    database = tmp_path / "migration.db"
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")

    command.upgrade(config, "head")

    tables = set(inspect(create_engine(f"sqlite:///{database}")).get_table_names())
    assert {
        "organizations",
        "sites",
        "chargers",
        "units",
        "profiles",
        "memberships",
        "import_batches",
        "raw_import_records",
        "charging_sessions",
        "audit_events",
    } <= tables
```

```python
# apps/api/tests/integration/test_operational_seed.py
from scripts.seed_operational_foundation import seed_operational_foundation


async def test_seed_is_repeatable(async_session) -> None:
    await seed_operational_foundation(async_session)
    await seed_operational_foundation(async_session)

    assert await count_rows(async_session, OrganizationModel) == 1
    assert await count_rows(async_session, SiteModel) == 1
    assert await count_rows(async_session, ChargerModel) == 1
    assert await count_rows(async_session, UnitModel) == 4
```

Add this shared integration fixture and helper:

```python
# apps/api/tests/integration/conftest.py
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.modules.audit.infrastructure import models as audit_models  # noqa: F401
from app.modules.ingestion.infrastructure import models as ingestion_models  # noqa: F401
from app.modules.organizations.infrastructure import models as organization_models  # noqa: F401
from app.shared.sqlalchemy import Base


@pytest_asyncio.fixture
async def async_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def count_rows(session: AsyncSession, model: type[Base]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)
```

Import the four ORM model classes in `test_operational_seed.py` and pass those classes to `count_rows`; do not pass table-name strings.

- [ ] **Step 2: Run the contract tests and observe RED**

Run:

```bash
uv run --project apps/api pytest apps/api/tests/integration/test_migrations.py apps/api/tests/integration/test_operational_seed.py -q
```

Expected: collection fails because Alembic, ORM mappings and seed script do not exist.

- [ ] **Step 3: Implement organization, ingestion and audit mappings**

Use SQLAlchemy 2 typed mappings with these exact invariants:

```python
# Exact declarations; split them into the files in the responsibility map.
class OrganizationModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(160), nullable=False)


class SiteModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sites"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)


class ChargerModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chargers"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    serial: Mapped[str] = mapped_column(String(96), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    nominal_power_kw: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    __table_args__ = (UniqueConstraint("organization_id", "serial"),)


class UnitModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "units"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    __table_args__ = (UniqueConstraint("organization_id", "code"),)


class ProfileModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "profiles"
    auth_user_id: Mapped[UUID] = mapped_column(unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)


class MembershipModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    unit_id: Mapped[UUID | None] = mapped_column(ForeignKey("units.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    __table_args__ = (UniqueConstraint("organization_id", "profile_id"),)


class ImportBatchModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_batches"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    total_count: Mapped[int] = mapped_column(nullable=False)
    valid_count: Mapped[int] = mapped_column(nullable=False)
    invalid_count: Mapped[int] = mapped_column(nullable=False)
    duplicate_count: Mapped[int] = mapped_column(nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    __table_args__ = (UniqueConstraint("organization_id", "checksum"),)


class RawImportRecordModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "raw_import_records"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("import_batches.id"), index=True)
    row_number: Mapped[int] = mapped_column(nullable=False)
    raw_payload: Mapped[dict[str, str | None]] = mapped_column(JSON, nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    error_field: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("import_batch_id", "row_number"),)


class ChargingSessionModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "charging_sessions"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    charger_id: Mapped[UUID] = mapped_column(ForeignKey("chargers.id"), index=True)
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("import_batches.id"), index=True)
    raw_record_id: Mapped[UUID] = mapped_column(ForeignKey("raw_import_records.id"), unique=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    deduplication_key: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    energy_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    charge_port: Mapped[int | None] = mapped_column(nullable=True)
    card_id_raw: Mapped[str | None] = mapped_column(String(160), nullable=True)
    identity_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    __table_args__ = (UniqueConstraint("organization_id", "deduplication_key"),)


class AuditEventModel(UuidPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_profile_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(index=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
```

- [ ] **Step 4: Create the explicit initial Alembic revision**

Initialize the async Alembic template and replace generated revision logic with explicit `op.create_table`, `op.create_index` and `op.create_unique_constraint` calls matching Step 3. Import all model modules in `alembic/env.py` before setting `target_metadata = Base.metadata`. The downgrade drops tables in reverse foreign-key order.

Run:

```bash
uv run --project apps/api alembic init -t async apps/api/alembic
```

Then keep only the files listed in this task and set `script_location = %(here)s/alembic` in `apps/api/alembic.ini`. `env.py` reads `DATABASE_URL` through `Settings` unless the test overrides `sqlalchemy.url`.

- [ ] **Step 5: Implement the deterministic business-data seed**

```python
# apps/api/scripts/seed_operational_foundation.py
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organizations.infrastructure.models import (
    ChargerModel,
    OrganizationModel,
    SiteModel,
    UnitModel,
)
from app.shared.sqlalchemy import UuidPrimaryKeyMixin

DEMO_ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
DEMO_SITE_ID = UUID("20000000-0000-0000-0000-000000000001")
DEMO_CHARGER_ID = UUID("30000000-0000-0000-0000-000000000001")
DEMO_UNIT_IDS = {
    code: UUID(f"40000000-0000-0000-0000-{index:012d}")
    for index, code in enumerate(("A-101", "A-102", "A-103", "A-104"), start=1)
}

async def add_if_missing(
    session: AsyncSession,
    instance: UuidPrimaryKeyMixin,
) -> None:
    if await session.get(type(instance), instance.id) is None:
        session.add(instance)


async def seed_operational_foundation(session: AsyncSession) -> None:
    await add_if_missing(
        session,
        OrganizationModel(
            id=DEMO_ORGANIZATION_ID,
            name="LAB FIAP Eco Smart Home",
        ),
    )
    await add_if_missing(
        session,
        SiteModel(
            id=DEMO_SITE_ID,
            organization_id=DEMO_ORGANIZATION_ID,
            name="LAB FIAP Eco Smart Home",
            timezone="America/Sao_Paulo",
        ),
    )
    await add_if_missing(
        session,
        ChargerModel(
            id=DEMO_CHARGER_ID,
            organization_id=DEMO_ORGANIZATION_ID,
            site_id=DEMO_SITE_ID,
            serial="97500NAP25BL0008",
            name="GoodWe HCA G2",
            nominal_power_kw=Decimal("11.000"),
        ),
    )
    for code, identifier in DEMO_UNIT_IDS.items():
        await add_if_missing(
            session,
            UnitModel(
                id=identifier,
                organization_id=DEMO_ORGANIZATION_ID,
                code=code,
                display_name=f"Unidade {code}",
            ),
        )
    await session.commit()
```

The script entrypoint creates a session through Task 1's factory, calls this function and disposes the engine. It must not create auth users or contain names, emails or passwords.

- [ ] **Step 6: Run GREEN migration, seed and schema verification**

Run:

```bash
uv run --project apps/api pytest apps/api/tests/integration/test_migrations.py apps/api/tests/integration/test_operational_seed.py -q
uv run --project apps/api alembic -c apps/api/alembic.ini check
uv run --project apps/api ruff check apps/api/app/modules/organizations apps/api/app/modules/ingestion/infrastructure/models.py apps/api/app/modules/audit apps/api/scripts apps/api/tests/integration
```

Expected: both tests pass, Alembic reports no pending model operations, and Ruff is clean.

- [ ] **Step 7: Commit Task 2**

```bash
git add apps/api/alembic.ini apps/api/alembic apps/api/app/modules/organizations apps/api/app/modules/ingestion/infrastructure/models.py apps/api/app/modules/audit apps/api/scripts/seed_operational_foundation.py apps/api/tests/integration
git commit -m "feat: add operational persistence schema"
```

---

### Task 3: Supabase JWT Verification and Organization Scope

**Files:**
- Create: `apps/api/app/modules/identity/__init__.py`
- Create: `apps/api/app/modules/identity/domain/__init__.py`
- Create: `apps/api/app/modules/identity/domain/auth.py`
- Create: `apps/api/app/modules/identity/domain/errors.py`
- Create: `apps/api/app/modules/identity/application/__init__.py`
- Create: `apps/api/app/modules/identity/application/ports.py`
- Create: `apps/api/app/modules/identity/application/resolve_scope.py`
- Create: `apps/api/app/modules/identity/infrastructure/__init__.py`
- Create: `apps/api/app/modules/identity/infrastructure/supabase_jwt.py`
- Create: `apps/api/app/modules/identity/infrastructure/fixture_jwt.py`
- Create: `apps/api/app/modules/identity/infrastructure/repository.py`
- Create: `apps/api/app/modules/identity/presentation/__init__.py`
- Create: `apps/api/app/modules/identity/presentation/dependencies.py`
- Create: `apps/api/app/modules/identity/presentation/router.py`
- Create: `apps/api/tests/modules/identity/conftest.py`
- Create: `apps/api/tests/modules/identity/application/test_resolve_scope.py`
- Create: `apps/api/tests/modules/identity/infrastructure/test_supabase_jwt.py`
- Create: `apps/api/tests/modules/identity/presentation/test_me_endpoint.py`
- Modify: `apps/api/app/main.py`

**Interfaces:**
- Produces: `AuthPrincipal`, `OrganizationScope`, `OrganizationRole`, `TokenVerifier.verify(token)`, `ScopeRepository.resolve(principal)`, `ResolveScope.execute(token)` and FastAPI `current_scope()`.
- Consumes: ES256 JWKS, issuer and audience from Task 1; profile/membership models from Task 2.

- [ ] **Step 1: Write failing domain and adapter tests**

```python
# apps/api/tests/modules/identity/application/test_resolve_scope.py
from dataclasses import dataclass
from uuid import UUID

import pytest

from app.modules.identity.application.resolve_scope import ResolveScope
from app.modules.identity.domain.auth import (
    AuthPrincipal,
    OrganizationRole,
    OrganizationScope,
)
from app.modules.identity.domain.errors import OrganizationAccessDenied


@dataclass
class FakeVerifier:
    user_id: UUID
    email: str

    def verify(self, token: str) -> AuthPrincipal:
        assert token == "signed-token"
        return AuthPrincipal(self.user_id, self.email)


class FakeScopeRepository:
    organization_id = UUID(int=20)

    def __init__(self, role: OrganizationRole | None) -> None:
        self.role = role

    async def resolve(self, principal: AuthPrincipal) -> OrganizationScope | None:
        if self.role is None:
            return None
        return OrganizationScope(
            auth_user_id=principal.user_id,
            profile_id=UUID(int=30),
            organization_id=self.organization_id,
            role=self.role,
            unit_id=None,
        )


async def test_resolve_scope_uses_verified_subject_and_membership() -> None:
    verifier = FakeVerifier(user_id=UUID(int=10), email="manager@example.test")
    repository = FakeScopeRepository(role=OrganizationRole.MANAGER)

    scope = await ResolveScope(verifier, repository).execute("signed-token")

    assert scope.auth_user_id == UUID(int=10)
    assert scope.organization_id == repository.organization_id
    assert scope.role is OrganizationRole.MANAGER


async def test_resolve_scope_rejects_user_without_membership() -> None:
    with pytest.raises(OrganizationAccessDenied):
        await ResolveScope(
            FakeVerifier(UUID(int=11), "outsider@example.test"),
            FakeScopeRepository(role=None),
        ).execute("signed-token")
```

```python
# apps/api/tests/modules/identity/infrastructure/test_supabase_jwt.py
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.shared.config import Settings
from app.modules.identity.domain.errors import InvalidAccessToken
from app.modules.identity.infrastructure.supabase_jwt import SupabaseJwtVerifier


class FakeSigningKey:
    def __init__(self, key: object) -> None:
        self.key = key


class FakeJwks:
    def __init__(self, public_key: object) -> None:
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
        assert token
        return FakeSigningKey(self.public_key)


def settings() -> Settings:
    return Settings(
        app_env="test",
        auth_mode="fixture",
        database_url="sqlite+aiosqlite:///:memory:",
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
    )


def sign_token(private_key: object, kid: str, claims: dict[str, object]) -> str:
    return jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": kid})


def valid_claims() -> dict[str, object]:
    return {
        "sub": str(uuid4()),
        "email": "manager@example.test",
        "aud": "authenticated",
        "iss": "https://lgjohsxipfctgooiuqnv.supabase.co/auth/v1",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }


def signed_token_with_invalid_claim(claim: str, ec_key_pair) -> str:
    claims = valid_claims()
    replacements: dict[str, object] = {
        "aud": "wrong-audience",
        "iss": "https://issuer.invalid",
        "exp": datetime.now(UTC) - timedelta(minutes=1),
    }
    claims[claim] = replacements[claim]
    return sign_token(ec_key_pair.private, "test-key", claims)


def test_supabase_verifier_accepts_expected_es256_claims(ec_key_pair) -> None:
    token = sign_token(
        ec_key_pair.private,
        kid="test-key",
        claims={
            "sub": str(uuid4()),
            "email": "manager@example.test",
            "aud": "authenticated",
            "iss": "https://lgjohsxipfctgooiuqnv.supabase.co/auth/v1",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
    )
    verifier = SupabaseJwtVerifier(settings(), jwks_client=FakeJwks(ec_key_pair.public))

    principal = verifier.verify(token)

    assert principal.email == "manager@example.test"


@pytest.mark.parametrize("claim", ["aud", "iss", "exp"])
def test_supabase_verifier_rejects_invalid_required_claim(claim, ec_key_pair) -> None:
    token = signed_token_with_invalid_claim(claim, ec_key_pair)
    verifier = SupabaseJwtVerifier(settings(), jwks_client=FakeJwks(ec_key_pair.public))

    with pytest.raises(InvalidAccessToken):
        verifier.verify(token)
```

`apps/api/tests/modules/identity/conftest.py` defines an `EcKeyPair` dataclass and an `ec_key_pair` fixture using `cryptography.hazmat.primitives.asymmetric.ec.generate_private_key(ec.SECP256R1())`. These helpers perform no network calls.

- [ ] **Step 2: Run RED identity tests**

Run:

```bash
uv run --project apps/api pytest apps/api/tests/modules/identity -q
```

Expected: collection fails because identity modules do not exist.

- [ ] **Step 3: Implement pure identity values and ports**

```python
# apps/api/app/modules/identity/domain/auth.py
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class OrganizationRole(StrEnum):
    MANAGER = "manager"
    RESIDENT = "resident"
    TECHNICAL_OPERATOR = "technical_operator"


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    user_id: UUID
    email: str


@dataclass(frozen=True, slots=True)
class OrganizationScope:
    auth_user_id: UUID
    profile_id: UUID
    organization_id: UUID
    role: OrganizationRole
    unit_id: UUID | None
```

```python
# apps/api/app/modules/identity/application/ports.py
from typing import Protocol


class TokenVerifier(Protocol):
    def verify(self, token: str) -> AuthPrincipal: ...


class ScopeRepository(Protocol):
    async def resolve(self, principal: AuthPrincipal) -> OrganizationScope | None: ...
```

`ResolveScope.execute()` verifies first, then resolves membership, and raises stable `InvalidAccessToken` or `OrganizationAccessDenied` domain errors. It never accepts organization or role from request parameters.

- [ ] **Step 4: Implement ES256 JWKS and fixture adapters**

```python
# apps/api/app/modules/identity/infrastructure/supabase_jwt.py
from uuid import UUID

import jwt
from jwt import PyJWKClient


class SupabaseJwtVerifier:
    def __init__(self, settings: Settings, jwks_client: PyJWKClient | None = None) -> None:
        self.settings = settings
        self.jwks = jwks_client or PyJWKClient(settings.supabase_jwks_url, cache_keys=True)

    def verify(self, token: str) -> AuthPrincipal:
        try:
            signing_key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256"],
                audience=self.settings.supabase_jwt_audience,
                issuer=self.settings.supabase_issuer,
                options={"require": ["sub", "email", "aud", "iss", "exp"]},
            )
            return AuthPrincipal(user_id=UUID(claims["sub"]), email=claims["email"])
        except (jwt.PyJWTError, ValueError, KeyError) as error:
            raise InvalidAccessToken() from error
```

`FixtureTokenVerifier` accepts only `settings.fixture_auth_token` and returns stable fixture principal UUID `50000000-0000-0000-0000-000000000001`. It is constructed only after `Settings` has enforced the environment guard.

- [ ] **Step 5: Implement organization scope resolution and controlled manager bootstrap**

`SqlAlchemyScopeRepository.resolve()` queries `profiles.auth_user_id`, then `memberships.profile_id`, always selecting one organization membership. If no membership exists and the verified email exactly equals `DEMO_MANAGER_EMAIL`, it creates the profile and a manager membership for the stable demo organization in one transaction. Any other missing membership returns `None`.

Add tests proving:

```python
async def test_bootstrap_creates_only_allowlisted_manager(async_session) -> None:
    repository = SqlAlchemyScopeRepository(async_session, demo_manager_email="manager@example.test")
    scope = await repository.resolve(AuthPrincipal(UUID(int=50), "manager@example.test"))
    assert scope is not None
    assert scope.role is OrganizationRole.MANAGER


async def test_bootstrap_does_not_provision_other_email(async_session) -> None:
    repository = SqlAlchemyScopeRepository(async_session, demo_manager_email="manager@example.test")
    assert await repository.resolve(
        AuthPrincipal(UUID(int=51), "other@example.test")
    ) is None
```

- [ ] **Step 6: Add FastAPI scope dependency and `/v1/me` endpoint**

The dependency uses `HTTPBearer(auto_error=False)`, returns 401 for missing or invalid token and 403 for a verified user without membership. `/v1/me` returns only:

```json
{
  "profileId": "uuid",
  "organizationId": "uuid",
  "role": "manager",
  "unitId": null
}
```

Use dependency factories so tests override the verifier and session without network access.

- [ ] **Step 7: Run GREEN identity verification**

Run:

```bash
uv run --project apps/api pytest apps/api/tests/modules/identity -q
uv run --project apps/api ruff check apps/api/app/modules/identity apps/api/tests/modules/identity
uv run --project apps/api mypy apps/api/app/modules/identity
```

Expected: all identity tests pass; Ruff and mypy are clean.

- [ ] **Step 8: Commit Task 3**

```bash
git add apps/api/app/main.py apps/api/app/modules/identity apps/api/tests/modules/identity
git commit -m "feat: authorize Supabase organization scopes"
```

---

### Task 4: Cross-Batch Review and Idempotent Confirm Import

**Files:**
- Create: `apps/api/app/modules/ingestion/domain/import_batch.py`
- Create: `apps/api/app/modules/ingestion/application/import_ports.py`
- Create: `apps/api/app/modules/ingestion/application/review_import.py`
- Create: `apps/api/app/modules/ingestion/application/confirm_import.py`
- Create: `apps/api/app/modules/ingestion/application/list_imports.py`
- Create: `apps/api/app/modules/ingestion/infrastructure/repository.py`
- Create: `apps/api/app/modules/ingestion/infrastructure/file_store.py`
- Create: `apps/api/tests/modules/ingestion/application/fakes.py`
- Create: `apps/api/tests/modules/ingestion/application/test_review_import.py`
- Create: `apps/api/tests/modules/ingestion/application/test_confirm_import.py`
- Create: `apps/api/tests/modules/ingestion/infrastructure/test_import_repository.py`
- Create: `apps/api/tests/modules/ingestion/infrastructure/test_file_store.py`
- Modify: `apps/api/app/modules/ingestion/application/preview_import.py`

**Interfaces:**
- Consumes: `ImportPreview`, `PreviewRecord`, `OrganizationScope`, SQLAlchemy mappings and `ChargingSessionSource`.
- Produces: `ImportRepository.existing_keys()`, `find_batch_by_checksum()`, `save_import()`, `list_batches()`, `get_batch()`; `OriginalFileStore.put()` and `delete()`; `ReviewImport.execute()`; `ConfirmImport.execute()`.

- [ ] **Step 1: Write RED use-case tests for cross-batch duplicates and replay**

```python
# apps/api/tests/modules/ingestion/application/test_review_import.py
async def test_review_marks_existing_database_session_duplicate() -> None:
    preview = preview_for_fixture()
    repository = FakeImportRepository(existing_keys={preview.records[0].session.deduplication_key})

    reviewed = await ReviewImport(repository).execute(scope(), preview)

    assert reviewed.records[0].classification == "duplicate"
    assert reviewed.duplicate_count == 1
    assert reviewed.valid_count == 1
```

```python
# apps/api/tests/modules/ingestion/application/test_confirm_import.py
async def test_confirm_persists_batch_raw_records_and_only_valid_sessions() -> None:
    repository = FakeImportRepository()
    store = FakeOriginalFileStore(path="imports/org/checksum.csv")

    result = await ConfirmImport(source(), repository, store).execute(
        scope(), "sems.csv", mixed_content()
    )

    assert result.created is True
    assert result.total_count == 3
    assert len(repository.saved_raw_records) == 3
    assert len(repository.saved_sessions) == 1
    assert repository.saved_sessions[0].raw_record_id is not None


async def test_confirm_replays_existing_checksum_without_new_writes() -> None:
    repository = FakeImportRepository(existing_batch=existing_batch())

    result = await ConfirmImport(source(), repository, FakeOriginalFileStore()).execute(
        scope(), "sems.csv", fixture_content()
    )

    assert result.created is False
    assert repository.save_calls == 0
```

Implement the named helpers in `application/fakes.py` in the same RED step:

- `scope()` returns manager scope IDs `5000...001`, `6000...001` and organization `1000...001`;
- `source()` returns the existing `SemsCsvSource` adapter;
- `fixture_content()` reads the existing `sems_sessions.csv` bytes and `mixed_content()` contains one valid, one invalid and one repeated row using the exact existing CSV header;
- `preview_for_fixture()` calls the existing `PreviewImport(source()).execute("sems_sessions.csv", fixture_content())`;
- `FakeImportRepository` records `saved_raw_records`, `saved_sessions` and `save_calls`, returns the constructor's `existing_keys`/`existing_batch`, and implements every `ImportRepository` method with in-memory deterministic results;
- `FakeOriginalFileStore` records `put_calls` and `deleted_paths`, returns its configured path, and never touches disk;
- `existing_batch()` returns a stable completed `ImportBatchResult` with `created=True`, then `ConfirmImport` must return a replaced value with `created=False`.

The fakes import the same port and domain types as production; do not introduce a test-only use-case signature.

- [ ] **Step 2: Run focused tests and observe RED**

Run:

```bash
uv run --project apps/api pytest apps/api/tests/modules/ingestion/application/test_review_import.py apps/api/tests/modules/ingestion/application/test_confirm_import.py -q
```

Expected: collection fails because the use cases and ports do not exist.

- [ ] **Step 3: Add immutable persistence-facing domain values**

```python
# apps/api/app/modules/ingestion/domain/import_batch.py
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PersistedRawRecord:
    id: UUID
    row_number: int
    raw: dict[str, str | None]
    classification: Literal["valid", "invalid", "duplicate"]
    error_field: str | None
    error_code: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class ImportBatchResult:
    id: UUID
    filename: str
    checksum: str
    source: str
    status: Literal["completed"]
    created: bool
    total_count: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    created_at: datetime
```

`ImportRepository.save_import()` receives the reviewed preview plus scope, resolved site/charger IDs, storage path and actor profile ID. It owns one transaction and returns `ImportBatchResult`.

- [ ] **Step 4: Implement review and confirmation orchestration**

`ReviewImport.execute(scope, preview)` collects non-null candidate keys, calls `existing_keys(organization_id, keys)` once, and returns a new immutable preview where database matches become `duplicate`. Invalid rows stay invalid and within-file duplicates remain duplicate.

`ConfirmImport.execute()` executes in this order:

```python
checksum = sha256(content).hexdigest()
existing = await repository.find_batch_by_checksum(scope.organization_id, checksum)
if existing:
    return replace(existing, created=False)

preview = PreviewImport(source).execute(filename, content)
reviewed = await ReviewImport(repository).execute(scope, preview)
storage_path = await file_store.put(scope.organization_id, checksum, filename, content)
return await repository.save_import(scope, reviewed, storage_path)
```

If storage succeeds and database persistence fails, `ConfirmImport` calls `file_store.delete(storage_path)` before re-raising. Local/test storage writes under a temporary directory; Supabase Storage uses bucket `sems-imports` and object path `{organization_id}/{checksum}/{sanitized_filename}`.

Implement two adapters behind the same port:

```python
class OriginalFileStore(Protocol):
    async def put(
        self,
        organization_id: UUID,
        checksum: str,
        filename: str,
        content: bytes,
    ) -> str: ...

    async def delete(self, storage_path: str) -> None: ...
```

`LocalOriginalFileStore` resolves every object beneath `ORIGINAL_FILES_ROOT`, rejects path traversal after `Path.resolve()`, creates parent directories and writes bytes. `SupabaseOriginalFileStore` receives an injected `httpx.AsyncClient`, project URL and service-role key. It uses these exact Storage API requests:

```python
headers = {
    "apikey": service_role_key,
    "Authorization": f"Bearer {service_role_key}",
}

# Upload one immutable object; a repeated path is an idempotent success only
# after ConfirmImport has already checked the batch checksum.
await client.post(
    f"{supabase_url}/storage/v1/object/sems-imports/{quote(object_path, safe='/')}",
    headers={**headers, "Content-Type": "text/csv", "x-upsert": "false"},
    content=content,
)

# Compensating cleanup after a database failure.
await client.request(
    "DELETE",
    f"{supabase_url}/storage/v1/object/sems-imports",
    headers={**headers, "Content-Type": "application/json"},
    json={"prefixes": [object_path]},
)
```

Call `raise_for_status()` for both operations and wrap `httpx.HTTPError` in a stable `OriginalFileStorageError`. The service-role key stays backend-only. `test_file_store.py` uses `httpx.MockTransport` to assert method, URL, headers and delete body without network access; it also proves that local traversal such as `../../secret.csv` is rejected.

- [ ] **Step 5: Implement the SQLAlchemy import repository**

The repository must:

- scope every query by `organization_id`;
- resolve charger serial to the seeded charger in the same organization;
- insert one raw record per preview row;
- flush each raw record before constructing its session so `raw_record_id` is available;
- insert sessions only for `valid` records;
- use the database unique constraints as the final idempotency defense;
- map a concurrent checksum or session-key integrity conflict to a stable replay or duplicate result;
- create one `AuditEventModel(event_type="import_completed")` with counts but no raw payload;
- commit once after the entire batch is consistent.

Repository integration tests use two organizations and prove that identical session keys in different organizations do not conflict, while duplicates inside one organization do.

- [ ] **Step 6: Run GREEN application and repository tests**

Run:

```bash
uv run --project apps/api pytest apps/api/tests/modules/ingestion/application apps/api/tests/modules/ingestion/infrastructure/test_import_repository.py -q
uv run --project apps/api ruff check apps/api/app/modules/ingestion apps/api/tests/modules/ingestion
uv run --project apps/api mypy apps/api/app/modules/ingestion
```

Expected: all focused tests pass; Ruff and mypy are clean.

- [ ] **Step 7: Commit Task 4**

```bash
git add apps/api/app/modules/ingestion apps/api/tests/modules/ingestion
git commit -m "feat: persist idempotent charging imports"
```

---

### Task 5: Authenticated Import REST Contract and TypeScript Client

**Files:**
- Modify: `apps/api/app/modules/ingestion/presentation/router.py`
- Modify: `apps/api/app/modules/ingestion/presentation/schemas.py`
- Create: `apps/api/app/modules/ingestion/presentation/dependencies.py`
- Create: `apps/api/tests/modules/ingestion/presentation/conftest.py`
- Create: `apps/api/tests/modules/ingestion/presentation/test_confirm_endpoint.py`
- Create: `apps/api/tests/modules/ingestion/presentation/test_import_history_endpoint.py`
- Modify: `apps/api/tests/modules/ingestion/presentation/test_preview_endpoint.py`
- Modify: `packages/api-client/src/index.ts`
- Modify: `packages/api-client/src/index.test.ts`
- Regenerate: `packages/api-client/openapi.json`
- Regenerate: `packages/api-client/src/schema.ts`

**Interfaces:**
- Produces: authenticated `POST /v1/import-batches/preview`, `POST /v1/import-batches`, `GET /v1/import-batches`, `GET /v1/import-batches/{batch_id}`.
- Produces client functions `previewImport(file, token, baseUrl?)`, `confirmImport(file, token, baseUrl?)`, `listImportBatches(token, baseUrl?)` and `getImportBatch(batchId, token, baseUrl?)`.

- [ ] **Step 1: Write endpoint RED tests**

```python
def test_confirm_endpoint_persists_authenticated_batch(api_client, fixture_token) -> None:
    response = api_client.post(
        "/v1/import-batches",
        headers={"Authorization": f"Bearer {fixture_token}"},
        files={"file": ("sems.csv", FIXTURE.read_bytes(), "text/csv")},
    )
    assert response.status_code == 201
    assert response.json()["created"] is True
    assert response.json()["validCount"] == 2


def test_confirm_replay_returns_existing_batch(api_client, fixture_token) -> None:
    first = post_fixture(api_client, fixture_token)
    replay = post_fixture(api_client, fixture_token)
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["created"] is False


def test_import_endpoints_require_bearer_token(api_client) -> None:
    assert api_client.get("/v1/import-batches").status_code == 401
    assert api_client.post("/v1/import-batches/preview").status_code == 401
```

History tests assert descending `createdAt`, summary counts and 404 when a batch belongs to another organization.

`presentation/conftest.py` creates a fresh in-memory SQLite schema per test, runs `seed_operational_foundation`, inserts the fixed fixture profile/membership, overrides `get_db_session` to yield that session, and configures `get_settings` with `APP_ENV=test`, fixture bearer `fixture-manager-token` and a temporary local original-file root. `api_client` is a `TestClient(app)` whose dependency overrides are cleared in fixture teardown; `fixture_token` returns the exact token above; `post_fixture()` posts the existing `sems_sessions.csv`. No endpoint test shares database or filesystem state.

- [ ] **Step 2: Run RED endpoint tests**

Run:

```bash
uv run --project apps/api pytest apps/api/tests/modules/ingestion/presentation -q
```

Expected: existing preview tests require fixture dependency updates and new routes return 404.

- [ ] **Step 3: Implement schemas, dependencies and endpoints**

Add:

```python
class ImportBatchResponse(ApiSchema):
    id: UUID
    filename: str
    checksum: str
    source: str
    status: str
    created: bool
    total_count: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    created_at: datetime


class ImportBatchListResponse(ApiSchema):
    items: list[ImportBatchResponse]
```

Preview calls the existing parser and `ReviewImport` so it reports database duplicates. Confirm returns 201 when `created=True` and 200 for checksum replay. The batch detail response includes raw-record classification and persisted session ID but never exposes an unrestricted storage URL.

- [ ] **Step 4: Regenerate OpenAPI and write TypeScript client RED tests**

```typescript
it("sends the bearer token when confirming an import", async () => {
  fetchMock.mockResolvedValueOnce(
    new Response(JSON.stringify(batchPayload), { status: 201 }),
  );
  const file = new File(["csv"], "sems.csv", { type: "text/csv" });

  await confirmImport(file, "signed-token", "http://api.test");

  expect(fetchMock).toHaveBeenCalledWith(
    "http://api.test/v1/import-batches",
    expect.objectContaining({
      method: "POST",
      headers: { Authorization: "Bearer signed-token" },
    }),
  );
});
```

Run:

```bash
pnpm generate:api
pnpm --filter @ev-chargeops/api-client test
```

Expected: contract generation succeeds; client tests fail before exports are implemented.

- [ ] **Step 5: Implement one authenticated client request wrapper**

```typescript
async function apiRequest<T>(
  path: string,
  token: string,
  init: RequestInit = {},
  baseUrl = "/api",
): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      ...init.headers,
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) throw new ApiError(response.status, await response.json());
  return response.json() as Promise<T>;
}
```

Multipart functions must not set `Content-Type`; the browser supplies the boundary. Export response types from generated `components["schemas"]`.

- [ ] **Step 6: Run GREEN contract and API-client gates**

Run:

```bash
uv run --project apps/api pytest apps/api/tests/modules/ingestion/presentation -q
pnpm check:api-contract
pnpm test:api-client
pnpm typecheck:api-client
```

Expected: endpoint tests, drift check, Vitest and TypeScript all pass.

- [ ] **Step 7: Commit Task 5**

```bash
git add apps/api/app/modules/ingestion/presentation apps/api/tests/modules/ingestion/presentation packages/api-client
git commit -m "feat: expose authenticated import batches"
```

---

### Task 6: Supabase SSR Login and Protected Product Shell

**Files:**
- Modify: `apps/web/package.json`
- Modify: `pnpm-lock.yaml`
- Modify: `apps/web/.env.example`
- Create: `apps/web/src/lib/supabase/client.ts`
- Create: `apps/web/src/lib/supabase/server.ts`
- Create: `apps/web/src/lib/supabase/proxy.ts`
- Create: `apps/web/src/lib/auth/access-token.ts`
- Create: `apps/web/src/proxy.ts`
- Create: `apps/web/src/app/login/actions.ts`
- Create: `apps/web/src/app/login/page.tsx`
- Create: `apps/web/src/app/(app)/layout.tsx`
- Create: `apps/web/src/components/shell/app-shell.tsx`
- Create: `apps/web/src/app/(app)/dashboard/page.tsx`
- Modify: `apps/web/src/app/page.tsx`
- Create: `apps/web/e2e/auth-shell.spec.ts`
- Modify: `apps/web/playwright.config.ts`

**Interfaces:**
- Produces: password login, session refresh proxy, authenticated shell and `/dashboard` landing page.
- Consumes: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, server-only `AUTH_MODE`, Supabase cookies and FastAPI fixture-auth configuration.

- [ ] **Step 1: Install official Supabase SSR dependencies**

Run:

```bash
pnpm --filter web add @supabase/ssr @supabase/supabase-js
```

- [ ] **Step 2: Write the protected-shell RED E2E tests**

```typescript
test("opens the manager product at the dashboard", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Visão operacional" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Fontes de dados" })).toBeVisible();
});

test("redirects an unauthenticated Supabase session to login", async ({ page }) => {
  await page.setExtraHTTPHeaders({ "x-ev-auth-test": "missing" });
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: "Entrar no EV ChargeOps" })).toBeVisible();
});
```

Both tests run in the same fixture-auth Playwright project. Only the second sends `x-ev-auth-test: missing`. Proxy recognizes that header exclusively when `AUTH_MODE=fixture` and `NODE_ENV !== "production"`, which deterministically exercises the unauthenticated redirect without contacting Supabase.

- [ ] **Step 3: Run RED shell test**

Run:

```bash
pnpm --dir apps/web exec playwright test e2e/auth-shell.spec.ts
```

Expected: `/` still redirects to `/imports/new` and no protected shell exists.

- [ ] **Step 4: Add current Supabase SSR client helpers**

```typescript
// apps/web/src/lib/supabase/client.ts
import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
  );
}
```

```typescript
// apps/web/src/lib/supabase/server.ts
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll(items) {
          try {
            items.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // Server Components cannot write cookies; proxy refresh owns it.
          }
        },
      },
    },
  );
}
```

`src/lib/supabase/proxy.ts` follows the current Supabase SSR pattern: create a client per request, call `auth.getClaims()` immediately, preserve response cookies and redirect missing users to `/login`. `src/proxy.ts` exports `proxy()` and excludes static assets. Do not create `middleware.ts`.

- [ ] **Step 5: Add a guarded fixture-auth path for deterministic E2E**

When server-only `AUTH_MODE=fixture` and `NODE_ENV !== "production"`, proxy treats requests as the fixed manager unless `x-ev-auth-test` is exactly `missing`; `getAccessToken()` returns `fixture-manager-token`. If fixture mode is present with `NODE_ENV=production`, throw during server initialization. The Playwright web server receives `AUTH_MODE=fixture`; its API server receives matching `APP_ENV=test`, `AUTH_MODE=fixture` and `FIXTURE_AUTH_TOKEN=fixture-manager-token`. Production code never reads a query parameter, cookie or client-visible variable to choose fixture authentication.

- [ ] **Step 6: Implement login and authenticated shell**

`login(formData)` validates non-empty email/password, calls `supabase.auth.signInWithPassword`, returns a generic Portuguese error on failure and redirects to `/dashboard` on success. It never logs credentials.

The shell navigation contains, in order: `Visão geral`, `Moradores e custos`, `Sessões`, `Insights`, `Faturas` and a secondary `Fontes de dados` under settings. Checkpoint A renders inactive future links with `aria-disabled="true"`; only dashboard and data sources are active.

The dashboard foundation heading is `Visão operacional` and states that the next checkpoint will add period totals, residents, action queue and close readiness. It must not contain an upload form.

- [ ] **Step 7: Run GREEN web verification**

Run:

```bash
pnpm --dir apps/web exec playwright test e2e/auth-shell.spec.ts
pnpm lint:web
pnpm --dir apps/web exec next build --webpack
```

Expected: two shell tests pass; lint and production build pass.

- [ ] **Step 8: Commit Task 6**

```bash
git add apps/web pnpm-lock.yaml
git commit -m "feat: add authenticated product shell"
```

---

### Task 7: Secondary Data-Source Workflow, Confirmation and History

**Files:**
- Create: `apps/web/src/app/(app)/settings/data-sources/page.tsx`
- Create: `apps/web/src/components/imports/import-history.tsx`
- Modify: `apps/web/src/components/imports/import-dropzone.tsx`
- Modify: `apps/web/src/components/imports/preview-summary.tsx`
- Modify: `apps/web/src/app/imports/new/page.tsx`
- Modify: `apps/web/e2e/import-preview.spec.ts`
- Create: `apps/web/e2e/import-confirmation.spec.ts`
- Create: `apps/api/scripts/start_e2e.py`
- Modify: `apps/web/playwright.config.ts`

**Interfaces:**
- Consumes: authenticated API-client functions from Task 5 and `getAccessToken()` from Task 6.
- Produces: data-source page with preview, explicit confirmation, import history and replay evidence.

- [ ] **Step 1: Write the full persisted-import RED E2E test**

```typescript
test("confirms a SEMS batch and shows idempotent history", async ({ page }) => {
  await page.goto("/settings/data-sources");
  await page.getByLabel("Arquivo CSV do SEMS+").setInputFiles(FIXTURE_PATH);
  await page.getByRole("button", { name: "Analisar arquivo" }).click();

  await expect(page.getByText("2 válidos")).toBeVisible();
  await expect(page.getByText("Nenhum registro foi gravado")).toBeVisible();
  await page.getByRole("button", { name: "Confirmar importação" }).click();

  await expect(page.getByRole("status")).toContainText("2 sessões importadas");
  await expect(page.getByRole("heading", { name: "Histórico de importações" })).toBeVisible();
  await expect(page.getByRole("row", { name: /sems_sessions.csv.*Concluído/ })).toBeVisible();

  await page.getByRole("button", { name: "Importar novamente" }).click();
  await expect(page.getByRole("status")).toContainText("Lote já importado");
  await expect(page.getByText("1 lote", { exact: true })).toBeVisible();
});
```

- [ ] **Step 2: Run RED persisted-import E2E**

Run:

```bash
pnpm --dir apps/web exec playwright test e2e/import-confirmation.spec.ts
```

Expected: route, confirmation button and history are missing.

- [ ] **Step 3: Move the existing UI without changing its validated drop behavior**

`/imports/new` becomes a permanent redirect to `/settings/data-sources`. The new page heading is `Fontes de dados`, with a source card `SEMS+ CSV` labeled `Adapter temporário · somente leitura`. Preserve drag depth, file-picker reset and non-CSV validation exactly as covered by existing E2E tests.

- [ ] **Step 4: Add explicit preview-to-confirm state transition**

After preview, render `Confirmar importação`. It calls `confirmImport(file, token)` using the exact selected `File`, disables during the request and shows:

- first import: `2 sessões importadas; nenhum registro inválido.`;
- checksum replay: `Lote já importado; nenhuma nova sessão criada.`;
- API error: stable alert with correlation-safe message and retry.

Never auto-confirm after file selection or preview. The preview banner continues to state that no record has been written until the user clicks confirm.

- [ ] **Step 5: Add import history**

`ImportHistory` lists filename, source, timestamp, totals and status in descending order. It has an empty state and refreshes after successful confirmation. No original-file download is exposed in Checkpoint A.

- [ ] **Step 6: Create deterministic E2E API startup**

Use one synchronous launcher so Alembic's async environment owns its event loop:

```python
# apps/api/scripts/start_e2e.py
import asyncio
import os
from pathlib import Path
import sys

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

import uvicorn
from alembic import command
from alembic.config import Config

from app.shared.config import Settings
from app.shared.database import create_engine_from_settings, create_session_factory
from scripts.seed_operational_foundation import seed_operational_foundation


async def seed(database_url: str) -> None:
    settings = Settings(
        app_env="test",
        auth_mode="fixture",
        database_url=database_url,
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
    )
    engine = create_engine_from_settings(settings)
    async with create_session_factory(engine)() as session:
        await seed_operational_foundation(session)
    await engine.dispose()


def main() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    allowed_root = (repository_root / "apps/web/test-results").resolve()
    database_path = Path(os.environ["E2E_DATABASE_PATH"]).resolve()
    if database_path.suffix != ".sqlite3" or allowed_root not in database_path.parents:
        raise RuntimeError("E2E database must be a .sqlite3 file under apps/web/test-results")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_path.unlink(missing_ok=True)

    database_url = f"sqlite+aiosqlite:///{database_path}"
    os.environ.update(
        APP_ENV="test",
        AUTH_MODE="fixture",
        FIXTURE_AUTH_TOKEN="fixture-manager-token",
        DATABASE_URL=database_url,
        SUPABASE_URL="https://lgjohsxipfctgooiuqnv.supabase.co",
    )
    config = Config(str(repository_root / "apps/api/alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    asyncio.run(seed(database_url))
    uvicorn.run("app.main:app", app_dir=str(repository_root / "apps/api"), port=8001)


if __name__ == "__main__":
    main()
```

Playwright sets the exact `E2E_DATABASE_PATH` to `apps/web/test-results/ev-chargeops-e2e.sqlite3`, launches the API through this script and sets the web server's `NEXT_PUBLIC_API_URL=/api` plus `AUTH_MODE=fixture`. The existing Next rewrite targets `http://127.0.0.1:8001`; this avoids CORS in browser tests. The launcher refuses any path outside the Playwright output directory, preventing accidental deletion or migration of Supabase.

- [ ] **Step 7: Run GREEN import UI and regression suite**

Run:

```bash
pnpm --dir apps/web exec playwright test e2e/import-preview.spec.ts e2e/import-confirmation.spec.ts
pnpm test:web
pnpm lint:web
pnpm --dir apps/web exec next build --webpack
```

Expected: old picker/drop tests pass at the redirected settings route; confirm/history/replay pass; lint and build pass.

- [ ] **Step 8: Commit Task 7**

```bash
git add apps/web apps/api/scripts/start_e2e.py
git commit -m "feat: add persisted data source workflow"
```

---

### Task 8: Documentation, Live Supabase Migration and Checkpoint Gate

**Files:**
- Modify: `README.md`
- Modify: `apps/api/README.md`
- Modify: `apps/web/README.md`
- Modify: `package.json`
- Create: `docs/demo/checkpoint-a-evidence.md`

**Interfaces:**
- Consumes: all Checkpoint A code and migrations.
- Produces: reproducible local setup, live-project setup without committed secrets, full repository gate and traceable checkpoint evidence.

- [ ] **Step 1: Run the documentation RED check**

Run each exact search before editing:

```bash
rg -n "Node.*22\.13|Supavisor session|DEMO_MANAGER_EMAIL|/dashboard|/settings/data-sources|alembic.*upgrade head" README.md apps/api/README.md apps/web/README.md
```

Expected: one or more required phrases are absent. Record the missing phrases in the task report; do not add a temporary tracked checklist.

- [ ] **Step 2: Update project documentation**

Document two modes:

1. `local/test`: SQLite plus fixture auth, no external account required;
2. `demo`: Supabase PostgreSQL/Auth/Storage, real signed access token, no fixture auth.

Explain that persistent-backend deployments use direct PostgreSQL when IPv6 is available and Supavisor session mode on port 5432 for IPv4-only environments. Never publish the actual connection string, password, publishable key or demo-account password.

Add root scripts:

```json
{
  "typecheck:api": "uv run --project apps/api mypy apps/api/app",
  "test:integration": "uv run --project apps/api pytest apps/api/tests/integration -q",
  "check": "pnpm lint:api && pnpm typecheck:api && pnpm test:api && pnpm test:integration && pnpm db:check && pnpm check:api-contract && pnpm test:api-client && pnpm typecheck:api-client && pnpm lint:web && pnpm --dir apps/web exec next build --webpack && pnpm test:web"
}
```

- [ ] **Step 3: Run the complete local gate**

Run with Node `>=22.13.0 <23`:

```bash
pnpm check
git diff --check
git status --short
```

Expected: Ruff, mypy, all API tests, integration tests, Alembic drift, OpenAPI drift, API-client tests/typecheck, web lint/build and all Playwright tests pass. `git diff --check` has no output; only intended documentation changes remain before commit.

- [ ] **Step 4: Prepare the live Supabase environment without transmitting secrets**

The user performs these local-only actions:

1. copy the Supabase session-pooler connection string from the dashboard;
2. insert the database password locally into that copied connection string;
3. place it in untracked `apps/api/.env` as `DATABASE_URL`;
4. set `APP_ENV=demo`, `AUTH_MODE=supabase`, `SUPABASE_URL`, `DEMO_MANAGER_EMAIL`, `ORIGINAL_FILE_STORE=supabase` and the backend-only `SUPABASE_SERVICE_ROLE_KEY`;
5. place the Supabase publishable key in untracked `apps/web/.env.local`.

Before the agent runs any migration or seed against project `lgjohsxipfctgooiuqnv`, stop and request action-time confirmation naming the project and the exact commands.

- [ ] **Step 5: Apply and verify the live migration after confirmation**

Run only after confirmation:

```bash
pnpm db:upgrade
uv run --project apps/api python apps/api/scripts/seed_operational_foundation.py
```

Before the first live import, create a private Storage bucket named `sems-imports` with MIME type `text/csv` and a 10 MB per-object limit. Creating the bucket is a separate live write: name that exact action in the same action-time confirmation or request a second confirmation before doing it.

Expected: Alembic reaches head; the Supabase table editor shows the ten operational tables; organization/site/charger/four units exist exactly once; the private bucket exists. Do not create auth users automatically. The user creates or identifies the manager Supabase Auth account with the email in `DEMO_MANAGER_EMAIL`; the first authenticated `/v1/me` request creates only the allowlisted manager profile/membership.

- [ ] **Step 6: Run the live smoke flow with an explicit write boundary**

With the API and web app configured for Supabase:

```bash
curl -fsS http://127.0.0.1:8000/health
```

Sign-in and navigation to `/dashboard` and `/settings/data-sources` are read-only checks. Immediately before clicking `Confirmar importação`, request action-time confirmation that names project `lgjohsxipfctgooiuqnv` and states that the action will create one import batch, two raw records, two charging sessions, one audit event and one private Storage object. After confirmation, submit the fixture once, re-submit it to prove replay, and verify that counts did not double. Record only counts, IDs and screenshots without tokens, emails, passwords or raw sensitive payloads in `docs/demo/checkpoint-a-evidence.md`.

- [ ] **Step 7: Commit Task 8**

```bash
git add README.md apps/api/README.md apps/web/README.md package.json docs/demo/checkpoint-a-evidence.md
git commit -m "docs: record operational foundation workflow"
```

- [ ] **Step 8: Final checkpoint review**

Run:

```bash
pnpm check
git diff --check
git status --short --branch
```

Review Checkpoint A against the spec:

- authenticated default route is dashboard;
- source workflow is secondary;
- batch, raw records and sessions persist with provenance;
- checksum replay and cross-batch session deduplication are proven;
- organization isolation is tested;
- live Supabase evidence is recorded without secrets;
- no GoodWe command path exists.

Expected: no unmet Checkpoint A criteria and a clean worktree.

---

## Plan Self-Review

### Spec coverage

- Supabase configuration, Alembic and repositories: Tasks 1, 2 and 8.
- Supabase Auth and organization scoping: Tasks 3, 5, 6 and 8.
- Persisted idempotent import batches, raw records and sessions: Tasks 4, 5 and 7.
- Seeded site, charger and units: Task 2; manager profile/membership is safely bootstrapped in Task 3 after a real verified user exists.
- Source management moved out of the product path: Tasks 6 and 7.
- Dashboard becomes the product home without pretending Checkpoint B metrics exist: Task 6.
- Real/simulated provenance and GoodWe safety: global constraints, Tasks 2, 4 and 8.

### Explicitly deferred to later checkpoint plans

- Session assignment UI and `session_assignments`: Checkpoint B.
- Manager period metrics, resident cost table, tariff, billing and reconciliation: Checkpoint B.
- Anomaly, forecast and segmentation implementations: Checkpoint C.
- Mercado Pago, resident view and final presentation hardening: Checkpoint D.

These are not omissions from Checkpoint A; the approved design deliberately separates them into independently demonstrable checkpoints.

### Type consistency

- `AuthPrincipal`, `OrganizationScope`, `OrganizationRole`, `TokenVerifier` and `ScopeRepository` keep the same signatures from Task 3 through API dependencies.
- `ImportBatchResult` and authenticated API-client functions retain the same fields from Task 4 through UI and E2E.
- `organization_id`, `profile_id`, `import_batch_id`, `raw_record_id`, `deduplication_key` and provenance values match the approved technical specification.
- Next.js fixture auth and FastAPI fixture auth use the same exact token only in local/test.

### Placeholder scan

This plan contains no unresolved product decision, unnamed error handling, generic test request or unfinished interface. Stable demo UUIDs, route names, environment guards, table constraints, test commands and acceptance results are explicit.
