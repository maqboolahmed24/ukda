import { NextRequest, NextResponse } from "next/server";

import { revalidateAfterMutation } from "../../../../lib/data/invalidation";
import { createProject } from "../../../../lib/projects";

function redirectTo(path: string, status = 303): NextResponse {
  return new NextResponse(null, {
    status,
    headers: {
      Location: path
    }
  });
}

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const name = formData.get("name");
  const purpose = formData.get("purpose");
  const intendedAccessTier = formData.get("intended_access_tier");

  if (
    typeof name !== "string" ||
    typeof purpose !== "string" ||
    typeof intendedAccessTier !== "string"
  ) {
    return redirectTo("/projects?error=create-invalid");
  }

  const result = await createProject({
    name,
    purpose,
    intendedAccessTier:
      intendedAccessTier === "OPEN" ||
      intendedAccessTier === "SAFEGUARDED" ||
      intendedAccessTier === "CONTROLLED"
        ? intendedAccessTier
        : "CONTROLLED"
  });

  if (!result.ok || !result.data) {
    return redirectTo("/projects?error=create-failed");
  }

  revalidateAfterMutation("projects.create", {
    createdProjectId: result.data.id
  });

  return redirectTo(`/projects/${result.data.id}/overview?created=1`);
}
