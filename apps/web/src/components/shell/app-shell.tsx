"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const operationalDestinations = [
  { href: "/dashboard", label: "Visão geral" },
  { href: "/sessions", label: "Recargas" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="app-shell">
      <aside className="product-rail">
        <div className="product-identity">
          <span className="product-signal" aria-hidden="true" />
          <div>
            <p className="product-name">EV ChargeOps</p>
            <p className="product-scope">LAB FIAP · Gestão</p>
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

        <nav aria-label="Configurações" className="secondary-navigation">
          <p className="navigation-label">Configurações</p>
          <Link
            href="/settings/data-sources"
            aria-current={
              pathname === "/settings/data-sources" ? "page" : undefined
            }
            className={`nav-link secondary${pathname === "/settings/data-sources" ? " active" : ""}`}
          >
            Fontes de dados
          </Link>
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
            <p className="dashboard-site-name">LAB FIAP Eco Smart Home</p>
            <p className="dashboard-site-meta">
              Gestão condominial · 1 carregador
            </p>
          </div>
          <div className="manager-context">
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
          </div>
        </header>
        <main className="app-workspace-content">{children}</main>
      </div>
    </div>
  );
}
