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

export type BillingPeriodResponse =
  components["schemas"]["BillingPeriodResponse"];
export type BillingPeriodListResponse =
  components["schemas"]["BillingPeriodListResponse"];
export type OpenBillingPeriodRequest =
  components["schemas"]["OpenBillingPeriodRequest"];
export type BlockerResponse = components["schemas"]["BlockerResponse"];
export type ReadinessResponse = components["schemas"]["ReadinessResponse"];
export type PeriodReadinessResponse =
  components["schemas"]["PeriodReadinessResponse"];
export type FindingResponse = components["schemas"]["FindingResponse"];
export type ClosingOpinionResponse =
  components["schemas"]["ClosingOpinionResponse"];
export type PeriodOpinionResponse =
  components["schemas"]["PeriodOpinionResponse"];
export type ClosePeriodResponse = components["schemas"]["ClosePeriodResponse"];
export type InvoiceItemResponse = components["schemas"]["InvoiceItemResponse"];
export type InvoiceResponse = components["schemas"]["InvoiceResponse"];
export type InvoiceListResponse = components["schemas"]["InvoiceListResponse"];
export type InvoiceContextResponse =
  components["schemas"]["InvoiceContextResponse"];
export type TariffBandResponse = components["schemas"]["TariffBandResponse"];
export type InvoiceDetailResponse =
  components["schemas"]["InvoiceDetailResponse"];
export type ResidentContextResponse =
  components["schemas"]["ResidentContextResponse"];
export type InvoiceFilters = NonNullable<
  operations["list_invoices_v1_invoices_get"]["parameters"]["query"]
>;

/** Where to send the request, and under whose eyes to read it.
 *
 * `residentContextId` travels as `X-Resident-Context`, the same header the API
 * resolves through its real authorization dependency. Setting it narrows the
 * caller to one unit and to reading; it does not change the route.
 */
export type RequestOptions = {
  baseUrl?: string;
  residentContextId?: string | null;
};

function scopedHeaders(
  options: RequestOptions,
  extra: Record<string, string> = {},
): Record<string, string> {
  const headers = { ...extra };
  if (options.residentContextId != null) {
    headers["X-Resident-Context"] = options.residentContextId;
  }
  return headers;
}

async function scopedRequest<T>(
  path: string,
  token: string,
  options: RequestOptions,
  init: RequestInit = {},
): Promise<T> {
  return apiRequest<T>(
    path,
    token,
    { ...init, headers: scopedHeaders(options, init.headers as Record<string, string> | undefined) },
    options.baseUrl ?? "/api",
  );
}

export async function listBillingPeriods(
  token: string,
  options: RequestOptions = {},
): Promise<BillingPeriodListResponse> {
  return scopedRequest<BillingPeriodListResponse>(
    "/v1/billing-periods",
    token,
    options,
  );
}

export async function openBillingPeriod(
  request: OpenBillingPeriodRequest,
  token: string,
  options: RequestOptions = {},
): Promise<BillingPeriodResponse> {
  return scopedRequest<BillingPeriodResponse>(
    "/v1/billing-periods",
    token,
    options,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
  );
}

export async function getBillingPeriod(
  periodId: string,
  token: string,
  options: RequestOptions = {},
): Promise<BillingPeriodResponse> {
  return scopedRequest<BillingPeriodResponse>(
    `/v1/billing-periods/${encodeURIComponent(periodId)}`,
    token,
    options,
  );
}

export async function getBillingPeriodReadiness(
  periodId: string,
  token: string,
  options: RequestOptions = {},
): Promise<PeriodReadinessResponse> {
  return scopedRequest<PeriodReadinessResponse>(
    `/v1/billing-periods/${encodeURIComponent(periodId)}/readiness`,
    token,
    options,
  );
}

