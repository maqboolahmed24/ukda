import { NextRequest, NextResponse } from "next/server";

import { updateProjectPolicy } from "../../../../../../../lib/policies";

function redirectTo(path: string, status = 303): NextResponse {
  return new NextResponse(null, {
    status,
    headers: { Location: path }
  });
}

function readRequiredText(formData: FormData, key: string): string | null {
  const raw = formData.get(key);
  if (typeof raw !== "string") {
    return null;
  }
  const normalized = raw.trim();
  return normalized.length > 0 ? normalized : null;
}

function resolveFailureStatus(
  detail: string | undefined,
  status: number
): string {
  if (status === 403) {
    return "forbidden";
  }
  if (status === 409) {
    const normalized = detail?.toLowerCase() ?? "";
    if (normalized.includes("etag") || normalized.includes("stale")) {
      return "stale-etag";
    }
    return "conflict";
  }
  return "action-failed";
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId: string; policyId: string }> }
) {
  const { projectId, policyId } = await context.params;
  const formData = await request.formData();

  const name = readRequiredText(formData, "name");
  const rulesJsonRaw = readRequiredText(formData, "rules_json");
  const versionEtag = readRequiredText(formData, "version_etag");
  if (!name || !rulesJsonRaw || !versionEtag) {
    return redirectTo(
      `/projects/${projectId}/policies/${policyId}?status=action-failed`
    );
  }

  let rulesJson: Record<string, unknown>;
  try {
    const parsed = JSON.parse(rulesJsonRaw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return redirectTo(
        `/projects/${projectId}/policies/${policyId}?status=malformed-rules`
      );
    }
    rulesJson = parsed as Record<string, unknown>;
  } catch {
    return redirectTo(
      `/projects/${projectId}/policies/${policyId}?status=malformed-rules`
    );
  }

  const result = await updateProjectPolicy(projectId, policyId, {
    name,
    rulesJson,
    versionEtag
  });
  if (!result.ok) {
    return redirectTo(
      `/projects/${projectId}/policies/${policyId}?status=${resolveFailureStatus(
        result.detail,
        result.status
      )}`
    );
  }

  return redirectTo(
    `/projects/${projectId}/policies/${policyId}?status=updated`
  );
}
