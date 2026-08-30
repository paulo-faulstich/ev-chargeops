import type { ImportPreviewResponse } from "@ev-chargeops/api-client";

export function PreviewSummary({ preview }: { preview: ImportPreviewResponse }) {
  const cards = [
    [preview.totalCount, "registros", "Linhas lidas do arquivo"],
    [preview.validCount, "válidos", "Prontos para importação"],
    [preview.invalidCount, "inválidos", "Exigem correção no arquivo"],
    [preview.duplicateCount, "duplicados", "Já vistos nesta análise"],
  ] as const;

  return (
    <section aria-label="Resumo da análise" className="grid gap-px overflow-hidden border border-[#213849] bg-[#213849] sm:grid-cols-2 xl:grid-cols-4">
      {cards.map(([value, label, detail]) => (
        <div key={label} className="bg-[#0b1b28] px-5 py-5 sm:px-6">
          <p className="font-mono text-3xl font-semibold tracking-[-0.06em] text-white">
            {value} <span className="text-sm font-normal tracking-normal text-[#c2d2dc]">{label}</span>
          </p>
          <p className="mt-2 text-sm text-[#90a7b8]">{detail}</p>
        </div>
      ))}
    </section>
  );
}
