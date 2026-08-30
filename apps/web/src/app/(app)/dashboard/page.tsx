import { redirect } from "next/navigation";

import { DashboardOverview } from "@/components/dashboard/dashboard-overview";
import { getAccessToken } from "@/lib/auth/access-token";

export default async function DashboardPage() {
  const accessToken = await getAccessToken();
  if (!accessToken) redirect("/login");

  return <DashboardOverview accessToken={accessToken} />;
}
