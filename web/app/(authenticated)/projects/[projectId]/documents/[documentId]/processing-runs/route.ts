import { NextResponse } from "next/server";

import { listProjectDocumentProcessingRuns } from "../../../../../../../lib/documents";

export async function GET(
  _request: Request,
  context: { params: Promise<{ projectId: string; documentId: string }> }
) {
  const { projectId, documentId } = await context.params;
  const result = await listProjectDocumentProcessingRuns(projectId, documentId);
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Processing runs unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
