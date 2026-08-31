import { expect, test, type Page } from "@playwright/test";

/** Rows of the review queue, not of the period's full session list.
 *
 * The screen shows both tables, so an unscoped row locator matches the same
 * charge twice and the assertion stops meaning "the queue holds this".
 */
function queue(page: Page) {
  return page.getByRole("table", { name: "Recargas pendentes" });
}

const UNIT_A_ID = "40000000-0000-0000-0000-000000000001";
const UNIT_B_ID = "40000000-0000-0000-0000-000000000002";
const FIRST_SESSION_ID = "90000000-0000-0000-0000-000000000001";
const JULY_SESSION_ID = "90000000-0000-0000-0000-000000000007";

const pendingSessions = {
  items: [
    {
      id: FIRST_SESSION_ID,
      startedAt: "2026-08-29T20:10:00Z",
      endedAt: "2026-08-29T21:10:00Z",
      energyKwh: "7.000",
      chargerSerial: "97500NAP25BL0008",
      source: "sems_export",
      provenance: "observed",
      identityConfidence: "unknown",
      status: "pending_review",
      unitId: null,
      unitCode: null,
      unitName: null,
      residentName: null,
    },
    {
      id: "90000000-0000-0000-0000-000000000002",
      startedAt: "2026-08-30T00:30:00Z",
      endedAt: "2026-08-30T01:00:00Z",
      energyKwh: "3.500",
      chargerSerial: "97500NAP25BL0008",
      source: "sems_export",
      provenance: "observed",
      identityConfidence: "unknown",
      status: "pending_review",
      unitId: null,
      unitCode: null,
      unitName: null,
      residentName: null,
    },
  ],
};

const assignmentUnits = {
  items: [
    {
      id: UNIT_A_ID,
      code: "A-101",
      displayName: "Unidade A-101",
      residentName: "Ana Oliveira",
    },
    {
      id: UNIT_B_ID,
      code: "A-102",
      displayName: "Unidade A-102",
      residentName: null,
    },
  ],
};

const julySessions = {
  items: [
    {
      id: JULY_SESSION_ID,
      startedAt: "2026-07-18T18:00:00Z",
      endedAt: "2026-07-18T18:45:00Z",
      energyKwh: "4.250",
      chargerSerial: "97500NAP25BL0008",
      source: "sems_export",
      provenance: "observed",
      identityConfidence: "unknown",
      status: "pending_review",
      unitId: null,
      unitCode: null,
      unitName: null,
      residentName: null,
    },
  ],
};

async function routeSessionReview(
  page: Page,
  options: {
    assignmentGate?: Promise<void>;
    onAssignmentStart?: () => void;
  } = {},
) {
  let assignmentBody: unknown;

  await page.route("**/api/v1/sessions**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (
      request.method() === "GET" &&
      url.pathname === "/api/v1/sessions"
    ) {
      expect(url.searchParams.get("period")).toBe("2026-08");
      if (url.searchParams.has("status")) {
        expect(url.searchParams.get("status")).toBe("pending_review");
      }
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(pendingSessions),
      });
      return;
    }

    if (
      request.method() === "PUT" &&
      url.pathname === `/api/v1/sessions/${FIRST_SESSION_ID}/assignment`
    ) {
      assignmentBody = request.postDataJSON();
      options.onAssignmentStart?.();
      await options.assignmentGate;
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          assignment: {
            id: "a0000000-0000-0000-0000-000000000001",
            sessionId: FIRST_SESSION_ID,
            unitId: UNIT_A_ID,
            assignedBy: "60000000-0000-0000-0000-000000000001",
            justification: "Confirmado pela portaria",
            createdAt: "2026-08-30T12:00:00Z",
            updatedAt: "2026-08-30T12:00:00Z",
          },
          session: {
            id: FIRST_SESSION_ID,
            startedAt: "2026-08-29T20:10:00Z",
            endedAt: "2026-08-29T21:10:00Z",
            energyKwh: "7.000",
            chargerSerial: "97500NAP25BL0008",
            source: "sems_export",
            provenance: "observed",
            identityConfidence: "assigned",
            status: "ready",
            unitId: UNIT_A_ID,
            unitCode: "A-101",
            unitName: "Unidade A-101",
            residentName: "Ana Oliveira",
          },
          created: true,
        }),
      });
      return;
    }

    await route.abort();
  });

  await page.route("**/api/v1/assignment-units", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(assignmentUnits),
    });
  });

  return () => assignmentBody;
}

