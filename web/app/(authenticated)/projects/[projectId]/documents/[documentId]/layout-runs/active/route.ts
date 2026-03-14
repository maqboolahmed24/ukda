import { NextResponse } from "next/server";

import { getProjectDocumentActiveLayoutRun } from "../../../../../../../../lib/documents";

export async function GET(
  _request: Request,
  context: { params: Promise<{ projectId: string; documentId: string }> }
) {
  const { projectId, documentId } = await context.params;
  const result = await getProjectDocumentActiveLayoutRun(projectId, documentId);
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Active layout run unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
