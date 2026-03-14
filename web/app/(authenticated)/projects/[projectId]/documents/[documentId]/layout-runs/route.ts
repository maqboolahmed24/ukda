import { NextResponse } from "next/server";

import {
  createProjectDocumentLayoutRun,
  listProjectDocumentLayoutRuns
} from "../../../../../../../lib/documents";

interface CreatePayload {
  containerDigest?: unknown;
  inputPreprocessRunId?: unknown;
  modelId?: unknown;
  paramsJson?: unknown;
  parentRunId?: unknown;
  pipelineVersion?: unknown;
  profileId?: unknown;
  supersedesRunId?: unknown;
}

function toOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : undefined;
}

function toOptionalParams(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

export async function GET(
  request: Request,
  context: { params: Promise<{ projectId: string; documentId: string }> }
) {
  const { projectId, documentId } = await context.params;
  const requestUrl = new URL(request.url);
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
  const result = await listProjectDocumentLayoutRuns(projectId, documentId, {
    cursor: Number.isFinite(cursor) ? cursor : undefined,
    pageSize: Number.isFinite(pageSize) ? pageSize : undefined
  });
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Layout runs unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}

export async function POST(
  request: Request,
  context: { params: Promise<{ projectId: string; documentId: string }> }
) {
  let payload: CreatePayload = {};
  try {
    payload = (await request.json()) as CreatePayload;
  } catch {}
  const { projectId, documentId } = await context.params;
  const result = await createProjectDocumentLayoutRun(projectId, documentId, {
    inputPreprocessRunId: toOptionalString(payload.inputPreprocessRunId),
    modelId: toOptionalString(payload.modelId),
    profileId: toOptionalString(payload.profileId),
    paramsJson: toOptionalParams(payload.paramsJson),
    pipelineVersion: toOptionalString(payload.pipelineVersion),
    containerDigest: toOptionalString(payload.containerDigest),
    parentRunId: toOptionalString(payload.parentRunId),
    supersedesRunId: toOptionalString(payload.supersedesRunId)
  });
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Layout run create failed." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