async function routeCrossPeriodReview(
  page: Page,
  options: {
    assignmentGate?: Promise<void>;
    onAssignmentStart?: () => void;
    julyLoadGate?: Promise<void>;
    onJulyLoadStart?: () => void;
  } = {},
) {
  await page.route("**/api/v1/sessions**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (
      request.method() === "GET" &&
      url.pathname === "/api/v1/sessions"
    ) {
      if (url.searchParams.get("period") === "2026-07") {
        options.onJulyLoadStart?.();
        await options.julyLoadGate;
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify(julySessions),
        });
        return;
      }

      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(pendingSessions),
      });
      return;
    }

    if (
      request.method() === "PUT" &&
      url.pathname === `/api/v1/sessions/${FIRST_SESSION_ID}/assignment`
    ) {
      options.onAssignmentStart?.();
      await options.assignmentGate;
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          assignment: {
            id: "a0000000-0000-0000-0000-000000000001",
            sessionId: FIRST_SESSION_ID,
            unitId: UNIT_A_ID,
            assignedBy: "60000000-0000-0000-0000-000000000001",
            justification: "Confirmado pela portaria",
            createdAt: "2026-08-30T12:00:00Z",
            updatedAt: "2026-08-30T12:00:00Z",
          },
          session: {
            id: FIRST_SESSION_ID,
            startedAt: "2026-08-29T20:10:00Z",
            endedAt: "2026-08-29T21:10:00Z",
            energyKwh: "7.000",
            chargerSerial: "97500NAP25BL0008",
            source: "sems_export",
            provenance: "observed",
            identityConfidence: "assigned",
            status: "ready",
            unitId: UNIT_A_ID,
            unitCode: "A-101",
            unitName: "Unidade A-101",
            residentName: "Ana Oliveira",
          },
          created: true,
        }),
      });
      return;
    }

    await route.abort();
  });

  await page.route("**/api/v1/assignment-units", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(assignmentUnits),
    });
  });
}

test("redirects an unauthenticated session review to login", async ({ page }) => {
  await page.setExtraHTTPHeaders({ "x-ev-auth-test": "missing" });
  await page.goto("/sessions?status=pending_review&period=2026-08");

  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", { name: "Entrar no EV ChargeOps" }),
  ).toBeVisible();
});

