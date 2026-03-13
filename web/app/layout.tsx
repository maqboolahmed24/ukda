import type { Metadata } from "next";

import "@ukde/ui/styles.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "UKDE",
  description: "Secure, audit-first browser foundation for UKDataExtraction."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
