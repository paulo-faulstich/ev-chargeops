import path from "node:path";

import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
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
