"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getBillingPeriodReadiness,
  listBillingPeriods,
  listFindings,
  listSessions,
  type PersistedFindingResponse,
  type ReadinessResponse,
} from "@ev-chargeops/api-client";

import {
  buildDashboardSummary,
  type DashboardSummary,
  type SessionProvenance,
} from "./dashboard-summary";
import { PageBreadcrumb } from "@/components/shell/page-breadcrumb";
import { findingTitle, severityCountLabel } from "@/lib/vocabulary";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api";
const closeStages = [
  "Importar recargas",
  "Revisar atribuições",
  "Conferir custos",
  "Fechar mês",
];

const energyFormatter = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

type DashboardState =
  | { status: "loading"; summary: null }
  | { status: "error"; summary: null }
  | { status: "ready"; summary: DashboardSummary | null };

/** The month the overview opens on.
 *
 * The newest charge is a poor default: charges keep arriving into a month
 * nobody has opened yet, while the operation is still closing an earlier one.
 * The billing periods say which month is actually being worked on, and the two
 * screens must not disagree about it.
 */
async function fetchDashboardSummary(
  accessToken: string,
  periodKey: string | undefined,
  workingPeriod: string | undefined,
) {
  const sessions = await listSessions(accessToken, {}, apiUrl);
  return buildDashboardSummary(sessions.items, periodKey ?? workingPeriod);
}

async function fetchWorkingPeriod(
  accessToken: string,
): Promise<string | undefined> {
  try {
    const periods = await listBillingPeriods(accessToken, { baseUrl: apiUrl });
    return periods.items
      .map((period) => period.periodValue)
      .sort((left, right) => right.localeCompare(left))[0];
  } catch {
    return undefined;
  }
}

type PeriodContext = {
  closedPeriods: Set<string>;
  readiness: ReadinessResponse | null;
  findings: PersistedFindingResponse[];
};

/** What the billing side knows about the month on screen.
 *
 * The closed set comes from the periods themselves rather than from the
 * pending count: a period with nothing pending is *ready* to close, which is
 * not the same as closed, and a timeline that cannot tell them apart
 * misreports the one thing it exists to show.
 */
async function fetchPeriodContext(
  accessToken: string,
  periodKey: string | undefined,
): Promise<PeriodContext> {
  try {
    const periods = await listBillingPeriods(accessToken, { baseUrl: apiUrl });
    const closedPeriods = new Set(
      periods.items
        .filter((period) => period.status === "closed")
        .map((period) => period.periodValue),
    );
    const current =
      periodKey === undefined
        ? undefined
        : periods.items.find((period) => period.periodValue === periodKey);
    if (current === undefined) {
      return { closedPeriods, readiness: null, findings: [] };
    }
    const [readiness, findings] = await Promise.all([
      getBillingPeriodReadiness(current.id, accessToken, { baseUrl: apiUrl }),
      listFindings(current.id, accessToken, { baseUrl: apiUrl }),
    ]);
    return {
      closedPeriods,
      readiness: readiness.readiness,
      findings: findings.items,
    };
  } catch {
    return { closedPeriods: new Set(), readiness: null, findings: [] };
  }
}

