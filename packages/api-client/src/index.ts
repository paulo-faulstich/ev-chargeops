import type { components, operations } from "./schema";

export type ImportPreviewResponse =
  components["schemas"]["ImportPreviewResponse"];
export type ImportBatchResponse = components["schemas"]["ImportBatchResponse"];
export type ImportBatchListResponse =
  components["schemas"]["ImportBatchListResponse"];
export type ImportBatchDetailResponse =
  components["schemas"]["ImportBatchDetailResponse"];
export type SessionResponse = components["schemas"]["SessionResponse"];
export type SessionListResponse = components["schemas"]["SessionListResponse"];
export type AssignmentUnitResponse =
  components["schemas"]["AssignmentUnitResponse"];
export type AssignmentUnitListResponse =
  components["schemas"]["AssignmentUnitListResponse"];
export type SessionAssignmentRequest =
  components["schemas"]["SessionAssignmentRequest"];
export type SessionAssignmentResponse =
  components["schemas"]["SessionAssignmentResponse"];
export type SessionFilters = NonNullable<
  operations["list_sessions_v1_sessions_get"]["parameters"]["query"]
>;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`API request failed with status ${status}`);
    this.name = "ApiError";
  }
}

async function errorBody(response: Response): Promise<unknown> {
  const rawBody = await response.text();
  if (rawBody === "") return null;

  const contentType = response.headers.get("content-type")?.toLowerCase();
  if (!contentType?.includes("json")) return rawBody;

  try {
    return JSON.parse(rawBody) as unknown;
  } catch {
    return rawBody;
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
    throw new ApiError(response.status, await errorBody(response));
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

export async function listSessions(
  token: string,
  filters: SessionFilters = {},
  baseUrl = "/api",
): Promise<SessionListResponse> {
  const query = new URLSearchParams();
  if (filters.period != null) query.set("period", filters.period);
  if (filters.status != null) query.set("status", filters.status);
  const encodedFilters = query.toString();
  const path = `/v1/sessions${encodedFilters ? `?${encodedFilters}` : ""}`;
  return apiRequest<SessionListResponse>(path, token, {}, baseUrl);
}

export async function listAssignmentUnits(
  token: string,
  baseUrl = "/api",
): Promise<AssignmentUnitListResponse> {
  return apiRequest<AssignmentUnitListResponse>(
    "/v1/assignment-units",
    token,
    {},
    baseUrl,
  );
}

export async function assignSession(
  sessionId: string,
  request: SessionAssignmentRequest,
  token: string,
  baseUrl = "/api",
): Promise<SessionAssignmentResponse> {
  return apiRequest<SessionAssignmentResponse>(
    `/v1/sessions/${encodeURIComponent(sessionId)}/assignment`,
    token,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
    baseUrl,
  );
}
