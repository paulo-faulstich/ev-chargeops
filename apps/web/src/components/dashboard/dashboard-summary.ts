import type { SessionResponse } from "@ev-chargeops/api-client";

/**
 * Periods are measured in the site's wall clock, matching the API.
 *
 * Bucketing by UTC instead would move every session from 21:00 onwards into the
 * next day, and the last evening of a month into the next month, so the chart
 * and the close would disagree about which month the energy belongs to.
 */
const SITE_TIME_ZONE = "America/Sao_Paulo";

export type SessionProvenance = "real" | "simulated" | "mixed";

type DashboardSession = {
  startedAt: Date;
  dateKey: string;
  energyKwh: number;
  provenance: string;
  responsibleKey: string;
  responsibleLabel: string;
  assigned: boolean;
};

export type DailyUsage = {
  dateKey: string;
  dateLabel: string;
  energyKwh: number;
};

/** Measured consumption per responsible, with no money attached.
 *
 * What each unit owes is decided by the close and lives in an issued invoice,
 * never in an estimate the frontend invented from a hardcoded rate.
 */
export type ResponsibleConsumption = {
  key: string;
  label: string;
  assigned: boolean;
  sessionCount: number;
  energyKwh: number;
};

export type PeriodOption = {
  periodKey: string;
  periodLabel: string;
  sessionCount: number;
  provenance: SessionProvenance;
};

export type DashboardSummary = {
  periodKey: string;
  periodLabel: string;
  provenance: SessionProvenance;
  periods: PeriodOption[];
  updatedAt: string;
  totalEnergyKwh: number;
  sessionCount: number;
  assignedCount: number;
  pendingCount: number;
  dailyUsage: DailyUsage[];
  responsibleConsumption: ResponsibleConsumption[];
};

const periodFormatter = new Intl.DateTimeFormat("pt-BR", {
  month: "long",
  year: "numeric",
  timeZone: SITE_TIME_ZONE,
});

const dayFormatter = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "short",
  timeZone: "UTC",
});

const updatedFormatter = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: SITE_TIME_ZONE,
});

// en-CA renders as YYYY-MM-DD, which sorts and slices cleanly.
const dateKeyFormatter = new Intl.DateTimeFormat("en-CA", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  timeZone: SITE_TIME_ZONE,
});

function formatPeriod(date: Date): string {
  const label = periodFormatter.format(date).replace(" de ", " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function combineProvenance(values: Iterable<string>): SessionProvenance {
  const distinct = new Set(values);
  if (distinct.size === 1 && distinct.has("simulated")) return "simulated";
  if (distinct.size === 1 && distinct.has("real")) return "real";
  return distinct.size > 1 ? "mixed" : "real";
}

function sessionForDashboard(session: SessionResponse): DashboardSession | null {
  const startedAt = new Date(session.startedAt);
  const energyKwh = Number(session.energyKwh);
  if (
    Number.isNaN(startedAt.getTime()) ||
    !Number.isFinite(energyKwh) ||
    energyKwh <= 0
  ) {
    return null;
  }

  const assigned =
    session.identityConfidence !== "unknown" && session.unitId !== null;

  return {
    startedAt,
    dateKey: dateKeyFormatter.format(startedAt),
    energyKwh,
    provenance: session.provenance,
    assigned,
    responsibleKey: assigned ? (session.unitId as string) : "unassigned",
    responsibleLabel: assigned
      ? session.unitName ??
        (session.unitCode ? `Unidade ${session.unitCode}` : "Unidade atribuída")
      : "Não atribuído",
  };
}

function buildPeriodOptions(sessions: DashboardSession[]): PeriodOption[] {
  const grouped = new Map<string, DashboardSession[]>();
  for (const session of sessions) {
    const key = session.dateKey.slice(0, 7);
    grouped.set(key, [...(grouped.get(key) ?? []), session]);
  }
  return [...grouped.entries()]
    .sort(([left], [right]) => right.localeCompare(left))
    .map(([periodKey, periodSessions]) => ({
      periodKey,
      periodLabel: formatPeriod(periodSessions[0].startedAt),
      sessionCount: periodSessions.length,
      provenance: combineProvenance(
        periodSessions.map((session) => session.provenance),
      ),
    }));
}

export function buildDashboardSummary(
  canonicalSessions: SessionResponse[],
  selectedPeriodKey?: string,
): DashboardSummary | null {
  const sessions = canonicalSessions.flatMap((session) => {
    const normalized = sessionForDashboard(session);
    return normalized ? [normalized] : [];
  });
  if (sessions.length === 0) return null;

  const periods = buildPeriodOptions(sessions);
  const latestSession = sessions.reduce((latest, session) =>
    session.startedAt > latest.startedAt ? session : latest,
  );
  const requested =
    selectedPeriodKey && periods.some((p) => p.periodKey === selectedPeriodKey)
      ? selectedPeriodKey
      : null;
  const periodKey = requested ?? latestSession.dateKey.slice(0, 7);
  const periodSessions = sessions.filter((session) =>
    session.dateKey.startsWith(periodKey),
  );
  if (periodSessions.length === 0) return null;

  const daily = new Map<string, number>();
  const responsible = new Map<
    string,
    {
      label: string;
      assigned: boolean;
      sessionCount: number;
      energyKwh: number;
    }
  >();

  for (const session of periodSessions) {
    daily.set(
      session.dateKey,
      (daily.get(session.dateKey) ?? 0) + session.energyKwh,
    );

    const current = responsible.get(session.responsibleKey) ?? {
      label: session.responsibleLabel,
      assigned: session.assigned,
      sessionCount: 0,
      energyKwh: 0,
    };
    current.sessionCount += 1;
    current.energyKwh += session.energyKwh;
    responsible.set(session.responsibleKey, current);
  }

  const totalEnergyKwh = periodSessions.reduce(
    (total, session) => total + session.energyKwh,
    0,
  );
  const assignedCount = periodSessions.filter((session) => session.assigned).length;
  const mostRecentInPeriod = periodSessions.reduce((latest, session) =>
    session.startedAt > latest.startedAt ? session : latest,
  );

  return {
    periodKey,
    periodLabel: formatPeriod(mostRecentInPeriod.startedAt),
    provenance: combineProvenance(
      periodSessions.map((session) => session.provenance),
    ),
    periods,
    updatedAt: updatedFormatter.format(mostRecentInPeriod.startedAt),
    totalEnergyKwh,
    sessionCount: periodSessions.length,
    assignedCount,
    pendingCount: periodSessions.length - assignedCount,
    dailyUsage: [...daily.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([dateKey, energyKwh]) => ({
        dateKey,
        dateLabel: dayFormatter.format(new Date(`${dateKey}T00:00:00Z`)),
        energyKwh,
      })),
    responsibleConsumption: [...responsible.entries()]
      .map(([key, value]) => ({
        key,
        label: value.label,
        assigned: value.assigned,
        sessionCount: value.sessionCount,
        energyKwh: value.energyKwh,
      }))
      .sort(
        (left, right) =>
          Number(right.assigned) - Number(left.assigned) ||
          right.energyKwh - left.energyKwh,
      ),
  };
}
