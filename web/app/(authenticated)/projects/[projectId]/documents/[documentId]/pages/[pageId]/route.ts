import { NextResponse } from "next/server";

import { updateProjectDocumentPage } from "../../../../../../../../lib/documents";

interface PatchPayload {
  viewerRotation?: unknown;
}

function resolveRotation(payload: PatchPayload): number | null {
  if (typeof payload.viewerRotation !== "number") {
    return null;
  }
  if (!Number.isFinite(payload.viewerRotation)) {
    return null;
  }
  return payload.viewerRotation;
}

export async function PATCH(
  request: Request,
  context: {
    params: Promise<{
      projectId: string;
      documentId: string;
      pageId: string;
    }>;
  }
) {
  let payload: PatchPayload;
  try {
    payload = (await request.json()) as PatchPayload;
  } catch {
    return NextResponse.json(
      { detail: "Patch payload must be valid JSON." },
      { status: 422 }
    );
  }

  const viewerRotation = resolveRotation(payload);
  if (viewerRotation === null) {
    return NextResponse.json(
      { detail: "viewerRotation must be a number." },
      { status: 422 }
    );
  }

  const { projectId, documentId, pageId } = await context.params;
  const result = await updateProjectDocumentPage(
    projectId,
    documentId,
    pageId,
    {
      viewerRotation
    }
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Page update request failed." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
