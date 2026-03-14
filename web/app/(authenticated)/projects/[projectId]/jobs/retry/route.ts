import { NextRequest, NextResponse } from "next/server";

import { revalidateAfterMutation } from "../../../../../../lib/data/invalidation";
import { retryProjectJob } from "../../../../../../lib/jobs";

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
    return redirectTo(`/projects/${projectId}/jobs?status=retry-invalid`);
  }

  const result = await retryProjectJob(projectId, jobId);
  if (!result.ok || !result.data) {
    return redirectTo(
      `/projects/${projectId}/jobs/${jobId}?status=retry-failed`
    );
  }
  revalidateAfterMutation("jobs.retry", {
    projectId,
    jobId: result.data.job.id
  });
  return redirectTo(
    `/projects/${projectId}/jobs/${result.data.job.id}?status=retry-${result.data.reason.toLowerCase()}`
  );
}
