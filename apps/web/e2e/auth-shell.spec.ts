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
