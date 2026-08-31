"""Provenance follows from the source, so a scenario cannot pose as telemetry."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.modules.ingestion.domain.session import (
    DataProvenance,
    SessionCandidate,
    SourceKind,
    provenance_of,
)


def candidate(source: SourceKind) -> SessionCandidate:
    return SessionCandidate.create(
        source=source,
        external_id=None,
        charger_serial="97500NAP25BL0008",
        started_at=datetime(2026, 5, 4, 22, 0, tzinfo=UTC),
        ended_at=datetime(2026, 5, 5, 1, 0, tzinfo=UTC),
        energy_kwh=Decimal("21.5"),
        charge_port=1,
        card_id_raw=None,
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (SourceKind.SEMS_EXPORT, DataProvenance.REAL),
        (SourceKind.MANUAL, DataProvenance.REAL),
        (SourceKind.GOODWE_API, DataProvenance.REAL),
        (SourceKind.SIMULATED, DataProvenance.SIMULATED),
    ],
)
def test_provenance_is_derived_from_the_source(source, expected):
    assert provenance_of(source) is expected
    assert candidate(source).provenance is expected


def test_a_simulated_session_can_never_claim_to_be_real():
    """The guardrail, enforced at construction rather than by convention."""
    assert candidate(SourceKind.SIMULATED).provenance is not DataProvenance.REAL


def test_every_source_kind_has_a_provenance():
    for source in SourceKind:
        assert isinstance(provenance_of(source), DataProvenance)
