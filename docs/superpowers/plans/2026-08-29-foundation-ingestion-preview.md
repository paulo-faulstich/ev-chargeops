# Foundation and SEMS+ Ingestion Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the first executable EV ChargeOps vertical slice: a Next.js interface uploads an observed-format SEMS+ CSV to FastAPI and receives an explainable preview of valid, invalid, and duplicate charging sessions without persisting data.

**Architecture:** Keep the Next.js frontend and FastAPI backend independently executable in one mixed monorepo. The ingestion use case depends on a `ChargingSessionSource` port and canonical domain models; the SEMS+ CSV parser is an infrastructure adapter. This increment stops before Supabase persistence and authentication so the ingestion contract can be validated locally before adding state.

**Tech Stack:** Next.js, React, TypeScript, Tailwind CSS, FastAPI, Pydantic, Python, pytest, uv, pnpm, OpenAPI, Playwright.

**Spec:** `docs/technical/ev-chargeops-architecture.md`

## Global Constraints

- TypeScript is used in the frontend and API client; Python is used in the backend.
- The domain cannot import FastAPI, Pydantic, pandas, Supabase, GoodWe, Mercado Pago, or SQLAlchemy.
- Timestamps are converted to UTC; energy uses `Decimal`, never binary floating point.
- No flow sends commands to the LAB FIAP equipment.
- Every preview record exposes provenance as `real`, `assigned`, `simulated`, `derived`, or `external`; this slice uses `real` for source fields and `unknown` for identity confidence.
- The raw source row remains available in the preview response, but logs must not include its contents.
- OpenAPI is the source of truth for the frontend/backend contract.
- This plan covers FR-04, FR-05, FR-07, NFR-01, NFR-02, NFR-06, NFR-08, NFR-09, NFR-10 and the preview portion of M-01.
- Persistence, Supabase Auth, cross-batch deduplication, session assignment, rateio, IA and payments are intentionally deferred to later vertical-slice plans.

---

### Task 1: Mixed-monorepo scaffold and executable health checks

**Files:**
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `.nvmrc`
- Create: `apps/web/**` through `create-next-app`
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/uv.lock`
- Create: `apps/api/app/__init__.py`
- Create: `apps/api/app/main.py`
- Create: `apps/api/tests/test_health.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `GET /health -> {"status": "ok", "service": "ev-chargeops-api"}`.
- Produces: root scripts `dev:web`, `dev:api`, `test:web`, `test:api`, `lint:web`, and `lint:api`.

- [ ] **Step 1: Generate the frontend and Python project shells**

Run:

```bash
mkdir -p apps
pnpm dlx create-next-app@latest apps/web --ts --tailwind --eslint --app --src-dir --import-alias '@/*' --use-pnpm --yes
uv init --project --python '>=3.12' apps/api
uv add --project apps/api fastapi uvicorn pydantic-settings python-multipart
uv add --project apps/api --dev pytest pytest-asyncio httpx ruff mypy
```

Delete the generated `apps/api/main.py`; production imports start at `app.main`. Delete a generated `apps/web/pnpm-lock.yaml` if present; the repository keeps one root lockfile after workspace configuration.

- [ ] **Step 2: Add root workspace configuration**

Create `pnpm-workspace.yaml`:

```yaml
packages:
  - apps/web
  - packages/*
```

Create `package.json`:

```json
{
  "name": "ev-chargeops",
  "private": true,
  "packageManager": "pnpm@11.19.0",
  "scripts": {
    "dev:web": "pnpm --dir apps/web dev",
    "dev:api": "uv run --project apps/api uvicorn app.main:app --app-dir apps/api --reload",
    "test:web": "pnpm --dir apps/web test:e2e",
    "test:api": "uv run --project apps/api pytest apps/api/tests -q",
    "lint:web": "pnpm --dir apps/web lint",
    "lint:api": "uv run --project apps/api ruff check apps/api/app apps/api/tests"
  }
}
```

Create `.nvmrc` with `22` and add `.next/`, `node_modules/`, `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`, `.env`, and `.env.*` to `.gitignore`, retaining an exception for `.env.example`.

Run `pnpm install` from the repository root to create the root `pnpm-lock.yaml`.

- [ ] **Step 3: Write the failing API health test**

Create `apps/api/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_service_ready() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ev-chargeops-api",
    }
```

- [ ] **Step 4: Run the health test and verify RED**

Run: `uv run --project apps/api pytest apps/api/tests/test_health.py -v`

Expected: FAIL because `app.main` or the `/health` route does not exist.

- [ ] **Step 5: Implement the minimum FastAPI application**

Create `apps/api/app/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="EV ChargeOps API", version="0.1.0")


@app.get("/health", tags=["platform"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ev-chargeops-api"}
```

- [ ] **Step 6: Run the health test and verify GREEN**

Run: `uv run --project apps/api pytest apps/api/tests/test_health.py -v`

Expected: PASS, one test.

- [ ] **Step 7: Commit the scaffold**

```bash
git add .gitignore .nvmrc package.json pnpm-workspace.yaml pnpm-lock.yaml apps/web apps/api
git commit -m "chore: scaffold Next.js and FastAPI applications"
```

---

### Task 2: Canonical charging-session domain model

**Files:**
- Create: `apps/api/app/modules/__init__.py`
- Create: `apps/api/app/modules/ingestion/__init__.py`
- Create: `apps/api/app/modules/ingestion/domain/__init__.py`
- Create: `apps/api/app/modules/ingestion/domain/session.py`
- Create: `apps/api/app/modules/ingestion/domain/errors.py`
- Create: `apps/api/tests/modules/ingestion/domain/test_session.py`

**Interfaces:**
- Produces: `SessionCandidate.create(...) -> SessionCandidate`.
- Produces: `SessionCandidate.deduplication_key: str` as a stable SHA-256 hex digest.
- Produces: `InvalidSession(field: str, code: str, message: str)`.

