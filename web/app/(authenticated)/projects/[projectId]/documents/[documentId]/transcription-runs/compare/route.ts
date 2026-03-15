import { NextResponse } from "next/server";

import { compareProjectDocumentTranscriptionRuns } from "../../../../../../../../lib/documents";

export async function GET(
  request: Request,
  context: { params: Promise<{ projectId: string; documentId: string }> }
) {
  const { projectId, documentId } = await context.params;
  const requestUrl = new URL(request.url);
  const baseRunId = requestUrl.searchParams.get("baseRunId") ?? "";
  const candidateRunId = requestUrl.searchParams.get("candidateRunId") ?? "";
  const pageParam = requestUrl.searchParams.get("page");
  const lineId = requestUrl.searchParams.get("lineId") ?? undefined;
  const tokenId = requestUrl.searchParams.get("tokenId") ?? undefined;
  if (!baseRunId || !candidateRunId) {
    return NextResponse.json(
      { detail: "baseRunId and candidateRunId are required." },
      { status: 422 }
    );
  }
  const parsedPage =
    typeof pageParam === "string" && pageParam.trim().length > 0
      ? Number.parseInt(pageParam.trim(), 10)
      : Number.NaN;
  const result = await compareProjectDocumentTranscriptionRuns(
    projectId,
    documentId,
    baseRunId,
    candidateRunId,
    {
      page:
        Number.isFinite(parsedPage) && parsedPage > 0
          ? parsedPage
          : undefined,
      lineId:
        typeof lineId === "string" && lineId.trim().length > 0
          ? lineId.trim()
          : undefined,
      tokenId:
        typeof tokenId === "string" && tokenId.trim().length > 0
          ? tokenId.trim()
          : undefined
    }
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcription compare unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
