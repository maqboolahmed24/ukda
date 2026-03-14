import { NextResponse } from "next/server";

import { activateProjectModelAssignment } from "../../../../../../../lib/model-assignments";

function redirectTo(path: string, status = 303): NextResponse {
  return new NextResponse(null, {
    status,
    headers: { Location: path }
  });
}

export async function POST(
  _request: Request,
  context: { params: Promise<{ projectId: string; assignmentId: string }> }
) {
  const { projectId, assignmentId } = await context.params;
  const result = await activateProjectModelAssignment(projectId, assignmentId);
  if (!result.ok) {
    return redirectTo(`/projects/${projectId}/model-assignments?status=action-failed`);
  }
  return redirectTo(`/projects/${projectId}/model-assignments?status=activated`);
}