- [ ] **Step 1: Write the failing canonical-session test**

Create `apps/api/tests/modules/ingestion/domain/test_session.py`:

```python
from datetime import UTC, datetime
from decimal import Decimal

from app.modules.ingestion.domain.session import IdentityConfidence, SessionCandidate, SourceKind


def test_session_candidate_builds_stable_deduplication_key() -> None:
    values = {
        "source": SourceKind.SEMS_EXPORT,
        "external_id": None,
        "charger_serial": "97500NAP25BL0008",
        "started_at": datetime(2026, 8, 29, 17, 10, tzinfo=UTC),
        "ended_at": datetime(2026, 8, 29, 18, 10, tzinfo=UTC),
        "energy_kwh": Decimal("7.00"),
        "charge_port": 1,
        "card_id_raw": "97500NAP25BL0008",
    }

    first = SessionCandidate.create(**values)
    second = SessionCandidate.create(**values)

    assert first.deduplication_key == second.deduplication_key
    assert len(first.deduplication_key) == 64
    assert first.identity_confidence is IdentityConfidence.UNKNOWN
```

- [ ] **Step 2: Run the test and verify RED**

Run: `uv run --project apps/api pytest apps/api/tests/modules/ingestion/domain/test_session.py -v`

Expected: FAIL because `SessionCandidate` does not exist.

- [ ] **Step 3: Implement the canonical model and validation error**

Create `apps/api/app/modules/ingestion/domain/errors.py`:

```python
class InvalidSession(ValueError):
    def __init__(self, field: str, code: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.code = code
        self.message = message
```

Create `apps/api/app/modules/ingestion/domain/session.py`:

```python
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256

from .errors import InvalidSession


class SourceKind(StrEnum):
    SEMS_EXPORT = "sems_export"
    MANUAL = "manual"
    SIMULATED = "simulated"
    GOODWE_API = "goodwe_api"


class IdentityConfidence(StrEnum):
    CONFIRMED = "confirmed"
    ASSIGNED = "assigned"
    UNKNOWN = "unknown"


class DataProvenance(StrEnum):
    REAL = "real"
    ASSIGNED = "assigned"
    SIMULATED = "simulated"
    DERIVED = "derived"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class SessionCandidate:
    source: SourceKind
    external_id: str | None
    charger_serial: str
    started_at: datetime
    ended_at: datetime
    energy_kwh: Decimal
    charge_port: int | None
    card_id_raw: str | None
    identity_confidence: IdentityConfidence
    provenance: DataProvenance
    deduplication_key: str

    @classmethod
    def create(
        cls,
        *,
        source: SourceKind,
        external_id: str | None,
        charger_serial: str,
        started_at: datetime,
        ended_at: datetime,
        energy_kwh: Decimal,
        charge_port: int | None,
        card_id_raw: str | None,
    ) -> "SessionCandidate":
        normalized_serial = charger_serial.strip()
        started_at_utc = started_at.astimezone(UTC)
        ended_at_utc = ended_at.astimezone(UTC)
        payload = "|".join(
            (
                source.value,
                normalized_serial,
                started_at_utc.isoformat(),
                ended_at_utc.isoformat(),
                format(energy_kwh.normalize(), "f"),
            )
        )
        return cls(
            source=source,
            external_id=external_id,
            charger_serial=normalized_serial,
            started_at=started_at_utc,
            ended_at=ended_at_utc,
            energy_kwh=energy_kwh,
            charge_port=charge_port,
            card_id_raw=card_id_raw or None,
            identity_confidence=IdentityConfidence.UNKNOWN,
            provenance=DataProvenance.REAL,
            deduplication_key=sha256(payload.encode("utf-8")).hexdigest(),
        )
```

- [ ] **Step 4: Run the canonical-session test and verify GREEN**

Run: `uv run --project apps/api pytest apps/api/tests/modules/ingestion/domain/test_session.py -v`

Expected: PASS.

- [ ] **Step 5: Write failing validation tests**

Append parameterized tests that assert:

```python
import pytest

from app.modules.ingestion.domain.errors import InvalidSession


@pytest.mark.parametrize(
    ("energy", "end_hour", "field", "code"),
    [
        (Decimal("0"), 18, "energy_kwh", "ENERGY_NOT_POSITIVE"),
        (Decimal("7"), 16, "ended_at", "END_NOT_AFTER_START"),
    ],
)
def test_session_candidate_rejects_invalid_measurements(
    energy: Decimal,
    end_hour: int,
    field: str,
    code: str,
) -> None:
    with pytest.raises(InvalidSession) as error:
        SessionCandidate.create(
            source=SourceKind.SEMS_EXPORT,
            external_id=None,
            charger_serial="97500NAP25BL0008",
            started_at=datetime(2026, 8, 29, 17, tzinfo=UTC),
            ended_at=datetime(2026, 8, 29, end_hour, tzinfo=UTC),
            energy_kwh=energy,
            charge_port=1,
            card_id_raw=None,
        )

    assert (error.value.field, error.value.code) == (field, code)
```

- [ ] **Step 6: Run validation tests and verify RED, then implement the minimum guards**

Run before implementation: `uv run --project apps/api pytest apps/api/tests/modules/ingestion/domain/test_session.py -v`

Expected: the two new cases FAIL with no `InvalidSession`.

Add these guards at the beginning of `SessionCandidate.create`, then run the same command again and expect all tests to PASS:

