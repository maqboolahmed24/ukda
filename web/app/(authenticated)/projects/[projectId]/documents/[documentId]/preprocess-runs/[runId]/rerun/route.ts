import { NextResponse } from "next/server";

import { rerunProjectDocumentPreprocessRun } from "../../../../../../../../../lib/documents";

type PreprocessProfileId =
  | "BALANCED"
  | "CONSERVATIVE"
  | "AGGRESSIVE"
  | "BLEED_THROUGH";

interface RerunPayload {
  advancedRiskAcknowledgement?: unknown;
  advancedRiskConfirmed?: unknown;
  containerDigest?: unknown;
  paramsJson?: unknown;
  pipelineVersion?: unknown;
  profileId?: unknown;
  targetPageIds?: unknown;
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

function toOptionalBoolean(value: unknown): boolean | undefined {
  if (typeof value === "boolean") {
    return value;
  }
  return undefined;
}

function toOptionalPageIds(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const normalized = Array.from(
    new Set(
      value
        .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
        .filter((entry) => entry.length > 0)
    )
  );
  return normalized.length > 0 ? normalized : undefined;
}

export async function POST(
  request: Request,
  context: {
    params: Promise<{ projectId: string; documentId: string; runId: string }>;
  }
) {
  let payload: RerunPayload = {};
  try {
    payload = (await request.json()) as RerunPayload;
  } catch {}
  const { projectId, documentId, runId } = await context.params;
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
  const result = await rerunProjectDocumentPreprocessRun(
    projectId,
    documentId,
    runId,
    {
      profileId: normalizedProfileId as PreprocessProfileId | undefined,
      paramsJson: toOptionalParams(payload.paramsJson),
      pipelineVersion: toOptionalString(payload.pipelineVersion),
      containerDigest: toOptionalString(payload.containerDigest),
      targetPageIds: toOptionalPageIds(payload.targetPageIds),
      advancedRiskConfirmed: toOptionalBoolean(payload.advancedRiskConfirmed),
      advancedRiskAcknowledgement: toOptionalString(payload.advancedRiskAcknowledgement)
    }
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Preprocess run rerun failed." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
