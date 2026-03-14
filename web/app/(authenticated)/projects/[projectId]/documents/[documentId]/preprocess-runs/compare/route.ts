import { NextResponse } from "next/server";

import { compareProjectDocumentPreprocessRuns } from "../../../../../../../../lib/documents";

export async function GET(
  request: Request,
  context: { params: Promise<{ projectId: string; documentId: string }> }
) {
  const { projectId, documentId } = await context.params;
  const requestUrl = new URL(request.url);
  const baseRunId = requestUrl.searchParams.get("baseRunId") ?? "";
  const candidateRunId = requestUrl.searchParams.get("candidateRunId") ?? "";
  if (!baseRunId || !candidateRunId) {
    return NextResponse.json(
      { detail: "baseRunId and candidateRunId are required." },
      { status: 422 }
    );
  }
  const result = await compareProjectDocumentPreprocessRuns(
    projectId,
    documentId,
    baseRunId,
    candidateRunId
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Preprocess compare unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
