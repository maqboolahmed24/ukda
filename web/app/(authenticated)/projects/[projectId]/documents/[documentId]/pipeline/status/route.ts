import { NextResponse } from "next/server";

import { queryCachePolicy } from "../../../../../../../../lib/data/cache-policy";
import {
  getProjectDocument,
  getProjectDocumentGovernanceOverview,
  getProjectDocumentGovernanceRunLedgerStatus,
  getProjectDocumentGovernanceRunManifestStatus,
  getProjectDocumentLayoutOverview,
  getProjectDocumentPreprocessOverview,
  getProjectDocumentProcessingRunStatus,
  getProjectDocumentRedactionOverview,
  getProjectDocumentTranscriptionOverview,
  listProjectDocumentProcessingRuns
} from "../../../../../../../../lib/documents";
import {
  computeGovernancePipelinePhase,
  computeIngestPipelinePhase,
  computeLayoutPipelinePhase,
  computeOverallPipelinePercent,
  computePreprocessPipelinePhase,
  computePrivacyPipelinePhase,
  computeTranscriptionPipelinePhase,
  createDegradedPipelinePhase,
  mergeProcessingTimelineStatuses,
  normalizePipelinePhaseOrder,
  resolvePipelineErrors,
  type DocumentPipelinePhaseId,
  type DocumentPipelineStatusResponse
} from "../../../../../../../../lib/pipeline-status";

export const dynamic = "force-dynamic";

const FALLBACK_POLL_MS = queryCachePolicy["operations-live"].pollIntervalMs ?? 4_000;

function resolveFailureDetail(
  fallback: string,
  detail: string | null | undefined
): string {
  const normalized = (detail ?? "").trim();
  return normalized.length > 0 ? normalized : fallback;
}

