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
