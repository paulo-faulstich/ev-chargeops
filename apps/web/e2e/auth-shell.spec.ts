import { expect, test } from "@playwright/test";

test("opens the manager product at the dashboard", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Visão operacional" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Fontes de dados" }),
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
});
