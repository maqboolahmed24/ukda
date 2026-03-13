import { NextResponse } from "next/server";

import { getProjectJobStatus } from "../../../../../../../lib/jobs";

export async function GET(
  _request: Request,
  context: { params: Promise<{ projectId: string; jobId: string }> }
) {
  const { projectId, jobId } = await context.params;
  const result = await getProjectJobStatus(projectId, jobId);
  if (!result.ok) {
    return NextResponse.json(
      { detail: result.detail ?? "Job status unavailable." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: 200 });
}
