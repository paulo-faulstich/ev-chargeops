"use client";

import { useActionState } from "react";

import { login, type LoginState } from "./actions";

const initialState: LoginState = { error: null };

export default function LoginPage() {
  const [state, action, pending] = useActionState(login, initialState);

  return (
    <main className="login-layout">
      <section className="login-intro" aria-labelledby="login-title">
        <p className="utility-label">Operação de recarga compartilhada</p>
        <div className="login-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <h1 id="login-title">Entrar no EV ChargeOps</h1>
        <p className="login-lede">
          Acesse o fechamento auditável de sessões, atribuições e custos do
          condomínio.
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

          {state.error ? <p role="alert" className="form-error">{state.error}</p> : null}

          <button type="submit" disabled={pending}>
            {pending ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </section>

      <aside className="login-context" aria-label="Fluxo operacional">
        <span className="context-index">01—04</span>
        <p>Evidência confiável antes de qualquer fechamento.</p>
      </aside>
    </main>
  );
}
