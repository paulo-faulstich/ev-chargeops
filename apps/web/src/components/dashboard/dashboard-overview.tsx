"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getImportBatch,
  listImportBatches,
} from "@ev-chargeops/api-client";

import {
  buildDashboardSummary,
  ESTIMATED_TARIFF_BRL_PER_KWH,
  type DashboardSummary,
} from "./dashboard-summary";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api";
const closeStages = [
  "Importar sessões",
  "Revisar atribuições",
  "Conferir custos",
  "Fechar mês",
];

const energyFormatter = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

type DashboardState =
  | { status: "loading"; summary: null }
  | { status: "error"; summary: null }
  | { status: "ready"; summary: DashboardSummary | null };

async function fetchDashboardSummary(accessToken: string) {
  const batches = await listImportBatches(accessToken, apiUrl);
  const details = await Promise.all(
    batches.items.map((batch) => getImportBatch(batch.id, accessToken, apiUrl)),
  );
  return buildDashboardSummary(batches.items, details);
}

export function DashboardOverview({ accessToken }: { accessToken: string }) {
  const [state, setState] = useState<DashboardState>({
    status: "loading",
    summary: null,
  });
  const [refreshGeneration, setRefreshGeneration] = useState(0);

  useEffect(() => {
    let ignore = false;

    void fetchDashboardSummary(accessToken)
      .then((summary) => {
        if (!ignore) setState({ status: "ready", summary });
      })
      .catch(() => {
        if (!ignore) setState({ status: "error", summary: null });
      });

    return () => {
      ignore = true;
    };
  }, [accessToken, refreshGeneration]);

  const activeStage = state.summary
    ? state.summary.pendingCount > 0
      ? 1
      : 2
    : 0;

  return (
    <div className="dashboard-overview">
      <div className="dashboard-context-bar">
        <div>
          <p className="dashboard-site-name">LAB FIAP Eco Smart Home</p>
          <p className="dashboard-site-meta">Gestão condominial · 1 carregador</p>
        </div>
        <div className="dashboard-period-context">
          <span>{state.summary?.periodLabel ?? "Período atual"}</span>
          <span className="manager-avatar" aria-label="Administrador Paulo Faulstich">
            PF
          </span>
        </div>
      </div>

      <header className="dashboard-heading">
        <div>
          <h1>Visão geral</h1>
          <p>O que precisa de atenção para fechar o mês.</p>
        </div>
        {state.summary ? (
          <p className="dashboard-updated">Atualizado em {state.summary.updatedAt}</p>
        ) : null}
      </header>

      <CloseProgress activeStage={activeStage} summary={state.summary} />

      {state.status === "loading" ? <DashboardLoading /> : null}
      {state.status === "error" ? (
        <DashboardError
          onRetry={() => {
            setState({ status: "loading", summary: null });
            setRefreshGeneration((generation) => generation + 1);
          }}
        />
      ) : null}
      {state.status === "ready" && !state.summary ? <EmptyDashboard /> : null}
      {state.status === "ready" && state.summary ? (
        <OperationalDashboard summary={state.summary} />
      ) : null}
    </div>
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
              : "Sessões prontas para conferência de custos"
            : "Comece trazendo as sessões do carregador"}
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
        <p>Carregando sessões, atribuições e custos…</p>
      </div>
    </div>
  );
}

function DashboardError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="dashboard-state-panel dashboard-error" role="alert">
      <div>
        <p className="utility-label">Dados indisponíveis</p>
        <p>A visão geral não foi carregada. Tente novamente.</p>
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
        <h2 id="empty-title">Importe as sessões para preparar o primeiro fechamento.</h2>
        <p>
          Use a exportação CSV do SEMS+. Antes de gravar qualquer dado, você
          poderá revisar linhas válidas, duplicadas e com problemas de
          identificação.
        </p>
        <Link href="/settings/data-sources" className="primary-dashboard-action">
          <span aria-hidden="true">↑</span>
          Importar dados
        </Link>
        <div className="safe-import-note">
          <span aria-hidden="true">◇</span>
          A importação é revisada antes de entrar no fechamento.
        </div>
      </section>

      <section className="dashboard-next-steps" aria-labelledby="next-steps-title">
        <h2 id="next-steps-title">O que acontece depois</h2>
        <ol>
          <li>
            <span>01</span>
            <div>
              <strong>Validamos as sessões</strong>
              <p>Erros e duplicidades ficam visíveis antes da confirmação.</p>
            </div>
          </li>
          <li>
            <span>02</span>
            <div>
              <strong>Relacionamos aos responsáveis</strong>
              <p>Cartões e sessões pendentes entram em uma fila de revisão.</p>
            </div>
          </li>
          <li>
            <span>03</span>
            <div>
              <strong>Calculamos os custos</strong>
              <p>O administrador confere valores antes de fechar o mês.</p>
            </div>
          </li>
        </ol>
      </section>
    </div>
  );
}

function OperationalDashboard({ summary }: { summary: DashboardSummary }) {
  const maxDailyEnergy = Math.max(
    ...summary.dailyUsage.map((day) => day.energyKwh),
    1,
  );
  const pendingMessage = `${summary.pendingCount} ${summary.pendingCount === 1 ? "sessão ainda não pode" : "sessões ainda não podem"} ser cobrada${summary.pendingCount === 1 ? "" : "s"} porque falta identificar o responsável.`;

  return (
    <div className="operational-dashboard">
      <section className="dashboard-metrics" aria-label="Indicadores do período">
        <MetricCard
          label="Energia no período"
          value={`${energyFormatter.format(summary.totalEnergyKwh)} kWh`}
          supporting={`${summary.sessionCount} ${summary.sessionCount === 1 ? "sessão importada" : "sessões importadas"}`}
        />
        <MetricCard
          label="Custo estimado"
          value={currencyFormatter.format(summary.estimatedCost)}
          supporting={`Tarifa de ${currencyFormatter.format(ESTIMATED_TARIFF_BRL_PER_KWH)}/kWh`}
        />
        <MetricCard
          label="Sessões atribuídas"
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
                  <dt>Morador não atribuído</dt>
                  <dd>{summary.pendingCount}</dd>
                </div>
              </dl>
              <Link href="/settings/data-sources" className="primary-dashboard-action compact">
                Revisar {summary.pendingCount} {summary.pendingCount === 1 ? "pendência" : "pendências"}
              </Link>
            </>
          ) : (
            <p className="attention-clear">
              Todas as sessões possuem um identificador de cobrança.
            </p>
          )}
        </section>
      </div>

      <section className="responsible-costs" aria-labelledby="responsible-costs-title">
        <div className="dashboard-section-heading">
          <h2 id="responsible-costs-title">Custos por responsável</h2>
          <span>Prévia do fechamento · tarifa estimada</span>
        </div>
        <div className="responsible-table-frame">
          <table aria-label="Custos por responsável">
            <thead>
              <tr>
                <th>Identificador</th>
                <th>Situação</th>
                <th>Sessões</th>
                <th>Energia</th>
                <th>Custo estimado</th>
              </tr>
            </thead>
            <tbody>
              {summary.responsibleCosts.map((responsible) => (
                <tr key={responsible.key}>
                  <td>{responsible.label}</td>
                  <td>
                    <span className={responsible.assigned ? "assigned" : "pending"}>
                      {responsible.assigned ? "Identificado" : "Revisar"}
                    </span>
                  </td>
                  <td>{responsible.sessionCount}</td>
                  <td>{energyFormatter.format(responsible.energyKwh)} kWh</td>
                  <td>{currencyFormatter.format(responsible.estimatedCost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
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
