import { expect, test, type Page } from "@playwright/test";

const batch = {
  id: "70000000-0000-0000-0000-000000000001",
  filename: "sems_sessions.csv",
  checksum: "dashboard-fixture",
  source: "sems_csv",
  status: "completed",
  created: true,
  totalCount: 2,
  validCount: 2,
  invalidCount: 0,
  duplicateCount: 0,
  createdAt: "2026-08-29T22:00:00Z",
};

async function routeDashboardData(page: Page, populated: boolean) {
  await page.route("**/api/v1/import-batches**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;

    if (pathname === "/api/v1/import-batches") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ items: populated ? [batch] : [] }),
      });
      return;
    }

    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ...batch,
        records: [
          {
            id: "80000000-0000-0000-0000-000000000001",
            rowNumber: 2,
            raw: {
              "Start Time": "29/08/2026 17:10:00",
              "End Time": "29/08/2026 18:10:00",
              "Charging Energy(kWh)": "7.00",
              "Charging Port": "1",
              "Card ID": "97500NAP25BL0008",
              "Device SN": "97500NAP25BL0008",
            },
            classification: "valid",
            errorField: null,
            errorCode: null,
            errorMessage: null,
            sessionId: "90000000-0000-0000-0000-000000000001",
          },
          {
            id: "80000000-0000-0000-0000-000000000002",
            rowNumber: 3,
            raw: {
              "Start Time": "29/08/2026 18:30:00",
              "End Time": "29/08/2026 19:00:00",
              "Charging Energy(kWh)": "3.50",
              "Charging Port": "1",
              "Card ID": "",
              "Device SN": "97500NAP25BL0008",
            },
            classification: "valid",
            errorField: null,
            errorCode: null,
            errorMessage: null,
            sessionId: "90000000-0000-0000-0000-000000000002",
          },
        ],
      }),
    });
  });
}

test("guides a first-time manager to import SEMS sessions", async ({ page }) => {
  await routeDashboardData(page, false);
  await page.goto("/dashboard");

  await expect(page.getByRole("heading", { name: "Visão geral" })).toBeVisible();
  await expect(page.getByText("Nenhum dado importado")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Importar dados do SEMS+" }),
  ).toHaveAttribute("href", "/settings/data-sources");
  await expect(page.getByText("Importar sessões", { exact: true })).toBeVisible();
  await expect(page.getByText("Revisar atribuições", { exact: true })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("turns imported sessions into an actionable monthly dashboard", async ({
  page,
}) => {
  await routeDashboardData(page, true);
  await page.goto("/dashboard");

  await expect(page.getByText("Agosto 2026", { exact: true })).toBeVisible();
  await expect(page.getByText("10,50 kWh", { exact: true })).toBeVisible();
  await expect(page.getByText(/R\$\s*9,87/)).toBeVisible();
  await expect(page.getByText("1 de 2", { exact: true })).toBeVisible();
  await expect(
    page.getByText("1 sessão ainda não pode ser cobrada porque falta identificar o responsável."),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Revisar 1 pendência" }),
  ).toHaveAttribute("href", "/settings/data-sources");
  await expect(
    page.getByRole("table", { name: "Custos por responsável" }),
  ).toContainText("Não atribuído");
});
