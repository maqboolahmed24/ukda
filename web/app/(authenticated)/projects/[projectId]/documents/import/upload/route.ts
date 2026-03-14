import { NextRequest, NextResponse } from "next/server";

import { revalidateAfterMutation } from "../../../../../../../lib/data/invalidation";
import { uploadProjectDocument } from "../../../../../../../lib/documents";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  const formData = await request.formData();
  const file = formData.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json(
      { detail: "Upload requires a file payload." },
      { status: 422 }
    );
  }

  const payload = new FormData();
  payload.set("file", file, file.name);
  const result = await uploadProjectDocument(projectId, payload);
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Upload request failed." },
      { status: result.status }
    );
  }

  revalidateAfterMutation("documents.import", {
    projectId,
    documentId: result.data.documentId
  });
  return NextResponse.json(result.data, { status: result.status });
}
