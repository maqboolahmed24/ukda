import { NextResponse } from "next/server";
import type {
  TranscriptionConfidenceBasis,
  TranscriptionRunEngine
} from "@ukde/contracts";

import {
  createProjectDocumentTranscriptionRun,
  listProjectDocumentTranscriptionRuns
} from "../../../../../../../lib/documents";

interface CreatePayload {
  confidenceBasis?: unknown;
  confidenceCalibrationVersion?: unknown;
  containerDigest?: unknown;
  engine?: unknown;
  inputLayoutRunId?: unknown;
  inputPreprocessRunId?: unknown;
  modelId?: unknown;
  paramsJson?: unknown;
  pipelineVersion?: unknown;
  projectModelAssignmentId?: unknown;
  promptTemplateId?: unknown;
  promptTemplateSha256?: unknown;
  responseSchemaVersion?: unknown;
  supersedesTranscriptionRunId?: unknown;
}

const TRANSCRIPTION_RUN_ENGINES: readonly TranscriptionRunEngine[] = [
  "VLM_LINE_CONTEXT",
  "REVIEW_COMPOSED",
  "KRAKEN_LINE",
  "TROCR_LINE",
  "DAN_PAGE"
];

const TRANSCRIPTION_CONFIDENCE_BASES: readonly TranscriptionConfidenceBasis[] = [
  "MODEL_NATIVE",
  "READ_AGREEMENT",
  "FALLBACK_DISAGREEMENT"
];

function toOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : undefined;
}

function toOptionalTranscriptionRunEngine(
  value: unknown
): TranscriptionRunEngine | undefined {
  const normalized = toOptionalString(value)?.toUpperCase();
  if (!normalized) {
    return undefined;
  }
  return TRANSCRIPTION_RUN_ENGINES.includes(normalized as TranscriptionRunEngine)
    ? (normalized as TranscriptionRunEngine)
    : undefined;
}

function toOptionalTranscriptionConfidenceBasis(
  value: unknown
): TranscriptionConfidenceBasis | undefined {
  const normalized = toOptionalString(value)?.toUpperCase();
  if (!normalized) {
    return undefined;
  }
  return TRANSCRIPTION_CONFIDENCE_BASES.includes(
    normalized as TranscriptionConfidenceBasis
  )
    ? (normalized as TranscriptionConfidenceBasis)
    : undefined;
}

function toOptionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
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
  const result = await listProjectDocumentTranscriptionRuns(projectId, documentId, {
    cursor: Number.isFinite(cursor) ? cursor : undefined,
    pageSize: Number.isFinite(pageSize) ? pageSize : undefined
  });
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcription runs unavailable." },
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
  const rawEngine = toOptionalString(payload.engine);
  const engine = toOptionalTranscriptionRunEngine(payload.engine);
  if (rawEngine && !engine) {
    return NextResponse.json(
      {
        detail:
          "engine must be one of VLM_LINE_CONTEXT, REVIEW_COMPOSED, KRAKEN_LINE, TROCR_LINE, or DAN_PAGE."
      },
      { status: 400 }
    );
  }
  const rawConfidenceBasis = toOptionalString(payload.confidenceBasis);
  const confidenceBasis = toOptionalTranscriptionConfidenceBasis(
    payload.confidenceBasis
  );
  if (rawConfidenceBasis && !confidenceBasis) {
    return NextResponse.json(
      {
        detail:
          "confidenceBasis must be one of MODEL_NATIVE, READ_AGREEMENT, or FALLBACK_DISAGREEMENT."
      },
      { status: 400 }
    );
  }
  const result = await createProjectDocumentTranscriptionRun(projectId, documentId, {
    inputPreprocessRunId: toOptionalString(payload.inputPreprocessRunId),
    inputLayoutRunId: toOptionalString(payload.inputLayoutRunId),
    engine,
    modelId: toOptionalString(payload.modelId),
    projectModelAssignmentId: toOptionalString(payload.projectModelAssignmentId),
    promptTemplateId: toOptionalString(payload.promptTemplateId),
    promptTemplateSha256: toOptionalString(payload.promptTemplateSha256),
    responseSchemaVersion: toOptionalNumber(payload.responseSchemaVersion),
    confidenceBasis,
    confidenceCalibrationVersion: toOptionalString(payload.confidenceCalibrationVersion),
    paramsJson: toOptionalParams(payload.paramsJson),
    pipelineVersion: toOptionalString(payload.pipelineVersion),
    containerDigest: toOptionalString(payload.containerDigest),
    supersedesTranscriptionRunId: toOptionalString(payload.supersedesTranscriptionRunId)
  });
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcription run create failed." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