export function DashboardOverview({ accessToken }: { accessToken: string }) {
  const [state, setState] = useState<DashboardState>({
    status: "loading",
    summary: null,
  });
  const [refreshGeneration, setRefreshGeneration] = useState(0);
  const [selectedPeriod, setSelectedPeriod] = useState<string | undefined>();
  const [periodContext, setPeriodContext] = useState<PeriodContext>({
    closedPeriods: new Set(),
    readiness: null,
    findings: [],
  });

  useEffect(() => {
    let ignore = false;

    void fetchWorkingPeriod(accessToken)
      .then((workingPeriod) =>
        fetchDashboardSummary(accessToken, selectedPeriod, workingPeriod),
      )
      .then(async (summary) => {
        if (ignore) return;
        setState({ status: "ready", summary });
        // The billing side is asked about the month the summary settled on, not
        // about the picker's value: on first load nobody has picked anything
        // yet, and asking about `undefined` returns a period that is not there.
        const context = await fetchPeriodContext(
          accessToken,
          summary?.periodKey,
        );
        if (!ignore) setPeriodContext(context);
      })
      .catch(() => {
        if (!ignore) setState({ status: "error", summary: null });
      });

    return () => {
      ignore = true;
    };
  }, [accessToken, refreshGeneration, selectedPeriod]);

  const periodClosed =
    state.summary !== null &&
    periodContext.closedPeriods.has(state.summary.periodKey);
  const activeStage = periodClosed
    ? closeStages.length
    : state.summary
      ? state.summary.pendingCount > 0
        ? 1
        : 2
      : 0;

  return (
    <div className="dashboard-overview">
      <header className="dashboard-heading">
        <div>
          <PageBreadcrumb section="Operação" current="Visão geral" />
          <h1>Visão geral</h1>
          <p>Acompanhe consumo, custos e pendências antes do fechamento do mês.</p>
        </div>
        {state.summary ? (
          <div className="dashboard-heading-meta">
            {/* Naming the period keeps the month from reading as a stray date. */}
            <span className="utility-label">Período em análise</span>
            <PeriodPicker
              summary={state.summary}
              onSelect={(periodKey) => {
                setState({ status: "loading", summary: null });
                setSelectedPeriod(periodKey);
              }}
            />
            <ProvenanceBadge provenance={state.summary.provenance} />
            <span className="dashboard-updated">
              Atualizado em {state.summary.updatedAt}
            </span>
          </div>
        ) : null}
      </header>

      <CloseProgress
        activeStage={activeStage}
        summary={state.summary}
        closed={periodClosed}
      />

      {state.status === "loading" ? <DashboardLoading /> : null}
      {state.status === "error" ? (
        <div className="dashboard-state-layout">
          <DashboardError
            onRetry={() => {
              setState({ status: "loading", summary: null });
              setRefreshGeneration((generation) => generation + 1);
            }}
          />
          <DashboardProcessGuide />
        </div>
      ) : null}
      {state.status === "ready" && !state.summary ? <EmptyDashboard /> : null}
      {state.status === "ready" && state.summary ? (
        <OperationalDashboard
          summary={state.summary}
          readiness={periodContext.readiness}
          findings={periodContext.findings}
          closed={periodClosed}
        />
      ) : null}
    </div>
  );
}

const provenanceLabels: Record<SessionProvenance, string> = {
  real: "SEMS+ real",
  simulated: "Cenário demonstrativo",
  mixed: "Origens combinadas",
};

/**
 * Provenance travels with the period, never with the screen.
 *
 * A manager must never have to remember whether the month on display came off
 * the charger or out of a demonstration dataset, and an evaluator must never be
 * able to mistake one for the other.
 */
function ProvenanceBadge({ provenance }: { provenance: SessionProvenance }) {
  return (
    <span
      className={`provenance-badge provenance-badge-${provenance}`}
      title={
        provenance === "real"
          ? "Telemetria observada no SEMS+."
          : provenance === "simulated"
            ? "Dados construídos para demonstração. Não são telemetria real."
            : "Este período combina telemetria real e dados demonstrativos."
      }
    >
      {provenanceLabels[provenance]}
    </span>
  );
}

function PeriodPicker({
  summary,
  onSelect,
}: {
  summary: DashboardSummary;
  onSelect: (periodKey: string) => void;
}) {
  if (summary.periods.length <= 1) {
    return <strong>{summary.periodLabel}</strong>;
  }
  return (
    <label className="dashboard-period-picker">
      <span className="visually-hidden">Período do fechamento</span>
      <select
        value={summary.periodKey}
        onChange={(event) => onSelect(event.target.value)}
      >
        {summary.periods.map((period) => (
          <option key={period.periodKey} value={period.periodKey}>
            {period.periodLabel} · {period.sessionCount} recargas
          </option>
        ))}
      </select>
    </label>
  );
}

