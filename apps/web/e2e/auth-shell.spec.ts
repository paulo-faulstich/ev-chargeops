import { expect, test } from "@playwright/test";

async function breadcrumbTitleGap(page: import("@playwright/test").Page) {
  const breadcrumb = await page
    .getByRole("navigation", { name: "Breadcrumb" })
    .boundingBox();
  const heading = await page.getByRole("heading", { level: 1 }).boundingBox();

  expect(breadcrumb).not.toBeNull();
  expect(heading).not.toBeNull();

  return heading!.y - (breadcrumb!.y + breadcrumb!.height);
}

test("opens the manager product at the dashboard", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Visão geral" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Fontes de dados" }),
  ).toBeVisible();
  const operation = page.getByRole("navigation", { name: "Operação" });
  await expect(operation.getByText("Operação", { exact: true })).toBeVisible();
  await expect(
    operation.getByRole("link", { name: "Visão geral" }),
  ).toHaveAttribute("aria-current", "page");
  await expect(
    operation.getByRole("link", { name: "Recargas" }),
  ).toHaveAttribute("href", "/sessions");
  await expect(operation.locator('[aria-disabled="true"]')).toHaveCount(0);
});

test("marks Recargas as permanent operational navigation", async ({ page }) => {
  await page.route("**/api/v1/sessions**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    });
  });
  await page.route("**/api/v1/assignment-units", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    });
  });
  await page.goto("/sessions?status=pending_review&period=2026-08");

  const operation = page.getByRole("navigation", { name: "Operação" });
  await expect(
    operation.getByRole("link", { name: "Recargas" }),
  ).toHaveAttribute("aria-current", "page");
  await expect(
    operation.getByRole("link", { name: "Visão geral" }),
  ).toHaveAttribute("href", "/dashboard");
  const appHeader = page.getByRole("banner");
  await expect(appHeader).toContainText("LAB FIAP Eco Smart Home");
  await expect(
    appHeader.getByLabel("Administrador Paulo Faulstich"),
  ).toBeVisible();
  expect(
    await page.getByRole("heading", { name: "Recargas" }).evaluate(
      (heading) => Number.parseFloat(getComputedStyle(heading).fontSize),
    ),
  ).toBeLessThanOrEqual(42);
  const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
  await expect(breadcrumb).toContainText("Operação");
  await expect(breadcrumb).toContainText("Recargas");
  await expect(
    page.getByText(
      "Cada recarga registra início, duração, energia consumida e o responsável pelo custo.",
    ),
  ).toBeVisible();
});

test("redirects an unauthenticated Supabase session to login", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-ev-auth-test": "missing" });
  await page.goto("/dashboard");

  await expect(page).toHaveURL(/\/login/);
  await expect(
    page.getByRole("heading", { name: "Entrar no EV ChargeOps" }),
  ).toBeVisible();
});

test("does not expose routes that merely share the login prefix", async ({
  page,
}) => {
  await page.setExtraHTTPHeaders({ "x-ev-auth-test": "missing" });
  await page.goto("/login-preview");

  await expect(page).toHaveURL(/\/login$/);
});

test("keeps data sources visibly scoped under settings on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/settings/data-sources");

  const settingsNavigation = page.getByRole("navigation", {
    name: "Configurações",
  });
  await expect(settingsNavigation.getByText("Configurações")).toBeVisible();
  await expect(
    settingsNavigation.getByRole("link", { name: "Fontes de dados" }),
  ).toBeVisible();
  await expect(page.getByRole("banner")).toContainText(
    "LAB FIAP Eco Smart Home",
  );
  await expect(
    page.getByRole("banner").getByLabel("Administrador Paulo Faulstich"),
  ).toBeVisible();
  const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
  await expect(breadcrumb).toContainText("Configurações");
  await expect(breadcrumb).toContainText("Fontes de dados");
  await expect(
    page.getByText(
      "Importe registros do SEMS+ e acompanhe como os dados entram no ChargeOps.",
    ),
  ).toBeVisible();
});

test("keeps the data sources title at the operational scale", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1640, height: 900 });
  await page.goto("/settings/data-sources");

  expect(
    await page.getByRole("heading", { name: "Fontes de dados" }).evaluate(
      (heading) => Number.parseFloat(getComputedStyle(heading).fontSize),
    ),
  ).toBeLessThanOrEqual(42);
});

test("keeps breadcrumb-to-title spacing consistent across operational pages", async ({
  page,
}) => {
  await page.goto("/dashboard");
  const dashboardGap = await breadcrumbTitleGap(page);

  await page.goto("/sessions?status=pending_review&period=2026-08");
  const recargasGap = await breadcrumbTitleGap(page);

  await page.goto("/settings/data-sources");
  const dataSourcesGap = await breadcrumbTitleGap(page);

  expect(Math.max(dashboardGap, recargasGap, dataSourcesGap)).toBeCloseTo(
    Math.min(dashboardGap, recargasGap, dataSourcesGap),
    0,
  );
});
