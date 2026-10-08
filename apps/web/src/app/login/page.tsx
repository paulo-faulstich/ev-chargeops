"use client";

import Image from "next/image";
import { useActionState } from "react";

import { login, type LoginState } from "./actions";

const initialState: LoginState = { error: null };

export default function LoginPage() {
  const [state, action, pending] = useActionState(login, initialState);

  return (
    <main className="login-layout">
      <section className="login-intro" aria-labelledby="login-title">
        <p className="login-eyebrow">Operação de recarga compartilhada</p>
        <div className="login-mark" aria-hidden="true" />
        <h1 id="login-title">EV ChargeOps</h1>
        <p className="login-lede">
          Ferramenta de gestão de recarga em garagens compartilhadas: lê as
          recargas do carregador, atribui cada uma à unidade responsável e emite
          a fatura do mês.
        </p>

        <div className="login-source">
          <p className="login-source-label">Dados de recarga</p>
          <Image
            src="/brands/goodwe-logo.svg"
            width={196}
            height={29}
            alt="GoodWe: Smart Energy Innovator"
            priority
          />
          <p className="login-source-note">
            Carregador GoodWe HCA G2 no LAB FIAP Eco Smart Home, lido pelo SEMS+.
          </p>
        </div>
      </section>

      <aside className="login-panel" aria-label="Acesso à plataforma">
        <div className="login-panel-inner">
          <h2 className="login-panel-title">Entrar</h2>
          <p className="login-panel-note">
            Acesso restrito à administração do condomínio.
          </p>

          <form action={action} className="login-form">
            <label htmlFor="email">E-mail</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
            />

            <label htmlFor="password">Senha</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />

            {state.error ? (
              <p role="alert" className="form-error">
                {state.error}
              </p>
            ) : null}

            <button type="submit" disabled={pending}>
              {pending ? "Entrando…" : "Entrar"}
            </button>
          </form>
        </div>
      </aside>
    </main>
  );
}
