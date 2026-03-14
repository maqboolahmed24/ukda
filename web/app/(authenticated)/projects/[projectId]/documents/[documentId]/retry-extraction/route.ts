import { NextResponse } from "next/server";

import { revalidateAfterMutation } from "../../../../../../../lib/data/invalidation";
import { retryProjectDocumentExtraction } from "../../../../../../../lib/documents";

export async function POST(
  _request: Request,
  context: { params: Promise<{ projectId: string; documentId: string }> }
) {
  const { projectId, documentId } = await context.params;
  const result = await retryProjectDocumentExtraction(projectId, documentId);
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Extraction retry failed." },
      { status: result.status }
    );
  }

  revalidateAfterMutation("documents.retry-extraction", {
    projectId,
    documentId
  });
  return NextResponse.json(result.data, { status: result.status });
}
