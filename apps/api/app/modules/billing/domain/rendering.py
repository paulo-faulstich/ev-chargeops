"""What the invoice document says, independent of how it is drawn.

The renderer receives the persisted invoice and this context, and must not
touch the database or recompute any figure: the stored integers are the only
source. `invoice_document_lines` is the pure, testable statement of the
document's content; the PDF is a typeset view of exactly these lines.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

from .invoice import InvoiceView


@dataclass(frozen=True, slots=True)
class InvoiceDocumentContext:
    organization_name: str
    site_name: str
    timezone: str
    tariff_name: str
    tariff_source: str
    tariff_source_reference: str | None
    tariff_valid_from: date
    tariff_valid_to: date | None
    policy_name: str
    infra_fee_cents: int
    loss_basis_points: int
    provenances: tuple[str, ...]


class InvoiceRenderer(Protocol):
    def render(
        self, invoice: InvoiceView, context: InvoiceDocumentContext
    ) -> bytes: ...


def format_brl(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    reais, rest = divmod(abs(cents), 100)
    grouped = f"{reais:,}".replace(",", ".")
    return f"{sign}R$ {grouped},{rest:02d}"


def format_kwh(value: Decimal) -> str:
    return f"{value:.3f}".replace(".", ",") + " kWh"


def format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _local(value: datetime, timezone: str) -> datetime:
    return value.astimezone(ZoneInfo(timezone))


def _percent(basis_points: int) -> str:
    return f"{basis_points / 100:.2f}%".replace(".", ",")


def _duration(start: datetime, end: datetime) -> str:
    minutes = int((end - start).total_seconds() // 60)
    hours, rest = divmod(minutes, 60)
    return f"{hours}h{rest:02d}"


PROVENANCE_LABELS = {
    "real": "dados reais",
    "simulated": "dados simulados",
}


def provenance_label(provenances: tuple[str, ...]) -> str:
    if not provenances:
        return "sem recargas no período"
    labels = [
        PROVENANCE_LABELS.get(provenance, provenance)
        for provenance in sorted(set(provenances))
    ]
    return ", ".join(labels)


def invoice_document_lines(
    invoice: InvoiceView, context: InvoiceDocumentContext
) -> tuple[str, ...]:
    """Every statement the document makes, in reading order.

    The four blocks mirror the invoice page of the design (section 9), minus
    the advice block, which is derived guidance for the screen rather than a
    fact of the bill.
    """
    timezone = context.timezone
    lines: list[str] = [
        f"Fatura {invoice.number}",
        f"{context.organization_name} - {context.site_name}",
        f"Unidade {invoice.unit_code} ({invoice.unit_name})",
        f"Responsável: {invoice.contact_label}",
        f"Período: {invoice.period_value}",
        f"Emitida em {format_date(_local(invoice.issued_at, timezone).date())}",
        "",
        "Quanto e por quê",
        f"Energia: {format_brl(invoice.energy_value_cents)}",
        f"Taxa de infraestrutura: {format_brl(invoice.infra_fee_cents)}",
        f"Perdas técnicas: {format_brl(invoice.loss_share_cents)}",
        f"Total: {format_brl(invoice.total_cents)}",
        "",
        "De onde veio",
    ]
    if invoice.items:
        lines.append(
            f"{len(invoice.items)} recarga(s), {format_kwh(invoice.energy_kwh)}"
        )
        for item in invoice.items:
            start = _local(item.started_at, timezone)
            end = _local(item.ended_at, timezone)
            lines.append(
                f"{start.strftime('%d/%m/%Y %H:%M')} a {end.strftime('%H:%M')}"
                f" ({_duration(item.started_at, item.ended_at)}), "
                f"{format_kwh(item.energy_kwh)}, {item.band_code}, "
                f"{item.rate_cents_per_kwh} centavos/kWh: "
                f"{format_brl(item.value_cents)}"
            )
    else:
        lines.append("Sem recargas no período. Sem consumo, nada é cobrado.")
    validity_end = (
        format_date(context.tariff_valid_to)
        if context.tariff_valid_to is not None
        else "em vigor"
    )
    lines.extend(
        [
            "",
            "Por que esta tarifa",
            f"Tarifa: {context.tariff_name} (fonte: {context.tariff_source})",
            f"Vigência: {format_date(context.tariff_valid_from)} a {validity_end}",
            (
                f"Política de rateio: {context.policy_name} "
                f"(taxa {format_brl(context.infra_fee_cents)} por unidade "
                f"ativa, perdas {_percent(context.loss_basis_points)})"
            ),
            "",
            f"Procedência: {provenance_label(context.provenances)}",
            (
                "Documento gerado a partir dos valores persistidos da fatura; "
                "nenhum valor é recalculado."
            ),
        ]
    )
    if context.tariff_source_reference:
        lines.append(f"Referência da tarifa: {context.tariff_source_reference}")
    return tuple(lines)
