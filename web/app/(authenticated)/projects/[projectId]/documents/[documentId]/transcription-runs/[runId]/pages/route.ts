import { NextResponse } from "next/server";
import type { TranscriptionRunStatus } from "@ukde/contracts";

import { listProjectDocumentTranscriptionRunPages } from "../../../../../../../../../lib/documents";

const TRANSCRIPTION_RUN_STATUSES: readonly TranscriptionRunStatus[] = [
  "QUEUED",
  "RUNNING",
  "SUCCEEDED",
  "FAILED",
  "CANCELED"
];

function parseTranscriptionRunStatus(value: string | null): TranscriptionRunStatus | undefined {
  if (!value) {
    return undefined;
  }
  const normalized = value.trim().toUpperCase();
  if (!normalized) {
    return undefined;
  }
  return TRANSCRIPTION_RUN_STATUSES.includes(normalized as TranscriptionRunStatus)
    ? (normalized as TranscriptionRunStatus)
    : undefined;
}

export async function GET(
  request: Request,
  context: {
    params: Promise<{ projectId: string; documentId: string; runId: string }>;
  }
) {
  const { projectId, documentId, runId } = await context.params;
  const requestUrl = new URL(request.url);
  const rawStatus = requestUrl.searchParams.get("status");
  const status = parseTranscriptionRunStatus(rawStatus);
  if (rawStatus && !status) {
    return NextResponse.json(
      {
        detail:
          "status must be one of QUEUED, RUNNING, SUCCEEDED, FAILED, or CANCELED."
      },
      { status: 400 }
    );
  }
  const cursorRaw = requestUrl.searchParams.get("cursor");
  const pageSizeRaw = requestUrl.searchParams.get("pageSize");
  const cursor =
    typeof cursorRaw === "string" && cursorRaw.length > 0
      ? Number.parseInt(cursorRaw, 10)
      : undefined;
  const pageSize =
    typeof pageSizeRaw === "string" && pageSizeRaw.length > 0
      ? Number.parseInt(pageSizeRaw, 10)
      : undefined;
  const result = await listProjectDocumentTranscriptionRunPages(
    projectId,
    documentId,
    runId,
    {
      status,
      cursor: Number.isFinite(cursor) ? cursor : undefined,
      pageSize: Number.isFinite(pageSize) ? pageSize : undefined
    }
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcription run pages unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
