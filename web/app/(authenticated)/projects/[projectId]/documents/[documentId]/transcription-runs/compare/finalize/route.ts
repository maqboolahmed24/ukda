import { NextResponse } from "next/server";
import type { FinalizeDocumentTranscriptionCompareRequest } from "@ukde/contracts";

import { finalizeProjectDocumentTranscriptionCompare } from "../../../../../../../../../lib/documents";

export async function POST(
  request: Request,
  context: { params: Promise<{ projectId: string; documentId: string }> }
) {
  let payload: FinalizeDocumentTranscriptionCompareRequest | null = null;
  try {
    payload = (await request.json()) as FinalizeDocumentTranscriptionCompareRequest;
  } catch {}
  if (!payload) {
    return NextResponse.json(
      { detail: "Compare finalize payload is required." },
      { status: 422 }
    );
  }
  const { projectId, documentId } = await context.params;
  const result = await finalizeProjectDocumentTranscriptionCompare(
    projectId,
    documentId,
    payload
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcription compare finalize request failed." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
