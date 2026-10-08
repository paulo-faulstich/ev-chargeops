"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  closeBillingPeriod,
  decideFinding,
  listFindings,
  generateClosingOpinion,
  getBillingPeriodReadiness,
  listBillingPeriods,
  listInvoices,
  openBillingPeriod,
  type BillingPeriodResponse,
  type ClosingOpinionResponse,
  type InvoiceResponse,
  type PersistedFindingResponse,
  type ReadinessResponse,
} from "@ev-chargeops/api-client";

import { useResidentContext } from "@/lib/billing/resident-context";
import {
  confidenceLabel,
  findingTitle,
  severityName,
} from "@/lib/vocabulary";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api";

function formatCents(cents: number): string {
  const reais = Math.trunc(Math.abs(cents) / 100);
  const rest = Math.abs(cents) % 100;
  return `${cents < 0 ? "-" : ""}R$ ${reais.toLocaleString("pt-BR")},${String(rest).padStart(2, "0")}`;
}

function formatKwh(value: string): string {
  return `${Number(value).toLocaleString("pt-BR", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  })} kWh`;
}

function formatPercent(value: string): string {
  return `${(Number(value) * 100).toLocaleString("pt-BR", {
    maximumFractionDigits: 1,
  })}%`;
}

const LOADING = { status: "loading" } as const;

type CloseState =
  | { status: "loading" }
  | { status: "not_opened" }
  | { status: "error"; message: string }
  | {
      status: "ready";
      period: BillingPeriodResponse;
      readiness: ReadinessResponse;
      invoices: InvoiceResponse[];
      findings: PersistedFindingResponse[];
    };

/** Everything the manager needs to decide, before deciding.
 *
 * The close button is the last thing on the page and stays disabled until the
 * blockers are gone and the opinion has been generated: the approval is a
 * judgement on evidence, not a button that happens to be there.
 */
