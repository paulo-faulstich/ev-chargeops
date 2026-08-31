import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  assignSession,
  closeBillingPeriod,
  confirmImport,
  downloadInvoiceDocument,
  enterResidentContext,
  exitResidentContext,
  getImportBatch,
  getInvoice,
  listAssignmentUnits,
  listImportBatches,
  listInvoices,
  listSessions,
  previewImport,
} from "./index";

const previewPayload = {
  filename: "sems.csv",
  checksum: "abc123",
  source: "sems_export",
  totalCount: 2,
  validCount: 2,
  invalidCount: 0,
  duplicateCount: 0,
  records: [],
};

const batchPayload = {
  id: "70000000-0000-0000-0000-000000000001",
  filename: "sems.csv",
  checksum: "abc123",
  source: "sems_export",
  status: "completed",
  created: true,
  totalCount: 2,
  validCount: 2,
  invalidCount: 0,
  duplicateCount: 0,
  createdAt: "2026-08-29T22:00:00Z",
};

const sessionPayload = {
  id: "90000000-0000-0000-0000-000000000001",
  startedAt: "2026-08-29T20:10:00Z",
  endedAt: "2026-08-29T21:10:00Z",
  energyKwh: "7.000",
  chargerSerial: "97500NAP25BL0008",
  source: "sems_export",
  provenance: "observed",
  identityConfidence: "unknown",
  status: "pending_review",
  unitId: null,
  unitCode: null,
  unitName: null,
  residentName: null,
};

const unitPayload = {
  id: "40000000-0000-0000-0000-000000000001",
  code: "A-101",
  displayName: "Unidade A-101",
  residentName: null,
};

afterEach(() => vi.unstubAllGlobals());

describe("authenticated import client", () => {
  it("posts preview multipart with bearer auth and no content-type override", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(previewPayload), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["header\nvalue"], "sems.csv", { type: "text/csv" });

    await expect(
      previewImport(file, "signed-token", "http://api.test"),
    ).resolves.toEqual(previewPayload);

    const [url, request] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/v1/import-batches/preview");
    expect(request.method).toBe("POST");
    expect(request.headers).toEqual({ Authorization: "Bearer signed-token" });
    expect(request.headers).not.toHaveProperty("Content-Type");
    expect(request.body).toBeInstanceOf(FormData);
    expect(request.body.get("file")).toBe(file);
  });

  it("sends the bearer token when confirming an import", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(batchPayload), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["csv"], "sems.csv", { type: "text/csv" });

    await expect(
      confirmImport(file, "signed-token", "http://api.test"),
    ).resolves.toEqual(batchPayload);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/v1/import-batches",
      expect.objectContaining({
        method: "POST",
        headers: { Authorization: "Bearer signed-token" },
      }),
    );
    const request = fetchMock.mock.calls[0][1];
    expect(request.headers).not.toHaveProperty("Content-Type");
    expect(request.body.get("file")).toBe(file);
  });

  it("lists import batches with bearer auth", async () => {
    const payload = { items: [batchPayload] };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      listImportBatches("signed-token", "http://api.test"),
    ).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/v1/import-batches",
      expect.objectContaining({
        headers: { Authorization: "Bearer signed-token" },
      }),
    );
  });

  it("gets one import batch with bearer auth", async () => {
    const payload = { ...batchPayload, records: [] };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      getImportBatch(batchPayload.id, "signed-token", "http://api.test"),
    ).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      `http://api.test/v1/import-batches/${batchPayload.id}`,
      expect.objectContaining({
        headers: { Authorization: "Bearer signed-token" },
      }),
    );
  });

  it("throws a typed API error with the server response", async () => {
    const errorBody = {
      error: {
        code: "UNSUPPORTED_FILE",
        message: "Only CSV files are supported.",
        details: [{ field: "file" }],
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(errorBody), {
          status: 422,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const file = new File(["bad"], "bad.txt", { type: "text/plain" });

    const request = confirmImport(file, "signed-token", "http://api.test");

    await expect(request).rejects.toBeInstanceOf(ApiError);
    await expect(request).rejects.toMatchObject({
      status: 422,
      body: errorBody,
    });
  });

  it("preserves status and plain text from a non-JSON failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("Bad gateway", {
          status: 502,
          headers: { "Content-Type": "text/plain" },
        }),
      ),
    );

    const request = listImportBatches("signed-token", "http://api.test");

    await expect(request).rejects.toMatchObject({
      name: "ApiError",
      status: 502,
      body: "Bad gateway",
    });
  });

  it("preserves status when a failure has no body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 401 })),
    );

    const request = listImportBatches("expired-token", "http://api.test");

    await expect(request).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      body: null,
    });
  });
});

