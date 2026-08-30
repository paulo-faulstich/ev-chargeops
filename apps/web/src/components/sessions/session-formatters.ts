const sessionDateFormatter = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "America/Sao_Paulo",
});

const queueDateFormatter = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "America/Sao_Paulo",
});

const energyFormatter = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const periodFormatter = new Intl.DateTimeFormat("pt-BR", {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

export function formatSessionDate(value: string): string {
  return sessionDateFormatter.format(new Date(value));
}

export function formatQueueDate(value: string): string {
  return queueDateFormatter.format(new Date(value)).replace(" de ", " ");
}

export function formatSessionDuration(startedAt: string, endedAt: string): string {
  const durationMinutes = Math.max(
    0,
    Math.round(
      (new Date(endedAt).getTime() - new Date(startedAt).getTime()) / 60_000,
    ),
  );
  const hours = Math.floor(durationMinutes / 60);
  const minutes = durationMinutes % 60;

  if (hours === 0) return `${minutes} min`;
  if (minutes === 0) return `${hours} h`;
  return `${hours} h ${String(minutes).padStart(2, "0")} min`;
}

export function formatSessionEnergy(value: string): string {
  return `${energyFormatter.format(Number(value))} kWh`;
}

export function formatSessionPeriod(period: string): string {
  const [year, month] = period.split("-").map(Number);
  const label = periodFormatter.format(new Date(Date.UTC(year, month - 1, 1)));
  return label.charAt(0).toUpperCase() + label.slice(1);
}
