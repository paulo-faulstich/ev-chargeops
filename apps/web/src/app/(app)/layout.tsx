import type { ReactNode } from "react";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/shell/app-shell";
import { getAccessToken } from "@/lib/auth/access-token";
import { ResidentContextProvider } from "@/lib/billing/resident-context";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api";

export default async function ProductLayout({
  children,
}: {
  children: ReactNode;
}) {
  const accessToken = await getAccessToken();
  if (!accessToken) redirect("/login");

  return (
    <ResidentContextProvider accessToken={accessToken} apiUrl={apiUrl}>
      <AppShell>{children}</AppShell>
    </ResidentContextProvider>
  );
}