test("assigns observed evidence and advances the pending queue", async ({
  page,
}) => {
  const assignmentBody = await routeSessionReview(page);

  await page.goto("/sessions?status=pending_review&period=2026-08");
  await expect(page.getByRole("heading", { name: "Recargas" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Voltar para visão geral" }),
  ).toBeVisible();
  await expect(page.getByText("2 pendências no período")).toBeVisible();

  const secondRow = queue(page).getByRole("row", { name: /3,50 kWh/ });
  await expect(secondRow).not.toHaveAttribute("tabindex");
  const secondSessionButton = secondRow.getByRole("button", {
    name: /3,50 kWh/,
  });
  await secondSessionButton.focus();
  await secondSessionButton.press("Enter");
  await expect(
    page.getByRole("region", { name: "Evidência da recarga" }),
  ).toContainText("3,50 kWh");
  await queue(page)
    .getByRole("row", { name: /7,00 kWh/ })
    .getByRole("button", { name: /7,00 kWh/ })
    .click();

  const evidence = page.getByRole("region", { name: "Evidência da recarga" });
  await expect(evidence).toContainText("7,00 kWh");
  await expect(evidence).toContainText("29/08/2026, 17:10");
  await expect(evidence).toContainText("97500NAP25BL0008");
  await expect(evidence).toContainText("Observada · SEMS+ CSV");

  await page.getByLabel("Unidade responsável").selectOption(UNIT_A_ID);
  await page.getByLabel("Justificativa").fill("Confirmado pela portaria");

  await expect(evidence).toContainText("7,00 kWh");
  await expect(evidence).toContainText("29/08/2026, 17:10");
  await expect(evidence).toContainText("97500NAP25BL0008");
  await expect(evidence).toContainText("Observada · SEMS+ CSV");

  await page
    .getByRole("button", { name: "Atribuir e revisar próxima" })
    .click();

  expect(assignmentBody()).toEqual({
    unitId: UNIT_A_ID,
    justification: "Confirmado pela portaria",
  });
  await expect(page.getByRole("status")).toContainText("Unidade A-101");
  await expect(page.getByText("1 pendência no período")).toBeVisible();
  await expect(page.getByLabel("Justificativa")).toHaveValue("");
  await expect(queue(page).getByRole("row", { name: /7,00 kWh/ })).toHaveCount(0);
  await expect(evidence).toContainText("3,50 kWh");

  await page.screenshot({
    path: "test-results/task5-session-review-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await expect(
    page.getByRole("link", { name: "Voltar para visão geral" }),
  ).toBeVisible();
  await expect(evidence).toBeVisible();
  await page.screenshot({
    path: "test-results/task5-session-review-mobile.png",
    fullPage: true,
  });
});

test("freezes the visible review context while an assignment is in flight", async ({
  page,
}) => {
  let releaseAssignment: () => void = () => undefined;
  let markAssignmentStarted: () => void = () => undefined;
  const assignmentGate = new Promise<void>((resolve) => {
    releaseAssignment = resolve;
  });
  const assignmentStarted = new Promise<void>((resolve) => {
    markAssignmentStarted = resolve;
  });
  await routeSessionReview(page, {
    assignmentGate,
    onAssignmentStart: markAssignmentStarted,
  });

  await page.goto("/sessions?status=pending_review&period=2026-08");
  await page.getByLabel("Unidade responsável").selectOption(UNIT_A_ID);
  await page.getByLabel("Justificativa").fill("Confirmado pela portaria");
  await page
    .getByRole("button", { name: "Atribuir e revisar próxima" })
    .click();
  await assignmentStarted;

  try {
    await expect(page.getByLabel("Filtrar período")).toBeDisabled();
    await expect(page.getByLabel("Unidade responsável")).toBeDisabled();
    await expect(page.getByLabel("Justificativa")).toBeDisabled();
    await expect(
      queue(page)
        .getByRole("row", { name: /3,50 kWh/ })
        .getByRole("button", { name: /3,50 kWh/ }),
    ).toBeDisabled();
    await expect(
      page.getByRole("region", { name: "Evidência da recarga" }),
    ).toContainText("7,00 kWh");
  } finally {
    releaseAssignment();
  }
  await expect(page.getByRole("status")).toContainText("Unidade A-101");
  await expect(page).toHaveURL(
    "/sessions?status=pending_review&period=2026-08",
  );
  await expect(
    page.getByRole("region", { name: "Evidência da recarga" }),
  ).toContainText("3,50 kWh");
});

test("ignores an August assignment completion after external navigation loads July", async ({
  page,
}) => {
  let releaseAssignment: () => void = () => undefined;
  let markAssignmentStarted: () => void = () => undefined;
  const assignmentGate = new Promise<void>((resolve) => {
    releaseAssignment = resolve;
  });
  const assignmentStarted = new Promise<void>((resolve) => {
    markAssignmentStarted = resolve;
  });
  await routeCrossPeriodReview(page, {
    assignmentGate,
    onAssignmentStart: markAssignmentStarted,
  });

  await page.goto("/sessions?status=pending_review&period=2026-08");
  await page.getByLabel("Unidade responsável").selectOption(UNIT_A_ID);
  await page.getByLabel("Justificativa").fill("Confirmado pela portaria");
  await page
    .getByRole("button", { name: "Atribuir e revisar próxima" })
    .click();
  await assignmentStarted;

  await page.evaluate(() => {
    window.history.pushState(
      null,
      "",
      "/sessions?status=pending_review&period=2026-07",
    );
  });
  await expect(page).toHaveURL(
    "/sessions?status=pending_review&period=2026-07",
  );
  await expect(page.getByText("Julho de 2026", { exact: true })).toBeVisible();
  const evidence = page.getByRole("region", { name: "Evidência da recarga" });
  await expect(evidence).toContainText("4,25 kWh");

  const assignmentResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      response.url().endsWith(`/api/v1/sessions/${FIRST_SESSION_ID}/assignment`),
  );
  releaseAssignment();
  await assignmentResponse;
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );

  await expect(page).toHaveURL(
    "/sessions?status=pending_review&period=2026-07",
  );
  await expect(page.getByText("Julho de 2026", { exact: true })).toBeVisible();
  await expect(evidence).toContainText("4,25 kWh");
  await expect(evidence).not.toContainText("3,50 kWh");
});

test("hides August evidence while a canonical July load is pending", async ({
  page,
}) => {
  let releaseJulyLoad: () => void = () => undefined;
  let markJulyLoadStarted: () => void = () => undefined;
  const julyLoadGate = new Promise<void>((resolve) => {
    releaseJulyLoad = resolve;
  });
  const julyLoadStarted = new Promise<void>((resolve) => {
    markJulyLoadStarted = resolve;
  });
  await routeCrossPeriodReview(page, {
    julyLoadGate,
    onJulyLoadStart: markJulyLoadStarted,
  });

  await page.goto("/sessions?status=pending_review&period=2026-08");
  await expect(
    page.getByRole("region", { name: "Evidência da recarga" }),
  ).toContainText("7,00 kWh");

  await page.evaluate(() => {
    window.history.pushState(
      null,
      "",
      "/sessions?status=pending_review&period=2026-07",
    );
  });
  await julyLoadStarted;

  try {
    await expect(page.getByText("Carregando recargas e unidades disponíveis…")).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Evidência da recarga" }),
    ).toHaveCount(0);
  } finally {
    releaseJulyLoad();
  }

  await expect(
    page.getByRole("region", { name: "Evidência da recarga" }),
  ).toContainText("4,25 kWh");
});

