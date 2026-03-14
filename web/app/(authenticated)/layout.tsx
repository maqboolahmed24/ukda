import { AuthenticatedShell } from "../../components/authenticated-shell";
import { readCsrfToken, requireCurrentSession } from "../../lib/auth/session";
import { listMyProjects } from "../../lib/projects";

export default async function AuthenticatedLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [session, csrfToken, projects] = await Promise.all([
    requireCurrentSession(),
    readCsrfToken(),
    listMyProjects()
  ]);

  return (
    <AuthenticatedShell
      csrfToken={csrfToken}
      projects={projects}
      session={session}
    >
      {children}
    </AuthenticatedShell>
  );
}
