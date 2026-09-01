"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  downloadInvoiceDocument,
  getInvoice,
  type InvoiceDetailResponse,
  type InvoiceItemResponse,
} from "@ev-chargeops/api-client";

import { useResidentContext } from "@/lib/billing/resident-context";
import { PageBreadcrumb } from "@/components/shell/page-breadcrumb";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api";

/** Money is printed from the stored integer cents, never from a float.
 *
 * The API sends the same integers the invoice was issued with and the PDF is
 * drawn from; formatting them here is the only transformation allowed, so the
 * screen and the document cannot disagree.
 */
function formatCents(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const reais = Math.trunc(Math.abs(cents) / 100);
  const rest = Math.abs(cents) % 100;
  const grouped = reais.toLocaleString("pt-BR");
  return `${sign}R$ ${grouped},${String(rest).padStart(2, "0")}`;
}

function formatKwh(value: string): string {
  return `${Number(value).toLocaleString("pt-BR", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  })} kWh`;
}

function formatRate(centsPerKwh: number): string {
  return `${formatCents(centsPerKwh)}/kWh`;
}

function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-");
  return `${day}/${month}/${year}`;
}

function dateTimeParts(iso: string, timeZone: string) {
  const value = new Date(iso);
  return {
    date: value.toLocaleDateString("pt-BR", { timeZone }),
    time: value.toLocaleTimeString("pt-BR", {
      timeZone,
      hour: "2-digit",
      minute: "2-digit",
    }),
  };
}

function duration(item: InvoiceItemResponse): string {
  const minutes = Math.floor(
    (Date.parse(item.endedAt) - Date.parse(item.startedAt)) / 60000,
  );
  const hours = Math.floor(minutes / 60);
  return `${hours}h${String(minutes % 60).padStart(2, "0")}`;
}

type InvoiceState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; detail: InvoiceDetailResponse };

const LOADING: InvoiceState = { status: "loading" };

