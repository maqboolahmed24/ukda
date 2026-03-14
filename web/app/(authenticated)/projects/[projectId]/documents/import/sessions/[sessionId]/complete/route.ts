import { NextResponse } from "next/server";

import { revalidateAfterMutation } from "../../../../../../../../../lib/data/invalidation";
import { completeProjectDocumentUploadSession } from "../../../../../../../../../lib/documents";

export async function POST(
  _request: Request,
  context: { params: Promise<{ projectId: string; sessionId: string }> }
) {
  const { projectId, sessionId } = await context.params;
  const result = await completeProjectDocumentUploadSession(
    projectId,
    sessionId
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Upload session completion failed." },
      { status: result.status }
    );
  }

  revalidateAfterMutation("documents.import", {
    projectId,
    documentId: result.data.documentId
  });
  return NextResponse.json(result.data, { status: result.status });
}
