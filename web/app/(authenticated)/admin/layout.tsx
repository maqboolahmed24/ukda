import { AdminConsoleShell } from "../../../components/admin-console-shell";
import { requirePlatformRole } from "../../../lib/auth/session";

export default async function AdminLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  return <AdminConsoleShell session={session}>{children}</AdminConsoleShell>;
}
