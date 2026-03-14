import { NextRequest, NextResponse } from "next/server";

import { revalidateAfterMutation } from "../../../../../../lib/data/invalidation";
import { removeProjectMember } from "../../../../../../lib/projects";

function redirectTo(path: string, status = 303): NextResponse {
  return new NextResponse(null, {
    status,
    headers: {
      Location: path
    }
  });
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  const formData = await request.formData();
  const memberUserId = formData.get("member_user_id");

  if (typeof memberUserId !== "string") {
    return redirectTo(`/projects/${projectId}/settings?status=action-failed`);
  }

  const result = await removeProjectMember(projectId, memberUserId);
  if (!result.ok) {
    return redirectTo(`/projects/${projectId}/settings?status=action-failed`);
  }

  revalidateAfterMutation("projects.members.remove", { projectId });
  return redirectTo(`/projects/${projectId}/settings?status=member-removed`);
}