test("uses roving focus and arrow keys across session actions", async ({ page }) => {
  await routeSessionReview(page);
  await page.goto("/sessions?status=pending_review&period=2026-08");

  const firstButton = queue(page)
    .getByRole("row", { name: /7,00 kWh/ })
    .getByRole("button", { name: /7,00 kWh/ });
  const secondButton = queue(page)
    .getByRole("row", { name: /3,50 kWh/ })
    .getByRole("button", { name: /3,50 kWh/ });
  await expect(firstButton).toHaveAttribute("tabindex", "0");
  await expect(secondButton).toHaveAttribute("tabindex", "-1");

  await firstButton.focus();
  await firstButton.press("ArrowDown");
  await expect(secondButton).toBeFocused();
  await expect(secondButton).toHaveAttribute("aria-pressed", "true");
  await expect(firstButton).toHaveAttribute("tabindex", "-1");
  await expect(secondButton).toHaveAttribute("tabindex", "0");
  await expect(
    page.getByRole("region", { name: "Evidência da recarga" }),
  ).toContainText("3,50 kWh");

  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Unidade responsável")).toBeFocused();
});

test("keeps start and energy values in distinct associated table columns", async ({
  page,
}) => {
  await routeSessionReview(page);
  await page.goto("/sessions?status=pending_review&period=2026-08");

  const table = page.getByRole("table", { name: "Recargas pendentes" });
  const headers = table.getByRole("columnheader");
  await expect(headers).toHaveCount(2);
  await expect(headers.nth(0)).toHaveAttribute("id", "session-start-heading");
  await expect(headers.nth(1)).toHaveAttribute("id", "session-energy-heading");

  const row = table.getByRole("row", { name: /7,00 kWh/ });
  const cells = row.getByRole("cell");
  await expect(cells).toHaveCount(2);
  await expect(cells.nth(0)).toHaveAttribute("headers", "session-start-heading");
  await expect(cells.nth(1)).toHaveAttribute("headers", "session-energy-heading");
  await expect(row.getByRole("button", { name: /7,00 kWh/ })).toBeVisible();
});

test("canonicalizes a contradictory session status before showing the queue", async ({
  page,
}) => {
  await routeSessionReview(page);

  await page.goto("/sessions?status=ready&period=2026-08");

  await expect(page).toHaveURL(
    "/sessions?status=pending_review&period=2026-08",
  );
  await expect(page.getByText("2 pendências no período")).toBeVisible();
});

