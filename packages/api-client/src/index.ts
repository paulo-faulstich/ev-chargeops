import type { paths } from "./schema";

export type ImportPreviewResponse =
  paths["/v1/import-batches/preview"]["post"]["responses"][200]["content"]["application/json"];

export async function previewImport(
  file: File,
  baseUrl = "http://localhost:8000",
): Promise<ImportPreviewResponse> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${baseUrl}/v1/import-batches/preview`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(`Import preview failed with status ${response.status}`);
  }
  return response.json() as Promise<ImportPreviewResponse>;
}
