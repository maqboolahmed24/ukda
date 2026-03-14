import { NextRequest, NextResponse } from "next/server";

import { uploadProjectDocumentChunk } from "../../../../../../../../../lib/documents";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId: string; sessionId: string }> }
) {
  const { projectId, sessionId } = await context.params;
  const chunkIndexRaw = request.nextUrl.searchParams.get("chunkIndex");
  const chunkIndex = Number(chunkIndexRaw);
  if (!Number.isInteger(chunkIndex) || chunkIndex < 0) {
    return NextResponse.json(
      { detail: "chunkIndex must be a non-negative integer." },
      { status: 422 }
    );
  }

  const formData = await request.formData();
  const file = formData.get("file");
  if (!(file instanceof Blob)) {
    return NextResponse.json(
      { detail: "Chunk upload requires a file payload." },
      { status: 422 }
    );
  }

  const payload = new FormData();
  const filename =
    "name" in file &&
    typeof file.name === "string" &&
    file.name.trim().length > 0
      ? file.name
      : `chunk-${chunkIndex}.bin`;
  payload.set("file", file, filename);
  const result = await uploadProjectDocumentChunk(
    projectId,
    sessionId,
    chunkIndex,
    payload
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Chunk upload failed." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
