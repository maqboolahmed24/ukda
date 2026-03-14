import { NextRequest, NextResponse } from "next/server";

import { createProjectDocumentUploadSession } from "../../../../../../../lib/documents";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  const payload = await request.json().catch(() => null);
  const originalFilename =
    payload && typeof payload.originalFilename === "string"
      ? payload.originalFilename
      : null;
  if (!originalFilename) {
    return NextResponse.json(
      { detail: "originalFilename is required." },
      { status: 422 }
    );
  }

  const result = await createProjectDocumentUploadSession(projectId, {
    originalFilename,
    expectedSha256:
      payload && typeof payload.expectedSha256 === "string"
        ? payload.expectedSha256
        : undefined,
    expectedTotalBytes:
      payload && typeof payload.expectedTotalBytes === "number"
        ? payload.expectedTotalBytes
        : undefined
  });
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Upload session could not be created." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