test("records the effective period when session filters are missing or invalid", async ({
  page,
}) => {
  await routeSessionReview(page);

  await page.goto("/sessions");
  await expect(page).toHaveURL(
    "/sessions?status=pending_review&period=2026-08",
  );
  await expect(page.getByText("2 pendências no período")).toBeVisible();

  await page.goto("/sessions?status=pending_review&period=2026-13");
  await expect(page).toHaveURL(
    "/sessions?status=pending_review&period=2026-08",
  );
  await expect(page.getByText("2 pendências no período")).toBeVisible();
});

test("keeps assignment evidence and inputs after a recoverable PUT error", async ({
  page,
}) => {
  await routeSessionReview(page);
  await page.route("**/api/v1/sessions/*/assignment", async (route) => {
    await route.fulfill({ status: 503, body: "temporarily unavailable" });
  });

  await page.goto("/sessions?status=pending_review&period=2026-08");
  await queue(page)
    .getByRole("row", { name: /7,00 kWh/ })
    .getByRole("button", { name: /7,00 kWh/ })
    .click();
  await page.getByLabel("Unidade responsável").selectOption(UNIT_A_ID);
  await page.getByLabel("Justificativa").fill("Confirmado pela portaria");
  await page
    .getByRole("button", { name: "Atribuir e revisar próxima" })
    .click();

  await expect(
    page.getByRole("alert").filter({ hasText: "A atribuição não foi salva." }),
  ).toBeVisible();
  await expect(page.getByLabel("Unidade responsável")).toHaveValue(UNIT_A_ID);
  await expect(page.getByLabel("Justificativa")).toHaveValue(
    "Confirmado pela portaria",
  );
  await expect(
    page.getByRole("region", { name: "Evidência da recarga" }),
  ).toContainText("7,00 kWh");
  await expect(
    page.getByRole("button", { name: "Atribuir e revisar próxima" }),
  ).toBeEnabled();
});

test("distinguishes no imports from an assigned period when the filter changes", async ({
  page,
}) => {
  await page.route("**/api/v1/sessions**", async (route) => {
    const url = new URL(route.request().url());
    const period = url.searchParams.get("period");
    const filtered = url.searchParams.get("status") === "pending_review";
    const assignedSession = {
      id: "90000000-0000-0000-0000-000000000003",
      startedAt: "2026-08-18T12:00:00Z",
      endedAt: "2026-08-18T13:00:00Z",
      energyKwh: "5.250",
      chargerSerial: "97500NAP25BL0008",
      source: "sems_export",
      provenance: "observed",
      identityConfidence: "assigned",
      status: "ready",
      unitId: UNIT_A_ID,
      unitCode: "A-101",
      unitName: "Unidade A-101",
      residentName: "Ana Oliveira",
    };

    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items:
          period === "2026-08" && !filtered ? [assignedSession] : [],
      }),
    });
  });
  await page.route("**/api/v1/assignment-units", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(assignmentUnits),
    });
  });

  await page.goto("/sessions?status=pending_review&period=2026-07");
  await expect(
    page.getByRole("heading", { name: "Nenhuma recarga importada." }),
  ).toBeVisible();

  await page.getByLabel("Filtrar período").fill("2026-08");
  await expect(page).toHaveURL(/period=2026-08/);
  await expect(
    page.getByRole("heading", {
      name: "Todas as recargas do período foram atribuídas.",
    }),
  ).toBeVisible();
  await expect(page.getByText("0 pendências no período")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Voltar para visão geral" }).first(),
  ).toBeVisible();
});

test("recovers the queue after a parallel load failure", async ({ page }) => {
  let recover = false;

  await page.route("**/api/v1/sessions**", async (route) => {
    if (!recover) {
      await route.fulfill({ status: 503, body: "temporarily unavailable" });
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(pendingSessions),
    });
  });
  await page.route("**/api/v1/assignment-units", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(assignmentUnits),
    });
  });

  await page.goto("/sessions?status=pending_review&period=2026-08");
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "As recargas e unidades não foram carregadas." }),
  ).toBeVisible();
  recover = true;
  await page.getByRole("button", { name: "Atualizar fila" }).click();

  await expect(page.getByText("2 pendências no período")).toBeVisible();
  await expect(queue(page).getByRole("row", { name: /7,00 kWh/ })).toBeVisible();
});
