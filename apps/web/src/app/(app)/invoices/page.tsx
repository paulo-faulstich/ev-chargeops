import { redirect } from "next/navigation";

import { InvoiceList } from "@/components/billing/invoice-list";
import { getAccessToken } from "@/lib/auth/access-token";

export default async function InvoicesPage() {
  const accessToken = await getAccessToken();
  if (!accessToken) redirect("/login");

  return <InvoiceList accessToken={accessToken} />;
}
