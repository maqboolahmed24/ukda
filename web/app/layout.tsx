import type { Metadata } from "next";

import "@ukde/ui/styles.css";
import "./globals.css";
import { ThemeRuntimeSync } from "../components/theme-runtime-sync";

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
      <body>
        <ThemeRuntimeSync />
        {children}
      </body>
    </html>
  );
}
