import { NextResponse } from "next/server";

import { getProjectDocumentLayoutRunStatus } from "../../../../../../../../../lib/documents";

export async function GET(
  _request: Request,
  context: {
    params: Promise<{ projectId: string; documentId: string; runId: string }>;
  }
) {
  const { projectId, documentId, runId } = await context.params;
  const result = await getProjectDocumentLayoutRunStatus(
    projectId,
    documentId,
    runId
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Layout run status unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