```python
if started_at.tzinfo is None:
    raise InvalidSession("started_at", "TIMEZONE_REQUIRED", "Start time must include a timezone.")
if ended_at.tzinfo is None:
    raise InvalidSession("ended_at", "TIMEZONE_REQUIRED", "End time must include a timezone.")
if ended_at <= started_at:
    raise InvalidSession("ended_at", "END_NOT_AFTER_START", "End time must be after start time.")
if energy_kwh <= 0:
    raise InvalidSession("energy_kwh", "ENERGY_NOT_POSITIVE", "Energy must be greater than zero.")
if not charger_serial.strip():
    raise InvalidSession("charger_serial", "CHARGER_REQUIRED", "Charger serial is required.")
```

- [ ] **Step 7: Commit the domain model**

```bash
git add apps/api/app/modules apps/api/tests/modules
git commit -m "feat: add canonical charging session model"
```

---

### Task 3: Replaceable SEMS+ CSV source adapter

**Files:**
- Create: `apps/api/app/modules/ingestion/application/__init__.py`
- Create: `apps/api/app/modules/ingestion/application/ports.py`
- Create: `apps/api/app/modules/ingestion/infrastructure/__init__.py`
- Create: `apps/api/app/modules/ingestion/infrastructure/sems_csv_source.py`
- Create: `apps/api/tests/fixtures/sems_sessions.csv`
- Create: `apps/api/tests/modules/ingestion/infrastructure/test_sems_csv_source.py`

**Interfaces:**
- Produces: `SourceRecord(row_number: int, raw: Mapping[str, str])`.
- Produces: `ChargingSessionSource.read(content: bytes) -> list[SourceRecord]` and `normalize(record: SourceRecord) -> SessionCandidate`.
- Produces: `SemsCsvSource(default_timezone: ZoneInfo)`.

- [ ] **Step 1: Define the source port**

Create `application/ports.py`:

```python
from dataclasses import dataclass
from typing import Mapping, Protocol

from app.modules.ingestion.domain.session import SessionCandidate, SourceKind


@dataclass(frozen=True, slots=True)
class SourceRecord:
    row_number: int
    raw: Mapping[str, str]


class ChargingSessionSource(Protocol):
    kind: SourceKind

    def read(self, content: bytes) -> list[SourceRecord]: ...

    def normalize(self, record: SourceRecord) -> SessionCandidate: ...
```

- [ ] **Step 2: Add the observed-format fixture and failing adapter test**

Create `tests/fixtures/sems_sessions.csv`:

```csv
Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN
29/08/2026 17:10:00,29/08/2026 18:10:00,7.00,1,97500NAP25BL0008,97500NAP25BL0008
29/08/2026 18:30:00,29/08/2026 19:00:00,3.50,1,,97500NAP25BL0008
```

Create `test_sems_csv_source.py`:

```python
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from app.modules.ingestion.domain.session import IdentityConfidence, SourceKind
from app.modules.ingestion.infrastructure.sems_csv_source import SemsCsvSource


FIXTURE = Path(__file__).parents[3] / "fixtures" / "sems_sessions.csv"


def test_sems_csv_normalizes_observed_fields_to_utc() -> None:
    source = SemsCsvSource(default_timezone=ZoneInfo("America/Sao_Paulo"))
    records = source.read(FIXTURE.read_bytes())

    session = source.normalize(records[0])

    assert len(records) == 2
    assert session.source is SourceKind.SEMS_EXPORT
    assert session.started_at == datetime(2026, 8, 29, 20, 10, tzinfo=UTC)
    assert session.ended_at == datetime(2026, 8, 29, 21, 10, tzinfo=UTC)
    assert session.energy_kwh == Decimal("7.00")
    assert session.card_id_raw == "97500NAP25BL0008"
    assert session.identity_confidence is IdentityConfidence.UNKNOWN
```

- [ ] **Step 3: Run the adapter test and verify RED**

Run: `uv run --project apps/api pytest apps/api/tests/modules/ingestion/infrastructure/test_sems_csv_source.py -v`

Expected: FAIL because `SemsCsvSource` does not exist.

- [ ] **Step 4: Implement exact-header parsing and normalization**

Create `sems_csv_source.py`:

```python
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from zoneinfo import ZoneInfo

from app.modules.ingestion.application.ports import SourceRecord
from app.modules.ingestion.domain.errors import InvalidSession
from app.modules.ingestion.domain.session import SessionCandidate, SourceKind

REQUIRED_COLUMNS = {
    "Start Time",
    "End Time",
    "Charging Energy(kWh)",
    "Charging Port",
    "Card ID",
    "Device SN",
}


class SemsCsvSource:
    kind = SourceKind.SEMS_EXPORT

    def __init__(self, default_timezone: ZoneInfo) -> None:
        self.default_timezone = default_timezone

    def read(self, content: bytes) -> list[SourceRecord]:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise InvalidSession("file", "INVALID_ENCODING", "CSV must use UTF-8 encoding.") from error
        reader = csv.DictReader(StringIO(text))
        columns = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise InvalidSession("file", "MISSING_COLUMNS", f"Missing columns: {', '.join(missing)}")
        return [SourceRecord(row_number=index, raw=dict(row)) for index, row in enumerate(reader, start=2)]

    def normalize(self, record: SourceRecord) -> SessionCandidate:
        raw = record.raw
        started_at = self._datetime(raw["Start Time"], "Start Time", record.row_number)
        ended_at = self._datetime(raw["End Time"], "End Time", record.row_number)
        energy_kwh = Decimal(raw["Charging Energy(kWh)"].strip())
        port_text = raw["Charging Port"].strip()
        try:
            charge_port = int(port_text) if port_text else None
        except ValueError as error:
            raise InvalidSession(
                "Charging Port",
                "INVALID_INTEGER",
                f"Invalid charging port at row {record.row_number}.",
            ) from error
        return SessionCandidate.create(
            source=self.kind,
            external_id=None,
            charger_serial=raw["Device SN"],
            started_at=started_at,
            ended_at=ended_at,
            energy_kwh=energy_kwh,
            charge_port=charge_port,
            card_id_raw=raw["Card ID"].strip() or None,
        )

    def _datetime(self, value: str, field: str, row_number: int) -> datetime:
        try:
            local = datetime.strptime(value.strip(), "%d/%m/%Y %H:%M:%S")
        except ValueError as error:
            raise InvalidSession(
                field,
                "INVALID_DATETIME",
                f"Invalid datetime at row {row_number}.",
            ) from error
        return local.replace(tzinfo=self.default_timezone)
```

