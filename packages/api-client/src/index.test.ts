import { afterEach, describe, expect, it, vi } from "vitest";

import { previewImport } from "./index";

afterEach(() => vi.unstubAllGlobals());

describe("previewImport", () => {
  it("posts the CSV as multipart data and returns the preview", async () => {
    const payload = {
      filename: "sems.csv",
      checksum: "abc123",
      source: "sems_export",
      totalCount: 2,
      validCount: 2,
      invalidCount: 0,
      duplicateCount: 0,
      records: [],
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["header\nvalue"], "sems.csv", { type: "text/csv" });

    await expect(previewImport(file, "http://api.test")).resolves.toEqual(payload);
    const [url, request] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/v1/import-batches/preview");
    expect(request.method).toBe("POST");
    expect(request.body).toBeInstanceOf(FormData);
    expect(request.body.get("file")).toBe(file);
  });
});
