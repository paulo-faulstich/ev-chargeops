"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { listInvoices, type InvoiceResponse } from "@ev-chargeops/api-client";

import { useResidentContext } from "@/lib/billing/resident-context";
import { PageBreadcrumb } from "@/components/shell/page-breadcrumb";

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

type ListState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; invoices: InvoiceResponse[] };

const LOADING: ListState = { status: "loading" };

export function InvoiceList({ accessToken }: { accessToken: string }) {
  const router = useRouter();
  const { context, enter } = useResidentContext();
  const residentContextId = context?.id ?? null;
  const requestKey = residentContextId ?? "manager";
  const [resolved, setResolved] = useState<{
    key: string;
    state: ListState;
  } | null>(null);
  const state = resolved?.key === requestKey ? resolved.state : LOADING;

  useEffect(() => {
    let ignore = false;

    void listInvoices(
      accessToken,
      {},
      { baseUrl: apiUrl, residentContextId },
    )
      .then((response) => {
        if (!ignore) {
          setResolved({
            key: requestKey,
            state: { status: "ready", invoices: response.items },
          });
        }
      })
      .catch(() => {
        if (!ignore) {
          setResolved({ key: requestKey, state: { status: "error" } });
        }
      });

    return () => {
      ignore = true;
    };
  }, [accessToken, residentContextId, requestKey]);

  const impersonate = useCallback(
    async (invoice: InvoiceResponse) => {
      await enter(invoice.unitId);
      router.push(`/invoices/${invoice.id}`);
    },
    [enter, router],
  );

  return (
    <div className="invoice-list-page">
      <header className="dashboard-heading">
        <div>
          <PageBreadcrumb section="Faturamento" current="Faturas" />
          <h1>Faturas</h1>
          <p>
            Cada fatura é imutável depois de emitida e explica a si mesma, linha
            por linha.
          </p>
        </div>
      </header>

      {state.status === "loading" ? (
        <p className="invoice-status">Carregando faturas…</p>
      ) : null}
      {state.status === "error" ? (
        <p className="invoice-status error">
          Não foi possível carregar as faturas.
        </p>
      ) : null}
      {state.status === "ready" && state.invoices.length === 0 ? (
        <section className="invoice-block">
          <p className="invoice-empty">
            Nenhuma fatura emitida ainda. Elas aparecem aqui depois que um
            período é aprovado no fechamento.
          </p>
        </section>
      ) : null}

      {state.status === "ready" && state.invoices.length > 0 ? (
        <section className="invoice-block" aria-labelledby="invoice-list-title">
          <div className="dashboard-section-heading">
            <h2 id="invoice-list-title">Faturas emitidas</h2>
            <span>{state.invoices.length} unidades</span>
          </div>
          <div className="responsible-table-frame">
            <table aria-label="Faturas emitidas">
              <thead>
                <tr>
                  <th>Período</th>
                  <th>Unidade</th>
                  <th>Responsável</th>
                  <th>Energia</th>
                  <th>Total</th>
                  <th>Fatura</th>
                </tr>
              </thead>
              <tbody>
                {state.invoices.map((invoice) => (
                  <tr key={invoice.id}>
                    <td>{invoice.periodValue}</td>
                    <td>{invoice.unitCode}</td>
                    <td>{invoice.contactLabel}</td>
                    <td>{formatKwh(invoice.energyKwh)}</td>
                    <td>{formatCents(invoice.totalCents)}</td>
                    <td className="invoice-row-actions">
                      <Link href={`/invoices/${invoice.id}`}>Abrir</Link>
                      {context === null ? (
                        <button
                          type="button"
                          onClick={() => void impersonate(invoice)}
                        >
                          Ver como morador
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
