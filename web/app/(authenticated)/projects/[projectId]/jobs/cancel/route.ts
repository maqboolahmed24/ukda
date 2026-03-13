import { NextRequest, NextResponse } from "next/server";

import { cancelProjectJob } from "../../../../../../lib/jobs";

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
  const jobId = formData.get("job_id");
  if (typeof jobId !== "string") {
    return redirectTo(`/projects/${projectId}/jobs?status=cancel-invalid`);
  }

  const result = await cancelProjectJob(projectId, jobId);
  if (!result.ok || !result.data) {
    return redirectTo(
      `/projects/${projectId}/jobs/${jobId}?status=cancel-failed`
    );
  }
  return redirectTo(
    `/projects/${projectId}/jobs/${result.data.job.id}?status=${
      result.data.terminal ? "canceled" : "cancel-requested"
    }`
  );
}
