import type {
  ImportBatchDetailResponse,
  ImportBatchResponse,
} from "@ev-chargeops/api-client";

export const ESTIMATED_TARIFF_BRL_PER_KWH = 0.94;

type DashboardSession = {
  startedAt: Date;
  dateKey: string;
  energyKwh: number;
  responsibleId: string | null;
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

function parseSemsDate(value: string | null | undefined): Date | null {
  if (!value) return null;

  const match = value.match(
    /^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})(?::(\d{2}))?$/,
  );
  if (!match) return null;

  const [, day, month, year, hour, minute, second = "00"] = match;
  const parsed = new Date(
    Date.UTC(
      Number(year),
      Number(month) - 1,
      Number(day),
      Number(hour),
      Number(minute),
      Number(second),
    ),
  );

  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function sessionFromRecord(
  record: ImportBatchDetailResponse["records"][number],
): DashboardSession | null {
  if (record.classification !== "valid" || !record.sessionId) return null;

  const startedAt = parseSemsDate(record.raw["Start Time"]);
  const energyKwh = Number(record.raw["Charging Energy(kWh)"]);
  if (!startedAt || !Number.isFinite(energyKwh) || energyKwh <= 0) return null;

  const responsibleId = record.raw["Card ID"]?.trim() || null;
  const year = startedAt.getUTCFullYear();
  const month = String(startedAt.getUTCMonth() + 1).padStart(2, "0");
  const day = String(startedAt.getUTCDate()).padStart(2, "0");

  return {
    startedAt,
    dateKey: `${year}-${month}-${day}`,
    energyKwh,
    responsibleId,
  };
}

function identifierLabel(identifier: string): string {
  if (identifier.length <= 14) return identifier;
  return `Cartão ${identifier.slice(0, 6)}…${identifier.slice(-4)}`;
}

export function buildDashboardSummary(
  batches: ImportBatchResponse[],
  details: ImportBatchDetailResponse[],
): DashboardSummary | null {
  const sessions = details.flatMap((detail) =>
    detail.records.flatMap((record) => {
      const session = sessionFromRecord(record);
      return session ? [session] : [];
    }),
  );
  if (sessions.length === 0) return null;

  const latestSession = sessions.reduce((latest, session) =>
    session.startedAt > latest.startedAt ? session : latest,
  );
  const periodSessions = sessions.filter(
    (session) =>
      session.startedAt.getUTCFullYear() ===
        latestSession.startedAt.getUTCFullYear() &&
      session.startedAt.getUTCMonth() === latestSession.startedAt.getUTCMonth(),
  );

  const daily = new Map<string, number>();
  const responsible = new Map<
    string,
    { assigned: boolean; sessionCount: number; energyKwh: number }
  >();

  for (const session of periodSessions) {
    daily.set(
      session.dateKey,
      (daily.get(session.dateKey) ?? 0) + session.energyKwh,
    );

    const key = session.responsibleId ?? "unassigned";
    const current = responsible.get(key) ?? {
      assigned: session.responsibleId !== null,
      sessionCount: 0,
      energyKwh: 0,
    };
    current.sessionCount += 1;
    current.energyKwh += session.energyKwh;
    responsible.set(key, current);
  }

  const totalEnergyKwh = periodSessions.reduce(
    (total, session) => total + session.energyKwh,
    0,
  );
  const assignedCount = periodSessions.filter(
    (session) => session.responsibleId,
  ).length;
  const latestBatchCreatedAt = batches.reduce(
    (latest, batch) =>
      Date.parse(batch.createdAt) > Date.parse(latest) ? batch.createdAt : latest,
    batches[0]?.createdAt ?? new Date(0).toISOString(),
  );

  return {
    periodLabel: formatPeriod(latestSession.startedAt),
    updatedAt: updatedFormatter.format(new Date(latestBatchCreatedAt)),
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
        label: value.assigned ? identifierLabel(key) : "Não atribuído",
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
