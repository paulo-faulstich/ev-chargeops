import type { ImportPreviewResponse } from "@ev-chargeops/api-client";

function statusLabel(classification: string) {
  const labels: Record<string, string> = {
    valid: "Válido",
    invalid: "Inválido",
    duplicate: "Duplicado",
  };

  return labels[classification] ?? classification;
}

function statusClass(classification: string) {
  if (classification === "valid") return "border-cyan-300/35 bg-cyan-300/10 text-cyan-100";
  if (classification === "duplicate") return "border-amber-300/35 bg-amber-300/10 text-amber-100";
  return "border-rose-300/35 bg-rose-300/10 text-rose-100";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));
}

export function PreviewTable({ preview }: { preview: ImportPreviewResponse }) {
  return (
    <section aria-labelledby="ledger-title" className="border border-[#213849] bg-[#0b1b28]">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[#213849] px-5 py-5 sm:px-6">
        <div>
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-200">Livro-razão da classificação</p>
          <h2 id="ledger-title" className="mt-2 text-xl font-semibold tracking-[-0.025em] text-white">Sessões e procedência</h2>
        </div>
        <p className="max-w-sm text-sm leading-5 text-[#90a7b8]">A tabela preserva a linha de origem para facilitar a conferência no CSV.</p>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-[860px] w-full text-left text-sm">
          <thead className="bg-[#0d2130] font-mono text-[10px] uppercase tracking-[0.14em] text-[#90a7b8]">
            <tr>
              {["Linha", "Classificação", "Energia", "Início", "Carregador", "Evidência"].map((label) => (
                <th key={label} scope="col" className="px-5 py-3.5 font-medium sm:px-6">{label}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#213849]">
            {preview.records.map((record) => (
              <tr key={record.rowNumber} className="align-top transition-colors hover:bg-cyan-300/[0.035]">
                <td className="px-5 py-4 font-mono text-xs text-[#90a7b8] sm:px-6">{record.rowNumber}</td>
                <td className="px-5 py-4 sm:px-6">
                  <span className={`inline-flex border px-2 py-1 font-mono text-[11px] font-medium ${statusClass(record.classification)}`}>
                    {statusLabel(record.classification)}
                  </span>
                  {record.errorMessage ? <p className="mt-2 max-w-56 leading-5 text-rose-200">{record.errorMessage}</p> : null}
                </td>
                <td className="px-5 py-4 font-mono text-[#d9e7ed] sm:px-6">{record.session ? `${record.session.energyKwh} kWh` : "—"}</td>
                <td className="px-5 py-4 text-[#c2d2dc] sm:px-6">{record.session ? formatDate(record.session.startedAt) : "—"}</td>
                <td className="px-5 py-4 font-mono text-xs text-[#c2d2dc] sm:px-6">{record.session?.chargerSerial ?? "—"}</td>
                <td className="px-5 py-4 sm:px-6">
                  {record.session ? (
                    <div className="flex min-w-48 flex-col items-start gap-2">
                      <span className="border border-cyan-300/35 bg-cyan-300/10 px-2 py-1 text-xs text-cyan-100">Fonte real</span>
                      <span className="border border-amber-300/35 bg-amber-300/10 px-2 py-1 text-xs text-amber-100">Identidade desconhecida</span>
                    </div>
                  ) : <span className="text-[#90a7b8]">Sem sessão normalizada</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
