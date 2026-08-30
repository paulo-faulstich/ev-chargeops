"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from "react";
import {
  assignSession,
  listAssignmentUnits,
  listSessions,
  type AssignmentUnitResponse,
  type SessionResponse,
} from "@ev-chargeops/api-client";

import {
  formatQueueDate,
  formatSessionDate,
  formatSessionDuration,
  formatSessionEnergy,
  formatSessionPeriod,
} from "./session-formatters";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api";

type ReviewData = {
  allSessions: SessionResponse[];
  pendingSessions: SessionResponse[];
  units: AssignmentUnitResponse[];
};

type ReviewState =
  | { status: "loading"; data: null }
  | { status: "error"; data: null }
  | { status: "ready"; data: ReviewData };

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

function isPeriod(value: string | null): value is string {
  return value !== null && /^\d{4}-(0[1-9]|1[0-2])$/.test(value);
}

function pendingCountLabel(count: number): string {
  return `${count} ${count === 1 ? "pendência" : "pendências"} no período`;
}

function provenanceLabel(session: SessionResponse): string {
  const provenance = session.provenance === "observed" ? "Observada" : session.provenance;
  const source = session.source === "sems_export" ? "SEMS+ CSV" : session.source;
  return `${provenance} · ${source}`;
}

async function loadReviewData(
  accessToken: string,
  period: string,
): Promise<ReviewData> {
  const [pendingResponse, allResponse, unitResponse] = await Promise.all([
    listSessions(accessToken, { period, status: "pending_review" }, apiUrl),
    listSessions(accessToken, { period }, apiUrl),
    listAssignmentUnits(accessToken, apiUrl),
  ]);

  return {
    allSessions: allResponse.items,
    pendingSessions: pendingResponse.items,
    units: unitResponse.items,
  };
}

export function SessionReview({ accessToken }: { accessToken: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const period = isPeriod(searchParams.get("period"))
    ? searchParams.get("period")!
    : currentPeriod();
  const [state, setState] = useState<ReviewState>({ status: "loading", data: null });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [unitId, setUnitId] = useState("");
  const [justification, setJustification] = useState("");
  const [submissionState, setSubmissionState] = useState<
    "idle" | "submitting" | "error"
  >("idle");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [refreshGeneration, setRefreshGeneration] = useState(0);

  useEffect(() => {
    let ignore = false;

    void loadReviewData(accessToken, period)
      .then((data) => {
        if (ignore) return;
        setState({ status: "ready", data });
        setSelectedId((current) =>
          data.pendingSessions.some((session) => session.id === current)
            ? current
            : (data.pendingSessions[0]?.id ?? null),
        );
      })
      .catch(() => {
        if (!ignore) setState({ status: "error", data: null });
      });

    return () => {
      ignore = true;
    };
  }, [accessToken, period, refreshGeneration]);

  const selectedSession = useMemo(() => {
    if (state.status !== "ready") return null;
    return (
      state.data.pendingSessions.find((session) => session.id === selectedId) ??
      state.data.pendingSessions[0] ??
      null
    );
  }, [selectedId, state]);

  const selectedUnit =
    state.status === "ready"
      ? state.data.units.find((unit) => unit.id === unitId)
      : undefined;

  function selectSession(sessionId: string) {
    setSelectedId(sessionId);
    setUnitId("");
    setJustification("");
    setSubmissionState("idle");
    setSuccessMessage(null);
  }

  function handleRowKeyDown(
    event: KeyboardEvent<HTMLTableRowElement>,
    sessionId: string,
  ) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    selectSession(sessionId);
  }

  async function handleAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSession || !selectedUnit || justification.trim() === "") return;

    setSubmissionState("submitting");
    setSuccessMessage(null);

    try {
      await assignSession(
        selectedSession.id,
        { unitId: selectedUnit.id, justification: justification.trim() },
        accessToken,
        apiUrl,
      );

      if (state.status !== "ready") return;
      const selectedIndex = state.data.pendingSessions.findIndex(
        (session) => session.id === selectedSession.id,
      );
      const remainingSessions = state.data.pendingSessions.filter(
        (session) => session.id !== selectedSession.id,
      );
      const nextSession =
        remainingSessions[Math.min(selectedIndex, remainingSessions.length - 1)] ?? null;

      setState({
        status: "ready",
        data: {
          ...state.data,
          allSessions: state.data.allSessions.map((session) =>
            session.id === selectedSession.id
              ? { ...session, status: "ready", unitId: selectedUnit.id }
              : session,
          ),
          pendingSessions: remainingSessions,
        },
      });
      setSelectedId(nextSession?.id ?? null);
      setUnitId("");
      setJustification("");
      setSubmissionState("idle");
      setSuccessMessage(
        `Sessão atribuída à ${selectedUnit.displayName}. ${
          remainingSessions.length === 1
            ? "Resta 1 sessão para revisar."
            : `Restam ${remainingSessions.length} sessões para revisar.`
        }`,
      );
    } catch {
      setSubmissionState("error");
    }
  }

  function updatePeriod(nextPeriod: string) {
    if (!isPeriod(nextPeriod)) return;
    setState({ status: "loading", data: null });
    setSelectedId(null);
    setUnitId("");
    setJustification("");
    setSubmissionState("idle");
    setSuccessMessage(null);
    router.replace(`/sessions?status=pending_review&period=${nextPeriod}`);
  }

  return (
    <div className="session-review-page">
      <header className="session-review-header">
        <div>
          <p className="utility-label">Fechamento mensal · atribuições</p>
          <h1>Sessões</h1>
          <p>Revise a evidência importada e indique a unidade responsável.</p>
        </div>
        <Link href="/dashboard" className="session-back-link">
          <span aria-hidden="true">←</span>
          Voltar para visão geral
        </Link>
      </header>

      <div className="session-review-context">
        <div>
          <span className="session-context-label">Período observado</span>
          <strong>{formatSessionPeriod(period)}</strong>
        </div>
        <label>
          <span>Filtrar período</span>
          <input
            type="month"
            value={period}
            onChange={(event) => updatePeriod(event.target.value)}
          />
        </label>
        <p className="session-pending-count">
          {state.status === "ready"
            ? pendingCountLabel(state.data.pendingSessions.length)
            : "Consultando pendências"}
        </p>
      </div>

      {successMessage ? (
        <div className="session-success" role="status">
          <span aria-hidden="true">✓</span>
          {successMessage}
        </div>
      ) : null}

      {state.status === "loading" ? <SessionLoading /> : null}
      {state.status === "error" ? (
        <SessionLoadError
          onRetry={() => {
            setState({ status: "loading", data: null });
            setRefreshGeneration((generation) => generation + 1);
          }}
        />
      ) : null}
      {state.status === "ready" && state.data.allSessions.length === 0 ? (
        <NoImportedSessions />
      ) : null}
      {state.status === "ready" &&
      state.data.allSessions.length > 0 &&
      state.data.pendingSessions.length === 0 ? (
        <NoPendingSessions period={period} />
      ) : null}
      {state.status === "ready" && selectedSession ? (
        <div className="session-review-grid">
          <SessionQueue
            sessions={state.data.pendingSessions}
            selectedId={selectedSession.id}
            onSelect={selectSession}
            onKeyDown={handleRowKeyDown}
          />
          <SessionDecision
            session={selectedSession}
            units={state.data.units}
            unitId={unitId}
            justification={justification}
            selectedUnit={selectedUnit}
            submissionState={submissionState}
            onUnitChange={setUnitId}
            onJustificationChange={setJustification}
            onSubmit={handleAssignment}
          />
        </div>
      ) : null}
    </div>
  );
}