The stable error codes are `INVALID_ENCODING`, `MISSING_COLUMNS`, `INVALID_DATETIME`, `INVALID_DECIMAL`, and `INVALID_INTEGER`; domain guards continue to supply canonical measurement errors.

- [ ] **Step 5: Run the adapter test and verify GREEN**

Run: `uv run --project apps/api pytest apps/api/tests/modules/ingestion/infrastructure/test_sems_csv_source.py -v`

Expected: PASS.

- [ ] **Step 6: Add a failing malformed-row test, then implement error translation**

Append this test:

```python
import pytest

from app.modules.ingestion.domain.errors import InvalidSession


def test_sems_csv_explains_invalid_energy_with_row_number() -> None:
    source = SemsCsvSource(default_timezone=ZoneInfo("America/Sao_Paulo"))
    content = FIXTURE.read_text(encoding="utf-8").replace("7.00", "not-a-number", 1).encode()
    record = source.read(content)[0]

    with pytest.raises(InvalidSession) as error:
        source.normalize(record)

    assert error.value.field == "Charging Energy(kWh)"
    assert error.value.code == "INVALID_DECIMAL"
    assert "row 2" in error.value.message
```

Run it before adding translation and verify RED with an unhandled `decimal.InvalidOperation`. Replace the direct `Decimal(...)` line with:

```python
try:
    energy_kwh = Decimal(raw["Charging Energy(kWh)"].strip())
except InvalidOperation as error:
    raise InvalidSession(
        "Charging Energy(kWh)",
        "INVALID_DECIMAL",
        f"Invalid energy at row {record.row_number}.",
    ) from error
```

Run the adapter test file again and expect PASS.

- [ ] **Step 7: Commit the source adapter**

```bash
git add apps/api/app/modules/ingestion apps/api/tests/fixtures apps/api/tests/modules/ingestion
git commit -m "feat: normalize SEMS CSV sessions"
```

---

### Task 4: Import-preview use case and FastAPI endpoint

**Files:**
- Create: `apps/api/app/modules/ingestion/application/preview_import.py`
- Create: `apps/api/app/modules/ingestion/presentation/__init__.py`
- Create: `apps/api/app/modules/ingestion/presentation/schemas.py`
- Create: `apps/api/app/modules/ingestion/presentation/router.py`
- Create: `apps/api/tests/modules/ingestion/application/test_preview_import.py`
- Create: `apps/api/tests/modules/ingestion/presentation/test_preview_endpoint.py`
- Modify: `apps/api/app/main.py`

**Interfaces:**
- Produces: `PreviewImport.execute(filename: str, content: bytes) -> ImportPreview`.
- Produces: `POST /v1/import-batches/preview` accepting multipart field `file`.
- Produces: response fields `filename`, `checksum`, `source`, `totalCount`, `validCount`, `invalidCount`, `duplicateCount`, and `records`.

- [ ] **Step 1: Write the failing use-case test**

Create `test_preview_import.py`:

```python
from zoneinfo import ZoneInfo

from app.modules.ingestion.application.preview_import import PreviewImport
from app.modules.ingestion.infrastructure.sems_csv_source import SemsCsvSource


def test_preview_classifies_valid_duplicate_and_invalid_rows() -> None:
    content = b"""Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN
29/08/2026 17:10:00,29/08/2026 18:10:00,7.00,1,CARD-1,97500NAP25BL0008
29/08/2026 17:10:00,29/08/2026 18:10:00,7.00,1,CARD-1,97500NAP25BL0008
29/08/2026 19:10:00,29/08/2026 20:10:00,0.00,1,CARD-2,97500NAP25BL0008
"""
    use_case = PreviewImport(SemsCsvSource(ZoneInfo("America/Sao_Paulo")))

    preview = use_case.execute("sems.csv", content)

assert preview.total_count == 3
assert preview.valid_count == 1
assert preview.duplicate_count == 1
assert preview.invalid_count == 1
assert preview.records[1].classification == "duplicate"
assert preview.records[2].error_code == "ENERGY_NOT_POSITIVE"
assert len(preview.checksum) == 64
```

- [ ] **Step 2: Run the use-case test and verify RED**

Run: `uv run --project apps/api pytest apps/api/tests/modules/ingestion/application/test_preview_import.py -v`

Expected: FAIL because `PreviewImport` does not exist.

- [ ] **Step 3: Implement preview classifications**

Create `preview_import.py`:

