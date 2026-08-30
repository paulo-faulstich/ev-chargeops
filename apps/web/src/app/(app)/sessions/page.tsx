import { redirect } from "next/navigation";

import { SessionReview } from "@/components/sessions/session-review";
import { getAccessToken } from "@/lib/auth/access-token";

export default async function SessionsPage() {
  const accessToken = await getAccessToken();
  if (!accessToken) redirect("/login");

  return <SessionReview accessToken={accessToken} />;
}
