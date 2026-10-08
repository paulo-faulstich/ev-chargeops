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
  const cheapest = cheaper[0];

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
        {/* The comparison is worked out further down, but a reader who never
            scrolls that far is exactly the one it was written for. */}
        {cheapest !== undefined ? (
          <p className="invoice-advice-lead">
            Carregando sempre <strong>{cheapest.hours}</strong> — o horário que
            a conta de luz chama de{" "}
            {cheapest.label.toLocaleLowerCase("pt-BR")} — esta energia custaria{" "}
            <strong>
              {formatCents(invoice.energyValueCents - cheapest.energyValueCents)}
            </strong>{" "}
            a menos.{" "}
            <a href="#invoice-advice-title">Ver a comparação</a>
          </p>
        ) : null}
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
                  <th>Faixa de horário</th>
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
                      <td>{item.bandLabel}</td>
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
            <dt>Quem definiu</dt>
            <dd>{context.tariffSourceLabel}</dd>
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
            <dt>Regra de divisão</dt>
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
              <strong>{band.label}</strong>
              <span className="tariff-band-hours">{band.hours}</span>
              <span>{formatRate(band.rateCentsPerKwh)}</span>
              {appliedBands.has(band.code) ? (
                <em>usada nesta fatura</em>
              ) : null}
            </li>
          ))}
        </ul>
        {/* The tariff has to explain itself here, on the invoice. Sending the
            reader somewhere else to find out how they were charged is the same
            as not telling them. */}
        <div className="tariff-explainer">
          <h3>Como a conta é montada</h3>
          <ol>
            <li>
              <strong>A energia.</strong> A energia da recarga é multiplicada
              pelo preço do horário em que ela começou. Os três horários acima
              são os mesmos que a distribuidora usa na conta de luz do
              condomínio — ponta é o fim da tarde, quando a rede está mais
              carregada e a energia custa mais. Uma recarga que começa às 22h
              paga o preço da madrugada inteira, mesmo que termine de manhã: o
              medidor informa o total da recarga, não minuto a minuto.
            </li>
            <li>
              <strong>A taxa de infraestrutura.</strong>{" "}
              {formatCents(context.infraFeeCents)} por mês, cobrados só de quem
              usou o carregador no período. É a parte fixa: manutenção,
              disponibilidade e o próprio equipamento.
            </li>
            <li>
              <strong>As perdas técnicas.</strong> Entre o relógio do
              condomínio e o carro, parte da energia se perde no caminho — cabo,
              conversão, calor. O condomínio paga por ela, então ela é dividida
              na proporção do que cada um consumiu:{" "}
              {(context.lossBasisPoints / 100).toLocaleString("pt-BR", {
                minimumFractionDigits: 2,
              })}
              % da energia de cada fatura.
            </li>
          </ol>
          <p>
            Os preços por horário valem desde{" "}
            {formatDate(context.tariffValidFrom)} e ficam congelados dentro de
            cada fatura: uma tarifa nova só vale para os meses seguintes, nunca
            para uma conta já emitida.
          </p>
          {context.tariffSourceReference ? (
            <p>Documento de referência: {context.tariffSourceReference}</p>
          ) : null}
        </div>
      </section>

      {invoice.items.length > 0 ? (
        <section className="invoice-block" aria-labelledby="invoice-advice-title">
          <div className="dashboard-section-heading">
            <h2 id="invoice-advice-title">O que fazer com isso</h2>
            <span>Quanto custaria carregando em outro horário</span>
          </div>
          {cheaper.length === 0 ? (
            <p className="invoice-empty">
              Estas recargas já foram cobradas no horário mais barato da
              tarifa. Não há economia possível só mudando a hora de carregar.
            </p>
          ) : (
            <>
              <div className="responsible-table-frame">
                <table aria-label="Comparação entre horários">
                  <thead>
                    <tr>
                      <th>Se tudo fosse carregado</th>
                      <th>Horário</th>
                      <th>Preço</th>
                      <th>A energia custaria</th>
                      <th>Economia</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cheaper.map((band) => (
                      <tr key={band.code}>
                        <td>{band.label}</td>
                        <td>{band.hours}</td>
                        <td>{formatRate(band.rateCentsPerKwh)}</td>
                        <td>{formatCents(band.energyValueCents)}</td>
                        <td>
                          {formatCents(
                            invoice.energyValueCents - band.energyValueCents,
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td colSpan={3}>Esta fatura, como foi cobrada</td>
                      <td>{formatCents(invoice.energyValueCents)}</td>
                      <td>—</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
              <p className="invoice-note">
                A conta é a mesma energia desta fatura, recalculada como se
                todas as recargas tivessem começado naquele horário, com a
                tarifa desta fatura e o mesmo arredondamento por recarga. Não é
                promessa de economia: depende de quando o carro for carregado no
                mês que vem.
              </p>
            </>
          )}
        </section>
      ) : null}
    </div>
  );
}