```python
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal, Mapping

from app.modules.ingestion.application.ports import ChargingSessionSource
from app.modules.ingestion.domain.errors import InvalidSession
from app.modules.ingestion.domain.session import SessionCandidate


@dataclass(frozen=True, slots=True)
class PreviewRecord:
    row_number: int
    classification: Literal["valid", "invalid", "duplicate"]
    raw: Mapping[str, str]
    session: SessionCandidate | None = None
    error_field: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ImportPreview:
    filename: str
    checksum: str
    source: str
    records: tuple[PreviewRecord, ...]

    @property
    def total_count(self) -> int:
        return len(self.records)

    @property
    def valid_count(self) -> int:
        return sum(record.classification == "valid" for record in self.records)

    @property
    def invalid_count(self) -> int:
        return sum(record.classification == "invalid" for record in self.records)

    @property
    def duplicate_count(self) -> int:
        return sum(record.classification == "duplicate" for record in self.records)


class PreviewImport:
    def __init__(self, source: ChargingSessionSource) -> None:
        self.source = source

    def execute(self, filename: str, content: bytes) -> ImportPreview:
        if not filename.lower().endswith(".csv"):
            raise InvalidSession("file", "UNSUPPORTED_FILE", "Only CSV files are supported.")
        records: list[PreviewRecord] = []
        seen: set[str] = set()
        for source_record in self.source.read(content):
            try:
                session = self.source.normalize(source_record)
                classification: Literal["valid", "duplicate"] = (
                    "duplicate" if session.deduplication_key in seen else "valid"
                )
                seen.add(session.deduplication_key)
                records.append(
                    PreviewRecord(
                        row_number=source_record.row_number,
                        classification=classification,
                        raw=source_record.raw,
                        session=session,
                    )
                )
            except InvalidSession as error:
                records.append(
                    PreviewRecord(
                        row_number=source_record.row_number,
                        classification="invalid",
                        raw=source_record.raw,
                        error_field=error.field,
                        error_code=error.code,
                        error_message=error.message,
                    )
                )
        return ImportPreview(
            filename=filename,
            checksum=sha256(content).hexdigest(),
            source=self.source.kind.value,
            records=tuple(records),
        )
```

- [ ] **Step 4: Run the use-case test and verify GREEN**

Run: `uv run --project apps/api pytest apps/api/tests/modules/ingestion/application/test_preview_import.py -v`

Expected: PASS.

- [ ] **Step 5: Write the failing endpoint test**

Create `test_preview_endpoint.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

FIXTURE = Path(__file__).parents[3] / "fixtures" / "sems_sessions.csv"


def test_preview_endpoint_returns_camel_case_summary() -> None:
    response = TestClient(app).post(
        "/v1/import-batches/preview",
        files={"file": ("sems.csv", FIXTURE.read_bytes(), "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "sems_export"
    assert body["totalCount"] == 2
    assert body["validCount"] == 2
    assert body["invalidCount"] == 0
    assert body["duplicateCount"] == 0
    assert body["records"][0]["session"]["provenance"] == "real"
    assert body["records"][0]["session"]["identityConfidence"] == "unknown"


def test_preview_endpoint_returns_stable_error_for_unsupported_file() -> None:
    response = TestClient(app).post(
        "/v1/import-batches/preview",
        files={"file": ("sessions.txt", b"not csv", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "UNSUPPORTED_FILE",
            "message": "Only CSV files are supported.",
            "details": [{"field": "file"}],
        }
    }
```

- [ ] **Step 6: Run the endpoint test and verify RED**

Run: `uv run --project apps/api pytest apps/api/tests/modules/ingestion/presentation/test_preview_endpoint.py -v`

Expected: FAIL with 404 because the route does not exist.

- [ ] **Step 7: Implement Pydantic schemas, dependency composition, and router**

Create `presentation/schemas.py`:

```python
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

from app.modules.ingestion.application.preview_import import ImportPreview


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.title() for part in rest)


class ApiSchema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SessionPreviewResponse(ApiSchema):
    charger_serial: str
    started_at: datetime
    ended_at: datetime
    energy_kwh: Decimal
    charge_port: int | None
    card_id_raw: str | None
    identity_confidence: str
    provenance: str
    deduplication_key: str


class PreviewRecordResponse(ApiSchema):
    row_number: int
    classification: str
    raw: dict[str, str]
    session: SessionPreviewResponse | None = None
    error_field: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class ImportPreviewResponse(ApiSchema):
    filename: str
    checksum: str
    source: str
    total_count: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    records: list[PreviewRecordResponse]

    @classmethod
    def from_result(cls, result: ImportPreview) -> "ImportPreviewResponse":
        return cls(
            filename=result.filename,
            checksum=result.checksum,
            source=result.source,
            total_count=result.total_count,
            valid_count=result.valid_count,
            invalid_count=result.invalid_count,
            duplicate_count=result.duplicate_count,
            records=[
                PreviewRecordResponse(
                    row_number=record.row_number,
                    classification=record.classification,
                    raw=dict(record.raw),
                    session=(
                        SessionPreviewResponse.model_validate(record.session, from_attributes=True)
                        if record.session
                        else None
                    ),
                    error_field=record.error_field,
                    error_code=record.error_code,
                    error_message=record.error_message,
                )
                for record in result.records
            ],
        )


class ErrorDetail(ApiSchema):
    field: str


class ErrorBody(ApiSchema):
    code: str
    message: str
    details: list[ErrorDetail]


class ErrorResponse(ApiSchema):
    error: ErrorBody
```

Create `presentation/router.py`:

```python
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse

from app.modules.ingestion.application.preview_import import PreviewImport
from app.modules.ingestion.domain.errors import InvalidSession
from app.modules.ingestion.infrastructure.sems_csv_source import SemsCsvSource
from app.modules.ingestion.presentation.schemas import (
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    ImportPreviewResponse,
)

router = APIRouter(prefix="/v1/import-batches", tags=["imports"])


def preview_use_case() -> PreviewImport:
    return PreviewImport(SemsCsvSource(ZoneInfo("America/Sao_Paulo")))


@router.post(
    "/preview",
    response_model=ImportPreviewResponse,
    response_model_by_alias=True,
    responses={422: {"model": ErrorResponse}},
)
async def preview_import(
    file: UploadFile = File(...),
    use_case: PreviewImport = Depends(preview_use_case),
) -> ImportPreviewResponse | JSONResponse:
    try:
        result = use_case.execute(file.filename or "", await file.read())
    except InvalidSession as error:
        body = ErrorResponse(
            error=ErrorBody(
                code=error.code,
                message=error.message,
                details=[ErrorDetail(field=error.field)],
            )
        )
        return JSONResponse(
            status_code=422,
            content=body.model_dump(by_alias=True),
        )
    return ImportPreviewResponse.from_result(result)
```

