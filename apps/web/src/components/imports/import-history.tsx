import type { ImportBatchResponse } from "@ev-chargeops/api-client";
import { importStatusLabel, sourceLabel } from "@/lib/vocabulary";

type ImportHistoryProps = {
  batches: ImportBatchResponse[];
  error: boolean;
  loading: boolean;
  onRefresh: () => void;
};

const dateFormatter = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: "America/Sao_Paulo",
});

function countedLabel(count: number, singular: string, plural: string) {
  return `${count} ${count === 1 ? singular : plural}`;
}

export function ImportHistory({
  batches,
  error,
  loading,
  onRefresh,
}: ImportHistoryProps) {
  const orderedBatches = [...batches].sort(
    (left, right) =>
      Date.parse(right.createdAt) - Date.parse(left.createdAt) ||
      right.id.localeCompare(left.id),
  );

  return (
    <section className="import-history" aria-labelledby="import-history-title">
      <div className="import-history-heading">
        <div>
          <p className="utility-label">Registro de procedência</p>
          <h2 id="import-history-title">Histórico de importações</h2>
        </div>
        <p className="history-count">
          {batches.length} {batches.length === 1 ? "lote" : "lotes"}
        </p>
      </div>

      {loading ? (
        <p aria-live="polite" className="history-state">
          Atualizando histórico…
        </p>
      ) : null}

      {error ? (
        <div role="alert" className="history-state history-error">
          <p>O histórico não foi carregado. Tente novamente.</p>
          <button type="button" onClick={onRefresh}>
            Atualizar histórico
          </button>
        </div>
      ) : null}

      {!loading && !error && orderedBatches.length === 0 ? (
        <div className="history-empty">
          <span aria-hidden="true" />
          <div>
            <p>Nenhum lote importado ainda.</p>
            <p>A primeira confirmação aparecerá aqui com origem e totais.</p>
          </div>
        </div>
      ) : null}

      {!loading && !error && orderedBatches.length > 0 ? (
        <div className="history-table-frame">
          <table aria-label="Histórico de importações">
            <thead>
              <tr>
                <th>Arquivo</th>
                <th>Fonte</th>
                <th>Importado em</th>
                <th>Resultado</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {orderedBatches.map((batch) => (
                <tr key={batch.id}>
                  <td className="history-filename">{batch.filename}</td>
                  <td>{sourceLabel(batch.source)}</td>
                  <td>{dateFormatter.format(new Date(batch.createdAt))}</td>
                  <td>
                    {batch.totalCount} total · {countedLabel(
                      batch.validCount,
                      "válido",
                      "válidos",
                    )} · {countedLabel(
                      batch.invalidCount,
                      "inválido",
                      "inválidos",
                    )} · {countedLabel(
                      batch.duplicateCount,
                      "duplicado",
                      "duplicados",
                    )}
                  </td>
                  <td>
                    <span className="history-status">
                      {importStatusLabel(batch.status)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
