import { NextResponse } from "next/server";

import { getProjectDocumentTranscriptionMetrics } from "../../../../../../../../lib/documents";

function parseNumeric(value: string | null): number | undefined {
  if (!value || value.trim().length === 0) {
    return undefined;
  }
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export async function GET(
  request: Request,
  context: { params: Promise<{ projectId: string; documentId: string }> }
) {
  const { projectId, documentId } = await context.params;
  const requestUrl = new URL(request.url);
  const runId = requestUrl.searchParams.get("runId") ?? undefined;
  const confidenceBelow = parseNumeric(requestUrl.searchParams.get("confidenceBelow"));

  const result = await getProjectDocumentTranscriptionMetrics(projectId, documentId, {
    runId,
    confidenceBelow
  });
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcription metrics unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
