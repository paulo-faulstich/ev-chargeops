import { readFile } from "node:fs/promises";
import path from "node:path";

import { expect, test } from "@playwright/test";

test("previews a SEMS export with explicit provenance", async ({ page }) => {
  await page.goto("/imports/new");
  await page.getByLabel("Arquivo CSV do SEMS+").setInputFiles(
    path.resolve(process.cwd(), "../api/tests/fixtures/sems_sessions.csv"),
  );
  await page.getByRole("button", { name: "Analisar arquivo" }).click();

  await expect(page.getByText("2 registros")).toBeVisible();
  await expect(page.getByText("2 válidos")).toBeVisible();
  await expect(page.getByText("0 inválidos")).toBeVisible();
  await expect(page.getByText("0 duplicados")).toBeVisible();
  await expect(page.getByText("Fonte real").first()).toBeVisible();
  await expect(page.getByText("Identidade desconhecida").first()).toBeVisible();
});

test("selects and previews a SEMS export dropped on the upload panel", async ({ page }) => {
  const fixturePath = path.resolve(process.cwd(), "../api/tests/fixtures/sems_sessions.csv");
  const fixtureContents = await readFile(fixturePath, "utf8");

  await page.goto("/imports/new");

  const uploadPanel = page.getByRole("region", { name: "Selecione a exportação do SEMS+" });
  const dataTransfer = await page.evaluateHandle(
    ({ contents }) => {
      const transfer = new DataTransfer();
      transfer.items.add(new File([contents], "sems_sessions.csv", { type: "text/csv" }));
      return transfer;
    },
    { contents: fixtureContents },
  );

  await uploadPanel.dispatchEvent("dragenter", { dataTransfer });
  await expect(page.getByText("Solte o CSV para selecionar")).toBeVisible();
  await uploadPanel.dispatchEvent("drop", { dataTransfer });

  await expect(page.getByText("Selecionado: sems_sessions.csv")).toBeVisible();
  await page.getByRole("button", { name: "Analisar arquivo" }).click();

  await expect(page.getByText("2 registros")).toBeVisible();
  await expect(page.getByText("2 válidos")).toBeVisible();
});

test("rejects a non-CSV file dropped on the upload panel", async ({ page }) => {
  await page.goto("/imports/new");

  const uploadPanel = page.getByRole("region", { name: "Selecione a exportação do SEMS+" });
  const dataTransfer = await page.evaluateHandle(() => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(["not a SEMS export"], "sessions.txt", { type: "text/plain" }));
    return transfer;
  });

  await uploadPanel.dispatchEvent("drop", { dataTransfer });

  await expect(uploadPanel.getByRole("alert")).toContainText("Selecione um arquivo CSV");
  await expect(page.getByRole("button", { name: "Analisar arquivo" })).toBeDisabled();
});
