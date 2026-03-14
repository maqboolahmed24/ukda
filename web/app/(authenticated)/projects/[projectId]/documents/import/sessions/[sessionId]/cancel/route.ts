import { NextResponse } from "next/server";

import { cancelProjectDocumentUploadSession } from "../../../../../../../../../lib/documents";

export async function POST(
  _request: Request,
  context: { params: Promise<{ projectId: string; sessionId: string }> }
) {
  const { projectId, sessionId } = await context.params;
  const result = await cancelProjectDocumentUploadSession(projectId, sessionId);
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Upload session cancel failed." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
