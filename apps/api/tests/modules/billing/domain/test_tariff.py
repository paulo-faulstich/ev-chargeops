"""Band resolution and the coverage invariant.

A tariff with a gap would silently drop a session from the bill; a tariff with
an overlap would make the applied rate depend on band ordering. Both are
rejected at construction, so an invalid tariff cannot reach a close.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.modules.billing.domain.errors import (
    BandNotFound,
    InvalidRate,
    TariffCoverageError,
)
from app.modules.billing.domain.reference import SPRINT1_TIMEZONE, sprint1_tariff
from app.modules.billing.domain.tariff import (
    MINUTES_IN_DAY,
    TariffBand,
    TariffSnapshot,
    TariffWindow,
)

SITE_ZONE = ZoneInfo(SPRINT1_TIMEZONE)
UTC = ZoneInfo("UTC")


def at_local(day: int, hour: int, minute: int = 0) -> datetime:
    """An instant expressed in the site's wall clock, stored as UTC."""
    return datetime(2026, 5, day, hour, minute, tzinfo=SITE_ZONE).astimezone(UTC)


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (0, 0, "fora_ponta"),
        (5, 59, "fora_ponta"),
        (6, 0, "intermediario"),
        (17, 59, "intermediario"),
        (18, 0, "ponta"),
        (20, 59, "ponta"),
        (21, 0, "fora_ponta"),
        (23, 59, "fora_ponta"),
    ],
)
def test_band_boundaries_are_half_open(hour, minute, expected):
    """A window owns its start minute and releases its end minute."""
    assert sprint1_tariff().resolve_band(at_local(4, hour, minute)).code == expected


def test_a_session_is_billed_in_the_band_it_started_in():
    """Crossing midnight does not split the session; the start decides."""
    tariff = sprint1_tariff()
    assert tariff.resolve_band(at_local(2, 22, 10)).code == "fora_ponta"
    assert tariff.resolve_band(at_local(3, 1, 40)).code == "fora_ponta"


def test_peak_applies_on_weekends_as_sprint1_defined_it():
    """3 May 2026 is a Sunday, and Sprint 1 billed it at the peak rate."""
    assert at_local(3, 19, 5).astimezone(SITE_ZONE).weekday() == 6
    assert sprint1_tariff().resolve_band(at_local(3, 19, 5)).code == "ponta"


def test_reference_rates_match_sprint1():
    tariff = sprint1_tariff()
    assert tariff.band_for("ponta").rate_cents_per_kwh == 125
    assert tariff.band_for("intermediario").rate_cents_per_kwh == 95
    assert tariff.band_for("fora_ponta").rate_cents_per_kwh == 78


def test_unknown_band_code_is_rejected():
    with pytest.raises(BandNotFound):
        sprint1_tariff().band_for("verde")


def test_a_gap_in_coverage_is_rejected():
    with pytest.raises(TariffCoverageError, match="uncovered"):
        TariffSnapshot(
            name="com buraco",
            timezone=SPRINT1_TIMEZONE,
            bands=(
                TariffBand("dia", 100, (TariffWindow(0, 12 * 60),)),
                TariffBand("noite", 80, (TariffWindow(13 * 60, MINUTES_IN_DAY),)),
            ),
        )


def test_an_overlap_in_coverage_is_rejected():
    with pytest.raises(TariffCoverageError, match="overlaps"):
        TariffSnapshot(
            name="sobreposta",
            timezone=SPRINT1_TIMEZONE,
            bands=(
                TariffBand("dia", 100, (TariffWindow(0, 13 * 60),)),
                TariffBand("noite", 80, (TariffWindow(12 * 60, MINUTES_IN_DAY),)),
            ),
        )


def test_coverage_is_checked_per_weekday():
    """A band restricted to weekdays leaves the weekend uncovered."""
    with pytest.raises(TariffCoverageError, match="uncovered"):
        TariffSnapshot(
            name="só dias úteis",
            timezone=SPRINT1_TIMEZONE,
            bands=(
                TariffBand(
                    "útil",
                    100,
                    (TariffWindow(0, MINUTES_IN_DAY, frozenset({0, 1, 2, 3, 4})),),
                ),
            ),
        )


def test_a_tariff_without_bands_is_rejected():
    with pytest.raises(TariffCoverageError, match="no bands"):
        TariffSnapshot(name="vazia", timezone=SPRINT1_TIMEZONE, bands=())


def test_duplicate_band_codes_are_rejected():
    with pytest.raises(TariffCoverageError, match="duplicate"):
        TariffSnapshot(
            name="duplicada",
            timezone=SPRINT1_TIMEZONE,
            bands=(
                TariffBand("dia", 100, (TariffWindow(0, 12 * 60),)),
                TariffBand("dia", 80, (TariffWindow(12 * 60, MINUTES_IN_DAY),)),
            ),
        )


def test_a_negative_rate_is_rejected():
    with pytest.raises(InvalidRate):
        TariffBand("negativa", -1, (TariffWindow(0, MINUTES_IN_DAY),))


@pytest.mark.parametrize(
    ("start", "end"),
    [(-1, 60), (0, 0), (600, 600), (700, 600), (0, MINUTES_IN_DAY + 1)],
)
def test_a_window_that_does_not_advance_is_rejected(start, end):
    with pytest.raises(TariffCoverageError):
        TariffWindow(start, end)