function SessionLoading() {
  return (
    <div className="session-state-panel" role="status">
      <span className="session-state-line" aria-hidden="true" />
      <div>
        <p className="utility-label">Lendo evidências</p>
        <p>Carregando sessões e unidades disponíveis…</p>
      </div>
    </div>
  );
}

function SessionLoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="session-state-panel session-load-error" role="alert">
      <div>
        <p className="utility-label">Dados indisponíveis</p>
        <p>As sessões e unidades não foram carregadas. Tente novamente.</p>
      </div>
      <button type="button" onClick={onRetry}>
        Atualizar fila
      </button>
    </div>
  );
}

function NoImportedSessions() {
  return (
    <section className="session-empty-panel" aria-labelledby="no-sessions-title">
      <p className="utility-label">Sem evidência no período</p>
      <h2 id="no-sessions-title">Nenhuma sessão importada.</h2>
      <p>Importe o arquivo do carregador antes de atribuir responsabilidades.</p>
      <Link href="/settings/data-sources">Ir para fontes de dados</Link>
    </section>
  );
}

function NoPendingSessions({ period }: { period: string }) {
  return (
    <section className="session-empty-panel complete" aria-labelledby="no-pending-title">
      <p className="utility-label">Revisão concluída</p>
      <h2 id="no-pending-title">Todas as sessões do período foram atribuídas.</h2>
      <p>{formatSessionPeriod(period)} não possui pendências de responsabilidade.</p>
      <Link href="/dashboard">Voltar para visão geral</Link>
    </section>
  );
}

