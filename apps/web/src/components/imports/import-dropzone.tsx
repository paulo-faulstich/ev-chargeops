"use client";

import { useRef, useState, type DragEvent } from "react";
import { previewImport, type ImportPreviewResponse } from "@ev-chargeops/api-client";

import { PreviewSummary } from "./preview-summary";
import { PreviewTable } from "./preview-table";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api";

export function ImportDropzone() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const dragDepth = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function selectFile(selectedFile: File | null) {
    if (selectedFile && !selectedFile.name.toLowerCase().endsWith(".csv")) {
      setFile(null);
      setError("Selecione um arquivo CSV exportado do SEMS+.");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setFile(selectedFile);
    setError(null);
  }

  function handleDragEnter(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    if (loading) return;

    dragDepth.current += 1;
    setIsDragging(true);
  }

  function handleDragOver(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    event.dataTransfer.dropEffect = loading ? "none" : "copy";
  }

  function handleDragLeave(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    if (loading) return;

    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setIsDragging(false);
  }

  function handleDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    dragDepth.current = 0;
    setIsDragging(false);
    if (loading) return;

    if (fileInputRef.current) fileInputRef.current.value = "";
    selectFile(event.dataTransfer.files.item(0));
  }

  async function analyze() {
    if (!file) return;

    setLoading(true);
    setError(null);

    try {
      setPreview(await previewImport(file, apiUrl));
    } catch {
      setError("A análise não foi concluída. Confirme se o arquivo é um CSV exportado do SEMS+ e tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setFile(null);
    setPreview(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  if (preview) {
    return (
      <div className="space-y-6 sm:space-y-8">
        <div className="flex flex-wrap items-end justify-between gap-4 border-l-2 border-cyan-300 bg-cyan-300/[0.045] px-4 py-4 sm:px-5">
          <div>
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.17em] text-cyan-200">Prévia concluída</p>
            <p className="mt-2 font-mono text-sm text-white">{preview.filename}</p>
            <p className="mt-1 text-sm text-[#90a7b8]">Nenhum registro foi gravado.</p>
          </div>
          <button type="button" onClick={reset} className="border border-[#426071] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:border-cyan-300 hover:bg-cyan-300/10">
            Revisar outro arquivo
          </button>
        </div>
        <PreviewSummary preview={preview} />
        <PreviewTable preview={preview} />
      </div>
    );
  }

  return (
    <section
      aria-labelledby="upload-title"
      className={`border p-5 transition-colors sm:p-8 lg:p-10 ${
        isDragging
          ? "border-solid border-cyan-200 bg-[#102a38] ring-1 ring-cyan-200/60 shadow-[0_0_28px_rgba(34,211,238,0.16)]"
          : "border-dashed border-cyan-300/45 bg-[#0b1b28]"
      }`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_16rem] lg:items-end">
        <div>
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-200">Etapa 01 · origem do dado</p>
          <h2 id="upload-title" className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-white">Selecione a exportação do SEMS+</h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-[#90a7b8]">A análise verifica cada linha e mostra a classificação antes de criar qualquer lote de importação.</p>

          <label htmlFor="sems-file" className="mt-7 block text-sm font-medium text-white">Arquivo CSV do SEMS+</label>
          <p id="upload-guidance" className={`mt-2 text-sm ${isDragging ? "font-medium text-cyan-100" : "text-[#90a7b8]"}`}>
            {isDragging ? "Solte o CSV para selecionar" : "Arraste e solte o CSV neste painel ou use o seletor abaixo."}
          </p>
          <input
            id="sems-file"
            ref={fileInputRef}
            aria-describedby="upload-guidance"
            className="mt-3 block w-full max-w-2xl cursor-pointer border border-[#426071] bg-[#07131d] px-3 py-2 text-sm text-[#c2d2dc] file:mr-4 file:border-0 file:bg-cyan-300 file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-[#07131d]"
            type="file"
            accept=".csv,text/csv"
            disabled={loading}
            onChange={(event) => {
              selectFile(event.target.files?.[0] ?? null);
            }}
          />
          {file ? <p className="mt-3 font-mono text-xs text-cyan-100">Selecionado: {file.name}</p> : <p className="mt-3 text-sm text-[#90a7b8]">Nenhum arquivo selecionado.</p>}
        </div>

        <aside className="border-l border-[#213849] pl-5 text-sm leading-6 text-[#b8c9d4]">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[#90a7b8]">O que será exibido</p>
          <p className="mt-2">Status por linha, energia, carregador e sinais de procedência.</p>
        </aside>
      </div>

      {loading ? <p role="status" className="mt-6 border-l-2 border-cyan-300 px-3 text-sm text-cyan-100">Lendo e classificando as sessões…</p> : null}
      {error ? <div role="alert" className="mt-6 border-l-2 border-rose-300 bg-rose-300/[0.06] px-4 py-3 text-sm leading-6 text-rose-100">{error}</div> : null}

      <div className="mt-7 flex flex-wrap items-center gap-3">
        <button type="button" disabled={!file || loading} onClick={analyze} className="bg-[#ff6b57] px-5 py-3 text-sm font-semibold text-[#1e0b08] transition-colors hover:bg-[#ff8675] disabled:cursor-not-allowed disabled:opacity-45">
          {loading ? "Analisando…" : "Analisar arquivo"}
        </button>
        {error && file ? <button type="button" onClick={analyze} className="border border-[#426071] px-4 py-3 text-sm font-medium text-white transition-colors hover:border-cyan-300 hover:bg-cyan-300/10">Tentar novamente</button> : null}
      </div>
    </section>
  );
}
