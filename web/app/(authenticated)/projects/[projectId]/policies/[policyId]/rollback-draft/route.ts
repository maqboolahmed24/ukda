import { NextRequest, NextResponse } from "next/server";

import { createProjectPolicyRollbackDraft } from "../../../../../../../lib/policies";

function redirectTo(path: string, status = 303): NextResponse {
  return new NextResponse(null, {
    status,
    headers: { Location: path }
  });
}

function resolveRedirectPath(
  projectId: string,
  policyId: string,
  returnTo: string | null
): string {
  if (returnTo === "list") {
    return `/projects/${projectId}/policies`;
  }
  return `/projects/${projectId}/policies/${policyId}`;
}

function readRequiredText(formData: FormData, key: string): string | null {
  const raw = formData.get(key);
  if (typeof raw !== "string") {
    return null;
  }
  const normalized = raw.trim();
  return normalized.length > 0 ? normalized : null;
}

function resolveFailureStatus(status: number): string {
  if (status === 403) {
    return "forbidden";
  }
  if (status === 409) {
    return "conflict";
  }
  return "action-failed";
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId: string; policyId: string }> }
) {
  const { projectId, policyId } = await context.params;
  const returnTo = new URL(request.url).searchParams.get("returnTo");
  const basePath = resolveRedirectPath(projectId, policyId, returnTo);
  const formData = await request.formData();
  const fromPolicyId = readRequiredText(formData, "from_policy_id");
  if (!fromPolicyId) {
    return redirectTo(`${basePath}?status=action-failed`);
  }
  const result = await createProjectPolicyRollbackDraft(projectId, policyId, {
    fromPolicyId
  });
  if (!result.ok) {
    return redirectTo(`${basePath}?status=${resolveFailureStatus(result.status)}`);
  }
  return redirectTo(`/projects/${projectId}/policies?status=rollback-created`);
}
