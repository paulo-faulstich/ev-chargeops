/** The words the screen uses for values the API stores as codes.
 *
 * The rule for where a name lives: if the invoice document says it, the API
 * owns the wording, so the PDF and the screen cannot drift apart. If only a
 * screen ever shows it — a finding, a severity, where a charge came from — the
 * name lives here. Every lookup falls back to the raw value, because an
 * unlabelled code on screen is bad and a blank cell is worse.
 */

const FINDING_TITLES: Record<string, string> = {
  INVALID_INTERVAL: "Recarga termina antes de começar",
  NON_POSITIVE_ENERGY: "Recarga sem energia",
  POWER_EXCEEDS_RATED: "Potência acima do que o carregador entrega",
  DUPLICATE_SUSPECT: "Possível recarga repetida",
  ENERGY_OUTLIER: "Consumo fora do padrão da unidade",
  AGGREGATE_MISMATCH: "Diferença contra o total do carregador",
  AGGREGATE_RECONCILED: "Confere com o total do carregador",
  UNASSIGNED_ENERGY: "Recargas sem responsável",
  DISTRIBUTION_INCONCLUSIVE: "Poucas recargas para comparar",
};

export function findingTitle(code: string): string {
  return FINDING_TITLES[code] ?? code;
}

/** Severities as they are counted: "2 críticos · 1 atenção". */
const SEVERITY_COUNT_LABELS: Record<string, string> = {
  critical: "críticos",
  warning: "atenções",
  info: "observações",
};

export function severityCountLabel(severity: string): string {
  return SEVERITY_COUNT_LABELS[severity] ?? severity;
}

/** The same severities named one at a time. */
const SEVERITY_NAMES: Record<string, string> = {
  critical: "Crítico",
  warning: "Atenção",
  info: "Informativo",
};

export function severityName(severity: string): string {
  return SEVERITY_NAMES[severity] ?? severity;
}

const CONFIDENCE_LABELS: Record<string, string> = {
  high: "alta",
  medium: "média",
  low: "baixa",
  inconclusive: "inconclusiva",
};

export function confidenceLabel(confidence: string): string {
  return CONFIDENCE_LABELS[confidence] ?? confidence;
}

/** Whether a charge was measured or made up. Never abbreviate this one. */
const PROVENANCE_LABELS: Record<string, string> = {
  real: "Medição real",
  assigned: "Medição real, unidade atribuída",
  simulated: "Dado simulado",
  derived: "Valor derivado",
  external: "Origem externa",
};

export function provenanceLabel(provenance: string): string {
  return PROVENANCE_LABELS[provenance] ?? provenance;
}

const SOURCE_LABELS: Record<string, string> = {
  // "SEMS+ CSV" is what the manager exported from GoodWe's own portal, so the
  // import history, the data source and a charge's row all call it that.
  sems_export: "SEMS+ CSV",
  sems_csv: "SEMS+ CSV",
  manual: "Lançamento manual",
  simulated: "Gerador de demonstração",
  goodwe_api: "API da GoodWe",
};

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

const IMPORT_STATUS_LABELS: Record<string, string> = {
  completed: "Concluído",
  pending: "Em andamento",
  failed: "Falhou",
};

export function importStatusLabel(status: string): string {
  return IMPORT_STATUS_LABELS[status] ?? status;
}
