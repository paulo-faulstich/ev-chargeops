import type { SessionResponse } from "@ev-chargeops/api-client";

export const ESTIMATED_TARIFF_BRL_PER_KWH = 0.94;

type DashboardSession = {
  startedAt: Date;
  dateKey: string;
  energyKwh: number;
  responsibleKey: string;
  responsibleLabel: string;
  assigned: boolean;
};

export type DailyUsage = {
  dateKey: string;
  dateLabel: string;
  energyKwh: number;
};

export type ResponsibleCost = {
  key: string;
  label: string;
  assigned: boolean;
  sessionCount: number;
  energyKwh: number;
  estimatedCost: number;
};

export type DashboardSummary = {
  periodKey: string;
  periodLabel: string;
  updatedAt: string;
  totalEnergyKwh: number;
  estimatedCost: number;
  sessionCount: number;
  assignedCount: number;
  pendingCount: number;
  dailyUsage: DailyUsage[];
  responsibleCosts: ResponsibleCost[];
};

const periodFormatter = new Intl.DateTimeFormat("pt-BR", {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
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
  timeZone: "America/Sao_Paulo",
});

function formatPeriod(date: Date): string {
  const label = periodFormatter.format(date).replace(" de ", " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
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
  const year = startedAt.getUTCFullYear();
  const month = String(startedAt.getUTCMonth() + 1).padStart(2, "0");
  const day = String(startedAt.getUTCDate()).padStart(2, "0");

  return {
    startedAt,
    dateKey: `${year}-${month}-${day}`,
    energyKwh,
    assigned,
    responsibleKey: assigned ? (session.unitId as string) : "unassigned",
    responsibleLabel: assigned
      ? session.unitName ??
        (session.unitCode ? `Unidade ${session.unitCode}` : "Unidade atribuída")
      : "Não atribuído",
  };
}

export function buildDashboardSummary(
  canonicalSessions: SessionResponse[],
): DashboardSummary | null {
  const sessions = canonicalSessions.flatMap((session) => {
    const normalized = sessionForDashboard(session);
    return normalized ? [normalized] : [];
  });
  if (sessions.length === 0) return null;

  const latestSession = sessions.reduce((latest, session) =>
    session.startedAt > latest.startedAt ? session : latest,
  );
  const periodKey = latestSession.dateKey.slice(0, 7);
  const periodSessions = sessions.filter((session) =>
    session.dateKey.startsWith(periodKey),
  );
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

  return {
    periodKey,
    periodLabel: formatPeriod(latestSession.startedAt),
    updatedAt: updatedFormatter.format(latestSession.startedAt),
    totalEnergyKwh,
    estimatedCost: totalEnergyKwh * ESTIMATED_TARIFF_BRL_PER_KWH,
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
    responsibleCosts: [...responsible.entries()]
      .map(([key, value]) => ({
        key,
        label: value.label,
        assigned: value.assigned,
        sessionCount: value.sessionCount,
        energyKwh: value.energyKwh,
        estimatedCost: value.energyKwh * ESTIMATED_TARIFF_BRL_PER_KWH,
      }))
      .sort(
        (left, right) =>
          Number(right.assigned) - Number(left.assigned) ||
          right.energyKwh - left.energyKwh,
      ),
  };
}