describe("authenticated sessions client", () => {
  it("lists sessions with literal optional filters and bearer auth", async () => {
    const payload = { items: [sessionPayload] };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      listSessions(
        "signed-token",
        { period: "2026-08", status: "pending_review" },
        "http://api.test",
      ),
    ).resolves.toEqual(payload);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/v1/sessions?period=2026-08&status=pending_review",
      expect.objectContaining({
        headers: { Authorization: "Bearer signed-token" },
      }),
    );
  });

  it("lists assignment units with bearer auth", async () => {
    const payload = { items: [unitPayload] };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      listAssignmentUnits("signed-token", "http://api.test"),
    ).resolves.toEqual(payload);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/v1/assignment-units",
      expect.objectContaining({
        headers: { Authorization: "Bearer signed-token" },
      }),
    );
  });

  it("assigns an encoded session ID with an exact JSON mutation", async () => {
    const request = {
      unitId: unitPayload.id,
      justification: "Confirmado pelo síndico",
    };
    const payload = {
      assignment: {
        id: "a0000000-0000-0000-0000-000000000001",
        sessionId: sessionPayload.id,
        unitId: unitPayload.id,
        assignedBy: "60000000-0000-0000-0000-000000000001",
        justification: request.justification,
        createdAt: "2026-08-30T12:00:00Z",
        updatedAt: "2026-08-30T12:00:00Z",
      },
      session: {
        ...sessionPayload,
        identityConfidence: "assigned",
        status: "ready",
        unitId: unitPayload.id,
        unitCode: unitPayload.code,
        unitName: unitPayload.displayName,
      },
      created: true,
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      assignSession(
        "session/id with spaces",
        request,
        "signed-token",
        "http://api.test",
      ),
    ).resolves.toEqual(payload);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/v1/sessions/session%2Fid%20with%20spaces/assignment",
      expect.objectContaining({
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer signed-token",
        },
        body: JSON.stringify(request),
      }),
    );
  });
});

const invoicePayload = {
  id: "b0000000-0000-0000-0000-000000000001",
  number: "2026-05-A-101",
  billingPeriodId: "c0000000-0000-0000-0000-000000000001",
  periodValue: "2026-05",
  unitId: "40000000-0000-0000-0000-000000000001",
  unitCode: "A-101",
  unitName: "Unidade A-101",
  contactLabel: "Ana Souza",
  energyKwh: "120.000",
  energyValueCents: 11280,
  infraFeeCents: 2500,
  lossShareCents: 340,
  totalCents: 14120,
  issuedAt: "2026-06-01T12:00:00Z",
  items: [],
};

const invoiceDetailPayload = {
  invoice: invoicePayload,
  context: {
    organizationName: "Condomínio",
    siteName: "Garagem",
    timezone: "America/Sao_Paulo",
    tariffName: "Referência",
    tariffSource: "sprint1_reference",
    tariffSourceReference: null,
    tariffValidFrom: "2026-01-01",
    tariffValidTo: null,
    policyName: "Referência",
    infraFeeCents: 2500,
    lossBasisPoints: 400,
    provenanceLabel: "dados simulados",
  },
  bands: [{ code: "fora_ponta", rateCentsPerKwh: 78, energyValueCents: 9360 }],
};

