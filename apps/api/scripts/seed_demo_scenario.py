"""Seed the labelled monthly demonstration scenario.

The real SEMS+ export available for the challenge holds two charging sessions on
a single day, which is not enough to show a monthly close, a distribution across
tariff bands, or an analytical opinion with anything to say. This script builds a
full month so those flows can be demonstrated.

Everything it writes is marked `simulated`, both on the import batch and on every
session, and `provenance_of` in the ingestion domain makes that impossible to
bypass. Real telemetry and this scenario never share a batch and never merge
silently: the interface reads provenance from the session, not from the screen it
happens to be on.

The generator is deterministic. The same seed always produces the same month, so
a demonstration can be rehearsed and a bug can be reproduced.

Usage:
    apps/api/.venv/bin/python apps/api/scripts/seed_demo_scenario.py
"""

import asyncio
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from random import Random
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parents[1]))

from seed_operational_foundation import (
    DEMO_CHARGER_ID,
    DEMO_ORGANIZATION_ID,
    DEMO_SITE_ID,
    seed_operational_foundation,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.domain.reference import sprint1_policy, sprint1_tariff
from app.modules.billing.infrastructure.models import (
    BillingPolicyModel,
    ChargerEnergyReadingModel,
    TariffBandModel,
    TariffSnapshotModel,
)
from app.modules.ingestion.domain.session import (
    IdentityConfidence,
    SessionCandidate,
    SourceKind,
)
from app.modules.ingestion.infrastructure.models import (
    ChargingSessionModel,
    ImportBatchModel,
    RawImportRecordModel,
)
from app.modules.organizations.infrastructure.models import ProfileModel, UnitModel
from app.modules.sessions.infrastructure.models import SessionAssignmentModel
from app.shared.config import get_settings
from app.shared.database import create_engine_from_settings, create_session_factory

SCENARIO_NAMESPACE = UUID("00000000-0000-0000-0000-00000000de70")
SCENARIO_MONTH = "2026-05"
SCENARIO_LABEL = "cenario-demonstrativo-2026-05.csv"
SITE_ZONE = ZoneInfo("America/Sao_Paulo")
CHARGER_SERIAL = "97500NAP25BL0008"
NOMINAL_POWER_KW = Decimal("11.000")
RANDOM_SEED = 20260501

TARIFF_ID = uuid5(SCENARIO_NAMESPACE, "tariff")
POLICY_ID = uuid5(SCENARIO_NAMESPACE, "policy")
SHOP_UNIT_ID = uuid5(SCENARIO_NAMESPACE, "unit-LJ-01")

# Standby draw and cable losses the charger reports but no session captures.
# Gives the external reconciliation a small, explainable, non-zero difference
# instead of a suspiciously perfect match against the manufacturer's own total.
UNMETERED_KWH_PER_ACTIVE_DAY = Decimal("0.08")


@dataclass(frozen=True, slots=True)
class Habit:
    """How one unit tends to charge, so the month looks lived-in."""

    unit_code: str
    sessions_per_week: int
    earliest_hour: int
    latest_hour: int
    min_energy: Decimal
    max_energy: Decimal
    power_kw: Decimal


HABITS = (
    Habit("A-101", 3, 22, 23, Decimal(18), Decimal(24), Decimal("7.0")),
    Habit("A-102", 2, 19, 20, Decimal(12), Decimal(22), Decimal("7.0")),
    Habit("A-103", 2, 23, 23, Decimal(25), Decimal(30), Decimal("7.2")),
    Habit("A-104", 2, 8, 11, Decimal(15), Decimal(18), Decimal("7.1")),
    Habit("LJ-01", 2, 13, 15, Decimal(8), Decimal(12), Decimal("7.0")),
)


@dataclass(frozen=True, slots=True)
class PlannedSession:
    started_at: datetime
    ended_at: datetime
    energy_kwh: Decimal
    unit_code: str | None
    note: str


def month_days(month: str) -> list[date]:
    year, mon = (int(part) for part in month.split("-"))
    first = date(year, mon, 1)
    last = date(year + (mon == 12), (mon % 12) + 1, 1)
    return [first + timedelta(days=offset) for offset in range((last - first).days)]


def duration_for(energy_kwh: Decimal, power_kw: Decimal) -> timedelta:
    minutes = int((energy_kwh / power_kw) * 60)
    return timedelta(minutes=max(minutes, 5))


def plan_month() -> list[PlannedSession]:
    """Build the month deterministically, then bend three sessions on purpose.

    The three deliberate defects exist so the closing opinion has real material
    to find during a demonstration, rather than a clean month that makes the
    analytical step look decorative.
    """
    rng = Random(RANDOM_SEED)
    days = month_days(SCENARIO_MONTH)
    planned: list[PlannedSession] = []

    for habit in HABITS:
        for week_start in range(0, len(days), 7):
            week = days[week_start : week_start + 7]
            if not week:
                continue
            for day in rng.sample(week, min(habit.sessions_per_week, len(week))):
                hour = rng.randint(habit.earliest_hour, habit.latest_hour)
                minute = rng.choice((0, 10, 15, 25, 30, 40, 45, 50))
                energy = Decimal(
                    rng.randint(int(habit.min_energy * 10), int(habit.max_energy * 10))
                ) / Decimal(10)
                started = datetime.combine(
                    day, datetime.min.time(), tzinfo=SITE_ZONE
                ).replace(hour=hour, minute=minute)
                planned.append(
                    PlannedSession(
                        started_at=started,
                        ended_at=started + duration_for(energy, habit.power_kw),
                        energy_kwh=energy,
                        unit_code=habit.unit_code,
                        note="uso recorrente",
                    )
                )

    planned.sort(key=lambda item: item.started_at)

    # A session whose average power exceeds the 11 kW nameplate of the HCA G2.
    # Physically impossible on this equipment, so the opinion must flag it.
    impossible_start = datetime(2026, 5, 14, 20, 0, tzinfo=SITE_ZONE)
    planned.append(
        PlannedSession(
            started_at=impossible_start,
            ended_at=impossible_start + timedelta(minutes=30),
            energy_kwh=Decimal("9.4"),
            unit_code="A-102",
            note="potência média acima da nominal",
        )
    )

    # Two sessions overlapping on a single-connector charger: one of them is a
    # duplicate or a metering fault, and the close should not guess which.
    overlap_start = datetime(2026, 5, 21, 22, 30, tzinfo=SITE_ZONE)
    planned.append(
        PlannedSession(
            started_at=overlap_start,
            ended_at=overlap_start + timedelta(hours=3),
            energy_kwh=Decimal("21.0"),
            unit_code="A-101",
            note="suspeita de duplicidade",
        )
    )
    planned.append(
        PlannedSession(
            started_at=overlap_start + timedelta(minutes=20),
            ended_at=overlap_start + timedelta(hours=3, minutes=20),
            energy_kwh=Decimal("20.6"),
            unit_code=None,
            note="suspeita de duplicidade, sem atribuição",
        )
    )

    # Three ordinary sessions left unassigned, so the pending queue has work and
    # the close has a blocker the manager actually has to resolve.
    unassigned = [item for item in planned if item.unit_code is not None][-3:]
    for item in unassigned:
        planned[planned.index(item)] = PlannedSession(
            started_at=item.started_at,
            ended_at=item.ended_at,
            energy_kwh=item.energy_kwh,
            unit_code=None,
            note="aguardando atribuição",
        )

    planned.sort(key=lambda item: item.started_at)
    return planned


async def resolve_actor(session: AsyncSession) -> UUID:
    profile = (await session.execute(select(ProfileModel).limit(1))).scalar_one_or_none()
    if profile is not None:
        return profile.id
    demo = ProfileModel(
        id=uuid5(SCENARIO_NAMESPACE, "profile"),
        auth_user_id=uuid5(SCENARIO_NAMESPACE, "auth"),
        email="manager@example.test",
        display_name="Síndico (demonstração)",
    )
    session.add(demo)
    await session.flush()
    return demo.id


async def ensure_units(session: AsyncSession) -> dict[str, UUID]:
    if await session.get(UnitModel, SHOP_UNIT_ID) is None:
        session.add(
            UnitModel(
                id=SHOP_UNIT_ID,
                organization_id=DEMO_ORGANIZATION_ID,
                code="LJ-01",
                display_name="Loja LJ-01",
            )
        )
        await session.flush()
    rows = await session.execute(
        select(UnitModel).where(UnitModel.organization_id == DEMO_ORGANIZATION_ID)
    )
    return {unit.code: unit.id for unit in rows.scalars()}


async def ensure_tariff_and_policy(session: AsyncSession) -> None:
    """Persist the Sprint 1 reference tariff and policy, if not already there."""
    tariff = sprint1_tariff()
    if await session.get(TariffSnapshotModel, TARIFF_ID) is None:
        session.add(
            TariffSnapshotModel(
                id=TARIFF_ID,
                organization_id=DEMO_ORGANIZATION_ID,
                name=tariff.name,
                timezone=tariff.timezone,
                # Who set these prices, classified the way a real condominium
                # would: the administration did, in its own table. A path into
                # this repository is an answer to a question nobody asked.
                source="manual",
                source_reference=None,
                captured_at=datetime(2026, 6, 21, tzinfo=UTC),
                valid_from=date(2026, 1, 1),
                valid_to=None,
            )
        )
        for band in tariff.bands:
            session.add(
                TariffBandModel(
                    id=uuid5(SCENARIO_NAMESPACE, f"band-{band.code}"),
                    organization_id=DEMO_ORGANIZATION_ID,
                    tariff_snapshot_id=TARIFF_ID,
                    code=band.code,
                    rate_cents_per_kwh=band.rate_cents_per_kwh,
                    windows=[
                        {
                            "start_minute": window.start_minute,
                            "end_minute": window.end_minute,
                            "weekdays": sorted(window.weekdays),
                        }
                        for window in band.windows
                    ],
                )
            )

    policy = sprint1_policy()
    if await session.get(BillingPolicyModel, POLICY_ID) is None:
        session.add(
            BillingPolicyModel(
                id=POLICY_ID,
                organization_id=DEMO_ORGANIZATION_ID,
                name=policy.name,
                infra_fee_cents=policy.infra_fee_cents,
                loss_basis_points=policy.loss_basis_points,
                valid_from=date(2026, 1, 1),
                valid_to=None,
            )
        )
    await session.flush()


async def clear_previous_scenario(session: AsyncSession, batch_id: UUID) -> None:
    """Make the seed re-runnable without duplicating the month."""
    sessions = (
        await session.execute(
            select(ChargingSessionModel.id).where(
                ChargingSessionModel.import_batch_id == batch_id
            )
        )
    ).scalars().all()
    if sessions:
        await session.execute(
            delete(SessionAssignmentModel).where(
                SessionAssignmentModel.charging_session_id.in_(sessions)
            )
        )
        await session.execute(
            delete(ChargingSessionModel).where(ChargingSessionModel.id.in_(sessions))
        )
    await session.execute(
        delete(RawImportRecordModel).where(
            RawImportRecordModel.import_batch_id == batch_id
        )
    )
    await session.execute(
        delete(ChargerEnergyReadingModel).where(
            ChargerEnergyReadingModel.import_batch_id == batch_id
        )
    )
    await session.flush()


async def seed_demo_scenario(session: AsyncSession) -> dict[str, int]:
    await seed_operational_foundation(session)
    actor_id = await resolve_actor(session)
    units = await ensure_units(session)
    await ensure_tariff_and_policy(session)

    planned = plan_month()
    batch_id = uuid5(SCENARIO_NAMESPACE, f"batch-{SCENARIO_MONTH}")
    await clear_previous_scenario(session, batch_id)

    checksum = sha256(
        "|".join(
            f"{item.started_at.isoformat()}:{item.energy_kwh}" for item in planned
        ).encode("utf-8")
    ).hexdigest()

    batch = await session.get(ImportBatchModel, batch_id)
    if batch is None:
        batch = ImportBatchModel(
            id=batch_id,
            organization_id=DEMO_ORGANIZATION_ID,
            source=SourceKind.SIMULATED.value,
            checksum=checksum,
            filename=SCENARIO_LABEL,
            storage_path=None,
            status="completed",
            total_count=len(planned),
            valid_count=len(planned),
            invalid_count=0,
            duplicate_count=0,
            created_by=actor_id,
        )
        session.add(batch)
    else:
        batch.checksum = checksum
        batch.total_count = len(planned)
        batch.valid_count = len(planned)
    await session.flush()

    assigned = 0
    for row_number, item in enumerate(planned, start=1):
        candidate = SessionCandidate.create(
            source=SourceKind.SIMULATED,
            external_id=f"demo-{SCENARIO_MONTH}-{row_number:03d}",
            charger_serial=CHARGER_SERIAL,
            started_at=item.started_at,
            ended_at=item.ended_at,
            energy_kwh=item.energy_kwh,
            charge_port=1,
            card_id_raw=None,
        )
        raw_id = uuid5(SCENARIO_NAMESPACE, f"raw-{row_number}")
        session.add(
            RawImportRecordModel(
                id=raw_id,
                organization_id=DEMO_ORGANIZATION_ID,
                import_batch_id=batch_id,
                row_number=row_number,
                raw_payload={
                    "Start Time": item.started_at.isoformat(),
                    "End Time": item.ended_at.isoformat(),
                    "Charging Energy(kWh)": str(item.energy_kwh),
                    "Charging Port": "1",
                    "Device SN": CHARGER_SERIAL,
                    "Cenario": SCENARIO_LABEL,
                    "Observacao": item.note,
                },
                classification="valid",
            )
        )
        session_id = uuid5(SCENARIO_NAMESPACE, f"session-{row_number}")
        unit_id = units.get(item.unit_code) if item.unit_code else None
        session.add(
            ChargingSessionModel(
                id=session_id,
                organization_id=DEMO_ORGANIZATION_ID,
                site_id=DEMO_SITE_ID,
                charger_id=DEMO_CHARGER_ID,
                import_batch_id=batch_id,
                raw_record_id=raw_id,
                source=candidate.source.value,
                external_id=candidate.external_id,
                deduplication_key=candidate.deduplication_key,
                started_at=candidate.started_at,
                ended_at=candidate.ended_at,
                energy_kwh=candidate.energy_kwh,
                charge_port=candidate.charge_port,
                card_id_raw=candidate.card_id_raw,
                identity_confidence=(
                    IdentityConfidence.ASSIGNED.value
                    if unit_id
                    else IdentityConfidence.UNKNOWN.value
                ),
                provenance=candidate.provenance.value,
                status="ready" if unit_id else "pending_review",
            )
        )
        if unit_id is not None:
            assigned += 1
            session.add(
                SessionAssignmentModel(
                    id=uuid5(SCENARIO_NAMESPACE, f"assignment-{row_number}"),
                    organization_id=DEMO_ORGANIZATION_ID,
                    charging_session_id=session_id,
                    unit_id=unit_id,
                    assigned_by=actor_id,
                    justification=(
                        "Atribuição do cenário demonstrativo, com base no padrão "
                        "de uso da unidade."
                    ),
                )
            )

    readings = await seed_charger_readings(session, planned, batch_id)
    await session.commit()
    return {
        "sessions": len(planned),
        "assigned": assigned,
        "pending": len(planned) - assigned,
        "readings": readings,
    }


async def seed_charger_readings(
    session: AsyncSession,
    planned: list[PlannedSession],
    batch_id: UUID,
) -> int:
    """Daily totals the equipment would report, as the external control total.

    Each active day carries a small unmetered amount on top of its sessions, so
    the external reconciliation reports a real difference the manager has to look
    at rather than a perfect match that would prove nothing.
    """
    by_day: dict[str, Decimal] = {}
    for item in planned:
        day = item.started_at.astimezone(SITE_ZONE).date().isoformat()
        by_day[day] = by_day.get(day, Decimal(0)) + item.energy_kwh

    for day, energy in by_day.items():
        reading_id = uuid5(SCENARIO_NAMESPACE, f"reading-{day}")
        if await session.get(ChargerEnergyReadingModel, reading_id) is not None:
            continue
        session.add(
            ChargerEnergyReadingModel(
                id=reading_id,
                organization_id=DEMO_ORGANIZATION_ID,
                charger_id=DEMO_CHARGER_ID,
                import_batch_id=batch_id,
                period_type="day",
                period_value=day,
                energy_kwh=energy + UNMETERED_KWH_PER_ACTIVE_DAY,
                source=SourceKind.SIMULATED.value,
                provenance="simulated",
                captured_at=datetime(2026, 6, 1, tzinfo=UTC),
            )
        )
    return len(by_day)


async def main() -> None:
    engine = create_engine_from_settings(get_settings())
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            summary = await seed_demo_scenario(session)
    finally:
        await engine.dispose()

    total = sum(item.energy_kwh for item in plan_month())
    print(f"Cenário demonstrativo {SCENARIO_MONTH} — {SCENARIO_LABEL}")
    print(f"  recargas ...... {summary['sessions']}")
    print(f"  atribuídas .... {summary['assigned']}")
    print(f"  pendentes ..... {summary['pending']}")
    print(f"  dias com leitura do carregador ... {summary['readings']}")
    print(f"  energia total ... {total} kWh")


if __name__ == "__main__":
    asyncio.run(main())
