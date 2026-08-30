import "server-only";

export const FIXTURE_ACCESS_TOKEN = "fixture-manager-token";

const authMode = process.env.AUTH_MODE ?? "supabase";

if (authMode === "fixture" && process.env.NODE_ENV === "production") {
  throw new Error("Fixture authentication is disabled in production.");
}

export function isFixtureAuth(): boolean {
  return authMode === "fixture";
}
