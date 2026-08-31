import { readFile } from "node:fs/promises";
import path from "node:path";

import { expect, test } from "@playwright/test";

const FIXTURE_PATH = path.resolve(
  process.cwd(),
  "../api/tests/fixtures/sems_sessions.csv",
);

test.describe.configure({ mode: "serial" });

test("shows an empty import history before any write", async ({ page }) => {
  await page.goto("/settings/data-sources");

  await expect(
    page.getByRole("heading", { name: "Histórico de importações" }),
  ).toBeVisible();
  await expect(page.getByText("Nenhum lote importado ainda.")).toBeVisible();
});

test("shows a recoverable import-history error", async ({ page }) => {
  await page.route("**/api/v1/import-batches", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 503, body: "temporarily unavailable" });
      return;
    }
    await route.continue();
  });

  await page.goto("/settings/data-sources");

  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "O histórico não foi carregado. Tente novamente." }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Atualizar histórico" }),
  ).toBeVisible();
});

test("orders import history from newest to oldest", async ({ page }) => {
  await page.route("**/api/v1/import-batches", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }

    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "70000000-0000-0000-0000-000000000001",
            filename: "oldest.csv",
            checksum: "oldest",
            source: "sems_csv",
            status: "completed",
            created: true,
            totalCount: 1,
            validCount: 1,
            invalidCount: 0,
            duplicateCount: 0,
            createdAt: "2026-08-28T12:00:00Z",
          },
          {
            id: "70000000-0000-0000-0000-000000000002",
            filename: "newest.csv",
            checksum: "newest",
            source: "sems_csv",
            status: "completed",
            created: true,
            totalCount: 3,
            validCount: 1,
            invalidCount: 1,
            duplicateCount: 1,
            createdAt: "2026-08-29T12:00:00Z",
          },
        ],
      }),
    });
  });

  await page.goto("/settings/data-sources");

  const historyRows = page
    .getByRole("table", { name: "Histórico de importações" })
    .locator("tbody tr");
  await expect(historyRows).toHaveCount(2);
  await expect(historyRows.nth(0)).toContainText("newest.csv");
  await expect(historyRows.nth(0)).toContainText(
    "3 total · 1 válido · 1 inválido · 1 duplicado",
  );
  await expect(historyRows.nth(1)).toContainText("oldest.csv");
  await expect(historyRows.nth(1)).toContainText(
    "1 total · 1 válido · 0 inválidos · 0 duplicados",
  );
});

test("keeps confirmation errors recoverable without losing the preview", async ({
  page,
}) => {
  await page.goto("/settings/data-sources");
  await page.getByLabel("Arquivo CSV do SEMS+").setInputFiles(FIXTURE_PATH);
  await page.getByRole("button", { name: "Analisar arquivo" }).click();

  await page.route("**/api/v1/import-batches", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ status: 503, body: "temporarily unavailable" });
      return;
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "Confirmar importação" }).click();

  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "A importação não foi concluída. Tente novamente." }),
  ).toBeVisible();
  await expect(page.getByText("Nenhum registro foi gravado")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Confirmar importação" }),
  ).toBeEnabled();
});