Add the router and local CORS configuration to `app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

from app.modules.ingestion.presentation.router import router as ingestion_router

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ingestion_router)
```

Translate `InvalidSession` raised at file level to HTTP 422 using this stable payload:

```json
{
  "error": {
    "code": "UNSUPPORTED_FILE",
    "message": "Only CSV files are supported.",
    "details": [{"field": "file"}]
  }
}
```

Include the router under `/v1/import-batches` in `app.main`.

- [ ] **Step 8: Run endpoint and backend suites and verify GREEN**

Run:

```bash
uv run --project apps/api pytest apps/api/tests/modules/ingestion/presentation/test_preview_endpoint.py -v
uv run --project apps/api pytest apps/api/tests -q
```

Expected: all tests PASS with no warnings.

- [ ] **Step 9: Commit the preview API**

```bash
git add apps/api/app apps/api/tests
git commit -m "feat: expose import preview API"
```

---

### Task 5: OpenAPI-backed TypeScript client

**Files:**
- Create: `apps/api/scripts/export_openapi.py`
- Create: `packages/api-client/package.json`
- Create: `packages/api-client/tsconfig.json`
- Create: `packages/api-client/src/index.ts`
- Create: `packages/api-client/src/index.test.ts`
- Generate: `packages/api-client/openapi.json`
- Generate: `packages/api-client/src/schema.ts`
- Modify: `package.json`
- Modify: `apps/web/package.json`

**Interfaces:**
- Produces: `ImportPreviewResponse` from `paths["/v1/import-batches/preview"]["post"]`.
- Produces: `previewImport(file: File, baseUrl?: string): Promise<ImportPreviewResponse>`.

- [ ] **Step 1: Export the OpenAPI document**

Create `apps/api/scripts/export_openapi.py`:

```python
import json
from pathlib import Path

from app.main import app

target = Path(__file__).parents[3] / "packages" / "api-client" / "openapi.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
```

Run: `uv run --project apps/api python apps/api/scripts/export_openapi.py`

Expected: `packages/api-client/openapi.json` contains `/v1/import-batches/preview`.

- [ ] **Step 2: Configure and generate the TypeScript schema**

Create `packages/api-client/package.json`:

```json
{
  "name": "@ev-chargeops/api-client",
  "private": true,
  "type": "module",
  "exports": "./src/index.ts",
  "scripts": {
    "generate": "openapi-typescript openapi.json -o src/schema.ts",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "devDependencies": {
    "openapi-typescript": "latest",
    "typescript": "latest",
    "vitest": "latest"
  }
}
```

Create `packages/api-client/tsconfig.json`:

```json
{
  "compilerOptions": {
    "strict": true,
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "lib": ["ES2022", "DOM"],
    "noEmit": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts"]
}
```

Run `pnpm install` and `pnpm --filter @ev-chargeops/api-client generate`.

- [ ] **Step 3: Write the failing typed-client test**

Create `packages/api-client/src/index.test.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";

import { previewImport } from "./index";

afterEach(() => vi.unstubAllGlobals());

describe("previewImport", () => {
  it("posts the CSV as multipart data and returns the preview", async () => {
    const payload = {
      filename: "sems.csv",
      checksum: "abc123",
      source: "sems_export",
      totalCount: 2,
      validCount: 2,
      invalidCount: 0,
      duplicateCount: 0,
      records: [],
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["header\nvalue"], "sems.csv", { type: "text/csv" });

    await expect(previewImport(file, "http://api.test")).resolves.toEqual(payload);
    const [url, request] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/v1/import-batches/preview");
    expect(request.method).toBe("POST");
    expect(request.body).toBeInstanceOf(FormData);
    expect(request.body.get("file")).toBe(file);
  });
});
```

- [ ] **Step 4: Run the client test and verify RED**

Run: `pnpm --filter @ev-chargeops/api-client test`

Expected: FAIL because `previewImport` is not exported.

- [ ] **Step 5: Write the typed fetch wrapper**

Create `packages/api-client/src/index.ts`:

```typescript
import type { paths } from "./schema";

export type ImportPreviewResponse =
  paths["/v1/import-batches/preview"]["post"]["responses"][200]["content"]["application/json"];

export async function previewImport(
  file: File,
  baseUrl = "http://localhost:8000",
): Promise<ImportPreviewResponse> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${baseUrl}/v1/import-batches/preview`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(`Import preview failed with status ${response.status}`);
  }
  return response.json() as Promise<ImportPreviewResponse>;
}
```

Add `"@ev-chargeops/api-client": "workspace:*"` to `apps/web` dependencies and add these root scripts:

```json
{
  "generate:api": "uv run --project apps/api python apps/api/scripts/export_openapi.py && pnpm --filter @ev-chargeops/api-client generate",
  "test:api-client": "pnpm --filter @ev-chargeops/api-client test",
  "typecheck:api-client": "pnpm --filter @ev-chargeops/api-client typecheck"
}
```

- [ ] **Step 6: Verify client test, contract generation, and type checking**

Run:

```bash
pnpm generate:api
pnpm test:api-client
pnpm typecheck:api-client
```

Expected: both commands exit 0 and the generated response type exposes the camel-case fields used by the UI.

- [ ] **Step 7: Commit the generated contract and client**

```bash
git add package.json pnpm-lock.yaml apps/api/scripts apps/web/package.json packages/api-client
git commit -m "feat: generate TypeScript client from OpenAPI"
```

---

### Task 6: Manager import-preview interface

**Files:**
- Create: `apps/web/src/app/imports/new/page.tsx`
- Create: `apps/web/src/components/imports/import-dropzone.tsx`
- Create: `apps/web/src/components/imports/preview-summary.tsx`
- Create: `apps/web/src/components/imports/preview-table.tsx`
- Create: `apps/web/e2e/import-preview.spec.ts`
- Create: `apps/web/playwright.config.ts`
- Modify: `apps/web/src/app/page.tsx`
- Modify: `apps/web/src/app/layout.tsx`
- Modify: `apps/web/src/app/globals.css`
- Modify: `apps/web/package.json`

**Interfaces:**
- Consumes: `previewImport(file)` and `ImportPreviewResponse` from `@ev-chargeops/api-client`.
- Produces: `/imports/new`, with upload, loading, success, row-error, and retry states.

- [ ] **Step 1: Install Playwright and write the failing browser test**

Run: `pnpm --dir apps/web add -D @playwright/test`

Add `"test:e2e": "playwright test"` to `apps/web/package.json` and run `pnpm --dir apps/web exec playwright install chromium` once on the development machine.

Create `apps/web/playwright.config.ts`:

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://127.0.0.1:3000" },
  webServer: [
    {
      command: "uv run --project ../api uvicorn app.main:app --app-dir ../api --port 8000",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "pnpm dev --hostname 127.0.0.1",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
```

