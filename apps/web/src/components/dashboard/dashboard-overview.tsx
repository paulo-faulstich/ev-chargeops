"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getBillingPeriodReadiness,
  listBillingPeriods,
  listSessions,
  type ReadinessResponse,
} from "@ev-chargeops/api-client";

import {
  buildDashboardSummary,
  type DashboardSummary,
  type SessionProvenance,
} from "./dashboard-summary";
import { PageBreadcrumb } from "@/components/shell/page-breadcrumb";

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

async function fetchDashboardSummary(accessToken: string, periodKey?: string) {
  const sessions = await listSessions(accessToken, {}, apiUrl);
  return buildDashboardSummary(sessions.items, periodKey);
}

type PeriodContext = {
  closedPeriods: Set<string>;
  readiness: ReadinessResponse | null;
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
    if (current === undefined) return { closedPeriods, readiness: null };
    const readiness = await getBillingPeriodReadiness(
      current.id,
      accessToken,
      { baseUrl: apiUrl },
    );
    return { closedPeriods, readiness: readiness.readiness };
  } catch {
    return { closedPeriods: new Set(), readiness: null };
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
  });

  useEffect(() => {
    let ignore = false;

    void fetchDashboardSummary(accessToken, selectedPeriod)
      .then((summary) => {
        if (!ignore) setState({ status: "ready", summary });
      })
      .catch(() => {
        if (!ignore) setState({ status: "error", summary: null });
      });

    void fetchPeriodContext(accessToken, selectedPeriod).then((context) => {
      if (!ignore) setPeriodContext(context);
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
  closed,
}: {
  summary: DashboardSummary;
  readiness: ReadinessResponse | null;
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
        </section>
      </div>

      <ClosingHighlights
        summary={summary}
        readiness={readiness}
        closed={closed}
      />
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
