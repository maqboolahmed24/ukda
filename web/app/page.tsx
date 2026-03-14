import { redirect } from "next/navigation";

import { resolveCurrentSession } from "../lib/auth/session";
import { loginPath, projectsPath } from "../lib/routes";

export const dynamic = "force-dynamic";

export default async function EntryResolverPage() {
  const session = await resolveCurrentSession();
  redirect(session ? projectsPath : loginPath);
}
