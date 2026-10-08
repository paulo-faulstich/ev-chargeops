"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

import { logout } from "@/app/(app)/actions";
import {
  ResidentBanner,
  useResidentContext,
} from "@/lib/billing/resident-context";

const operationalDestinations = [
  { href: "/dashboard", label: "Visão geral" },
  { href: "/sessions", label: "Recargas" },
  { href: "/charging-cards", label: "Cartões" },
];

/** Closing is a monthly decision, not daily monitoring.
 *
 * It approves, emits documents and records who signed, so it lives apart from
 * the screens the manager checks in passing.
 */
const settingsDestinations = [
  { href: "/settings/data-sources", label: "Fontes de dados" },
];

const billingDestinations = [
  { href: "/closing", label: "Fechamento" },
  { href: "/invoices", label: "Faturas" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { context: residentContext, exit: exitResidentContext } =
    useResidentContext();
  // An invoice opened from the closing keeps the reader inside that task, so
  // the rail must not claim they left it for the invoice list.
  const openedFromClosing =
    pathname.startsWith("/invoices/") && searchParams.get("from") === "closing";

  function isCurrent(href: string): boolean {
    if (openedFromClosing) return href === "/closing";
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  return (
    <div className={`app-shell${residentContext ? " resident-view" : ""}`}>
      {/* Outside the workspace on purpose: the warning is about the whole
          session, so it has to cross the rail too, and the shell reserves the
          room for it. */}
      {residentContext ? (
        <ResidentBanner context={residentContext} onExit={exitResidentContext} />
      ) : null}
      <aside className="product-rail">
        <div className="product-identity">
          <span className="product-signal" aria-hidden="true" />
          <div>
            <p className="product-name">EV ChargeOps</p>
            <div className="product-partnership">
              <span className="product-partner-name">FIAP Challenge</span>
              <span className="product-partner-cross" aria-hidden="true">
                ×
              </span>
              <Image
                src="/brands/goodwe-logo.svg"
                width={74}
                height={11}
                alt="GoodWe: Smart Energy Innovator"
                priority
              />
            </div>
          </div>
        </div>

        <nav aria-label="Operação" className="primary-navigation">
          <p className="navigation-label">Operação</p>
          {operationalDestinations.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              aria-current={pathname === href ? "page" : undefined}
              className={`nav-link${pathname === href ? " active" : ""}`}
            >
              {label}
            </Link>
          ))}
        </nav>

        <nav aria-label="Faturamento" className="primary-navigation">
          <p className="navigation-label">Faturamento</p>
          {billingDestinations.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              aria-current={isCurrent(href) ? "page" : undefined}
              className={`nav-link${isCurrent(href) ? " active" : ""}`}
            >
              {label}
            </Link>
          ))}
        </nav>

        <nav aria-label="Configurações" className="secondary-navigation">
          <p className="navigation-label">Configurações</p>
          {settingsDestinations.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              aria-current={pathname === href ? "page" : undefined}
              className={`nav-link secondary${pathname === href ? " active" : ""}`}
            >
              {label}
            </Link>
          ))}
        </nav>

        <div className="rail-status">
          <span className="status-pulse" aria-hidden="true" />
          <div>
            <span className="utility-label">Ambiente</span>
            <p>Operação protegida</p>
          </div>
        </div>
      </aside>

      <div className="app-workspace">
        <header className="app-workspace-header">
          <div>
            <p className="dashboard-site-name">Powered by GoodWe / SEMS+</p>
            <p className="dashboard-site-meta">
              Instalação: LAB FIAP Eco Smart Home · 1 carregador
            </p>
          </div>
          <details className="manager-menu">
            <summary
              className="manager-context"
              role="button"
              aria-label="Abrir menu de Paulo Faulstich"
            >
              <div>
                <span>Administrador</span>
                <strong>Paulo Faulstich</strong>
              </div>
              <span
                className="manager-avatar"
                aria-label="Administrador Paulo Faulstich"
              >
                PF
              </span>
              <span className="manager-menu-chevron" aria-hidden="true">
                ▾
              </span>
            </summary>
            <div
              className="manager-popover"
              role="menu"
              aria-label="Perfil do usuário"
            >
              <div className="manager-popover-identity">
                <span className="utility-label">Conta ativa</span>
                <strong>Paulo Faulstich</strong>
                <span>Administrador do condomínio</span>
              </div>
              <form action={logout}>
                <button type="submit" role="menuitem">
                  <span>Sair</span>
                  <span aria-hidden="true">→</span>
                </button>
              </form>
            </div>
          </details>
        </header>
        <main className="app-workspace-content">{children}</main>
      </div>
    </div>
  );
}
