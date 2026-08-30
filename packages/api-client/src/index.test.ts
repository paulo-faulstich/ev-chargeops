import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  assignSession,
  confirmImport,
  getImportBatch,
  listAssignmentUnits,
  listImportBatches,
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
