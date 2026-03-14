import { NextResponse } from "next/server";
import type { CreateDocumentTranscriptionFallbackRunRequest } from "@ukde/contracts";

import { createProjectDocumentFallbackTranscriptionRun } from "../../../../../../../../lib/documents";

export async function POST(
  request: Request,
  context: { params: Promise<{ projectId: string; documentId: string }> }
) {
  let payload: CreateDocumentTranscriptionFallbackRunRequest = {};
  try {
    payload = (await request.json()) as CreateDocumentTranscriptionFallbackRunRequest;
  } catch {}
  const { projectId, documentId } = await context.params;
  const result = await createProjectDocumentFallbackTranscriptionRun(
    projectId,
    documentId,
    payload
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Fallback transcription run create failed." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
