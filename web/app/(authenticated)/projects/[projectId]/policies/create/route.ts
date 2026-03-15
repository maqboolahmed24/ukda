import { NextRequest, NextResponse } from "next/server";

import { createProjectPolicy } from "../../../../../../lib/policies";

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

function readOptionalText(formData: FormData, key: string): string | null {
  const raw = formData.get(key);
  if (typeof raw !== "string") {
    return null;
  }
  const normalized = raw.trim();
  return normalized.length > 0 ? normalized : null;
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  const formData = await request.formData();
  const name = readRequiredText(formData, "name");
  const rulesJsonRaw = readRequiredText(formData, "rules_json");
  if (!name || !rulesJsonRaw) {
    return redirectTo(`/projects/${projectId}/policies?status=action-failed`);
  }

  let rulesJson: Record<string, unknown>;
  try {
    const parsed = JSON.parse(rulesJsonRaw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return redirectTo(`/projects/${projectId}/policies?status=malformed-rules`);
    }
    rulesJson = parsed as Record<string, unknown>;
  } catch {
    return redirectTo(`/projects/${projectId}/policies?status=malformed-rules`);
  }

  const result = await createProjectPolicy(projectId, {
    name,
    rulesJson,
    supersedesPolicyId: readOptionalText(formData, "supersedes_policy_id"),
    seededFromBaselineSnapshotId: readOptionalText(
      formData,
      "seeded_from_baseline_snapshot_id"
    )
  });
  if (!result.ok) {
    return redirectTo(`/projects/${projectId}/policies?status=action-failed`);
  }
  return redirectTo(`/projects/${projectId}/policies?status=created`);
}
