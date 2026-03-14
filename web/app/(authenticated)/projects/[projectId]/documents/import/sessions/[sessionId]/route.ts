import { NextResponse } from "next/server";

import { getProjectDocumentUploadSession } from "../../../../../../../../lib/documents";

export async function GET(
  _request: Request,
  context: { params: Promise<{ projectId: string; sessionId: string }> }
) {
  const { projectId, sessionId } = await context.params;
  const result = await getProjectDocumentUploadSession(projectId, sessionId);
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Upload session status unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