export function PeriodClose({
  accessToken,
  periodValue,
}: {
  accessToken: string;
  periodValue: string;
}) {
  const router = useRouter();
  const { context, enter } = useResidentContext();
  const residentContextId = context?.id ?? null;
  // An opinion is a statement about one period; carrying it across a period
  // change would attribute one month's findings to another.
  const [opinionFor, setOpinionFor] = useState<{
    periodValue: string;
    opinion: ClosingOpinionResponse;
  } | null>(null);
  const [busy, setBusy] = useState<
    "opinion" | "close" | "decision" | "open" | null
  >(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [generation, setGeneration] = useState(0);
  // Tagging the result with the request it answers lets a reload fall back to
  // loading without the effect writing state synchronously on its way in.
  const requestKey = `${periodValue}:${generation}`;
  const [resolved, setResolved] = useState<{
    key: string;
    state: CloseState;
  } | null>(null);
  const state: CloseState =
    resolved?.key === requestKey ? resolved.state : LOADING;

  useEffect(() => {
    // Nothing here is readable under a resident context; asking anyway would
    // only produce refusals for the audit log.
    if (residentContextId != null) return;
    let ignore = false;

    async function load(): Promise<CloseState> {
      const known = await listBillingPeriods(accessToken, { baseUrl: apiUrl });
      const period = known.items.find(
        (item) => item.periodValue === periodValue,
      );
      // Looking at a month must not create one. Opening a period is a decision
      // the manager takes explicitly, not a side effect of loading a page.
      if (period === undefined) {
        return { status: "not_opened" };
      }
      const [readiness, invoices, findings] = await Promise.all([
        getBillingPeriodReadiness(period.id, accessToken, { baseUrl: apiUrl }),
        listInvoices(accessToken, { periodId: period.id }, { baseUrl: apiUrl }),
        listFindings(period.id, accessToken, { baseUrl: apiUrl }),
      ]);
      return {
        status: "ready",
        period: readiness.period,
        readiness: readiness.readiness,
        invoices: invoices.items,
        findings: findings.items,
      };
    }

    void load()
      .then((loaded) => {
        if (!ignore) setResolved({ key: requestKey, state: loaded });
      })
      .catch(() => {
        if (!ignore) {
          setResolved({
            key: requestKey,
            state: {
              status: "error",
              message: "Não foi possível carregar o fechamento do período.",
            },
          });
        }
      });

    return () => {
      ignore = true;
    };
  }, [accessToken, periodValue, generation, requestKey, residentContextId]);

  const runOpinion = useCallback(async () => {
    if (state.status !== "ready") return;
    setBusy("opinion");
    setNotice(null);
    try {
      const result = await generateClosingOpinion(
        state.period.id,
        accessToken,
        { baseUrl: apiUrl },
      );
      setOpinionFor({ periodValue, opinion: result.opinion });
    } catch {
      setNotice("Não foi possível gerar o parecer.");
    } finally {
      setBusy(null);
    }
  }, [state, accessToken, periodValue]);

  const runClose = useCallback(async () => {
    if (state.status !== "ready") return;
    setBusy("close");
    setNotice(null);
    try {
      await closeBillingPeriod(state.period.id, accessToken, {
        baseUrl: apiUrl,
      });
      setGeneration((value) => value + 1);
    } catch (error: unknown) {
      // A 409 is the period defending itself: something changed between the
      // readiness read and the approval, so the screen reloads instead of
      // insisting.
      setNotice(
        error instanceof ApiError && error.status === 409
          ? "O período mudou desde a última leitura e não foi fechado. Revise os bloqueios."
          : "Não foi possível fechar o período.",
      );
      setGeneration((value) => value + 1);
    } finally {
      setBusy(null);
    }
  }, [state, accessToken]);

  const openPeriod = useCallback(async () => {
    setBusy("open");
    setNotice(null);
    try {
      await openBillingPeriod({ periodValue }, accessToken, {
        baseUrl: apiUrl,
      });
      setGeneration((value) => value + 1);
    } catch {
      setNotice("Não foi possível abrir o período.");
    } finally {
      setBusy(null);
    }
  }, [accessToken, periodValue]);

  const decide = useCallback(
    async (findingId: string, note: string) => {
      if (state.status !== "ready") return;
      setBusy("decision");
      setNotice(null);
      try {
        await decideFinding(state.period.id, findingId, note, accessToken, {
          baseUrl: apiUrl,
        });
        setGeneration((value) => value + 1);
      } catch {
        setNotice("Não foi possível registrar a decisão.");
      } finally {
        setBusy(null);
      }
    },
    [state, accessToken],
  );

  const impersonate = useCallback(
    async (invoice: InvoiceResponse) => {
      await enter(invoice.unitId);
      router.push(`/invoices/${invoice.id}?from=closing`);
    },
    [enter, router],
  );

  // Under a resident context the scope is narrowed to one unit and to reading,
  // so the close endpoints correctly reject it. Saying so beats reporting the
  // refusal as a failure to load.
  if (context != null) {
    return (
      <p className="invoice-status">
        O fechamento não é visível na visão do morador. Saia da visão da unidade{" "}
        {context.unitCode} para retomar a operação.
      </p>
    );
  }

  if (state.status === "loading") {
    return <p className="invoice-status">Carregando fechamento…</p>;
  }
  if (state.status === "error") {
    return <p className="invoice-status error">{state.message}</p>;
  }
  if (state.status === "not_opened") {
    return (
      <section className="period-close" aria-labelledby="period-close-title">
        <div className="dashboard-section-heading">
          <h2 id="period-close-title">Fechamento de {periodValue}</h2>
          <span>Ainda não aberto</span>
        </div>
        <p className="invoice-note">
          Abrir o período congela o mês para conferência e é o primeiro passo do
          fechamento. Nenhuma cobrança é gerada agora.
        </p>
        <button
          type="button"
          className="primary-dashboard-action compact"
          onClick={() => void openPeriod()}
          disabled={busy != null}
        >
          {busy === "open" ? "Abrindo…" : `Abrir fechamento de ${periodValue}`}
        </button>
      </section>
    );
  }

  const { period, readiness, invoices, findings } = state;
  const openCritical = findings.filter(
    (finding) => finding.severity === "critical" && finding.resolvedAt === null,
  );
  const closed = period.status === "closed";
  const opinion =
    opinionFor?.periodValue === periodValue ? opinionFor.opinion : null;
  const canClose = readiness.canClose && opinion != null;

  return (
    <section className="period-close" aria-labelledby="period-close-title">
      <div className="dashboard-section-heading">
        <h2 id="period-close-title">Fechamento de {period.periodValue}</h2>
        <span>
          {closed
            ? `Fechado por ${period.approvedByName ?? "—"}`
            : "Em aberto · aguardando aprovação"}
        </span>
      </div>

      {notice ? <p className="invoice-status error">{notice}</p> : null}

      <dl className="close-readiness">
        <div>
          <dt>Recargas no período</dt>
          <dd>{readiness.sessionCount}</dd>
        </div>
        <div>
          <dt>Já com responsável</dt>
          <dd>{readiness.billableCount}</dd>
        </div>
        <div>
          <dt>Ainda sem responsável</dt>
          <dd className={readiness.pendingCount > 0 ? "warning" : undefined}>
            {readiness.pendingCount}
          </dd>
        </div>
        <div>
          <dt>Percentual já atribuído</dt>
          <dd>{formatPercent(readiness.assignmentCoverage)}</dd>
        </div>
        <div>
          <dt>Energia a faturar</dt>
          <dd>{formatKwh(readiness.billableEnergyKwh)}</dd>
        </div>
        <div>
          <dt>Faturas × recargas</dt>
          <dd>{formatKwh(readiness.internalDifferenceKwh)}</dd>
        </div>
        <div>
          <dt>Recargas × total do carregador</dt>
          <dd>
            {readiness.externalDifferenceKwh == null
              ? "sem leitura do carregador"
              : formatKwh(readiness.externalDifferenceKwh)}
          </dd>
        </div>
      </dl>
      <RecoveryStatement
        readiness={readiness}
        invoices={invoices}
        closed={closed}
      />

      <p className="invoice-note">
        As duas conferências não têm o mesmo peso. <strong>Faturas × recargas</strong>{" "}
        compara o que vai ser cobrado com o que foi medido, e qualquer sobra aí
        impede o fechamento. <strong>Recargas × total do carregador</strong>{" "}
        compara a soma das recargas com o número que o próprio equipamento
        acumulou; ela avisa, mas nunca vira centavo em fatura de ninguém.
      </p>

      {readiness.blockers.length > 0 ? (
        <ul className="close-blockers">
          {readiness.blockers.map((blocker) => (
            <li key={blocker.code}>
              <strong>{blocker.detail}</strong>
              <span>{blocker.count}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="attention-clear">Nenhum bloqueio impede o fechamento.</p>
      )}

      {openCritical.length > 0 && !closed ? (
        <div className="critical-findings">
          <div className="dashboard-section-heading">
            <h3>Achados críticos aguardando decisão</h3>
            <span>{openCritical.length} em aberto</span>
          </div>
          <p className="invoice-note">
            A análise não deixa o período fechar em silêncio. Cada achado é
            aceito com um motivo registrado, que fica no histórico junto do
            próprio achado — nada é apagado.
          </p>
          {openCritical.map((finding) => (
            <FindingDecision
              key={finding.id}
              finding={finding}
              disabled={busy != null}
              onDecide={(note) => void decide(finding.id, note)}
            />
          ))}
        </div>
      ) : null}

      {!closed ? (
        <div className="close-actions">
          <button
            type="button"
            className="primary-dashboard-action compact"
            onClick={() => void runOpinion()}
            disabled={busy != null}
          >
            {busy === "opinion" ? "Analisando…" : "Gerar parecer da IA"}
          </button>
          <button
            type="button"
            className="primary-dashboard-action compact"
            onClick={() => void runClose()}
            disabled={!canClose || busy != null}
          >
            {busy === "close" ? "Fechando…" : "Aprovar e emitir faturas"}
          </button>
          {!canClose ? (
            <span className="close-hint">
              {readiness.canClose
                ? "Gere o parecer antes de aprovar."
                : "Resolva os bloqueios antes de aprovar."}
            </span>
          ) : null}
        </div>
      ) : null}

      {opinion ? (
        <div className="closing-opinion">
          <div className="dashboard-section-heading">
            <h3>Parecer</h3>
            <span>
              {severityName(opinion.severity)} · confiança{" "}
              {confidenceLabel(opinion.confidence)} · {opinion.sampleSize}{" "}
              recargas
            </span>
          </div>
          <p className="attention-message">{opinion.conclusion}</p>
          <p className="invoice-note">{opinion.recommendation}</p>
          {opinion.findings.length > 0 ? (
            <ul className="opinion-findings">
              {opinion.findings.map((finding, index) => (
                <li key={`${finding.code}-${index}`}>
                  <strong>{findingTitle(finding.code)}</strong>
                  <span>{finding.explanation}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {invoices.length > 0 ? (
        <div className="issued-invoices">
          <div className="dashboard-section-heading">
            <h3>Faturas emitidas</h3>
            <span>{invoices.length} unidades</span>
          </div>
          <div className="responsible-table-frame">
            <table aria-label="Faturas emitidas">
              <thead>
                <tr>
                  <th>Unidade</th>
                  <th>Responsável</th>
                  <th>Energia</th>
                  <th>Total</th>
                  <th>Fatura</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((invoice) => (
                  <tr key={invoice.id}>
                    <td>{invoice.unitCode}</td>
                    <td>{invoice.contactLabel}</td>
                    <td>{formatKwh(invoice.energyKwh)}</td>
                    <td>{formatCents(invoice.totalCents)}</td>
                    <td className="invoice-row-actions">
                      <Link href={`/invoices/${invoice.id}?from=closing`}>Abrir</Link>
                      <button
                        type="button"
                        onClick={() => void impersonate(invoice)}
                      >
                        Ver como morador
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}


function FindingDecision({
  finding,
  disabled,
  onDecide,
}: {
  finding: PersistedFindingResponse;
  disabled: boolean;
  onDecide: (note: string) => void;
}) {
  const [note, setNote] = useState("");

  return (
    <form
      className="finding-decision"
      onSubmit={(event) => {
        event.preventDefault();
        onDecide(note.trim());
      }}
    >
      <div className="finding-decision-body">
        <strong>{findingTitle(finding.code)}</strong>
        <p>{finding.explanation}</p>
        {Object.keys(finding.evidence).length > 0 ? (
          <dl className="finding-evidence">
            {Object.entries(finding.evidence).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
      <div className="finding-decision-action">
        <label htmlFor={`note-${finding.id}`}>Motivo da decisão</label>
        <input
          id={`note-${finding.id}`}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Por que este achado não impede a cobrança?"
          minLength={3}
          required
        />
        <button type="submit" disabled={disabled || note.trim().length < 3}>
          Registrar decisão
        </button>
      </div>
    </form>
  );
}


/** The sentence the manager repeats in the assembly, in money.
 *
 * The reconciliation is already computed in kWh, which is engineer's language.
 * The question a condominium actually argues about is whether the neighbours
 * without an electric car are paying for the ones who have one, and that
 * question is answered in reais or not at all.
 */
function RecoveryStatement({
  readiness,
  invoices,
  closed,
}: {
  readiness: ReadinessResponse;
  invoices: InvoiceResponse[];
  closed: boolean;
}) {
  const billed = invoices.reduce(
    (total, invoice) => total + invoice.totalCents,
    0,
  );
  const unrecovered = readiness.unassignedValueCents;
  const external = readiness.externalDifferenceKwh;

  return (
    <div className="recovery-statement">
      <p className="utility-label">O que o condomínio recuperou</p>
      <p className="recovery-sentence">
        Os carregadores entregaram{" "}
        <strong>{formatKwh(readiness.periodEnergyKwh)}</strong> em{" "}
        {readiness.periodValue}.{" "}
        {closed ? (
          <>
            O condomínio cobrou <strong>{formatCents(billed)}</strong> das
            unidades.
          </>
        ) : (
          <>
            {formatKwh(readiness.billableEnergyKwh)} estão prontos para cobrança.
          </>
        )}{" "}
        {unrecovered === null ? (
          <>
            Sem tarifa vigente, o que não foi atribuído não tem preço — e por
            isso não é estimado aqui.
          </>
        ) : unrecovered === 0 ? (
          <>
            <strong>Nada ficou no rateio geral:</strong> toda a energia tem uma
            unidade responsável.
          </>
        ) : (
          <>
            <strong className="warning">{formatCents(unrecovered)}</strong>{" "}
            ficariam no rateio geral, divididos entre todos os moradores —
            inclusive quem não tem carro elétrico.
          </>
        )}
      </p>
      {external !== null && Number(external) !== 0 ? (
        <p className="invoice-note">
          O carregador mediu {formatKwh(external)} a mais do que as recargas
          somam. Essa diferença é relatada e nunca entra em fatura.
        </p>
      ) : null}
    </div>
  );
}
