"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import {
  FIXTURE_SIGNED_OUT_COOKIE,
  isFixtureAuth,
} from "@/lib/auth/mode";
import { createClient } from "@/lib/supabase/server";

export async function logout() {
  if (isFixtureAuth()) {
    const cookieStore = await cookies();
    cookieStore.set(FIXTURE_SIGNED_OUT_COOKIE, "1", {
      httpOnly: true,
      path: "/",
      sameSite: "lax",
    });
  } else {
    const supabase = await createClient();
    await supabase.auth.signOut();
  }

  redirect("/login");
}
