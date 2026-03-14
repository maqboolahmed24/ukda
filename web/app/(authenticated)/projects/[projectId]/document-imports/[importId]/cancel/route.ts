import { NextResponse } from "next/server";

import { revalidateAfterMutation } from "../../../../../../../lib/data/invalidation";
import { cancelProjectDocumentImport } from "../../../../../../../lib/documents";

export async function POST(
  _request: Request,
  context: { params: Promise<{ projectId: string; importId: string }> }
) {
  const { projectId, importId } = await context.params;
  const result = await cancelProjectDocumentImport(projectId, importId);
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Import cancel request failed." },
      { status: result.status }
    );
  }

  revalidateAfterMutation("documents.import.cancel", {
    projectId,
    documentId: result.data.documentId
  });
  return NextResponse.json(result.data, { status: result.status });
}
