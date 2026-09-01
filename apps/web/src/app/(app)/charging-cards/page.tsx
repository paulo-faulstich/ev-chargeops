import { redirect } from "next/navigation";

import { ChargingCards } from "@/components/cards/charging-cards";
import { getAccessToken } from "@/lib/auth/access-token";

export default async function ChargingCardsPage() {
  const accessToken = await getAccessToken();
  if (!accessToken) redirect("/login");

  return <ChargingCards accessToken={accessToken} />;
}
