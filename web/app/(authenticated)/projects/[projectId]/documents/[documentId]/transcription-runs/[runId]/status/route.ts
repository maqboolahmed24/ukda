import { NextResponse } from "next/server";

import { getProjectDocumentTranscriptionRunStatus } from "../../../../../../../../../lib/documents";

export async function GET(
  _request: Request,
  context: {
    params: Promise<{ projectId: string; documentId: string; runId: string }>;
  }
) {
  const { projectId, documentId, runId } = await context.params;
  const result = await getProjectDocumentTranscriptionRunStatus(
    projectId,
    documentId,
    runId
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcription run status unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
