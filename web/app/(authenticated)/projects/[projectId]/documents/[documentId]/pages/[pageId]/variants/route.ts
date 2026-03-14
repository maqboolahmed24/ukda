import { NextResponse } from "next/server";

import { getProjectDocumentPageVariants } from "../../../../../../../../../lib/documents";

export async function GET(
  request: Request,
  context: {
    params: Promise<{
      projectId: string;
      documentId: string;
      pageId: string;
    }>;
  }
) {
  const { projectId, documentId, pageId } = await context.params;
  const requestUrl = new URL(request.url);
  const runId = requestUrl.searchParams.get("runId")?.trim() || undefined;

  const result = await getProjectDocumentPageVariants(
    projectId,
    documentId,
    pageId,
    { runId }
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Page variants request failed." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