export async function generateClosingOpinion(
  periodId: string,
  token: string,
  options: RequestOptions = {},
): Promise<PeriodOpinionResponse> {
  return scopedRequest<PeriodOpinionResponse>(
    `/v1/billing-periods/${encodeURIComponent(periodId)}/closing-opinion`,
    token,
    options,
    { method: "POST" },
  );
}

export async function closeBillingPeriod(
  periodId: string,
  token: string,
  options: RequestOptions = {},
): Promise<ClosePeriodResponse> {
  return scopedRequest<ClosePeriodResponse>(
    `/v1/billing-periods/${encodeURIComponent(periodId)}/close`,
    token,
    options,
    { method: "POST" },
  );
}

export async function listInvoices(
  token: string,
  filters: InvoiceFilters = {},
  options: RequestOptions = {},
): Promise<InvoiceListResponse> {
  const query = new URLSearchParams();
  if (filters.periodId != null) query.set("periodId", filters.periodId);
  if (filters.unitId != null) query.set("unitId", filters.unitId);
  const encoded = query.toString();
  return scopedRequest<InvoiceListResponse>(
    `/v1/invoices${encoded ? `?${encoded}` : ""}`,
    token,
    options,
  );
}

/** The invoice plus the frozen tariff and policy it cites. */
export async function getInvoice(
  invoiceId: string,
  token: string,
  options: RequestOptions = {},
): Promise<InvoiceDetailResponse> {
  return scopedRequest<InvoiceDetailResponse>(
    `/v1/invoices/${encodeURIComponent(invoiceId)}`,
    token,
    options,
  );
}

/** Fetch the PDF as bytes.
 *
 * The document is behind the same bearer token as every other route, so it
 * cannot be reached by a plain link; the caller turns this blob into a
 * download itself.
 */
export async function downloadInvoiceDocument(
  invoiceId: string,
  token: string,
  options: RequestOptions = {},
): Promise<Blob> {
  const baseUrl = options.baseUrl ?? "/api";
  const response = await fetch(
    `${baseUrl}/v1/invoices/${encodeURIComponent(invoiceId)}/document`,
    { headers: { ...scopedHeaders(options), Authorization: `Bearer ${token}` } },
  );
  if (!response.ok) {
    throw new ApiError(response.status, await errorBody(response));
  }
  return response.blob();
}

export async function enterResidentContext(
  unitId: string,
  token: string,
  options: RequestOptions = {},
): Promise<ResidentContextResponse> {
  return scopedRequest<ResidentContextResponse>(
    "/v1/resident-context",
    token,
    { baseUrl: options.baseUrl },
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ unitId }),
    },
  );
}

/** Leave the context. Returns `204`, so there is no body to read. */
export async function exitResidentContext(
  residentContextId: string,
  token: string,
  options: RequestOptions = {},
): Promise<void> {
  const baseUrl = options.baseUrl ?? "/api";
  const response = await fetch(`${baseUrl}/v1/resident-context`, {
    method: "DELETE",
    headers: {
      "X-Resident-Context": residentContextId,
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    throw new ApiError(response.status, await errorBody(response));
  }
}

export type PersistedFindingResponse =
  components["schemas"]["PersistedFindingResponse"];
export type FindingListResponse =
  components["schemas"]["FindingListResponse"];

export async function listFindings(
  periodId: string,
  token: string,
  options: RequestOptions = {},
): Promise<FindingListResponse> {
  return scopedRequest<FindingListResponse>(
    `/v1/billing-periods/${encodeURIComponent(periodId)}/findings`,
    token,
    options,
  );
}

/** Accept a finding, on the record, so it stops blocking the close. */
export async function decideFinding(
  periodId: string,
  findingId: string,
  note: string,
  token: string,
  options: RequestOptions = {},
): Promise<PersistedFindingResponse> {
  return scopedRequest<PersistedFindingResponse>(
    `/v1/billing-periods/${encodeURIComponent(periodId)}/findings/${encodeURIComponent(findingId)}/decision`,
    token,
    options,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note }),
    },
  );
}
