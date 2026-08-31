"""Each rule must fire on its own case and stay quiet otherwise.

A detector that fires on everything is as useless as one that never fires, so
every rule here is tested against both a case it should catch and a case it
should let through.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.billing.domain.opinion import (
    AGGREGATE_MISMATCH,
    AGGREGATE_RECONCILED,
    DISTRIBUTION_INCONCLUSIVE,
    DUPLICATE_SUSPECT,
    ENERGY_OUTLIER,
    INVALID_INTERVAL,
    NON_POSITIVE_ENERGY,
    POWER_EXCEEDS_RATED,
    UNASSIGNED_ENERGY,
    Conclusion,
    Confidence,
    OpinionDataset,
    OpinionSession,
    Severity,
    analyze_period,
)

UNIT_A = UUID("40000000-0000-0000-0000-000000000001")
UNIT_B = UUID("40000000-0000-0000-0000-000000000002")
NOMINAL = Decimal("11.000")
BASE = datetime(2026, 5, 4, 22, 0, tzinfo=UTC)


def charge(
    energy: str,
    *,
    hours: float = 3,
    day: int = 4,
    hour: int = 22,
    unit_id: UUID | None = UNIT_A,
    unit_label: str | None = "A-101",
    status: str = "ready",
) -> OpinionSession:
    started = datetime(2026, 5, day, hour, 0, tzinfo=UTC)
    return OpinionSession(
        id=uuid4(),
        unit_id=unit_id,
        unit_label=unit_label,
        started_at=started,
        ended_at=started + timedelta(hours=hours),
        energy_kwh=Decimal(energy),
        status=status,
    )


def analyze(sessions, aggregate=None, nominal=NOMINAL):
    return analyze_period(
        OpinionDataset(
            sessions=tuple(sessions),
            nominal_power_kw=nominal,
            aggregate_energy_kwh=aggregate,
        )
    )


def codes(opinion):
    return [finding.code for finding in opinion.findings]


def routine(count: int = 6, unit_id: UUID = UNIT_A) -> list[OpinionSession]:
    """A believable month for one unit: enough sample, no outliers."""
    return [
        charge("20", day=day, unit_id=unit_id, unit_label="A-101")
        for day in range(1, count + 1)
    ]


def test_a_clean_period_is_clear():
    opinion = analyze(routine())
    assert opinion.conclusion is Conclusion.CLEAR
    assert opinion.severity is Severity.INFO
    assert opinion.findings == ()
    assert "pode ser fechado" in opinion.recommendation


def test_an_interval_that_does_not_advance_blocks():
    broken = charge("10", hours=0)
    opinion = analyze([*routine(), broken])
    assert INVALID_INTERVAL in codes(opinion)
    assert opinion.conclusion is Conclusion.BLOCKED


def test_non_positive_energy_blocks():
    opinion = analyze([*routine(), charge("0")])
    assert NON_POSITIVE_ENERGY in codes(opinion)
    assert opinion.conclusion is Conclusion.BLOCKED


def test_power_above_the_nameplate_blocks_and_shows_the_arithmetic():
    """9,4 kWh in half an hour is 18,8 kW on an 11 kW charger."""
    opinion = analyze([*routine(), charge("9.4", hours=0.5, day=14)])
    finding = next(f for f in opinion.findings if f.code == POWER_EXCEEDS_RATED)
    assert finding.severity is Severity.CRITICAL
    assert finding.evidence["potencia_media_kw"] == "18.80"
    assert finding.evidence["potencia_nominal_kw"] == "11.00"
    assert opinion.conclusion is Conclusion.BLOCKED


def test_power_within_tolerance_does_not_fire():
    """A 10% metering margin keeps ordinary sessions quiet."""
    opinion = analyze([*routine(), charge("11.5", hours=1, day=15)])
    assert POWER_EXCEEDS_RATED not in codes(opinion)


def test_overlapping_sessions_on_one_connector_block():
    first = charge("21", hours=3, day=21, hour=22)
    second = charge("20.6", hours=3, day=21, hour=23)
    opinion = analyze([*routine(), first, second])
    finding = next(f for f in opinion.findings if f.code == DUPLICATE_SUSPECT)
    assert finding.severity is Severity.CRITICAL
    assert finding.confidence is Confidence.MEDIUM
    assert opinion.conclusion is Conclusion.BLOCKED


def test_back_to_back_sessions_do_not_overlap():
    first = charge("10", hours=2, day=21, hour=20)
    second = charge("10", hours=2, day=21, hour=22)
    opinion = analyze([*routine(), first, second])
    assert DUPLICATE_SUSPECT not in codes(opinion)


def test_unassigned_energy_blocks_and_totals_the_kwh():
    opinion = analyze([*routine(), charge("18", unit_id=None, unit_label=None)])
    finding = next(f for f in opinion.findings if f.code == UNASSIGNED_ENERGY)
    assert finding.evidence["energia_kwh"] == "18"
    assert finding.evidence["recargas"] == "1"
    assert opinion.conclusion is Conclusion.BLOCKED


def test_an_energy_outlier_warns_without_blocking():
    """A believable history with ordinary variation, then one session apart."""
    sessions = [
        *[
            charge(energy, day=day, hours=4)
            for day, energy in enumerate(["18", "19", "20", "21", "22", "20", "19"], 1)
        ],
        charge("95", day=9, hours=12),
    ]
    opinion = analyze(sessions)
    finding = next(f for f in opinion.findings if f.code == ENERGY_OUTLIER)
    assert finding.severity is Severity.WARNING
    assert finding.evidence["mediana_da_unidade_kwh"] == "20"
    assert opinion.conclusion is Conclusion.REVIEW_RECOMMENDED


def test_an_outlier_is_still_caught_when_the_history_is_perfectly_uniform():
    """A zero median deviation must not silence the rule."""
    sessions = [
        *[charge("20", day=day, hours=4) for day in range(1, 8)],
        charge("95", day=9, hours=12),
    ]
    opinion = analyze(sessions)
    assert ENERGY_OUTLIER in codes(opinion)


def test_an_identical_history_flags_nothing():
    opinion = analyze([charge("20", day=day, hours=4) for day in range(1, 8)])
    assert ENERGY_OUTLIER not in codes(opinion)
    assert opinion.conclusion is Conclusion.CLEAR


def test_a_unit_below_the_minimum_sample_is_declared_inconclusive():
    """Never a fabricated verdict on two data points."""
    opinion = analyze(
        [
            *routine(),
            *[charge("50", day=d, unit_id=UNIT_B, unit_label="A-102") for d in (1, 2)],
        ]
    )
    finding = next(f for f in opinion.findings if f.code == DISTRIBUTION_INCONCLUSIVE)
    assert finding.confidence is Confidence.INCONCLUSIVE
    assert finding.severity is Severity.INFO
    assert "A-102 (2)" in finding.evidence["unidades"]
    assert ENERGY_OUTLIER not in codes(opinion)


def test_an_inconclusive_rule_lowers_the_opinion_confidence():
    opinion = analyze([charge("20", day=1), charge("20", day=2)])
    assert opinion.confidence is Confidence.MEDIUM


def test_a_full_sample_keeps_confidence_high():
    assert analyze(routine()).confidence is Confidence.HIGH


def test_the_aggregate_reconciles_within_tolerance():
    opinion = analyze(routine(), aggregate=Decimal("120.5"))
    finding = next(f for f in opinion.findings if f.code == AGGREGATE_RECONCILED)
    assert finding.severity is Severity.INFO
    assert finding.evidence["diferenca_kwh"] == "0.5"
    assert opinion.conclusion is Conclusion.CLEAR


def test_an_aggregate_beyond_tolerance_warns():
    opinion = analyze(routine(), aggregate=Decimal(150))
    finding = next(f for f in opinion.findings if f.code == AGGREGATE_MISMATCH)
    assert finding.severity is Severity.WARNING
    assert finding.evidence["diferenca_kwh"] == "30"
    assert opinion.conclusion is Conclusion.REVIEW_RECOMMENDED


def test_without_an_aggregate_there_is_no_external_finding():
    opinion = analyze(routine())
    assert AGGREGATE_RECONCILED not in codes(opinion)
    assert AGGREGATE_MISMATCH not in codes(opinion)


def test_discarded_sessions_are_ignored_entirely():
    opinion = analyze([*routine(), charge("0", status="discarded")])
    assert opinion.conclusion is Conclusion.CLEAR
    assert opinion.sample_size == 6


def test_the_opinion_records_what_it_ran_on():
    """Reproducibility: version, parameters and a checksum of the data."""
    opinion = analyze(routine())
    assert opinion.algorithm_version == "closing-opinion/1.0.0"
    assert opinion.parameters["min_sample_for_distribution"] == "5"
    assert len(opinion.dataset_checksum) == 64


def test_the_checksum_does_not_depend_on_session_order():
    sessions = routine()
    assert (
        analyze(sessions).dataset_checksum
        == analyze(list(reversed(sessions))).dataset_checksum
    )


def test_the_checksum_changes_when_the_data_changes():
    sessions = routine()
    altered = [*sessions[:-1], charge("21", day=6)]
    assert analyze(sessions).dataset_checksum != analyze(altered).dataset_checksum


def test_blocking_findings_are_exposed_separately():
    """Only critical findings hold the close; warnings and info do not."""
    opinion = analyze([*routine(), charge("0", day=20)], aggregate=Decimal(500))
    assert {f.code for f in opinion.blocking_findings} == {NON_POSITIVE_ENERGY}
    assert AGGREGATE_MISMATCH in codes(opinion)
    assert AGGREGATE_MISMATCH not in {f.code for f in opinion.blocking_findings}


@pytest.mark.parametrize(
    "code", [INVALID_INTERVAL, NON_POSITIVE_ENERGY, UNASSIGNED_ENERGY]
)
def test_every_deterministic_rule_speaks_with_high_confidence(code):
    """Arithmetic, not inference: these hold at any sample size."""
    opinion = analyze(
        [charge("0"), charge("10", hours=0), charge("5", unit_id=None, unit_label=None)]
    )
    finding = next(f for f in opinion.findings if f.code == code)
    assert finding.confidence is Confidence.HIGH


def test_every_finding_carries_an_explanation_and_evidence():
    opinion = analyze(
        [*routine(), charge("0"), charge("9.4", hours=0.5, day=14)],
        aggregate=Decimal(300),
    )
    assert opinion.findings
    for finding in opinion.findings:
        assert finding.explanation.strip()
        assert finding.evidence
