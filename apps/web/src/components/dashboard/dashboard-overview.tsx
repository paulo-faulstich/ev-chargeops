"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listSessions } from "@ev-chargeops/api-client";

import {
  buildDashboardSummary,
  type DashboardSummary,
  type SessionProvenance,
} from "./dashboard-summary";
import { PeriodClose } from "@/components/billing/period-close";
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

export function DashboardOverview({ accessToken }: { accessToken: string }) {
  const [state, setState] = useState<DashboardState>({
    status: "loading",
    summary: null,
  });
  const [refreshGeneration, setRefreshGeneration] = useState(0);
  const [selectedPeriod, setSelectedPeriod] = useState<string | undefined>();

  useEffect(() => {
    let ignore = false;

    void fetchDashboardSummary(accessToken, selectedPeriod)
      .then((summary) => {
        if (!ignore) setState({ status: "ready", summary });
      })
      .catch(() => {
        if (!ignore) setState({ status: "error", summary: null });
      });

    return () => {
      ignore = true;
    };
  }, [accessToken, refreshGeneration, selectedPeriod]);

  const activeStage = state.summary
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

      <CloseProgress activeStage={activeStage} summary={state.summary} />

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
          accessToken={accessToken}
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
}: {
  activeStage: number;
  summary: DashboardSummary | null;
}) {
  return (
    <section className="close-progress" aria-labelledby="close-progress-title">
      <div className="close-progress-heading">
        <h2 id="close-progress-title">Fechamento do período</h2>
        <p>
          {summary
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
  accessToken,
}: {
  summary: DashboardSummary;
  accessToken: string;
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
      </section>

      <div className="dashboard-analysis-grid">
        <section className="dashboard-chart" aria-labelledby="usage-chart-title">
          <div className="dashboard-section-heading">
            <h2 id="usage-chart-title">Consumo diário</h2>
            <span>kWh · {summary.periodLabel}</span>
          </div>
          <div className="usage-bars" role="img" aria-label="Consumo diário de energia">
            {summary.dailyUsage.map((day) => (
              <div className="usage-day" key={day.dateKey}>
                <span className="usage-value">
                  {energyFormatter.format(day.energyKwh)}
                </span>
                <span
                  className="usage-bar"
                  style={{ height: `${Math.max(12, (day.energyKwh / maxDailyEnergy) * 100)}%` }}
                />
                <span className="usage-label">{day.dateLabel}</span>
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

      <section className="responsible-costs" aria-labelledby="responsible-costs-title">
        <div className="dashboard-section-heading">
          <h2 id="responsible-costs-title">Consumo por responsável</h2>
          <span>Medido · o valor devido é decidido no fechamento</span>
        </div>
        <div className="responsible-table-frame">
          <table aria-label="Consumo por responsável">
            <thead>
              <tr>
                <th>Identificador</th>
                <th>Situação</th>
                <th>Recargas</th>
                <th>Energia</th>
              </tr>
            </thead>
            <tbody>
              {summary.responsibleConsumption.map((responsible) => (
                <tr key={responsible.key}>
                  <td>{responsible.label}</td>
                  <td>
                    <span className={responsible.assigned ? "assigned" : "pending"}>
                      {responsible.assigned ? "Identificado" : "Revisar"}
                    </span>
                  </td>
                  <td>{responsible.sessionCount}</td>
                  <td>{energyFormatter.format(responsible.energyKwh)} kWh</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <PeriodClose accessToken={accessToken} periodValue={summary.periodKey} />
    </div>
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
