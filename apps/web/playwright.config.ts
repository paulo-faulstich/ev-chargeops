import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://127.0.0.1:3102" },
  webServer: [
    {
      command:
        "uv run --project ../api uvicorn app.main:app --app-dir ../api --port 8000",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "pnpm dev --hostname 127.0.0.1 --port 3102",
      url: "http://127.0.0.1:3102",
      env: { NEXT_PUBLIC_API_URL: "/api" },
      reuseExistingServer: !process.env.CI,
    },
  ],
});
