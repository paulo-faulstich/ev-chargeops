"use client";

import { useEffect, useState } from "react";
import {
  listBillingPeriods,
  listSessions,
  type SessionResponse,
} from "@ev-chargeops/api-client";

import { PeriodClose } from "@/components/billing/period-close";
import { PageBreadcrumb } from "@/components/shell/page-breadcrumb";
import {
  buildDashboardSummary,
  type ResponsibleConsumption,
} from "@/components/dashboard/dashboard-summary";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api";

const energyFormatter = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function currentPeriod(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    timeZone: "America/Sao_Paulo",
  }).formatToParts(new Date());
  const year = parts.find((part) => part.type === "year")?.value;
  const month = parts.find((part) => part.type === "month")?.value;
  return `${year}-${month}`;
}

type Loaded = {
  periodValue: string;
  consumption: ResponsibleConsumption[];
};

/** The month being closed, and what it is made of.
 *
 * Conferring consumption per unit and approving the close are the same act,
 * so they belong on the same screen rather than at opposite ends of the
 * dashboard's scroll.
 */
export function ClosingWorkspace({ accessToken }: { accessToken: string }) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let ignore = false;

    async function load(): Promise<Loaded> {
      const [periods, sessions] = await Promise.all([
        listBillingPeriods(accessToken, { baseUrl: apiUrl }),
        listSessions(accessToken, {}, apiUrl),
      ]);
      const latest = periods.items
        .map((period) => period.periodValue)
        .sort((left, right) => right.localeCompare(left))[0];
      const summary = buildDashboardSummary(
        sessions.items as SessionResponse[],
        latest,
      );
      return {
        periodValue: latest ?? summary?.periodKey ?? currentPeriod(),
        consumption: summary?.responsibleConsumption ?? [],
      };
    }

    void load()
      .then((result) => {
        if (!ignore) setLoaded(result);
      })
      .catch(() => {
        if (!ignore) setFailed(true);
      });

    return () => {
      ignore = true;
    };
  }, [accessToken]);

  return (
    <div className="closing-workspace">
      <header className="dashboard-heading">
        <div>
          <PageBreadcrumb section="Faturamento" current="Fechamento" />
          <h1>Fechamento</h1>
          <p>
            Confira o consumo do mês, leia o parecer e aprove a emissão das
            faturas.
          </p>
        </div>
      </header>

      {failed ? (
        <p className="invoice-status error">
          Não foi possível carregar o fechamento.
        </p>
      ) : null}

      {loaded === null && !failed ? (
        <p className="invoice-status">Carregando fechamento…</p>
      ) : null}

      {loaded !== null ? (
        <>
          <PeriodClose
            accessToken={accessToken}
            periodValue={loaded.periodValue}
          />

          {loaded.consumption.length > 0 ? (
            <section
              className="responsible-costs"
              aria-labelledby="responsible-costs-title"
            >
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
                    {loaded.consumption.map((responsible) => (
                      <tr key={responsible.key}>
                        <td>{responsible.label}</td>
                        <td>
                          <span
                            className={
                              responsible.assigned ? "assigned" : "pending"
                            }
                          >
                            {responsible.assigned ? "Identificado" : "Revisar"}
                          </span>
                        </td>
                        <td>{responsible.sessionCount}</td>
                        <td>
                          {energyFormatter.format(responsible.energyKwh)} kWh
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
