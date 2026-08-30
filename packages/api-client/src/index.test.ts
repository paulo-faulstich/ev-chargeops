import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  confirmImport,
  getImportBatch,
  listImportBatches,
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
        new Response(JSON.stringify(errorBody), { status: 422 }),
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
});
