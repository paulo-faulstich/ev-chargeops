import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "EV ChargeOps",
  description: "Operação auditável de recarga compartilhada",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
