"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  assignSession,
  listAssignmentUnits,
  listBillingPeriods,
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
import { PageBreadcrumb } from "@/components/shell/page-breadcrumb";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api";

type ReviewData = {
  allSessions: SessionResponse[];
  pendingSessions: SessionResponse[];
  units: AssignmentUnitResponse[];
};

type ReviewState =
  | { status: "loading"; data: null; period: string }
  | { status: "error"; data: null; period: string }
  | { status: "ready"; data: ReviewData; period: string };

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

/** The month to land on when the URL names none.
 *
 * The calendar month is a poor default: it is routinely empty while the
 * operation is still closing an earlier one, and the screen then reports
 * "nothing imported" about a period nobody was looking at. The billing
 * periods say which month the operation is actually working on.
 */
async function resolveDefaultPeriod(accessToken: string): Promise<string> {
  try {
    const periods = await listBillingPeriods(accessToken, { baseUrl: apiUrl });
    const latest = periods.items
      .map((period) => period.periodValue)
      .sort((left, right) => right.localeCompare(left))[0];
    return latest ?? currentPeriod();
  } catch {
    return currentPeriod();
  }
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
  const requestedPeriod = searchParams.get("period");
  const requestedStatus = searchParams.get("status");
  // Resolved asynchronously, so the URL is only canonicalised once the target
  // month is known; redirecting twice would flash the wrong period.
  const [defaultPeriod, setDefaultPeriod] = useState<string | null>(null);
  const period = isPeriod(requestedPeriod)
    ? requestedPeriod
    : (defaultPeriod ?? currentPeriod());
  const defaultResolved = isPeriod(requestedPeriod) || defaultPeriod !== null;
  const filtersCanonical =
    requestedPeriod === period && requestedStatus === "pending_review";
  const canonicalUrl = `/sessions?status=pending_review&period=${period}`;
  const [state, setState] = useState<ReviewState>({
    status: "loading",
    data: null,
    period,
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [unitId, setUnitId] = useState("");
  const [justification, setJustification] = useState("");
  const [submissionState, setSubmissionState] = useState<
    "idle" | "submitting" | "error"
  >("idle");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [refreshGeneration, setRefreshGeneration] = useState(0);
  const [interactionPeriod, setInteractionPeriod] = useState(period);
  const loadRequestId = useRef(0);
  const assignmentRequestId = useRef(0);
  const currentContext = useRef({ period, selectedId });
  const isCurrentInteraction = interactionPeriod === period;
  const isSubmitting =
    isCurrentInteraction && submissionState === "submitting";

  useEffect(() => {
    if (isPeriod(requestedPeriod)) return;
    let ignore = false;
    void resolveDefaultPeriod(accessToken).then((resolved) => {
      if (!ignore) setDefaultPeriod(resolved);
    });
    return () => {
      ignore = true;
    };
  }, [accessToken, requestedPeriod]);

  useEffect(() => {
    if (!defaultResolved) return;
    if (!filtersCanonical) router.replace(canonicalUrl);
  }, [canonicalUrl, defaultResolved, filtersCanonical, router]);

  useEffect(() => {
    currentContext.current = { period, selectedId };
  }, [period, selectedId]);

  useEffect(() => {
    const requestId = ++loadRequestId.current;
    if (!filtersCanonical) return;
    let ignore = false;

    void loadReviewData(accessToken, period)
      .then((data) => {
        if (ignore || requestId !== loadRequestId.current) return;
        setState({ status: "ready", data, period });
        setInteractionPeriod(period);
        setUnitId("");
        setJustification("");
        setSubmissionState("idle");
        setSuccessMessage(null);
        setSelectedId((current) =>
          data.pendingSessions.some((session) => session.id === current)
            ? current
            : (data.pendingSessions[0]?.id ?? null),
        );
      })
      .catch(() => {
        if (ignore || requestId !== loadRequestId.current) return;
        setState({ status: "error", data: null, period });
        setInteractionPeriod(period);
        setUnitId("");
        setJustification("");
        setSubmissionState("idle");
        setSuccessMessage(null);
      });

    return () => {
      ignore = true;
    };
  }, [accessToken, filtersCanonical, period, refreshGeneration]);

  const selectedSession = useMemo(() => {
    if (
      !filtersCanonical ||
      state.status !== "ready" ||
      state.period !== period
    ) {
      return null;
    }
    return (
      state.data.pendingSessions.find((session) => session.id === selectedId) ??
      state.data.pendingSessions[0] ??
      null
    );
  }, [filtersCanonical, period, selectedId, state]);

  const selectedUnit =
    isCurrentInteraction && state.status === "ready" && state.period === period
      ? state.data.units.find((unit) => unit.id === unitId)
      : undefined;

  function selectSession(sessionId: string) {
    if (isSubmitting) return;
    setSelectedId(sessionId);
    setUnitId("");
    setJustification("");
    setSubmissionState("idle");
    setSuccessMessage(null);
  }

  async function handleAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSession || !selectedUnit || justification.trim() === "") return;

    setSubmissionState("submitting");
    setSuccessMessage(null);
    const requestId = ++assignmentRequestId.current;
    const submittedLoadRequestId = loadRequestId.current;
    const submittedPeriod = period;
    const submittedSessionId = selectedSession.id;

    try {
      await assignSession(
        selectedSession.id,
        { unitId: selectedUnit.id, justification: justification.trim() },
        accessToken,
        apiUrl,
      );

      if (
        requestId !== assignmentRequestId.current ||
        loadRequestId.current !== submittedLoadRequestId ||
        currentContext.current.period !== submittedPeriod ||
        currentContext.current.selectedId !== submittedSessionId ||
        state.status !== "ready" ||
        state.period !== submittedPeriod
      ) {
        return;
      }
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
        period: submittedPeriod,
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
        `Recarga atribuída à ${selectedUnit.displayName}. ${
          remainingSessions.length === 1
            ? "Resta 1 recarga para revisar."
            : `Restam ${remainingSessions.length} recargas para revisar.`
        }`,
      );
    } catch {
      if (
        requestId !== assignmentRequestId.current ||
        loadRequestId.current !== submittedLoadRequestId ||
        currentContext.current.period !== submittedPeriod ||
        currentContext.current.selectedId !== submittedSessionId
      ) {
        return;
      }
      setSubmissionState("error");
    }
  }

  function updatePeriod(nextPeriod: string) {
    if (isSubmitting || !isPeriod(nextPeriod)) return;
    setState({ status: "loading", data: null, period: nextPeriod });
    setInteractionPeriod(nextPeriod);
    setSelectedId(null);
    setUnitId("");
    setJustification("");
    setSubmissionState("idle");
    setSuccessMessage(null);
    router.replace(`/sessions?status=pending_review&period=${nextPeriod}`);
  }

  const displayState: ReviewState =
    filtersCanonical && state.period === period
      ? state
      : { status: "loading", data: null, period };

  return (
    <div className="session-review-page">
      <header className="session-review-header">
        <div>
          <PageBreadcrumb section="Operação" current="Recargas" />
          <h1>Recargas</h1>
          <p>
            Cada recarga registra início, duração, energia consumida e o
            responsável pelo custo.
          </p>
        </div>
        <Link href="/dashboard" className="session-back-link">
          <span aria-hidden="true">←</span>
          Voltar para Visão geral
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
            disabled={isSubmitting}
            onChange={(event) => updatePeriod(event.target.value)}
          />
        </label>
        <p className="session-pending-count">
          {displayState.status === "ready"
            ? pendingCountLabel(displayState.data.pendingSessions.length)
            : "Consultando pendências"}
        </p>
      </div>

      {successMessage ? (
        <div className="session-success" role="status">
          <span aria-hidden="true">✓</span>
          {successMessage}
        </div>
      ) : null}

      {displayState.status === "loading" ? <SessionLoading /> : null}
      {displayState.status === "error" ? (
        <SessionLoadError
          onRetry={() => {
            setState({ status: "loading", data: null, period });
            setRefreshGeneration((generation) => generation + 1);
          }}
        />
      ) : null}
      {displayState.status === "ready" && displayState.data.allSessions.length === 0 ? (
        <NoImportedSessions />
      ) : null}
      {displayState.status === "ready" &&
      displayState.data.allSessions.length > 0 &&
      displayState.data.pendingSessions.length === 0 ? (
        <NoPendingSessions period={period} />
      ) : null}
      {displayState.status === "ready" &&
      displayState.data.allSessions.length > 0 ? (
        <SessionLedger sessions={displayState.data.allSessions} />
      ) : null}
      {displayState.status === "ready" && selectedSession ? (
        <div className="session-review-grid">
          <SessionQueue
            sessions={displayState.data.pendingSessions}
            selectedId={selectedSession.id}
            disabled={isSubmitting}
            onSelect={selectSession}
          />
          <SessionDecision
            session={selectedSession}
            units={displayState.data.units}
            unitId={isCurrentInteraction ? unitId : ""}
            justification={isCurrentInteraction ? justification : ""}
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
        <p>Carregando recargas e unidades disponíveis…</p>
      </div>
    </div>
  );
}

function SessionLoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="session-state-panel session-load-error" role="alert">
      <div>
        <p className="utility-label">Dados indisponíveis</p>
        <p>As recargas e unidades não foram carregadas. Tente novamente.</p>
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
      <h2 id="no-sessions-title">Nenhuma recarga importada.</h2>
      <p>Importe o arquivo do carregador antes de atribuir responsabilidades.</p>
      <Link href="/settings/data-sources">Ir para fontes de dados</Link>
    </section>
  );
}