function CloseProgress({
  activeStage,
  summary,
  closed,
}: {
  activeStage: number;
  summary: DashboardSummary | null;
  closed: boolean;
}) {
  return (
    <section className="close-progress" aria-labelledby="close-progress-title">
      <div className="close-progress-heading">
        <h2 id="close-progress-title">Fechamento do período</h2>
        <p>
          {closed
            ? "Mês fechado · faturas emitidas"
            : summary
            ? summary.pendingCount > 0
              ? `${summary.pendingCount} ${summary.pendingCount === 1 ? "pendência precisa" : "pendências precisam"} ser resolvida${summary.pendingCount === 1 ? "" : "s"}`
              : "Recargas prontas para conferência de custos"
            : "Comece trazendo as recargas do carregador"}
        </p>
      </div>
      <ol className="close-steps">
        {closeStages.map((stage, index) => (
          <li
            key={stage}
            className={
              index < activeStage
                ? "completed"
                : index === activeStage
                  ? "active"
                  : undefined
            }
          >
            <span className="close-step-node" aria-hidden="true" />
            <span className="close-step-index">0{index + 1}</span>
            <span className="close-step-name">{stage}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function DashboardLoading() {
  return (
    <div className="dashboard-state-panel" role="status">
      <span className="dashboard-state-signal" aria-hidden="true" />
      <div>
        <p className="utility-label">Atualizando visão geral</p>
        <p>Carregando recargas, atribuições e custos…</p>
      </div>
    </div>
  );
}

function DashboardError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="dashboard-state-panel dashboard-error" role="alert">
      <div>
        <p className="utility-label">Dados indisponíveis</p>
        <p className="dashboard-error-title">Serviço de recargas indisponível</p>
        <p>
          A visão geral não foi carregada. Verifique a conexão e tente novamente.
        </p>
      </div>
      <button type="button" onClick={onRetry}>
        Atualizar dashboard
      </button>
    </div>
  );
}

function EmptyDashboard() {
  return (
    <div className="dashboard-empty-layout">
      <section className="dashboard-empty-card" aria-labelledby="empty-title">
        <p className="utility-label">Próxima ação</p>
        <p className="empty-data-label">Nenhum dado importado</p>
        <h2 id="empty-title">Importe as recargas para preparar o primeiro fechamento.</h2>
        <p>
          Use a exportação CSV do SEMS+. Antes de gravar qualquer dado, você
          poderá revisar linhas válidas, duplicadas e com problemas de
          identificação.
        </p>
        <Link href="/settings/data-sources" className="primary-dashboard-action">
          <span aria-hidden="true">↑</span>
          Importar dados do SEMS+
        </Link>
        <div className="safe-import-note">
          <span aria-hidden="true">◇</span>
          A importação é revisada antes de entrar no fechamento.
        </div>
      </section>

      <DashboardProcessGuide />
    </div>
  );
}

function DashboardProcessGuide() {
  return (
    <section className="dashboard-next-steps" aria-labelledby="next-steps-title">
      <h2 id="next-steps-title">O que acontece depois</h2>
      <ol>
        <li>
          <span>01</span>
          <div>
            <strong>Validamos as recargas</strong>
            <p>Erros e duplicidades ficam visíveis antes da confirmação.</p>
          </div>
        </li>
        <li>
          <span>02</span>
          <div>
            <strong>Relacionamos aos responsáveis</strong>
            <p>Cartões e recargas pendentes entram em uma fila de revisão.</p>
          </div>
        </li>
        <li>
          <span>03</span>
          <div>
            <strong>A IA analisa o fechamento</strong>
            <p>
              Cruza consumo, duração, potência, tarifa e histórico para emitir
              um parecer com evidências.
            </p>
          </div>
        </li>
        <li>
          <span>04</span>
          <div>
            <strong>O administrador aprova</strong>
            <p>Revisa as recomendações e exceções antes de fechar o mês.</p>
          </div>
        </li>
      </ol>
    </section>
  );
}

function OperationalDashboard({
  summary,
  readiness,
  findings,
  closed,
}: {
  summary: DashboardSummary;
  readiness: ReadinessResponse | null;
  findings: PersistedFindingResponse[];
  closed: boolean;
}) {
  const maxDailyEnergy = Math.max(
    ...summary.dailyUsage.map((day) => day.energyKwh),
    1,
  );
  const pendingMessage = `${summary.pendingCount} ${summary.pendingCount === 1 ? "recarga ainda não pode" : "recargas ainda não podem"} ser cobrada${summary.pendingCount === 1 ? "" : "s"} porque falta identificar o responsável.`;

  return (
    <div className="operational-dashboard">
      <section className="dashboard-metrics" aria-label="Indicadores do período">
        <MetricCard
          label="Energia no período"
          value={`${energyFormatter.format(summary.totalEnergyKwh)} kWh`}
          supporting={`${summary.sessionCount} ${summary.sessionCount === 1 ? "recarga importada" : "recargas importadas"}`}
        />
        <MetricCard
          label="Recargas atribuídas"
          value={`${summary.assignedCount} de ${summary.sessionCount}`}
          supporting={`${energyFormatter.format((summary.assignedCount / summary.sessionCount) * 100)}% identificadas`}
        />
        <MetricCard
          label="Pendências"
          value={String(summary.pendingCount)}
          supporting={
            summary.pendingCount > 0 ? "Impedem o fechamento" : "Nenhum bloqueio"
          }
          warning={summary.pendingCount > 0}
        />
        {readiness !== null && readiness.aggregateEnergyKwh !== null ? (
          // The charger's own aggregate is the one number the equipment owner
          // can verify independently. It is reported, never billed.
          <MetricCard
            label="Reconciliação externa"
            value={`${energyFormatter.format(Number(readiness.externalDifferenceKwh ?? 0))} kWh`}
            supporting={`Carregador mediu ${energyFormatter.format(Number(readiness.aggregateEnergyKwh))} kWh · diferença não cobrada`}
          />
        ) : null}
      </section>

      <div className="dashboard-analysis-grid">
        <section className="dashboard-chart" aria-labelledby="usage-chart-title">
          <div className="dashboard-section-heading">
            <h2 id="usage-chart-title">Consumo diário</h2>
            <span>kWh · {summary.periodLabel}</span>
          </div>
          <div className="usage-bars" role="img" aria-label="Consumo diário de energia">
            {summary.dailyUsage.map((day) => (
              // A full month has to fit on the axis, so the column shows the
              // day alone and carries the whole reading in its tooltip.
              <div
                className="usage-day"
                key={day.dateKey}
                title={`${day.dateLabel} · ${energyFormatter.format(day.energyKwh)} kWh`}
              >
                <span
                  className="usage-bar"
                  style={{ height: `${Math.max(12, (day.energyKwh / maxDailyEnergy) * 100)}%` }}
                />
                <span className="usage-label" data-date={day.dateLabel}>
                  {day.dayLabel}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="dashboard-attention" aria-labelledby="attention-title">
          <div className="dashboard-section-heading">
            <h2 id="attention-title">Atenção necessária</h2>
            <span>Antes de fechar</span>
          </div>
          {summary.pendingCount > 0 ? (
            <>
              <p className="attention-message">{pendingMessage}</p>
              <dl>
                <div>
                  <dt>Unidade não atribuída</dt>
                  <dd>{summary.pendingCount}</dd>
                </div>
              </dl>
              <Link
                href={`/sessions?status=pending_review&period=${summary.periodKey}`}
                className="primary-dashboard-action compact"
              >
                Revisar {summary.pendingCount} {summary.pendingCount === 1 ? "pendência" : "pendências"}
              </Link>
            </>
          ) : (
            <p className="attention-clear">
              Todas as recargas possuem um identificador de cobrança.
            </p>
          )}
          <OpinionSummary findings={findings} />
        </section>
      </div>

      <ConsumptionTrend summary={summary} />

      <ClosingHighlights
        summary={summary}
        readiness={readiness}
        closed={closed}
      />
    </div>
  );
}

/** Where the consumption is going, and where the pressure actually is.
 *
 * Installing a second charger is electrical work, a budget line and an assembly
 * vote — a decision taken months ahead. The two questions it turns on are how
 * fast demand is growing and how much of the connector's time is already
 * spoken for, and both are answerable from the charges already imported.
 */
function ConsumptionTrend({ summary }: { summary: DashboardSummary }) {
  const months = [...summary.periods]
    .sort((left, right) => left.periodKey.localeCompare(right.periodKey))
    .slice(-8);
  if (months.length < 3) return null;

  const peak = Math.max(...months.map((month) => month.energyKwh), 1);
  const half = Math.ceil(months.length / 2);
  const early =
    months.slice(0, half).reduce((total, m) => total + m.energyKwh, 0) / half;
  const late =
    months.slice(-half).reduce((total, m) => total + m.energyKwh, 0) / half;
  const growth = early > 0 ? (late / early - 1) * 100 : 0;

  // Hours the connector spent delivering, against the hours in the period. A
  // condominium's constraint is rarely total energy: it is two neighbours
  // wanting the same connector on the same evening.
  const observedDays = summary.dailyUsage.length || 1;
  const occupancy = (summary.totalEnergyKwh / 7.5 / (observedDays * 24)) * 100;

  return (
    <section className="consumption-trend" aria-labelledby="trend-title">
      <div className="dashboard-section-heading">
        <h2 id="trend-title">Tendência e capacidade</h2>
        <span>{months.length} meses importados</span>
      </div>

      <div className="trend-bars" role="img" aria-label="Energia por mês">
        {months.map((month) => (
          <div
            className="trend-month"
            key={month.periodKey}
            title={`${month.periodLabel}: ${energyFormatter.format(month.energyKwh)} kWh em ${month.sessionCount} recargas`}
          >
            <span
              className="trend-bar"
              style={{ height: `${Math.max(6, (month.energyKwh / peak) * 100)}%` }}
            />
            <span className="trend-label">{month.periodKey.slice(5)}</span>
          </div>
        ))}
      </div>

      <dl className="trend-figures">
        <div>
          <dt>Variação no período</dt>
          <dd className={growth > 0 ? "warning" : undefined}>
            {growth >= 0 ? "+" : ""}
            {growth.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%
          </dd>
        </div>
        <div>
          <dt>Média mensal</dt>
          <dd>
            {energyFormatter.format(
              months.reduce((total, m) => total + m.energyKwh, 0) /
                months.length,
            )}{" "}
            kWh
          </dd>
        </div>
        <div>
          <dt>Ocupação do carregador</dt>
          <dd>
            {occupancy.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%
          </dd>
        </div>
      </dl>

      <p className="invoice-note">
        A ocupação compara a energia entregue com o que um conector de 7,5 kW
        entregaria funcionando sem parar. Ela é baixa porque a garagem carrega
        concentrada à noite: o limite de um condomínio raramente é energia
        total, e sim dois vizinhos querendo o mesmo conector na mesma noite.
      </p>
    </section>
  );
}

/** What the analysis found, in the panel that exists to raise concerns.
 *
 * The opinion runs over the period's own data before any invoice exists, so a
 * finding here is a reason not to close yet — not a note about a charge that
 * has already been billed.
 */
function OpinionSummary({
  findings,
}: {
  findings: PersistedFindingResponse[];
}) {
  if (findings.length === 0) return null;

  const open = findings.filter((finding) => finding.resolvedAt === null);
  const decided = findings.length - open.length;
  const counts = new Map<string, number>();
  for (const finding of open) {
    counts.set(finding.severity, (counts.get(finding.severity) ?? 0) + 1);
  }
  const highlighted = open.slice(0, 3);

  return (
    <div className="opinion-summary">
      <p className="utility-label">Parecer da IA</p>
      {open.length === 0 ? (
        <p className="attention-clear">
          {findings.length}{" "}
          {findings.length === 1 ? "achado analisado" : "achados analisados"},
          todos com decisão registrada.
        </p>
      ) : (
        <>
          <p className="attention-message">
            {[...counts.entries()]
              .map(
                ([severity, total]) =>
                  `${total} ${severityCountLabel(severity)}`,
              )
              .join(" · ")}
            {decided > 0 ? ` · ${decided} já decididos` : ""}
          </p>
          <ul className="opinion-findings">
            {highlighted.map((finding) => (
              <li key={finding.id}>
                <strong>{findingTitle(finding.code)}</strong>
                <span>{finding.explanation}</span>
              </li>
            ))}
          </ul>
          {open.length > highlighted.length ? (
            <p className="invoice-note">
              e mais {open.length - highlighted.length} no fechamento.
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}

/** The closing, reduced to what the manager needs to decide whether to go.
 *
 * The conference table and the approval itself live under Faturamento: this is
 * a pointer to a monthly decision, not the decision surface.
 */
function ClosingHighlights({
  summary,
  readiness,
  closed,
}: {
  summary: DashboardSummary;
  readiness: ReadinessResponse | null;
  closed: boolean;
}) {
  const blockers = readiness?.blockers ?? [];

  return (
    <section className="closing-highlights" aria-labelledby="closing-highlights-title">
      <div className="dashboard-section-heading">
        <h2 id="closing-highlights-title">Fechamento de {summary.periodKey}</h2>
        <span>{closed ? "Aprovado · faturas emitidas" : "Em aberto"}</span>
      </div>

      <dl className="closing-highlight-figures">
        <div>
          <dt>Energia faturável</dt>
          <dd>
            {readiness
              ? `${energyFormatter.format(Number(readiness.billableEnergyKwh))} kWh`
              : "—"}
          </dd>
        </div>
        <div>
          <dt>Unidades com consumo</dt>
          <dd>{summary.responsibleConsumption.filter((r) => r.assigned).length}</dd>
        </div>
        <div>
          <dt>Bloqueios</dt>
          <dd className={blockers.length > 0 ? "warning" : undefined}>
            {readiness ? blockers.length : "—"}
          </dd>
        </div>
      </dl>

      {blockers.length > 0 ? (
        <p className="invoice-note">
          {blockers.map((blocker) => blocker.detail).join(" · ")}
        </p>
      ) : null}

      <Link href="/closing" className="primary-dashboard-action compact">
        {closed ? "Ver o fechamento" : "Ir para o fechamento"}
      </Link>
    </section>
  );
}

function MetricCard({
  label,
  value,
  supporting,
  warning = false,
}: {
  label: string;
  value: string;
  supporting: string;
  warning?: boolean;
}) {
  return (
    <article className="dashboard-metric">
      <p>{label}</p>
      <strong>{value}</strong>
      <span className={warning ? "warning" : undefined}>{supporting}</span>
    </article>
  );
}
