import { NextResponse } from "next/server";

import {
  listProjectDocumentPreprocessRunPages,
  type ProjectDocumentPreprocessRunPagesFilters
} from "../../../../../../../../../lib/documents";

export async function GET(
  request: Request,
  context: {
    params: Promise<{ projectId: string; documentId: string; runId: string }>;
  }
) {
  const { projectId, documentId, runId } = await context.params;
  const requestUrl = new URL(request.url);
  const filters: ProjectDocumentPreprocessRunPagesFilters = {
    warning: requestUrl.searchParams.get("warning") ?? undefined,
    status:
      (requestUrl.searchParams.get("status") as ProjectDocumentPreprocessRunPagesFilters["status"]) ??
      undefined
  };
  const cursorRaw = requestUrl.searchParams.get("cursor");
  const pageSizeRaw = requestUrl.searchParams.get("pageSize");
  if (cursorRaw) {
    const parsed = Number.parseInt(cursorRaw, 10);
    if (Number.isFinite(parsed)) {
      filters.cursor = parsed;
    }
  }
  if (pageSizeRaw) {
    const parsed = Number.parseInt(pageSizeRaw, 10);
    if (Number.isFinite(parsed)) {
      filters.pageSize = parsed;
    }
  }

  const result = await listProjectDocumentPreprocessRunPages(
    projectId,
    documentId,
    runId,
    filters
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Preprocess run pages unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
