import { NextResponse } from "next/server";

import { getProjectDocumentPreprocessRunStatus } from "../../../../../../../../../lib/documents";

export async function GET(
  _request: Request,
  context: {
    params: Promise<{ projectId: string; documentId: string; runId: string }>;
  }
) {
  const { projectId, documentId, runId } = await context.params;
  const result = await getProjectDocumentPreprocessRunStatus(
    projectId,
    documentId,
    runId
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Preprocess run status unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
