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
            totalCount: 2,
            validCount: 2,
            invalidCount: 0,
            duplicateCount: 0,
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
  await expect(historyRows.nth(1)).toContainText("oldest.csv");
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

  await expect(page.getByText("2 válidos")).toBeVisible();
  await expect(page.getByText("Nenhum registro foi gravado")).toBeVisible();
  await expect(page.getByText("Nenhum lote importado ainda.")).toBeVisible();

  const creationResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/import-batches"),
  );
  await page.getByRole("button", { name: "Confirmar importação" }).click();
  expect((await creationResponse).status()).toBe(201);

  await expect(page.getByRole("status")).toContainText(
    "2 sessões importadas; nenhum registro inválido.",
  );
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
  await page.getByRole("button", { name: "Importar novamente" }).click();
  expect((await replayResponse).status()).toBe(200);

  await expect(page.getByRole("status")).toContainText(
    "Lote já importado; nenhuma nova sessão criada.",
  );
  await expect(page.getByText("1 lote", { exact: true })).toBeVisible();
  await expect(
    history.getByRole("row", { name: /sems_sessions\.csv.*Concluído/ }),
  ).toHaveCount(1);
});
