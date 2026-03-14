import { NextResponse } from "next/server";
import type { UpdateDocumentTranscriptionTriageAssignmentRequest } from "@ukde/contracts";

import { updateProjectDocumentTranscriptionTriageAssignment } from "../../../../../../../../../../../lib/documents";

export async function PATCH(
  request: Request,
  context: {
    params: Promise<{ projectId: string; documentId: string; pageId: string }>;
  }
) {
  let payload: UpdateDocumentTranscriptionTriageAssignmentRequest = {};
  try {
    payload = (await request.json()) as UpdateDocumentTranscriptionTriageAssignmentRequest;
  } catch {}

  const { projectId, documentId, pageId } = await context.params;
  const result = await updateProjectDocumentTranscriptionTriageAssignment(
    projectId,
    documentId,
    pageId,
    payload
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcription triage assignment update failed." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
