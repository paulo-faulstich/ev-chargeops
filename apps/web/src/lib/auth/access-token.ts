import "server-only";

import { createClient } from "@/lib/supabase/server";

import { FIXTURE_ACCESS_TOKEN, isFixtureAuth } from "./mode";

export async function getAccessToken(): Promise<string | null> {
  if (isFixtureAuth()) return FIXTURE_ACCESS_TOKEN;

  const supabase = await createClient();
  const { data, error } = await supabase.auth.getSession();

  if (error) return null;
  return data.session?.access_token ?? null;
}
