"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { logout } from "@/app/(app)/actions";

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
            <div className="product-partnership">
              <span>FIAP Challenge</span>
              <span aria-hidden="true">×</span>
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
