import { NextResponse } from "next/server";

import { getProjectDocumentImportStatus } from "../../../../../../lib/documents";

export async function GET(
  _request: Request,
  context: { params: Promise<{ projectId: string; importId: string }> }
) {
  const { projectId, importId } = await context.params;
  const result = await getProjectDocumentImportStatus(projectId, importId);
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Import status request failed." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
