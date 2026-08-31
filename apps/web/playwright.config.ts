import path from "node:path";

import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // One API process and one SQLite file serve the whole run, so parallel
  // workers read each other's writes: an import in one file adds history rows
  // another file then counts, and the dashboard shows sessions no single test
  // created. Serial execution is what makes a failure mean something.
  workers: 1,
  use: { baseURL: "http://127.0.0.1:3102" },
  webServer: [
    {
      command: "uv run --project ../api python ../api/scripts/start_e2e.py",
      url: "http://127.0.0.1:8001/health",
      env: {
        E2E_DATABASE_PATH: path.resolve(
          process.cwd(),
          "test-results/ev-chargeops-e2e.sqlite3",
        ),
      },
      reuseExistingServer: false,
    },
    {
      command: "pnpm dev --hostname 127.0.0.1 --port 3102",
      url: "http://127.0.0.1:3102",
      env: {
        // The repository lives inside a synced folder, where the default
        // watcher opens far more file handles than the OS allows and takes the
        // dev server down mid-run. Polling is the difference between the suite
        // running and failing before the first assertion.
        WATCHPACK_POLLING: "true",
        AUTH_MODE: "fixture",
        API_PROXY_TARGET: "http://127.0.0.1:8001",
        NEXT_PUBLIC_API_URL: "/api",
        NEXT_PUBLIC_SUPABASE_URL: "https://fixture.supabase.co",
        NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "fixture-publishable-key",
      },
      reuseExistingServer: false,
    },
  ],
});
