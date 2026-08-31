"""The analytical opinion the manager reads before approving a close.

This is where the AI earns its place in the product: it runs *before* the
invoice, over the period's own data, and a critical finding stops the close. It
never touches a monetary value — it decides whether the numbers are worth
billing, not what they are.

Two kinds of rule live here and they are deliberately not mixed up.

**Deterministic rules** state facts about a single session: an interval that does
not advance, energy that is not positive, an average power the equipment cannot
physically deliver, two sessions overlapping on one connector. They hold at any
sample size and their confidence is high, because they are arithmetic rather
than inference.

**Distribution rules** compare a session against the unit's own history. They
need a sample to mean anything, so below the minimum they return an explicit
`inconclusive` finding rather than a verdict. A small condominium in its first
month must be told "not enough history to judge", never given a fabricated
number that looks like knowledge.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from statistics import median
from uuid import UUID

ALGORITHM_VERSION = "closing-opinion/1.0.0"

# Below this many sessions for one unit, the distribution rule says so instead
# of pretending a median of two points describes a habit.
MIN_SAMPLE_FOR_DISTRIBUTION = 5

# A modified z-score built on the median absolute deviation. Robust to the very
# outliers it is looking for, unlike a mean and standard deviation.
MODIFIED_Z_THRESHOLD = Decimal("3.5")
MAD_SCALE = Decimal("0.6745")
MEAN_AD_SCALE = Decimal("0.7979")

# Metering tolerance over the nameplate rating before a session is called
# physically impossible.
POWER_TOLERANCE = Decimal("1.10")

# How far the charger's own total may drift from the sum of sessions before it
# stops being standby draw and starts being a missing session.
AGGREGATE_TOLERANCE_RATIO = Decimal("0.01")

INVALID_INTERVAL = "INVALID_INTERVAL"
NON_POSITIVE_ENERGY = "NON_POSITIVE_ENERGY"
POWER_EXCEEDS_RATED = "POWER_EXCEEDS_RATED"
DUPLICATE_SUSPECT = "DUPLICATE_SUSPECT"
ENERGY_OUTLIER = "ENERGY_OUTLIER"
AGGREGATE_MISMATCH = "AGGREGATE_MISMATCH"
AGGREGATE_RECONCILED = "AGGREGATE_RECONCILED"
UNASSIGNED_ENERGY = "UNASSIGNED_ENERGY"
DISTRIBUTION_INCONCLUSIVE = "DISTRIBUTION_INCONCLUSIVE"


class Severity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INCONCLUSIVE = "inconclusive"


class Conclusion(StrEnum):
    CLEAR = "clear"
    REVIEW_RECOMMENDED = "review_recommended"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class OpinionSession:
    id: UUID
    unit_id: UUID | None
    unit_label: str | None
    started_at: datetime
    ended_at: datetime
    energy_kwh: Decimal
    status: str

    @property
    def duration_hours(self) -> Decimal:
        seconds = Decimal((self.ended_at - self.started_at).total_seconds())
        return seconds / Decimal(3600)

    @property
    def average_power_kw(self) -> Decimal | None:
        hours = self.duration_hours
        return self.energy_kwh / hours if hours > 0 else None


@dataclass(frozen=True, slots=True)
class OpinionDataset:
    sessions: tuple[OpinionSession, ...]
    nominal_power_kw: Decimal
    aggregate_energy_kwh: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: Severity
    confidence: Confidence
    explanation: str
    evidence: dict[str, str] = field(default_factory=dict)
    charging_session_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ClosingOpinion:
    conclusion: Conclusion
    severity: Severity
    confidence: Confidence
    recommendation: str
    findings: tuple[Finding, ...]
    sample_size: int
    algorithm_version: str
    parameters: dict[str, str]
    dataset_checksum: str

    @property
    def blocking_findings(self) -> tuple[Finding, ...]:
        return tuple(
            item for item in self.findings if item.severity is Severity.CRITICAL
        )


def dataset_checksum(sessions: tuple[OpinionSession, ...]) -> str:
    """Pins the exact data an opinion was formed on, so it can be re-run."""
    payload = "|".join(
        f"{item.id}:{item.started_at.isoformat()}:{item.ended_at.isoformat()}:{item.energy_kwh}"
        for item in sorted(sessions, key=lambda item: str(item.id))
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _kwh(value: Decimal) -> str:
    return f"{value.normalize():f}"


def _detect_invalid_intervals(
    sessions: tuple[OpinionSession, ...],
) -> list[Finding]:
    findings = []
    for item in sessions:
        if item.ended_at <= item.started_at:
            findings.append(
                Finding(
                    code=INVALID_INTERVAL,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    explanation=(
                        "O término da recarga não é posterior ao início, então a "
                        "duração não pode ser calculada."
                    ),
                    evidence={
                        "inicio": item.started_at.isoformat(),
                        "fim": item.ended_at.isoformat(),
                    },
                    charging_session_id=item.id,
                )
            )
    return findings


def _detect_non_positive_energy(
    sessions: tuple[OpinionSession, ...],
) -> list[Finding]:
    return [
        Finding(
            code=NON_POSITIVE_ENERGY,
            severity=Severity.CRITICAL,
            confidence=Confidence.HIGH,
            explanation=(
                "A recarga não registrou energia positiva e não pode ser cobrada."
            ),
            evidence={"energia_kwh": _kwh(item.energy_kwh)},
            charging_session_id=item.id,
        )
        for item in sessions
        if item.energy_kwh <= 0
    ]


def _detect_power_above_rating(
    sessions: tuple[OpinionSession, ...],
    nominal_power_kw: Decimal,
) -> list[Finding]:
    ceiling = nominal_power_kw * POWER_TOLERANCE
    findings = []
    for item in sessions:
        power = item.average_power_kw
        if power is None or power <= ceiling:
            continue
        findings.append(
            Finding(
                code=POWER_EXCEEDS_RATED,
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                explanation=(
                    f"A potência média de {power:.2f} kW supera os "
                    f"{nominal_power_kw:.2f} kW nominais do carregador, o que é "
                    "fisicamente impossível neste equipamento. Provável erro de "
                    "medição ou de horário."
                ),
                evidence={
                    "potencia_media_kw": f"{power:.2f}",
                    "potencia_nominal_kw": f"{nominal_power_kw:.2f}",
                    "energia_kwh": _kwh(item.energy_kwh),
                    "duracao_h": f"{item.duration_hours:.2f}",
                },
                charging_session_id=item.id,
            )
        )
    return findings


def _detect_overlaps(sessions: tuple[OpinionSession, ...]) -> list[Finding]:
    """One connector cannot serve two cars at once."""
    ordered = sorted(sessions, key=lambda item: (item.started_at, str(item.id)))
    findings = []
    for index, current in enumerate(ordered):
        for candidate in ordered[index + 1 :]:
            if candidate.started_at >= current.ended_at:
                break
            findings.append(
                Finding(
                    code=DUPLICATE_SUSPECT,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.MEDIUM,
                    explanation=(
                        "Duas recargas se sobrepõem no mesmo carregador. Uma delas "
                        "é duplicidade ou falha de medição, e o fechamento não "
                        "deve adivinhar qual."
                    ),
                    evidence={
                        "recarga_anterior": str(current.id),
                        "inicio_anterior": current.started_at.isoformat(),
                        "fim_anterior": current.ended_at.isoformat(),
                        "inicio_sobreposta": candidate.started_at.isoformat(),
                    },
                    charging_session_id=candidate.id,
                )
            )
    return findings


def _detect_unassigned(sessions: tuple[OpinionSession, ...]) -> list[Finding]:
    orphans = [item for item in sessions if item.unit_id is None]
    if not orphans:
        return []
    energy = sum((item.energy_kwh for item in orphans), Decimal(0))
    return [
        Finding(
            code=UNASSIGNED_ENERGY,
            severity=Severity.CRITICAL,
            confidence=Confidence.HIGH,
            explanation=(
                f"{len(orphans)} recarga(s) somando {_kwh(energy)} kWh não têm "
                "unidade responsável e ficariam fora da cobrança."
            ),
            evidence={
                "recargas": str(len(orphans)),
                "energia_kwh": _kwh(energy),
            },
        )
    ]


def _dispersion(values: list[Decimal], centre: Decimal) -> tuple[Decimal, Decimal]:
    """Spread of the sample, and the scale factor that pairs with it.

    The median absolute deviation comes first because it is not dragged around by
    the outliers it is meant to find. But a unit that charges the same amount
    every time has a MAD of zero, and dividing by it would silence the rule
    exactly where a deviation is most obvious. When the MAD collapses we fall
    back to the mean absolute deviation with its own scale factor, as Iglewicz
    and Hoaglin describe. If both are zero every value is identical and there is
    nothing to flag.
    """
    deviations = [abs(value - centre) for value in values]
    mad = median(deviations)
    if mad > 0:
        return mad, MAD_SCALE
    mean_ad = sum(deviations, Decimal(0)) / Decimal(len(deviations))
    return mean_ad, MEAN_AD_SCALE


def _detect_energy_outliers(
    sessions: tuple[OpinionSession, ...],
) -> list[Finding]:
    """Compare each session against the habit of its own unit.

    Comparing against the building average would flag every large vehicle, so
    the distribution is built per unit. Below the minimum sample the rule says
    so instead of guessing.
    """
    by_unit: dict[UUID, list[OpinionSession]] = {}
    for item in sessions:
        if item.unit_id is not None:
            by_unit.setdefault(item.unit_id, []).append(item)

    findings: list[Finding] = []
    small_samples: list[str] = []

    for unit_id, unit_sessions in sorted(
        by_unit.items(), key=lambda pair: str(pair[0])
    ):
        label = unit_sessions[0].unit_label or str(unit_id)
        if len(unit_sessions) < MIN_SAMPLE_FOR_DISTRIBUTION:
            small_samples.append(f"{label} ({len(unit_sessions)})")
            continue
        values = [item.energy_kwh for item in unit_sessions]
        centre = Decimal(str(median(values)))
        deviation, scale = _dispersion(values, centre)
        if deviation == 0:
            continue
        for item in unit_sessions:
            score = scale * abs(item.energy_kwh - centre) / deviation
            if score <= MODIFIED_Z_THRESHOLD:
                continue
            findings.append(
                Finding(
                    code=ENERGY_OUTLIER,
                    severity=Severity.WARNING,
                    confidence=Confidence.MEDIUM,
                    explanation=(
                        f"A energia de {_kwh(item.energy_kwh)} kWh destoa do padrão "
                        f"da unidade {label}, cuja mediana é {_kwh(centre)} kWh. "
                        "Vale conferir antes de cobrar."
                    ),
                    evidence={
                        "energia_kwh": _kwh(item.energy_kwh),
                        "mediana_da_unidade_kwh": _kwh(centre),
                        "desvio_absoluto": _kwh(deviation),
                        "escore_modificado": f"{score:.2f}",
                        "amostra": str(len(unit_sessions)),
                    },
                    charging_session_id=item.id,
                )
            )

    if small_samples:
        findings.append(
            Finding(
                code=DISTRIBUTION_INCONCLUSIVE,
                severity=Severity.INFO,
                confidence=Confidence.INCONCLUSIVE,
                explanation=(
                    "Não há histórico suficiente para avaliar o padrão de consumo "
                    f"de {len(small_samples)} unidade(s). São necessárias ao menos "
                    f"{MIN_SAMPLE_FOR_DISTRIBUTION} recargas por unidade."
                ),
                evidence={"unidades": ", ".join(small_samples)},
            )
        )
    return findings


def _reconcile_aggregate(
    sessions: tuple[OpinionSession, ...],
    aggregate_energy_kwh: Decimal | None,
) -> list[Finding]:
    if aggregate_energy_kwh is None:
        return []
    measured = sum((item.energy_kwh for item in sessions), Decimal(0))
    difference = aggregate_energy_kwh - measured
    tolerance = measured * AGGREGATE_TOLERANCE_RATIO
    evidence = {
        "energia_das_recargas_kwh": _kwh(measured),
        "agregado_do_carregador_kwh": _kwh(aggregate_energy_kwh),
        "diferenca_kwh": _kwh(difference),
        "tolerancia_kwh": _kwh(tolerance),
    }
    if abs(difference) > tolerance:
        return [
            Finding(
                code=AGGREGATE_MISMATCH,
                severity=Severity.WARNING,
                confidence=Confidence.HIGH,
                explanation=(
                    f"O carregador reporta {_kwh(aggregate_energy_kwh)} kWh no "
                    f"período, contra {_kwh(measured)} kWh nas recargas "
                    f"importadas. A diferença de {_kwh(difference)} kWh passa da "
                    "tolerância e pode indicar recarga faltando na importação."
                ),
                evidence=evidence,
            )
        ]
    return [
        Finding(
            code=AGGREGATE_RECONCILED,
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            explanation=(
                f"As recargas importadas somam {_kwh(measured)} kWh e o próprio "
                f"carregador reporta {_kwh(aggregate_energy_kwh)} kWh. A diferença "
                f"de {_kwh(difference)} kWh está dentro da tolerância e é "
                "compatível com consumo de standby."
            ),
            evidence=evidence,
        )
    ]


def _recommend(conclusion: Conclusion, findings: tuple[Finding, ...]) -> str:
    if conclusion is Conclusion.BLOCKED:
        codes = sorted(
            {item.code for item in findings if item.severity is Severity.CRITICAL}
        )
        return (
            "Resolva os achados críticos antes de fechar o período: "
            f"{', '.join(codes)}. Cada um exige decisão registrada."
        )
    if conclusion is Conclusion.REVIEW_RECOMMENDED:
        return (
            "Nenhum impedimento crítico. Confira os alertas antes de aprovar; o "
            "fechamento pode seguir com a sua decisão registrada."
        )
    return "Nada a corrigir. O período pode ser fechado."


def analyze_period(dataset: OpinionDataset) -> ClosingOpinion:
    sessions = tuple(item for item in dataset.sessions if item.status != "discarded")

    findings = (
        *_detect_invalid_intervals(sessions),
        *_detect_non_positive_energy(sessions),
        *_detect_power_above_rating(sessions, dataset.nominal_power_kw),
        *_detect_overlaps(sessions),
        *_detect_unassigned(sessions),
        *_detect_energy_outliers(sessions),
        *_reconcile_aggregate(sessions, dataset.aggregate_energy_kwh),
    )

    severities = {item.severity for item in findings}
    if Severity.CRITICAL in severities:
        conclusion, severity = Conclusion.BLOCKED, Severity.CRITICAL
    elif Severity.WARNING in severities:
        conclusion, severity = Conclusion.REVIEW_RECOMMENDED, Severity.WARNING
    else:
        conclusion, severity = Conclusion.CLEAR, Severity.INFO

    inconclusive = any(item.confidence is Confidence.INCONCLUSIVE for item in findings)
    confidence = Confidence.MEDIUM if inconclusive else Confidence.HIGH

    return ClosingOpinion(
        conclusion=conclusion,
        severity=severity,
        confidence=confidence,
        recommendation=_recommend(conclusion, findings),
        findings=findings,
        sample_size=len(sessions),
        algorithm_version=ALGORITHM_VERSION,
        parameters={
            "min_sample_for_distribution": str(MIN_SAMPLE_FOR_DISTRIBUTION),
            "modified_z_threshold": str(MODIFIED_Z_THRESHOLD),
            "power_tolerance": str(POWER_TOLERANCE),
            "aggregate_tolerance_ratio": str(AGGREGATE_TOLERANCE_RATIO),
        },
        dataset_checksum=dataset_checksum(sessions),
    )


@dataclass(frozen=True, slots=True)
class PersistedFinding:
    """A finding as stored, addressable and with its decision, if any.

    The domain `Finding` is what a rule concluded; this is that conclusion once
    it has an identity a manager can act on and an audit trail attached.
    """

    id: UUID
    code: str
    severity: str
    confidence: str
    explanation: str
    evidence: dict[str, str]
    charging_session_id: UUID | None
    resolved_at: datetime | None
    resolved_by_name: str | None
    resolution_note: str | None
