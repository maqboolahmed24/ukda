import { NextResponse } from "next/server";

import { activateProjectDocumentPreprocessRun } from "../../../../../../../../../lib/documents";
import { revalidateAfterMutation } from "../../../../../../../../../lib/data/invalidation";

export async function POST(
  _request: Request,
  context: {
    params: Promise<{ projectId: string; documentId: string; runId: string }>;
  }
) {
  const { projectId, documentId, runId } = await context.params;
  const result = await activateProjectDocumentPreprocessRun(
    projectId,
    documentId,
    runId
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Preprocess run activation failed." },
      { status: result.status || 503 }
    );
  }
  revalidateAfterMutation("documents.preprocess.activate", {
    projectId,
    documentId,
    runId
  });
  return NextResponse.json(result.data, { status: result.status });
}
