import { NextRequest, NextResponse } from "next/server";

import { projectSearchPath } from "../../../../../../lib/routes";
import { openProjectSearchResult } from "../../../../../../lib/search";

function redirectTo(path: string, status = 303): NextResponse {
  return new NextResponse(null, {
    status,
    headers: { Location: path }
  });
}

function sanitizeReturnQuery(raw: string): string {
  const normalized = raw.startsWith("?") ? raw.slice(1) : raw;
  if (!normalized) {
    return "";
  }
  const params = new URLSearchParams(normalized);
  return params.toString();
}

async function resolveSearchOpenRedirect(options: {
  projectId: string;
  returnQueryRaw: string;
  searchDocumentIdRaw: string;
}): Promise<NextResponse> {
  const searchDocumentId = options.searchDocumentIdRaw.trim();
  const returnQuery = sanitizeReturnQuery(options.returnQueryRaw.trim());
  const fallbackBase = projectSearchPath(options.projectId);
  const fallbackPath = returnQuery ? `${fallbackBase}?${returnQuery}` : fallbackBase;

  if (!searchDocumentId) {
    return redirectTo(`${fallbackPath}${returnQuery ? "&" : "?"}status=open-failed`);
  }

  const result = await openProjectSearchResult(options.projectId, searchDocumentId);
  if (!result.ok || !result.data) {
    return redirectTo(`${fallbackPath}${returnQuery ? "&" : "?"}status=open-failed`);
  }
  return redirectTo(result.data.workspacePath);
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  return resolveSearchOpenRedirect({
    projectId,
    searchDocumentIdRaw: request.nextUrl.searchParams.get("search_document_id") ?? "",
    returnQueryRaw: request.nextUrl.searchParams.get("return_query") ?? ""
  });
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  const formData = await request.formData();
  return resolveSearchOpenRedirect({
    projectId,
    searchDocumentIdRaw: String(formData.get("search_document_id") ?? ""),
    returnQueryRaw: String(formData.get("return_query") ?? "")
  });
}
