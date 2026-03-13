import { requireCurrentSession } from "../../lib/auth/session";

export default async function AuthenticatedLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  await requireCurrentSession();
  return children;
}
