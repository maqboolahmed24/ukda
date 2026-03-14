import { NextResponse } from "next/server";
import type { TranscriptionTokenSourceKind } from "@ukde/contracts";

import { listProjectDocumentTranscriptionRunPageLines } from "../../../../../../../../../../../lib/documents";

function toSourceKind(value: string | null): TranscriptionTokenSourceKind | undefined {
  if (value === "LINE" || value === "PAGE_WINDOW" || value === "RESCUE_CANDIDATE") {
    return value;
  }
  return undefined;
}

export async function GET(
  request: Request,
  context: {
    params: Promise<{
      projectId: string;
      documentId: string;
      runId: string;
      pageId: string;
    }>;
  }
) {
  const { projectId, documentId, runId, pageId } = await context.params;
  const requestUrl = new URL(request.url);
  const result = await listProjectDocumentTranscriptionRunPageLines(
    projectId,
    documentId,
    runId,
    pageId,
    {
      lineId: requestUrl.searchParams.get("lineId") ?? undefined,
      tokenId: requestUrl.searchParams.get("tokenId") ?? undefined,
      sourceKind: toSourceKind(requestUrl.searchParams.get("sourceKind")),
      sourceRefId: requestUrl.searchParams.get("sourceRefId") ?? undefined,
      workspaceView:
        requestUrl.searchParams.get("workspaceView")?.toLowerCase() === "true"
    }
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcription line results unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
