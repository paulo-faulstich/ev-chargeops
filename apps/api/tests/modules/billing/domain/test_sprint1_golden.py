"""The apportionment engine must reproduce the Sprint 1 worked example.

`docs/product/prd.md` section 4.4 adopts the Sprint 1 formula as the
implementation contract, and `data/exemplos/faturas.csv` is the only artefact in
this project whose correct answer was published and graded before the code
existed. Reproducing it to the cent is the acceptance gate for the whole
calculation layer.

Each session's tariff band is resolved from its start time, never from the
`periodo_tarifario` column of the fixture, so these tests also prove that the
band windows in `reference.py` match what Sprint 1 assumed.
"""

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

import pytest

from app.modules.billing.domain.calculation import BillableSession, calculate_invoices
from app.modules.billing.domain.reference import (
    SPRINT1_TIMEZONE,
    sprint1_policy,
    sprint1_tariff,
)


def repo_root() -> Path:
    """Walk up to the workspace root, so the depth of this file can change."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pnpm-workspace.yaml").exists():
            return candidate
    raise RuntimeError("workspace root not found")


EXAMPLES = repo_root() / "data" / "exemplos"
NAMESPACE = UUID("00000000-0000-0000-0000-00000000f1a9")
SITE_ZONE = ZoneInfo(SPRINT1_TIMEZONE)
UTC = ZoneInfo("UTC")


def as_uuid(natural_key: str) -> UUID:
    """Stable identifier for a Sprint 1 natural key, so fixtures stay readable."""
    return uuid5(NAMESPACE, natural_key)


def read_csv(name: str) -> list[dict[str, str]]:
    with (EXAMPLES / name).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def to_cents(value: str) -> int:
    return int((Decimal(value) * 100).to_integral_value())


def local_to_utc(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=SITE_ZONE).astimezone(UTC)


@pytest.fixture(scope="module")
def sprint1_sessions() -> tuple[BillableSession, ...]:
    """Sprint 1 billed per RFID user; the product now bills the unit.

    Sessions are mapped to their user's unit, which is the durable financial
    target. U102 therefore collects the sessions of both its vehicles, and the
    two Sprint 1 invoices for that unit are compared as their sum.
    """
    unit_of_user = {
        row["id_usuario"]: row["id_unidade"] for row in read_csv("usuarios.csv")
    }
    return tuple(
        BillableSession(
            id=as_uuid(row["id_sessao"]),
            unit_id=as_uuid(unit_of_user[row["id_usuario"]]),
            started_at=local_to_utc(row["inicio"]),
            ended_at=local_to_utc(row["fim"]),
            energy_kwh=Decimal(row["energia_kwh"]),
        )
        for row in read_csv("sessoes.csv")
    )


@pytest.fixture(scope="module")
def expected_by_unit() -> dict[str, dict[str, int]]:
    """Sprint 1 invoices, summed per unit and converted to integer cents."""
    totals: dict[str, dict[str, int]] = {}
    for row in read_csv("faturas.csv"):
        bucket = totals.setdefault(
            row["id_unidade"], {"energy": 0, "infra": 0, "loss": 0, "total": 0}
        )
        bucket["energy"] += to_cents(row["valor_energia"])
        bucket["infra"] += to_cents(row["taxa_infra"])
        bucket["loss"] += to_cents(row["rateio_perdas"])
        bucket["total"] += to_cents(row["valor_total"])
    return totals


@pytest.fixture(scope="module")
def drafts(sprint1_sessions, expected_by_unit):
    unit_ids = tuple(as_uuid(code) for code in expected_by_unit)
    return {
        draft.unit_id: draft
        for draft in calculate_invoices(
            sprint1_sessions, sprint1_tariff(), sprint1_policy(), unit_ids
        )
    }


ALL_UNITS = ["U101", "U102", "U205", "U310", "LJ01"]
SINGLE_VEHICLE_UNITS = ["U101", "U205", "U310", "LJ01"]


@pytest.mark.parametrize("unit_code", ALL_UNITS)
@pytest.mark.parametrize("component", ["energy", "loss"])
def test_energy_and_losses_reproduce_sprint1(
    drafts, expected_by_unit, unit_code, component
):
    """The metered part of the bill is identical for every unit."""
    draft = drafts[as_uuid(unit_code)]
    actual = {
        "energy": draft.energy_value_cents,
        "loss": draft.loss_share_cents,
    }[component]
    assert actual == expected_by_unit[unit_code][component]


@pytest.mark.parametrize("unit_code", SINGLE_VEHICLE_UNITS)
@pytest.mark.parametrize("component", ["infra", "total"])
def test_fee_and_total_reproduce_sprint1(
    drafts, expected_by_unit, unit_code, component
):
    """Units with one vehicle reproduce the Sprint 1 invoice in full."""
    draft = drafts[as_uuid(unit_code)]
    actual = {
        "infra": draft.infra_fee_cents,
        "total": draft.total_cents,
    }[component]
    assert actual == expected_by_unit[unit_code][component]


@pytest.mark.parametrize("unit_code", ALL_UNITS)
def test_infrastructure_fee_is_charged_once_per_active_unit(drafts, unit_code):
    charged_in_period = unit_code != "U310"
    expected = sprint1_policy().infra_fee_cents if charged_in_period else 0
    assert drafts[as_uuid(unit_code)].infra_fee_cents == expected


def test_two_vehicle_unit_diverges_from_sprint1_only_on_the_fee(
    drafts, expected_by_unit
):
    """The single deliberate divergence from the Sprint 1 worked example.

    Sprint 1 billed each RFID user separately, so U102 paid the infrastructure
    fee twice, once per vehicle. The product now bills the unit, and the field
    data offers no way to tell two vehicles apart: the charger has no cards
    configured and the GoodWe OpenAPI carries no identity field at all. A fee
    per unit is therefore the only rule the data supports, and it is the easier
    one to defend in an assembly.

    Everything else about this unit reproduces exactly, which is what makes the
    divergence safe to accept: it has one cause and one line.
    """
    draft = drafts[as_uuid("U102")]
    sprint1 = expected_by_unit["U102"]

    assert draft.energy_value_cents == sprint1["energy"]
    assert draft.loss_share_cents == sprint1["loss"]

    assert sprint1["infra"] == 2 * sprint1_policy().infra_fee_cents
    assert draft.infra_fee_cents == sprint1_policy().infra_fee_cents
    assert sprint1["total"] - draft.total_cents == sprint1_policy().infra_fee_cents


def test_unit_without_consumption_is_billed_zero(drafts):
    """US005 charged nothing: no energy, and no infrastructure fee either."""
    draft = drafts[as_uuid("U310")]
    assert draft.items == ()
    assert draft.energy_value_cents == 0
    assert draft.infra_fee_cents == 0
    assert draft.loss_share_cents == 0
    assert draft.total_cents == 0


def test_interrupted_session_bills_the_energy_measured(drafts):
    """S0004 stopped early; the meter reading is real, so it is billed."""
    items = {item.charging_session_id: item for item in drafts[as_uuid("U101")].items}
    interrupted = items[as_uuid("S0004")]
    assert interrupted.energy_kwh == Decimal("3.1")
    assert interrupted.band_code == "fora_ponta"
    assert interrupted.value_cents == 242


def test_two_vehicles_share_one_unit_invoice(drafts):
    """U102 has two RFID users; the unit is the durable financial target."""
    draft = drafts[as_uuid("U102")]
    assert len(draft.items) == 3
    assert draft.energy_kwh == Decimal("64.3")


def test_invoice_total_is_the_sum_of_its_printed_lines(drafts):
    """Every line must be independently verifiable against the printed total."""
    for draft in drafts.values():
        assert draft.energy_value_cents == sum(item.value_cents for item in draft.items)
        assert draft.total_cents == (
            draft.energy_value_cents + draft.infra_fee_cents + draft.loss_share_cents
        )


def test_bands_come_from_start_time_not_from_the_fixture_column():
    """The reference windows must reproduce every Sprint 1 band label."""
    tariff = sprint1_tariff()
    for row in read_csv("sessoes.csv"):
        resolved = tariff.resolve_band(local_to_utc(row["inicio"]))
        assert resolved.code == row["periodo_tarifario"], row["id_sessao"]