test("confirms a SEMS batch and shows idempotent descending history", async ({
  page,
}) => {
  await page.goto("/settings/data-sources");
  await page.getByLabel("Arquivo CSV do SEMS+").setInputFiles(FIXTURE_PATH);
  await page.getByRole("button", { name: "Analisar arquivo" }).click();

  await expect(page.getByText("2 válidos", { exact: true })).toBeVisible();
  await expect(page.getByText("Nenhum registro foi gravado")).toBeVisible();
  await expect(page.getByText("Nenhum lote importado ainda.")).toBeVisible();

  const creationResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/import-batches"),
  );
  await page.getByRole("button", { name: "Confirmar importação" }).click();
  expect((await creationResponse).status()).toBe(201);

  await expect(
    page.getByText("Importação concluída", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("2 sessões adicionadas")).toBeVisible();
  await expect(page.getByText("Agosto 2026", { exact: true })).toBeVisible();
  await expect(
    page.getByText("0 inválidos · 0 duplicados", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Continuar fechamento" }),
  ).toHaveAttribute("href", "/dashboard");
  await expect(
    page.getByRole("button", { name: "Importar outro arquivo" }),
  ).toBeVisible();
  await expect(page.getByText("Confirmação necessária")).toBeHidden();
  await expect(
    page.getByRole("button", { name: "Importar novamente" }),
  ).toBeHidden();
  const history = page.getByRole("table", {
    name: "Histórico de importações",
  });
  await expect(
    history.getByRole("row", { name: /sems_sessions\.csv.*Concluído/ }),
  ).toBeVisible();
  await expect(history.getByText("SEMS+ CSV")).toBeVisible();
  await expect(page.getByText("1 lote", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const replayResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/import-batches"),
  );
  await page.getByRole("button", { name: "Importar outro arquivo" }).click();
  await expect(page.getByLabel("Arquivo CSV do SEMS+")).toBeVisible();
  await page.getByLabel("Arquivo CSV do SEMS+").setInputFiles(FIXTURE_PATH);
  await page.getByRole("button", { name: "Analisar arquivo" }).click();
  await page.getByRole("button", { name: "Confirmar importação" }).click();
  expect((await replayResponse).status()).toBe(200);

  await expect(
    page.getByText("Lote já existente; nenhuma sessão duplicada"),
  ).toBeVisible();
  await expect(page.getByText("1 lote", { exact: true })).toBeVisible();
  await expect(
    history.getByRole("row", { name: /sems_sessions\.csv.*Concluído/ }),
  ).toHaveCount(1);
});

test("ignores a stale initial history response after confirmation", async ({
  page,
}) => {
  let releaseInitialHistory: () => void = () => undefined;
  let markInitialHistoryRequested: () => void = () => undefined;
  const initialHistoryGate = new Promise<void>((resolve) => {
    releaseInitialHistory = resolve;
  });
  const initialHistoryRequested = new Promise<void>((resolve) => {
    markInitialHistoryRequested = resolve;
  });
  let delayedHistoryCount = 0;
  let confirmationStarted = false;

  await page.route("**/api/v1/import-batches", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }

    if (confirmationStarted) {
      await route.continue();
      return;
    }

    delayedHistoryCount += 1;
    const delayedHistoryId = delayedHistoryCount.toString();
    markInitialHistoryRequested();
    await initialHistoryGate;
    await route.fulfill({
      contentType: "application/json",
      headers: { "x-test-delayed-history": delayedHistoryId },
      body: JSON.stringify({ items: [] }),
    });
  });

  await page.goto("/settings/data-sources");
  await initialHistoryRequested;

  const fixture = await readFile(FIXTURE_PATH, "utf8");
  await page.getByLabel("Arquivo CSV do SEMS+").setInputFiles({
    name: "sems_race.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(fixture.replaceAll("29/08/2026", "30/08/2026")),
  });
  await page.getByRole("button", { name: "Analisar arquivo" }).click();
  confirmationStarted = true;
  const creationResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/import-batches"),
  );
  await page.getByRole("button", { name: "Confirmar importação" }).click();
  expect((await creationResponse).status()).toBe(201);

  const newBatchRow = page
    .getByRole("table", { name: "Histórico de importações" })
    .getByRole("row", { name: /sems_race\.csv.*Concluído/ });
  await expect(newBatchRow).toBeVisible();

  const delayedResponses = Array.from(
    { length: delayedHistoryCount },
    (_, index) =>
      page.waitForResponse(
        (response) =>
          response.headers()["x-test-delayed-history"] ===
          (index + 1).toString(),
      ),
  );
  releaseInitialHistory();
  const completedDelayedResponses = await Promise.all(delayedResponses);
  await Promise.all(
    completedDelayedResponses.map((response) => response.finished()),
  );
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );

  await expect(newBatchRow).toBeVisible();
  await expect(page.getByText("Nenhum lote importado ainda.")).toBeHidden();
});

test("hands a confirmed SEMS import to the manager action queue", async ({
  page,
}) => {
  const fixture = await readFile(FIXTURE_PATH, "utf8");

  await page.goto("/settings/data-sources");
  await page.getByLabel("Arquivo CSV do SEMS+").setInputFiles({
    name: "sems_monthly_close.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(fixture.replaceAll("29/08/2026", "29/09/2026")),
  });
  await page.getByRole("button", { name: "Analisar arquivo" }).click();
  const confirmationResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/import-batches"),
  );
  await page.getByRole("button", { name: "Confirmar importação" }).click();
  const confirmed = await confirmationResponse;
  expect(confirmed.status(), await confirmed.text()).toBe(201);

  await expect(page.getByText("2 sessões adicionadas")).toBeVisible();
  await page.getByRole("link", { name: "Continuar fechamento" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  // This test drives the real API, so the dashboard may hold several months
  // and render a picker instead of plain text. The chart caption names the
  // selected period in either shape.
  await expect(page.getByText("kWh · Setembro 2026")).toBeVisible();
  await expect(page.getByText("0 de 2", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Revisar 2 pendências" }).click();

  await expect(page).toHaveURL(
    /\/sessions\?status=pending_review&period=2026-09$/,
  );
  await page
    .getByLabel("Unidade responsável")
    .selectOption({ label: "Unidade A-101" });
  await page
    .getByLabel("Justificativa")
    .fill("Responsável confirmado pelo administrador");
  await page
    .getByRole("button", { name: "Atribuir e revisar próxima" })
    .click();

  await expect(page.getByRole("status")).toContainText("Unidade A-101");
  await expect(page.getByText("1 pendência no período")).toBeVisible();
});
