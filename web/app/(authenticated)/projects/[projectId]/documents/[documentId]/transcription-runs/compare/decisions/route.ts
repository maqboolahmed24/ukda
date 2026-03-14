import { NextResponse } from "next/server";
import type { RecordDocumentTranscriptionCompareDecisionsRequest } from "@ukde/contracts";

import { recordProjectDocumentTranscriptionCompareDecisions } from "../../../../../../../../../lib/documents";

export async function POST(
  request: Request,
  context: { params: Promise<{ projectId: string; documentId: string }> }
) {
  let payload: RecordDocumentTranscriptionCompareDecisionsRequest | null = null;
  try {
    payload = (await request.json()) as RecordDocumentTranscriptionCompareDecisionsRequest;
  } catch {}
  if (!payload) {
    return NextResponse.json(
      { detail: "Compare decision payload is required." },
      { status: 422 }
    );
  }
  const { projectId, documentId } = await context.params;
  const result = await recordProjectDocumentTranscriptionCompareDecisions(
    projectId,
    documentId,
    payload
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcription compare decision request failed." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
