import type { Metadata } from "next";
import { Manrope } from "next/font/google";

import "@ukde/ui/styles.css";
import "./globals.css";
import { ThemeRuntimeSync } from "../components/theme-runtime-sync";

const appSansFont = Manrope({
  subsets: ["latin"],
  display: "swap",
  variable: "--ukde-font-sans",
  weight: ["400", "500", "600", "700", "800"]
});

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
      <body className={appSansFont.variable}>
        <ThemeRuntimeSync />
        {children}
      </body>
    </html>
  );
}