function NoPendingSessions({ period }: { period: string }) {
  return (
    <section className="session-empty-panel complete" aria-labelledby="no-pending-title">
      <p className="utility-label">Revisão concluída</p>
      <h2 id="no-pending-title">Todas as recargas do período foram atribuídas.</h2>
      <p>{formatSessionPeriod(period)} não possui pendências de responsabilidade.</p>
    </section>
  );
}

/** Every charging session in the period, attributed or not.
 *
 * The review queue only ever holds what still needs a decision, so without
 * this the screen goes blank exactly when the operation is healthy — and the
 * evidence the whole product rests on becomes impossible to look at.
 */
function SessionLedger({ sessions }: { sessions: SessionResponse[] }) {
  const ordered = [...sessions].sort((left, right) =>
    right.startedAt.localeCompare(left.startedAt),
  );

  return (
    <section className="session-ledger" aria-labelledby="session-ledger-title">
      <div className="session-panel-heading">
        <div>
          <p className="utility-label">Evidência do período</p>
          <h2 id="session-ledger-title">Recargas do período</h2>
        </div>
        <span>{ordered.length}</span>
      </div>
      <div className="responsible-table-frame">
        <table aria-label="Recargas do período">
          <thead>
            <tr>
              <th scope="col">Início</th>
              <th scope="col">Duração</th>
              <th scope="col">Energia</th>
              <th scope="col">Responsável</th>
              <th scope="col">Como foi atribuída</th>
              <th scope="col">Procedência</th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((session) => (
              <tr key={session.id}>
                <td>{formatSessionDate(session.startedAt)}</td>
                <td>
                  {formatSessionDuration(session.startedAt, session.endedAt)}
                </td>
                <td>{formatSessionEnergy(session.energyKwh)}</td>
                <td>
                  {session.unitCode ? (
                    <span className="assigned">
                      {session.unitName ?? `Unidade ${session.unitCode}`}
                    </span>
                  ) : (
                    <span className="pending">Não atribuído</span>
                  )}
                </td>
                <td>
                  {/* A charge that resolved itself and one a manager decided
                      are both legitimate, and must not look alike. */}
                  {session.assignmentOrigin === "card" ? (
                    <span className="origin-card">Cartão registrado</span>
                  ) : session.assignmentOrigin === "manual" ? (
                    <span className="origin-manual">Decisão do gestor</span>
                  ) : (
                    <span className="pending">Aguarda decisão</span>
                  )}
                </td>
                <td>{provenanceLabel(session)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SessionQueue({
  sessions,
  selectedId,
  disabled,
  onSelect,
}: {
  sessions: SessionResponse[];
  selectedId: string;
  disabled: boolean;
  onSelect: (sessionId: string) => void;
}) {
  const buttonRefs = useRef(new Map<string, HTMLButtonElement>());

  function handleQueueKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) {
    let nextIndex: number | null = null;
    if (event.key === "ArrowDown") {
      nextIndex = Math.min(index + 1, sessions.length - 1);
    } else if (event.key === "ArrowUp") {
      nextIndex = Math.max(index - 1, 0);
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = sessions.length - 1;
    }
    if (nextIndex === null) return;

    event.preventDefault();
    const nextSession = sessions[nextIndex];
    onSelect(nextSession.id);
    buttonRefs.current.get(nextSession.id)?.focus();
  }

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
        <table aria-label="Recargas pendentes">
          <thead>
            <tr>
              <th id="session-start-heading" scope="col">Início</th>
              <th id="session-energy-heading" scope="col">Energia</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((session, index) => {
              const selected = session.id === selectedId;
              return (
                <tr
                  key={session.id}
                  className={selected ? "selected" : undefined}
                >
                  <td headers="session-start-heading">
                    <span>{formatQueueDate(session.startedAt)}</span>
                    <small>Pendente de atribuição</small>
                    <button
                      type="button"
                      ref={(button) => {
                        if (button) buttonRefs.current.set(session.id, button);
                        else buttonRefs.current.delete(session.id);
                      }}
                      aria-label={`Revisar recarga iniciada em ${formatQueueDate(session.startedAt)}, ${formatSessionEnergy(session.energyKwh)}, pendente de atribuição`}
                      aria-pressed={selected}
                      disabled={disabled}
                      tabIndex={selected ? 0 : -1}
                      onClick={() => onSelect(session.id)}
                      onKeyDown={(event) => handleQueueKeyDown(event, index)}
                    />
                  </td>
                  <td headers="session-energy-heading">
                    {formatSessionEnergy(session.energyKwh)}
                  </td>
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
          <p className="utility-label">Recarga selecionada</p>
          <h2 id="session-decision-title">Evidência e decisão</h2>
        </div>
        <span className="session-record-key">#{session.id.slice(-6)}</span>
      </div>

      <section className="session-evidence" aria-label="Evidência da recarga">
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
          disabled={submissionState === "submitting"}
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
            : "A unidade será usada no fechamento financeiro desta recarga."}
        </p>

        <label htmlFor="session-justification">Justificativa</label>
        <textarea
          id="session-justification"
          required
          maxLength={500}
          rows={4}
          disabled={submissionState === "submitting"}
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
            ? "Atribuindo recarga…"
            : "Atribuir e revisar próxima"}
          <span aria-hidden="true">→</span>
        </button>
      </form>
    </section>
  );
}
