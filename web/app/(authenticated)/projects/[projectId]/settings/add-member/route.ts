import { NextRequest, NextResponse } from "next/server";

import { revalidateAfterMutation } from "../../../../../../lib/data/invalidation";
import { addProjectMember } from "../../../../../../lib/projects";

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
  const memberEmail = formData.get("member_email");
  const role = formData.get("role");

  if (
    typeof memberEmail !== "string" ||
    typeof role !== "string" ||
    (role !== "PROJECT_LEAD" && role !== "RESEARCHER" && role !== "REVIEWER")
  ) {
    return redirectTo(`/projects/${projectId}/settings?status=action-failed`);
  }

  const result = await addProjectMember(projectId, {
    memberEmail,
    role
  });
  if (!result.ok) {
    return redirectTo(`/projects/${projectId}/settings?status=action-failed`);
  }

  revalidateAfterMutation("projects.members.add", { projectId });
  return redirectTo(`/projects/${projectId}/settings?status=member-added`);
}
