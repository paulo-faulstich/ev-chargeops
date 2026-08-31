import { redirect } from "next/navigation";

import { InvoiceView } from "@/components/billing/invoice-view";
import { getAccessToken } from "@/lib/auth/access-token";

/** One invoice, one route.
 *
 * The manager arrives from the closing list; the resident context reaches this
 * same page scoped to its unit. There is no second layout.
 */
export default async function InvoicePage({
  params,
}: {
  params: Promise<{ invoiceId: string }>;
}) {
  const accessToken = await getAccessToken();
  if (!accessToken) redirect("/login");

  const { invoiceId } = await params;
  return <InvoiceView invoiceId={invoiceId} accessToken={accessToken} />;
}