const residentContextPayload = {
  id: "d0000000-0000-0000-0000-000000000001",
  unitId: "40000000-0000-0000-0000-000000000001",
  unitCode: "A-101",
  unitName: "Unidade A-101",
  expiresAt: "2026-06-01T12:15:00Z",
};

describe("billing client", () => {
  it("lists invoices filtered by period and unit", async () => {
    const payload = { items: [invoicePayload] };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      listInvoices(
        "signed-token",
        { periodId: "c0000000-0000-0000-0000-000000000001", unitId: "40000000-0000-0000-0000-000000000001" },
        { baseUrl: "http://api.test" },
      ),
    ).resolves.toEqual(payload);

    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://api.test/v1/invoices?periodId=c0000000-0000-0000-0000-000000000001&unitId=40000000-0000-0000-0000-000000000001",
    );
  });

  it("omits the filter query when no filter is given", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await listInvoices("signed-token", {}, { baseUrl: "http://api.test" });

    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/v1/invoices");
  });

  it("closes a period with POST and no body", async () => {
    const payload = { period: {}, invoices: [invoicePayload] };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await closeBillingPeriod("c0000000-0000-0000-0000-000000000001", "signed-token", {
      baseUrl: "http://api.test",
    });

    const [url, request] = fetchMock.mock.calls[0];
    expect(url).toBe(
      "http://api.test/v1/billing-periods/c0000000-0000-0000-0000-000000000001/close",
    );
    expect(request.method).toBe("POST");
    expect(request.body).toBeUndefined();
  });

  it("surfaces the 409 body when a close is refused", async () => {
    const conflict = { code: "PERIOD_ALREADY_CLOSED", message: "Já fechado.", blockers: [] };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(conflict), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const error = await closeBillingPeriod("period-1", "signed-token", {
      baseUrl: "http://api.test",
    }).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).body).toEqual(conflict);
  });
});

describe("resident context", () => {
  it("sends the context header on a scoped read", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(invoiceDetailPayload), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await getInvoice("b0000000-0000-0000-0000-000000000001", "signed-token", {
      baseUrl: "http://api.test",
      residentContextId: "d0000000-0000-0000-0000-000000000001",
    });

    expect(fetchMock.mock.calls[0][1].headers).toEqual({
      Authorization: "Bearer signed-token",
      "X-Resident-Context": "d0000000-0000-0000-0000-000000000001",
    });
  });

  it("omits the context header when there is no context", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(invoiceDetailPayload), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await getInvoice("b0000000-0000-0000-0000-000000000001", "signed-token", {
      baseUrl: "http://api.test",
    });

    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty(
      "X-Resident-Context",
    );
  });

  it("enters a context without inheriting an active one", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(residentContextPayload), { status: 201 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      enterResidentContext("40000000-0000-0000-0000-000000000001", "signed-token", {
        baseUrl: "http://api.test",
        residentContextId: "d0000000-0000-0000-0000-000000000009",
      }),
    ).resolves.toEqual(residentContextPayload);

    const request = fetchMock.mock.calls[0][1];
    expect(request.headers).not.toHaveProperty("X-Resident-Context");
    expect(JSON.parse(request.body)).toEqual({
      unitId: "40000000-0000-0000-0000-000000000001",
    });
  });

  it("exits with the context header and reads no body from the 204", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      exitResidentContext("d0000000-0000-0000-0000-000000000001", "signed-token", {
        baseUrl: "http://api.test",
      }),
    ).resolves.toBeUndefined();

    const [url, request] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/v1/resident-context");
    expect(request.method).toBe("DELETE");
    expect(request.headers["X-Resident-Context"]).toBe(
      "d0000000-0000-0000-0000-000000000001",
    );
  });

  it("fetches the document as bytes with the bearer token", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(new Blob([new Uint8Array([37, 80, 68, 70])]), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const blob = await downloadInvoiceDocument(
      "b0000000-0000-0000-0000-000000000001",
      "signed-token",
      { baseUrl: "http://api.test" },
    );

    expect(blob.size).toBe(4);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://api.test/v1/invoices/b0000000-0000-0000-0000-000000000001/document",
    );
  });
});
