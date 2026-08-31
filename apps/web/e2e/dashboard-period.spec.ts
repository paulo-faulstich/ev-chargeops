import { expect, test, type Page } from "@playwright/test";
import type { SessionResponse } from "@ev-chargeops/api-client";

/**
 * Real telemetry and the demonstration scenario live in different months, and
 * the manager must be able to move between them without ever being unsure which
 * one is on screen.
 */

function session(
  id: string,
  startedAt: string,
  energyKwh: string,
  provenance: string,
  source: string,
): SessionResponse {
  return {
    id,
    startedAt,
    endedAt: startedAt,
    energyKwh,
    chargerSerial: "97500NAP25BL0008",
    source,
    provenance,
    identityConfidence: "assigned",
    status: "ready",
    unitId: "40000000-0000-0000-0000-000000000001",
    unitCode: "A-101",
    unitName: "Unidade A-101",
    residentName: null,
  };
}

const realAugust = session(
  "90000000-0000-0000-0000-000000000001",
  "2026-08-29T20:10:00Z",
  "7.000",
  "real",
  "sems_export",
);

const demoMay = [
  session(
    "90000000-0000-0000-0000-000000000010",
    "2026-05-04T23:00:00Z",
    "21.500",
    "simulated",
    "simulated",
  ),
  session(
    "90000000-0000-0000-0000-000000000011",
    "2026-05-19T22:00:00Z",
    "12.200",
    "simulated",
    "simulated",
  ),
];

async function routeSessions(page: Page, items: SessionResponse[]) {
  await page.route("**/api/v1/sessions**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ items }),
    });
  });
}

test("labels a real period as observed telemetry", async ({ page }) => {
  await routeSessions(page, [realAugust]);
  await page.goto("/dashboard");

  await expect(page.getByText("SEMS+ real")).toBeVisible();
  await expect(page.getByText("Cenário demonstrativo")).toHaveCount(0);
});

test("labels the demonstration month and never calls it real", async ({
  page,
}) => {
  await routeSessions(page, demoMay);
  await page.goto("/dashboard");

  await expect(page.getByText("Cenário demonstrativo")).toBeVisible();
  await expect(page.getByText("SEMS+ real")).toHaveCount(0);
});

test("lets the manager switch periods and relabels provenance", async ({
  page,
}) => {
  await routeSessions(page, [realAugust, ...demoMay]);
  await page.goto("/dashboard");

  // The most recent period opens by default: the real August telemetry.
  await expect(page.getByText("SEMS+ real")).toBeVisible();

  const picker = page.locator(".dashboard-period-picker select");
  await expect(picker).toBeVisible();
  await expect(picker.locator("option")).toHaveCount(2);

  await picker.selectOption("2026-05");

  await expect(page.getByText("Cenário demonstrativo")).toBeVisible();
  await expect(page.getByText("SEMS+ real")).toHaveCount(0);
});

test("keeps a single period as plain text instead of a picker", async ({
  page,
}) => {
  await routeSessions(page, [realAugust]);
  await page.goto("/dashboard");

  await expect(page.locator(".dashboard-period-picker")).toHaveCount(0);
  await expect(page.getByText("Agosto 2026", { exact: true })).toBeVisible();
});

test("buckets a late-evening session into the local day, not the UTC one", async ({
  page,
}) => {
  // 23:30 on 31 May in São Paulo is already 1 June in UTC. The chart must show
  // it under 31 May, matching the period the close will bill it in.
  await routeSessions(page, [
    session(
      "90000000-0000-0000-0000-000000000020",
      "2026-06-01T02:30:00Z",
      "18.000",
      "simulated",
      "simulated",
    ),
  ]);
  await page.goto("/dashboard");

  await expect(page.getByText("Maio 2026", { exact: true })).toBeVisible();
  // "Atualizado em 31 de mai., 23:30" carries the same date, so this must be
  // the chart's own label to prove the bucketing.
  await expect(
    page.locator(".usage-label", { hasText: "31 de mai." }),
  ).toBeVisible();
});
