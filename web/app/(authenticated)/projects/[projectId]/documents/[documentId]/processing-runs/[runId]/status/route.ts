import { NextResponse } from "next/server";

import { getProjectDocumentProcessingRunStatus } from "../../../../../../../../../lib/documents";

export async function GET(
  _request: Request,
  context: {
    params: Promise<{ projectId: string; documentId: string; runId: string }>;
  }
) {
  const { projectId, documentId, runId } = await context.params;
  const result = await getProjectDocumentProcessingRunStatus(
    projectId,
    documentId,
    runId
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Processing run status unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
