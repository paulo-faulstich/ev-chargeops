import { redirect } from "next/navigation";

import { InvoiceView } from "@/components/billing/invoice-view";
import { getAccessToken } from "@/lib/auth/access-token";

/** One invoice, one route.
 *
 * The manager arrives from the closing list or from the invoice list; the
 * resident context reaches this same page scoped to its unit. There is no
 * second layout — only the way back changes, so it travels in the query.
 */
export default async function InvoicePage({
  params,
  searchParams,
}: {
  params: Promise<{ invoiceId: string }>;
  searchParams: Promise<{ from?: string }>;
}) {
  const accessToken = await getAccessToken();
  if (!accessToken) redirect("/login");

  const { invoiceId } = await params;
  const { from } = await searchParams;
  return (
    <InvoiceView
      invoiceId={invoiceId}
      accessToken={accessToken}
      origin={from === "closing" ? "closing" : "invoices"}
    />
  );
}
