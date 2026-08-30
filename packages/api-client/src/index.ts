import type { components } from "./schema";

export type ImportPreviewResponse =
  components["schemas"]["ImportPreviewResponse"];
export type ImportBatchResponse = components["schemas"]["ImportBatchResponse"];
export type ImportBatchListResponse =
  components["schemas"]["ImportBatchListResponse"];
export type ImportBatchDetailResponse =
  components["schemas"]["ImportBatchDetailResponse"];

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`API request failed with status ${status}`);
    this.name = "ApiError";
  }
}

async function apiRequest<T>(
  path: string,
  token: string,
  init: RequestInit = {},
  baseUrl = "/api",
): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      ...(init.headers as Record<string, string> | undefined),
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    throw new ApiError(response.status, await response.json());
  }
  return response.json() as Promise<T>;
}

function multipart(file: File): FormData {
  const form = new FormData();
  form.append("file", file);
  return form;
}

export async function previewImport(
  file: File,
  token: string,
  baseUrl = "/api",
): Promise<ImportPreviewResponse> {
  return apiRequest<ImportPreviewResponse>(
    "/v1/import-batches/preview",
    token,
    { method: "POST", body: multipart(file) },
    baseUrl,
  );
}

export async function confirmImport(
  file: File,
  token: string,
  baseUrl = "/api",
): Promise<ImportBatchResponse> {
  return apiRequest<ImportBatchResponse>(
    "/v1/import-batches",
    token,
    { method: "POST", body: multipart(file) },
    baseUrl,
  );
}

export async function listImportBatches(
  token: string,
  baseUrl = "/api",
): Promise<ImportBatchListResponse> {
  return apiRequest<ImportBatchListResponse>(
    "/v1/import-batches",
    token,
    {},
    baseUrl,
  );
}

export async function getImportBatch(
  batchId: string,
  token: string,
  baseUrl = "/api",
): Promise<ImportBatchDetailResponse> {
  return apiRequest<ImportBatchDetailResponse>(
    `/v1/import-batches/${encodeURIComponent(batchId)}`,
    token,
    {},
    baseUrl,
  );
}
