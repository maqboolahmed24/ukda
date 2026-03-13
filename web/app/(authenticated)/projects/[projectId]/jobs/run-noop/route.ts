import { NextRequest, NextResponse } from "next/server";

import { enqueueNoopProjectJob } from "../../../../../../lib/jobs";

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
  const logicalKey = formData.get("logical_key");
  const mode = formData.get("mode");
  const maxAttemptsRaw = formData.get("max_attempts");

  if (
    typeof logicalKey !== "string" ||
    typeof mode !== "string" ||
    (mode !== "SUCCESS" && mode !== "FAIL_ONCE" && mode !== "FAIL_ALWAYS")
  ) {
    return redirectTo(`/projects/${projectId}/jobs?status=run-invalid`);
  }

  const parsedAttempts =
    typeof maxAttemptsRaw === "string" ? Number(maxAttemptsRaw) : 1;
  const maxAttempts = Number.isFinite(parsedAttempts)
    ? Math.max(1, Math.min(10, Math.trunc(parsedAttempts)))
    : 1;

  const result = await enqueueNoopProjectJob(projectId, {
    logicalKey,
    mode,
    maxAttempts
  });
  if (!result.ok) {
    return redirectTo(`/projects/${projectId}/jobs?status=run-failed`);
  }
  return redirectTo(
    `/projects/${projectId}/jobs/${result.data?.job.id ?? ""}?status=run-queued`
  );
}