Create `apps/web/e2e/import-preview.spec.ts`:

```typescript
import path from "node:path";
import { expect, test } from "@playwright/test";

test("previews a SEMS export with explicit provenance", async ({ page }) => {
  await page.goto("/imports/new");
  await page.getByLabel("Arquivo CSV do SEMS+").setInputFiles(
    path.resolve(process.cwd(), "../api/tests/fixtures/sems_sessions.csv"),
  );
  await page.getByRole("button", { name: "Analisar arquivo" }).click();

  await expect(page.getByText("2 registros")).toBeVisible();
  await expect(page.getByText("2 válidos")).toBeVisible();
  await expect(page.getByText("0 inválidos")).toBeVisible();
  await expect(page.getByText("0 duplicados")).toBeVisible();
  await expect(page.getByText("Fonte real").first()).toBeVisible();
  await expect(page.getByText("Identidade desconhecida").first()).toBeVisible();
});
```

- [ ] **Step 2: Run the browser test and verify RED**

Run: `pnpm --dir apps/web exec playwright test e2e/import-preview.spec.ts`

Expected: FAIL because `/imports/new` and its controls do not exist.

- [ ] **Step 3: Implement the import page and focused components**

Create `preview-summary.tsx`:

```tsx
import type { ImportPreviewResponse } from "@ev-chargeops/api-client";

export function PreviewSummary({ preview }: { preview: ImportPreviewResponse }) {
  const cards = [
    [preview.totalCount, "registros"],
    [preview.validCount, "válidos"],
    [preview.invalidCount, "inválidos"],
    [preview.duplicateCount, "duplicados"],
  ] as const;
  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumo da análise">
      {cards.map(([value, label]) => (
        <div key={label} className="rounded-2xl border border-white/10 bg-white/[0.06] p-5">
          <p className="font-mono text-3xl font-semibold text-white">{value} <span className="text-sm font-normal text-slate-400">{label}</span></p>
        </div>
      ))}
    </section>
  );
}
```

Create `preview-table.tsx`:

```tsx
import type { ImportPreviewResponse } from "@ev-chargeops/api-client";

export function PreviewTable({ preview }: { preview: ImportPreviewResponse }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-white/[0.06] text-xs uppercase tracking-[0.16em] text-slate-400">
          <tr>{["Linha", "Status", "Energia", "Início", "Carregador", "Procedência"].map((label) => <th key={label} className="px-4 py-3">{label}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-white/10">
          {preview.records.map((record) => (
            <tr key={record.rowNumber} className="bg-slate-950/40 align-top">
              <td className="px-4 py-4 font-mono text-slate-400">{record.rowNumber}</td>
              <td className="px-4 py-4 text-white">{record.classification}</td>
              <td className="px-4 py-4 font-mono text-white">{record.session ? `${record.session.energyKwh} kWh` : "—"}</td>
              <td className="px-4 py-4 text-slate-300">{record.session ? new Date(record.session.startedAt).toLocaleString("pt-BR") : record.errorMessage}</td>
              <td className="px-4 py-4 font-mono text-slate-300">{record.session?.chargerSerial ?? "—"}</td>
              <td className="px-4 py-4">
                {record.session ? (
                  <div className="flex flex-col gap-2">
                    <span className="w-fit rounded-full bg-cyan-400/10 px-2 py-1 text-xs text-cyan-300">Fonte real</span>
                    <span className="w-fit rounded-full bg-amber-300/10 px-2 py-1 text-xs text-amber-200">Identidade desconhecida</span>
                  </div>
                ) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

Create `import-dropzone.tsx`:

```tsx
"use client";

import { useState } from "react";
import { previewImport, type ImportPreviewResponse } from "@ev-chargeops/api-client";

import { PreviewSummary } from "./preview-summary";
import { PreviewTable } from "./preview-table";