export async function GET(
  _request: Request,
  context: { params: Promise<{ projectId: string; documentId: string }> }
) {
  const { projectId, documentId } = await context.params;
  const documentResult = await getProjectDocument(projectId, documentId);
  if (!documentResult.ok || !documentResult.data) {
    return NextResponse.json(
      { detail: resolveFailureDetail("Document unavailable.", documentResult.detail) },
      { status: documentResult.status }
    );
  }

  const document = documentResult.data;
  const failures: Array<{ phaseId: DocumentPipelinePhaseId; detail: string }> = [];

  const [
    processingRunsResult,
    preprocessOverviewResult,
    layoutOverviewResult,
    transcriptionOverviewResult,
    privacyOverviewResult,
    governanceOverviewResult
  ] = await Promise.all([
    listProjectDocumentProcessingRuns(projectId, document.id),
    getProjectDocumentPreprocessOverview(projectId, document.id),
    getProjectDocumentLayoutOverview(projectId, document.id),
    getProjectDocumentTranscriptionOverview(projectId, document.id),
    getProjectDocumentRedactionOverview(projectId, document.id),
    getProjectDocumentGovernanceOverview(projectId, document.id)
  ]);

  const phases: DocumentPipelineStatusResponse["phases"] = [];

  if (!processingRunsResult.ok || !processingRunsResult.data) {
    const detail = resolveFailureDetail(
      "Ingest timeline unavailable.",
      processingRunsResult.detail
    );
    phases.push(createDegradedPipelinePhase("INGEST", "Ingest", detail));
    failures.push({ phaseId: "INGEST", detail });
  } else {
    const timelineItems = processingRunsResult.data.items;
    const activeRunIds = timelineItems
      .filter((item) => item.status === "QUEUED" || item.status === "RUNNING")
      .map((item) => item.id);
    let mergedTimelineItems = timelineItems;

    if (activeRunIds.length > 0) {
      const statusResults = await Promise.all(
        activeRunIds.map((runId) =>
          getProjectDocumentProcessingRunStatus(projectId, document.id, runId)
        )
      );
      const statusEntries = statusResults.flatMap((result) => {
        if (!result.ok || !result.data) {
          return [];
        }
        return [
          {
            runId: result.data.runId,
            status: result.data.status,
            failureReason: result.data.failureReason,
            startedAt: result.data.startedAt,
            finishedAt: result.data.finishedAt,
            canceledAt: result.data.canceledAt
          }
        ];
      });

      mergedTimelineItems = mergeProcessingTimelineStatuses(timelineItems, statusEntries);

      const failedStatusCount = statusResults.length - statusEntries.length;
      if (failedStatusCount > 0) {
        failures.push({
          phaseId: "INGEST",
          detail:
            failedStatusCount === 1
              ? "One ingest status poll request failed."
              : `${failedStatusCount} ingest status poll requests failed.`
        });
      }
    }

    phases.push(computeIngestPipelinePhase(document.status, mergedTimelineItems));
  }

  if (!preprocessOverviewResult.ok || !preprocessOverviewResult.data) {
    const detail = resolveFailureDetail(
      "Preprocess overview unavailable.",
      preprocessOverviewResult.detail
    );
    phases.push(createDegradedPipelinePhase("PREPROCESS", "Preprocess", detail));
    failures.push({ phaseId: "PREPROCESS", detail });
  } else {
    phases.push(computePreprocessPipelinePhase(preprocessOverviewResult.data));
  }

  if (!layoutOverviewResult.ok || !layoutOverviewResult.data) {
    const detail = resolveFailureDetail(
      "Layout overview unavailable.",
      layoutOverviewResult.detail
    );
    phases.push(createDegradedPipelinePhase("LAYOUT", "Layout", detail));
    failures.push({ phaseId: "LAYOUT", detail });
  } else {
    phases.push(computeLayoutPipelinePhase(layoutOverviewResult.data));
  }

  if (!transcriptionOverviewResult.ok || !transcriptionOverviewResult.data) {
    const detail = resolveFailureDetail(
      "Transcription overview unavailable.",
      transcriptionOverviewResult.detail
    );
    phases.push(createDegradedPipelinePhase("TRANSCRIPTION", "Transcription", detail));
    failures.push({ phaseId: "TRANSCRIPTION", detail });
  } else {
    phases.push(computeTranscriptionPipelinePhase(transcriptionOverviewResult.data));
  }

  if (!privacyOverviewResult.ok || !privacyOverviewResult.data) {
    const detail = resolveFailureDetail(
      "Privacy overview unavailable.",
      privacyOverviewResult.detail
    );
    phases.push(createDegradedPipelinePhase("PRIVACY", "Privacy", detail));
    failures.push({ phaseId: "PRIVACY", detail });
  } else {
    phases.push(computePrivacyPipelinePhase(privacyOverviewResult.data));
  }

  if (!governanceOverviewResult.ok || !governanceOverviewResult.data) {
    const detail = resolveFailureDetail(
      "Governance overview unavailable.",
      governanceOverviewResult.detail
    );
    phases.push(createDegradedPipelinePhase("GOVERNANCE", "Governance", detail));
    failures.push({ phaseId: "GOVERNANCE", detail });
  } else {
    const governanceOverview = governanceOverviewResult.data;
    const activeRunId = governanceOverview.activeRunId;

    let manifestStatus = null;
    let ledgerStatus = null;

    if (activeRunId) {
      const [manifestStatusResult, ledgerStatusResult] = await Promise.all([
        getProjectDocumentGovernanceRunManifestStatus(projectId, document.id, activeRunId),
        getProjectDocumentGovernanceRunLedgerStatus(projectId, document.id, activeRunId)
      ]);

      if (manifestStatusResult.ok && manifestStatusResult.data) {
        manifestStatus = manifestStatusResult.data;
      } else {
        failures.push({
          phaseId: "GOVERNANCE",
          detail: resolveFailureDetail(
            "Governance manifest status unavailable.",
            manifestStatusResult.detail
          )
        });
      }

      if (ledgerStatusResult.ok && ledgerStatusResult.data) {
        ledgerStatus = ledgerStatusResult.data;
      } else {
        failures.push({
          phaseId: "GOVERNANCE",
          detail: resolveFailureDetail(
            "Governance ledger status unavailable.",
            ledgerStatusResult.detail
          )
        });
      }
    }

    phases.push(
      computeGovernancePipelinePhase({
        overview: governanceOverview,
        manifestStatus,
        ledgerStatus
      })
    );
  }

  const orderedPhases = normalizePipelinePhaseOrder(phases);
  const errors = resolvePipelineErrors(failures);
  const payload: DocumentPipelineStatusResponse = {
    phases: orderedPhases,
    overallPercent: computeOverallPipelinePercent(orderedPhases),
    degraded:
      errors.length > 0 ||
      orderedPhases.some((phase) => phase.status === "DEGRADED"),
    errors,
    recommendedPollMs: FALLBACK_POLL_MS
  };

  return NextResponse.json(payload, { status: 200 });
}
