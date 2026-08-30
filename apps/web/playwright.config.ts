import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://127.0.0.1:3102" },
  webServer: [
    {
      command:
        "uv run --project ../api uvicorn app.main:app --app-dir ../api --port 8000",
      url: "http://127.0.0.1:8000/health",
      env: {
        APP_ENV: "test",
        AUTH_MODE: "fixture",
        FIXTURE_AUTH_TOKEN: "fixture-manager-token",
      },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "pnpm dev --hostname 127.0.0.1 --port 3102",
      url: "http://127.0.0.1:3102",
      env: {
        AUTH_MODE: "fixture",
        NEXT_PUBLIC_API_URL: "/api",
        NEXT_PUBLIC_SUPABASE_URL: "https://fixture.supabase.co",
        NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "fixture-publishable-key",
      },
      reuseExistingServer: !process.env.CI,
    },
  ],
});