export function InvoiceView({
  invoiceId,
  accessToken,
  origin = "invoices",
}: {
  invoiceId: string;
  accessToken: string;
  /** Which list opened this invoice, so the way back leads there. */
  origin?: "invoices" | "closing";
}) {
  const { context: residentContext, enter } = useResidentContext();
  // The result is tagged with the request it answers, so switching invoice or
  // entering a resident context shows loading again without the effect having
  // to write state on its way in.
  const requestKey = `${invoiceId}:${residentContext?.id ?? ""}`;
  const [resolved, setResolved] = useState<{
    key: string;
    state: InvoiceState;
  } | null>(null);
  const [downloading, setDownloading] = useState(false);
  const state = resolved?.key === requestKey ? resolved.state : LOADING;

  useEffect(() => {
    let ignore = false;

    void getInvoice(invoiceId, accessToken, {
      baseUrl: apiUrl,
      residentContextId: residentContext?.id ?? null,
    })
      .then((detail) => {
        if (!ignore) {
          setResolved({ key: requestKey, state: { status: "ready", detail } });
        }
      })
      .catch((error: unknown) => {
        if (ignore) return;
        const message =
          error instanceof ApiError && error.status === 404
            ? "Fatura não encontrada nesta organização."
            : "Não foi possível carregar a fatura.";
        setResolved({ key: requestKey, state: { status: "error", message } });
      });

    return () => {
      ignore = true;
    };
  }, [invoiceId, accessToken, residentContext?.id, requestKey]);

  const download = useCallback(async () => {
    setDownloading(true);
    try {
      const blob = await downloadInvoiceDocument(invoiceId, accessToken, {
        baseUrl: apiUrl,
        residentContextId: residentContext?.id ?? null,
      });
      const href = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download =
        state.status === "ready"
          ? `${state.detail.invoice.number}.pdf`
          : "fatura.pdf";
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      // Revoking in the same tick can cancel the download the click just
      // started, so the URL is released once the browser has taken it.
      window.setTimeout(() => URL.revokeObjectURL(href), 0);
    } finally {
      setDownloading(false);
    }
  }, [invoiceId, accessToken, residentContext?.id, state]);

  if (state.status === "loading") {
    return <p className="invoice-status">Carregando fatura…</p>;
  }
  if (state.status === "error") {
    return <p className="invoice-status error">{state.message}</p>;
  }

  const { invoice, context, bands } = state.detail;
  const sum =
    invoice.energyValueCents + invoice.infraFeeCents + invoice.lossShareCents;
  const zone = context.timezone;
  const issued = dateTimeParts(invoice.issuedAt, zone);
  const appliedBands = new Set(invoice.items.map((item) => item.bandCode));
  // Only bands that would actually have cost less are worth showing; the rest
  // would be noise dressed as advice.
  const cheaper = bands
    .filter((band) => band.energyValueCents < invoice.energyValueCents)
    .sort((left, right) => left.energyValueCents - right.energyValueCents);

  return (
    <div className="invoice-page">
      <header className="dashboard-heading invoice-heading">
        <div>
          <PageBreadcrumb
            section={origin === "closing" ? "Fechamento" : "Faturas"}
            current={`Fatura ${invoice.number}`}
          />
          <h1>
            Unidade {invoice.unitCode} · {invoice.periodValue}
          </h1>
          <p>
            {invoice.unitName} · responsável {invoice.contactLabel} · emitida em{" "}
            {issued.date}
          </p>
          <Link
            href={origin === "closing" ? "/closing" : "/invoices"}
            className="session-back-link"
          >
            <span aria-hidden="true">←</span>
            {origin === "closing"
              ? "Voltar para Fechamento"
              : "Voltar para Faturas"}
          </Link>
        </div>
        <div className="invoice-heading-actions">
          {residentContext === null ? (
            // The resident's view is this same page, scoped. Offering it here
            // means the manager never has to go looking for a second screen.
            <button
              type="button"
              className="invoice-secondary-action"
              onClick={() => void enter(invoice.unitId)}
            >
              Ver como o morador
            </button>
          ) : null}
          <button
            type="button"
            className="primary-dashboard-action compact"
            onClick={() => void download()}
            disabled={downloading}
          >
            {downloading ? "Gerando PDF…" : "Baixar PDF"}
          </button>
        </div>
      </header>

      <section className="invoice-block" aria-labelledby="invoice-total-title">
        <div className="dashboard-section-heading">
          <h2 id="invoice-total-title">Quanto e por quê</h2>
          <span>Fatura {invoice.number}</span>
        </div>
        <p className="invoice-total">{formatCents(invoice.totalCents)}</p>
        <dl className="invoice-breakdown">
          <div>
            <dt>Energia consumida</dt>
            <dd>{formatCents(invoice.energyValueCents)}</dd>
          </div>
          <div>
            <dt>Taxa de infraestrutura</dt>
            <dd>{formatCents(invoice.infraFeeCents)}</dd>
          </div>
          <div>
            <dt>Perdas técnicas</dt>
            <dd>{formatCents(invoice.lossShareCents)}</dd>
          </div>
        </dl>
        <p className="invoice-sum-check">
          {formatCents(invoice.energyValueCents)} +{" "}
          {formatCents(invoice.infraFeeCents)} +{" "}
          {formatCents(invoice.lossShareCents)} = {formatCents(sum)}
        </p>
      </section>

      <section className="invoice-block" aria-labelledby="invoice-sessions-title">
        <div className="dashboard-section-heading">
          <h2 id="invoice-sessions-title">De onde veio</h2>
          <span>
            {invoice.items.length}{" "}
            {invoice.items.length === 1 ? "recarga" : "recargas"} ·{" "}
            {formatKwh(invoice.energyKwh)}
          </span>
        </div>
        {invoice.items.length === 0 ? (
          <p className="invoice-empty">
            Sem recargas no período. Sem consumo, nada é cobrado.
          </p>
        ) : (
          <div className="responsible-table-frame">
            <table aria-label="Recargas da fatura">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Início</th>
                  <th>Fim</th>
                  <th>Duração</th>
                  <th>Energia</th>
                  <th>Faixa</th>
                  <th>Tarifa</th>
                  <th>Valor</th>
                </tr>
              </thead>
              <tbody>
                {invoice.items.map((item) => {
                  const start = dateTimeParts(item.startedAt, zone);
                  const end = dateTimeParts(item.endedAt, zone);
                  return (
                    <tr key={item.id}>
                      <td>{start.date}</td>
                      <td>{start.time}</td>
                      <td>{end.time}</td>
                      <td>{duration(item)}</td>
                      <td>{formatKwh(item.energyKwh)}</td>
                      <td>{item.bandCode}</td>
                      <td>{formatRate(item.rateCentsPerKwh)}</td>
                      <td>{formatCents(item.valueCents)}</td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={7}>Soma das recargas</td>
                  <td>{formatCents(invoice.energyValueCents)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
        <p className="invoice-note">
          Cada linha é arredondada uma única vez, no fecho da própria recarga. O
          subtotal de energia é a soma exata das linhas acima.
        </p>
      </section>

      <section className="invoice-block" aria-labelledby="invoice-tariff-title">
        <div className="dashboard-section-heading">
          <h2 id="invoice-tariff-title">Por que esta tarifa</h2>
          <span>{context.provenanceLabel}</span>
        </div>
        <dl className="invoice-tariff">
          <div>
            <dt>Tarifa</dt>
            <dd>{context.tariffName}</dd>
          </div>
          <div>
            <dt>Fonte</dt>
            <dd>{context.tariffSource}</dd>
          </div>
          <div>
            <dt>Vigência</dt>
            <dd>
              {formatDate(context.tariffValidFrom)} a{" "}
              {context.tariffValidTo
                ? formatDate(context.tariffValidTo)
                : "em vigor"}
            </dd>
          </div>
          <div>
            <dt>Política de rateio</dt>
            <dd>{context.policyName}</dd>
          </div>
          <div>
            <dt>Taxa de infraestrutura</dt>
            <dd>{formatCents(context.infraFeeCents)} por unidade ativa</dd>
          </div>
          <div>
            <dt>Perdas técnicas</dt>
            <dd>
              {(context.lossBasisPoints / 100).toLocaleString("pt-BR", {
                minimumFractionDigits: 2,
              })}
              % da energia
            </dd>
          </div>
        </dl>
        <ul className="tariff-bands">
          {bands.map((band) => (
            <li
              key={band.code}
              className={appliedBands.has(band.code) ? "applied" : undefined}
            >
              <strong>{band.code}</strong>
              <span>{formatRate(band.rateCentsPerKwh)}</span>
              {appliedBands.has(band.code) ? (
                <em>aplicada nesta fatura</em>
              ) : null}
            </li>
          ))}
        </ul>
        {context.tariffSourceReference ? (
          <p className="invoice-note">
            Referência da tarifa: {context.tariffSourceReference}
          </p>
        ) : null}
        <p className="invoice-note">
          A faixa de cada recarga é a do seu horário de início. A energia de uma
          recarga não é dividida entre faixas: a medição dá um total por
          recarga, não uma curva.
        </p>
      </section>

      {invoice.items.length > 0 ? (
        <section className="invoice-block" aria-labelledby="invoice-advice-title">
          <div className="dashboard-section-heading">
            <h2 id="invoice-advice-title">O que fazer com isso</h2>
            <span>Comparação com as faixas da mesma tarifa</span>
          </div>
          {cheaper.length === 0 ? (
            <p className="invoice-empty">
              Esta energia já foi cobrada na faixa mais barata da tarifa
              vigente. Não há economia possível apenas mudando de horário.
            </p>
          ) : (
            <>
              <ul className="band-comparison">
                {cheaper.map((band) => (
                  <li key={band.code}>
                    <strong>{band.code}</strong>
                    <span>{formatRate(band.rateCentsPerKwh)}</span>
                    <span>{formatCents(band.energyValueCents)}</span>
                    <em>
                      {formatCents(
                        invoice.energyValueCents - band.energyValueCents,
                      )}{" "}
                      a menos
                    </em>
                  </li>
                ))}
              </ul>
              <p className="invoice-note">
                Quanto esta mesma energia teria custado se toda ela tivesse sido
                consumida na faixa indicada, calculado com a própria tarifa
                desta fatura e com o mesmo arredondamento por recarga. Não é uma
                promessa de economia: depende de quando o carro é carregado.
              </p>
            </>
          )}
        </section>
      ) : null}
    </div>
  );
}
