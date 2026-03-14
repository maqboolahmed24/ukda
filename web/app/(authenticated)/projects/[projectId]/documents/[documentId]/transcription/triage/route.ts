import { NextResponse } from "next/server";
import type { TranscriptionRunStatus } from "@ukde/contracts";

import { getProjectDocumentTranscriptionTriage } from "../../../../../../../../lib/documents";

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
  context: { params: Promise<{ projectId: string; documentId: string }> }
) {
  const { projectId, documentId } = await context.params;
  const requestUrl = new URL(request.url);
  const runId = requestUrl.searchParams.get("runId") ?? undefined;
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
  const confidenceBelowRaw = requestUrl.searchParams.get("confidenceBelow");
  const pageRaw = requestUrl.searchParams.get("page");
  const cursorRaw = requestUrl.searchParams.get("cursor");
  const pageSizeRaw = requestUrl.searchParams.get("pageSize");
  const confidenceBelow =
    typeof confidenceBelowRaw === "string" && confidenceBelowRaw.length > 0
      ? Number.parseFloat(confidenceBelowRaw)
      : undefined;
  const page =
    typeof pageRaw === "string" && pageRaw.length > 0
      ? Number.parseInt(pageRaw, 10)
      : undefined;
  const cursor =
    typeof cursorRaw === "string" && cursorRaw.length > 0
      ? Number.parseInt(cursorRaw, 10)
      : undefined;
  const pageSize =
    typeof pageSizeRaw === "string" && pageSizeRaw.length > 0
      ? Number.parseInt(pageSizeRaw, 10)
      : undefined;

  const result = await getProjectDocumentTranscriptionTriage(projectId, documentId, {
    runId,
    status,
    confidenceBelow: Number.isFinite(confidenceBelow) ? confidenceBelow : undefined,
    page: Number.isFinite(page) ? page : undefined,
    cursor: Number.isFinite(cursor) ? cursor : undefined,
    pageSize: Number.isFinite(pageSize) ? pageSize : undefined
  });
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcription triage unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
