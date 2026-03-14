import { NextResponse } from "next/server";

import { cancelProjectDocumentLayoutRun } from "../../../../../../../../../lib/documents";

export async function POST(
  _request: Request,
  context: {
    params: Promise<{ projectId: string; documentId: string; runId: string }>;
  }
) {
  const { projectId, documentId, runId } = await context.params;
  const result = await cancelProjectDocumentLayoutRun(projectId, documentId, runId);
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Layout run cancel failed." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
