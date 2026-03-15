import { NextResponse } from "next/server";

import { validateProjectPolicy } from "../../../../../../../lib/policies";

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
  request: Request,
  context: { params: Promise<{ projectId: string; policyId: string }> }
) {
  const { projectId, policyId } = await context.params;
  const returnTo = new URL(request.url).searchParams.get("returnTo");
  const basePath = resolveRedirectPath(projectId, policyId, returnTo);
  const result = await validateProjectPolicy(projectId, policyId);
  if (!result.ok || !result.data) {
    return redirectTo(
      `${basePath}?status=${resolveFailureStatus(result.status)}`
    );
  }

  const nextStatus =
    result.data.policy.validationStatus === "VALID" ? "validated" : "invalid";
  return redirectTo(`${basePath}?status=${nextStatus}`);
}
