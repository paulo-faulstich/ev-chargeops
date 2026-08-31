import { redirect } from "next/navigation";

import { ClosingWorkspace } from "@/components/billing/closing-workspace";
import { getAccessToken } from "@/lib/auth/access-token";

export default async function ClosingPage() {
  const accessToken = await getAccessToken();
  if (!accessToken) redirect("/login");

  return <ClosingWorkspace accessToken={accessToken} />;
}
