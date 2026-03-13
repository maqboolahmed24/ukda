import { requirePlatformRole } from "../../../lib/auth/session";

export default async function AdminLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  await requirePlatformRole(["ADMIN", "AUDITOR"]);
  return children;
}
