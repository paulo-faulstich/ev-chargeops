import { ImportDropzone } from "@/components/imports/import-dropzone";

export default function NewImportPage() {
  return (
    <main className="min-h-screen px-4 py-5 sm:px-8 sm:py-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="border-b border-[#213849] pb-7 sm:pb-9">
          <div className="flex items-center gap-3 font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-200">
            <span className="inline-block h-2 w-2 bg-cyan-300" aria-hidden="true" />
            GoodWe / SEMS+ / Ingestão
          </div>
          <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_15rem] lg:items-end">
            <div>
              <h1 className="max-w-4xl text-balance text-4xl font-semibold tracking-[-0.045em] text-white sm:text-5xl lg:text-6xl">
                Evidência antes da importação.
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-[#90a7b8]">
                Revise cada sessão do SEMS+ como um registro de operação: classificação, origem e identidade ficam visíveis antes de qualquer persistência.
              </p>
            </div>
            <p className="border-l border-cyan-300/50 pl-4 text-sm leading-6 text-[#b8c9d4]">
              <span className="block font-mono text-[10px] uppercase tracking-[0.16em] text-cyan-200">Modo de trabalho</span>
              Prévia local · sem gravação
            </p>
          </div>
        </header>

        <div className="pt-7 sm:pt-9">
          <ImportDropzone />
        </div>
      </div>
    </main>
  );
}