function SessionQueue({
  sessions,
  selectedId,
  onSelect,
  onKeyDown,
}: {
  sessions: SessionResponse[];
  selectedId: string;
  onSelect: (sessionId: string) => void;
  onKeyDown: (
    event: KeyboardEvent<HTMLTableRowElement>,
    sessionId: string,
  ) => void;
}) {
  return (
    <section className="session-queue" aria-labelledby="session-queue-title">
      <div className="session-panel-heading">
        <div>
          <p className="utility-label">Fila pendente</p>
          <h2 id="session-queue-title">Evidências observadas</h2>
        </div>
        <span>{sessions.length}</span>
      </div>
      <div className="session-queue-table-frame">
        <table aria-label="Sessões pendentes">
          <thead>
            <tr>
              <th>Início</th>
              <th>Energia</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((session) => {
              const selected = session.id === selectedId;
              return (
                <tr
                  key={session.id}
                  aria-selected={selected}
                  className={selected ? "selected" : undefined}
                  tabIndex={0}
                  onClick={() => onSelect(session.id)}
                  onKeyDown={(event) => onKeyDown(event, session.id)}
                >
                  <td>
                    <span>{formatQueueDate(session.startedAt)}</span>
                    <small>Pendente de atribuição</small>
                  </td>
                  <td>{formatSessionEnergy(session.energyKwh)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SessionDecision({
  session,
  units,
  unitId,
  justification,
  selectedUnit,
  submissionState,
  onUnitChange,
  onJustificationChange,
  onSubmit,
}: {
  session: SessionResponse;
  units: AssignmentUnitResponse[];
  unitId: string;
  justification: string;
  selectedUnit: AssignmentUnitResponse | undefined;
  submissionState: "idle" | "submitting" | "error";
  onUnitChange: (value: string) => void;
  onJustificationChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="session-decision" aria-labelledby="session-decision-title">
      <div className="session-panel-heading decision-heading">
        <div>
          <p className="utility-label">Sessão selecionada</p>
          <h2 id="session-decision-title">Evidência e decisão</h2>
        </div>
        <span className="session-record-key">#{session.id.slice(-6)}</span>
      </div>

      <section className="session-evidence" aria-label="Evidência da sessão">
        <div className="evidence-primary">
          <span>Energia observada</span>
          <strong>{formatSessionEnergy(session.energyKwh)}</strong>
        </div>
        <dl>
          <div>
            <dt>Início</dt>
            <dd>{formatSessionDate(session.startedAt)}</dd>
          </div>
          <div>
            <dt>Fim</dt>
            <dd>{formatSessionDate(session.endedAt)}</dd>
          </div>
          <div>
            <dt>Duração</dt>
            <dd>{formatSessionDuration(session.startedAt, session.endedAt)}</dd>
          </div>
          <div>
            <dt>Carregador</dt>
            <dd>{session.chargerSerial}</dd>
          </div>
          <div className="evidence-provenance">
            <dt>Proveniência</dt>
            <dd>{provenanceLabel(session)}</dd>
          </div>
        </dl>
        <p className="immutable-note">
          <span aria-hidden="true">◇</span>
          Evidência importada: horário, energia e origem não são alterados pela atribuição.
        </p>
      </section>

      <form className="session-assignment-form" onSubmit={onSubmit}>
        <div className="decision-rule">
          <span>Decisão auditável</span>
          <span aria-hidden="true" />
        </div>
        <label htmlFor="session-unit">Unidade responsável</label>
        <select
          id="session-unit"
          required
          value={unitId}
          onChange={(event) => onUnitChange(event.target.value)}
        >
          <option value="">Selecione uma unidade</option>
          {units.map((unit) => (
            <option key={unit.id} value={unit.id}>
              {unit.displayName}
              {unit.residentName ? ` · ${unit.residentName}` : ""}
            </option>
          ))}
        </select>
        <p className="field-context">
          {selectedUnit
            ? selectedUnit.residentName
              ? `${selectedUnit.displayName} · ${selectedUnit.residentName}`
              : `${selectedUnit.displayName} · morador não informado`
            : "A unidade será usada no fechamento financeiro desta sessão."}
        </p>

        <label htmlFor="session-justification">Justificativa</label>
        <textarea
          id="session-justification"
          required
          maxLength={500}
          rows={4}
          value={justification}
          onChange={(event) => onJustificationChange(event.target.value)}
          placeholder="Registre como a responsabilidade foi confirmada"
        />
        <div className="justification-meta">
          <span>Obrigatória para auditoria</span>
          <span>{justification.length}/500</span>
        </div>

        {submissionState === "error" ? (
          <p className="session-submit-error" role="alert">
            A atribuição não foi salva. Revise os dados e tente novamente.
          </p>
        ) : null}

        <button type="submit" disabled={submissionState === "submitting"}>
          {submissionState === "submitting"
            ? "Atribuindo sessão…"
            : "Atribuir e revisar próxima"}
          <span aria-hidden="true">→</span>
        </button>
      </form>
    </section>
  );
}