export function ImportDropzone() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function analyze() {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      setPreview(await previewImport(file, process.env.NEXT_PUBLIC_API_URL));
    } catch {
      setError("Não foi possível analisar o arquivo. Verifique o formato e tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  if (preview) {
    return (
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div><p className="text-sm text-slate-400">Preview local, ainda não persistido</p><p className="font-mono text-sm text-cyan-300">{preview.filename}</p></div>
          <button className="rounded-full border border-white/15 px-4 py-2 text-sm text-white hover:bg-white/10" onClick={() => { setFile(null); setPreview(null); }}>Revisar outro arquivo</button>
        </div>
        <PreviewSummary preview={preview} />
        <PreviewTable preview={preview} />
      </div>
    );
  }

  return (
    <section className="rounded-3xl border border-dashed border-cyan-300/30 bg-white/[0.04] p-8 sm:p-12">
      <label htmlFor="sems-file" className="block text-lg font-medium text-white">Arquivo CSV do SEMS+</label>
      <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">Os registros serão validados e classificados antes de qualquer persistência.</p>
      <input id="sems-file" className="mt-6 block w-full text-sm text-slate-300 file:mr-4 file:rounded-full file:border-0 file:bg-cyan-300 file:px-4 file:py-2 file:font-semibold file:text-slate-950" type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
      {file && <p className="mt-4 font-mono text-sm text-cyan-300">{file.name}</p>}
      {error && <p role="alert" className="mt-4 text-sm text-rose-300">{error}</p>}
      <button disabled={!file || loading} onClick={analyze} className="mt-6 rounded-full bg-[#ff5b45] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#ff735f] disabled:cursor-not-allowed disabled:opacity-40">
        {loading ? "Analisando…" : "Analisar arquivo"}
      </button>
    </section>
  );
}
```

Create `app/imports/new/page.tsx`:

```tsx
import { ImportDropzone } from "@/components/imports/import-dropzone";

export default function NewImportPage() {
  return (
    <main className="min-h-screen bg-[#08111f] px-5 py-10 text-white sm:px-10 lg:px-16">
      <div className="mx-auto max-w-7xl">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300">EV ChargeOps / Ingestão</p>
        <h1 className="mt-5 max-w-3xl text-4xl font-semibold tracking-tight sm:text-6xl">Transforme sessões brutas em evidência operacional.</h1>
        <p className="mb-10 mt-5 max-w-2xl text-base leading-7 text-slate-400">Pré-visualize o histórico do SEMS+, identifique problemas e confirme a procedência antes de importar.</p>
        <ImportDropzone />
      </div>
    </main>
  );
}
```

Replace `app/page.tsx`:

```tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/imports/new");
}
```

Set the generated `layout.tsx` metadata to:

```tsx
export const metadata: Metadata = {
  title: "EV ChargeOps",
  description: "Operação auditável de recarga compartilhada",
};
```

Replace `globals.css`:

```css
@import "tailwindcss";

:root {
  color-scheme: dark;
}

* {
  box-sizing: border-box;
}

html {
  background: #08111f;
}

body {
  margin: 0;
  background: #08111f;
  color: #f8fafc;
}

button,
input {
  font: inherit;
}
```

- [ ] **Step 4: Run the browser test and verify GREEN**

Run: `pnpm --dir apps/web exec playwright test e2e/import-preview.spec.ts`

Expected: PASS.

- [ ] **Step 5: Run frontend lint and production build**

Run:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Expected: both commands exit 0 with no TypeScript or ESLint errors.

- [ ] **Step 6: Perform visual QA in the local browser**

Start both development servers, inspect `/imports/new` at desktop and narrow viewport widths, upload the fixture, and verify that cards, table overflow, loading state, error text, provenance badges, focus rings, and empty state remain readable. Save no credentials or browser state to the repository.

- [ ] **Step 7: Commit the first vertical-slice UI**

```bash
git add apps/web package.json pnpm-lock.yaml
git commit -m "feat: add SEMS import preview interface"
```

---

### Task 7: Quality gate and developer handoff

**Files:**
- Create: `apps/api/.env.example`
- Create: `apps/web/.env.example`
- Modify: `README.md`
- Modify: `package.json`

**Interfaces:**
- Produces: `pnpm check` as the single local quality command.
- Produces: documented local startup and fixture-upload flow.

- [ ] **Step 1: Add configuration examples and aggregate checks**

Create `apps/web/.env.example` with `NEXT_PUBLIC_API_URL=http://localhost:8000`. Keep `apps/api/.env.example` empty except for a comment that Supabase variables arrive in the persistence increment. Add root scripts:

```json
{
  "check": "pnpm lint:api && pnpm test:api && pnpm generate:api && pnpm typecheck:api-client && pnpm lint:web && pnpm --dir apps/web build && pnpm test:web"
}
```

- [ ] **Step 2: Document local execution and scope**

Add a README development section with prerequisites, `pnpm install`, `uv sync --project apps/api`, the two development-server commands, `pnpm check`, and the fixture path. State explicitly that preview data is not persisted and authentication is not part of this first slice.

- [ ] **Step 3: Run the complete quality gate**

Run: `pnpm check`

Expected: ruff, pytest, OpenAPI generation, TypeScript client checking, ESLint, Next.js build, and Playwright all exit 0.

- [ ] **Step 4: Verify repository hygiene**

Run:

```bash
git diff --check
git status --short
git grep -nE '(SUPABASE_SERVICE_ROLE|MERCADO_PAGO_ACCESS_TOKEN|BEGIN PRIVATE KEY)' -- . ':!docs/superpowers/plans/*'
```

Expected: no whitespace errors, only intended files pending, and no secret-pattern matches.

- [ ] **Step 5: Commit the handoff**

```bash
git add README.md package.json apps/api/.env.example apps/web/.env.example
git commit -m "docs: add local development workflow"
```

## Self-review result

- **Spec coverage:** The plan delivers an executable preview across the source port, canonical model, FastAPI endpoint, OpenAPI client, and Next.js UI. It deliberately defers persistence and the other PRD subsystems to avoid coupling unvalidated input mapping to the database.
- **Placeholder scan:** The plan contains no TBD, TODO, generic error-handling instruction, or unnamed test step.
- **Type consistency:** `SessionCandidate`, `SourceRecord`, `ChargingSessionSource`, `PreviewImport`, `ImportPreviewResponse`, and the preview endpoint keep the same names and responsibilities across tasks.
- **Next plan:** Supabase Auth plus persisted idempotent import batches, raw records, charging sessions, and cross-batch duplicate detection (FR-01 through FR-03 and FR-06).
