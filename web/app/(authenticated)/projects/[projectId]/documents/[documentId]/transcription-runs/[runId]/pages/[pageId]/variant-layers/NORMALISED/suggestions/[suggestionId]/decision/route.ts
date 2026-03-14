import { NextResponse } from "next/server";
import type { RecordTranscriptVariantSuggestionDecisionRequest } from "@ukde/contracts";

import { recordProjectDocumentTranscriptionVariantSuggestionDecision } from "../../../../../../../../../../../../../../../lib/documents";

export async function POST(
  request: Request,
  context: {
    params: Promise<{
      projectId: string;
      documentId: string;
      runId: string;
      pageId: string;
      suggestionId: string;
    }>;
  }
) {
  let payload: RecordTranscriptVariantSuggestionDecisionRequest | null = null;
  try {
    payload =
      (await request.json()) as RecordTranscriptVariantSuggestionDecisionRequest;
  } catch {}

  if (!payload) {
    return NextResponse.json(
      { detail: "Suggestion-decision payload is required." },
      { status: 400 }
    );
  }

  const { projectId, documentId, runId, pageId, suggestionId } =
    await context.params;
  const result = await recordProjectDocumentTranscriptionVariantSuggestionDecision(
    projectId,
    documentId,
    runId,
    pageId,
    suggestionId,
    payload
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Assist decision could not be recorded." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
