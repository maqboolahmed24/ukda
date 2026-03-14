import { NextResponse } from "next/server";
import type { CorrectDocumentTranscriptionLineRequest } from "@ukde/contracts";

import { correctProjectDocumentTranscriptionLine } from "../../../../../../../../../../../../lib/documents";

export async function PATCH(
  request: Request,
  context: {
    params: Promise<{
      projectId: string;
      documentId: string;
      runId: string;
      pageId: string;
      lineId: string;
    }>;
  }
) {
  let payload: CorrectDocumentTranscriptionLineRequest | null = null;
  try {
    payload = (await request.json()) as CorrectDocumentTranscriptionLineRequest;
  } catch {}

  if (!payload) {
    return NextResponse.json(
      { detail: "Correction payload is required." },
      { status: 400 }
    );
  }

  const { projectId, documentId, runId, pageId, lineId } = await context.params;
  const result = await correctProjectDocumentTranscriptionLine(
    projectId,
    documentId,
    runId,
    pageId,
    lineId,
    payload
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcription line correction failed." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
