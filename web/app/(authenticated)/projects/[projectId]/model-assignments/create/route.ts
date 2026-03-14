import { NextRequest, NextResponse } from "next/server";

import type { ApprovedModelRole } from "@ukde/contracts";

import { createProjectModelAssignment } from "../../../../../../lib/model-assignments";

function redirectTo(path: string, status = 303): NextResponse {
  return new NextResponse(null, {
    status,
    headers: { Location: path }
  });
}

function isModelRole(value: string): value is ApprovedModelRole {
  return (
    value === "TRANSCRIPTION_PRIMARY" ||
    value === "TRANSCRIPTION_FALLBACK" ||
    value === "ASSIST"
  );
}

function readRequiredText(formData: FormData, key: string): string | null {
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

  const modelRole = readRequiredText(formData, "model_role");
  const approvedModelId = readRequiredText(formData, "approved_model_id");
  const assignmentReason = readRequiredText(formData, "assignment_reason");

  if (
    !modelRole ||
    !approvedModelId ||
    !assignmentReason ||
    !isModelRole(modelRole)
  ) {
    return redirectTo(`/projects/${projectId}/model-assignments?status=action-failed`);
  }

  const result = await createProjectModelAssignment(projectId, {
    modelRole,
    approvedModelId,
    assignmentReason
  });
  if (!result.ok) {
    return redirectTo(`/projects/${projectId}/model-assignments?status=action-failed`);
  }
  return redirectTo(`/projects/${projectId}/model-assignments?status=created`);
}
