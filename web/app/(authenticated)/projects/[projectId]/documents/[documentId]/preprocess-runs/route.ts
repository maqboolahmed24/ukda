import { NextResponse } from "next/server";

import {
  createProjectDocumentPreprocessRun,
  listProjectDocumentPreprocessRuns
} from "../../../../../../../lib/documents";

type PreprocessProfileId =
  | "BALANCED"
  | "CONSERVATIVE"
  | "AGGRESSIVE"
  | "BLEED_THROUGH";

interface CreatePayload {
  advancedRiskAcknowledgement?: unknown;
  advancedRiskConfirmed?: unknown;
  containerDigest?: unknown;
  paramsJson?: unknown;
  parentRunId?: unknown;
  pipelineVersion?: unknown;
  profileId?: unknown;
  supersedesRunId?: unknown;
}

function toOptionalBoolean(value: unknown): boolean | undefined {
  if (typeof value === "boolean") {
    return value;
  }
  return undefined;
}

function toOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : undefined;
}

function isPreprocessProfileId(value: string): value is PreprocessProfileId {
  return (
    value === "BALANCED" ||
    value === "CONSERVATIVE" ||
    value === "AGGRESSIVE" ||
    value === "BLEED_THROUGH"
  );
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

  const result = await listProjectDocumentPreprocessRuns(projectId, documentId, {
    cursor: Number.isFinite(cursor) ? cursor : undefined,
    pageSize: Number.isFinite(pageSize) ? pageSize : undefined
  });
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Preprocess runs unavailable." },
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
  const rawProfileId = toOptionalString(payload.profileId);
  const normalizedProfileId = rawProfileId?.toUpperCase();
  if (normalizedProfileId && !isPreprocessProfileId(normalizedProfileId)) {
    return NextResponse.json(
      {
        detail:
          "profileId must be BALANCED, CONSERVATIVE, AGGRESSIVE, or BLEED_THROUGH."
      },
      { status: 400 }
    );
  }
  const result = await createProjectDocumentPreprocessRun(projectId, documentId, {
    profileId: normalizedProfileId as PreprocessProfileId | undefined,
    paramsJson: toOptionalParams(payload.paramsJson),
    pipelineVersion: toOptionalString(payload.pipelineVersion),
    containerDigest: toOptionalString(payload.containerDigest),
    parentRunId: toOptionalString(payload.parentRunId),
    supersedesRunId: toOptionalString(payload.supersedesRunId),
    advancedRiskConfirmed: toOptionalBoolean(payload.advancedRiskConfirmed),
    advancedRiskAcknowledgement: toOptionalString(payload.advancedRiskAcknowledgement)
  });
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Preprocess run create failed." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
