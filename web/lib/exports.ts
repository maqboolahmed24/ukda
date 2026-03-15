import type {
  ExportDecisionRequest,
  CreateExportRequestRequest,
  ExportCandidateListResponse,
  ExportCandidateResponse,
  ExportReviewActionResponse,
  ExportReviewEtagRequest,
  ExportReviewQueueResponse,
  ExportReceipt,
  ExportReceiptListResponse,
  ExportReleasePackPreviewResponse,
  ExportRequest,
  ExportRequestEventsResponse,
  ExportRequestListResponse,
  ExportRequestReleasePackResponse,
  ExportRequestValidationSummaryResponse,
  ExportRequestReviewEventsResponse,
  ExportRequestReviewsResponse,
  ExportRequestProvenanceSummaryResponse,
  ExportProvenanceProofListResponse,
  ExportProvenanceProofDetailResponse,
  RegenerateExportProvenanceProofResponse,
  ExportDepositBundleListResponse,
  ExportDepositBundleDetailResponse,
  ExportDepositBundleStatusResponse,
  ExportBundleEventsResponse,
  ExportBundleVerificationResponse,
  ExportBundleVerificationRunDetailResponse,
  ExportBundleVerificationRunMutationResponse,
  ExportBundleVerificationRunStatusResponse,
  ExportBundleVerificationRunsResponse,
  ExportBundleVerificationStatusResponse,
  ExportBundleProfilesResponse,
  ExportBundleValidationRunDetailResponse,
  ExportBundleValidationRunMutationResponse,
  ExportBundleValidationRunStatusResponse,
  ExportBundleValidationRunsResponse,
  ExportBundleValidationStatusResponse,
  ExportDepositBundleMutationResponse,
  ExportStartReviewRequest,
  ExportRequestStatusResponse,
  ResubmitExportRequestRequest
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type ExportApiResult<T> = ApiResult<T>;

export interface ExportRequestsFilters {
  status?: string;
  requesterId?: string;
  candidateKind?: string;
  cursor?: number;
  limit?: number;
}

interface ExportReviewFilters {
  status?: string;
  agingBucket?: string;
  reviewerUserId?: string;
}

interface CandidateReleasePackPreviewInput {
  purposeStatement?: string;
  bundleProfile?: string;
}

async function requestExportApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<ExportApiResult<T>> {
  return requestServerApi<T>({
    path,
    method: options?.method,
    headers: options?.headers,
    body: options?.body,
    cacheClass: "governance-event",
    queryKey: options?.queryKey
  });
}

function toQueryString(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    query.set(key, String(value));
  }
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
}

export async function listExportCandidates(
  projectId: string
): Promise<ExportApiResult<ExportCandidateListResponse>> {
  return requestExportApi<ExportCandidateListResponse>(
    `/projects/${projectId}/export-candidates`,
    {
      queryKey: queryKeys.exports.candidates(projectId)
    }
  );
}

export async function getExportCandidate(
  projectId: string,
  candidateId: string
): Promise<ExportApiResult<ExportCandidateResponse>> {
  return requestExportApi<ExportCandidateResponse>(
    `/projects/${projectId}/export-candidates/${candidateId}`,
    {
      queryKey: queryKeys.exports.candidate(projectId, candidateId)
    }
  );
}

export async function getExportCandidateReleasePackPreview(
  projectId: string,
  candidateId: string,
  input?: CandidateReleasePackPreviewInput
): Promise<ExportApiResult<ExportReleasePackPreviewResponse>> {
  const query = toQueryString({
    bundleProfile: input?.bundleProfile,
    purposeStatement: input?.purposeStatement
  });
  return requestExportApi<ExportReleasePackPreviewResponse>(
    `/projects/${projectId}/export-candidates/${candidateId}/release-pack${query}`,
    {
      queryKey: queryKeys.exports.candidateReleasePack(projectId, candidateId, input)
    }
  );
}

export async function createExportRequest(
  projectId: string,
  input: CreateExportRequestRequest
): Promise<ExportApiResult<ExportRequest>> {
  return requestExportApi<ExportRequest>(`/projects/${projectId}/export-requests`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(input)
  });
}

export async function resubmitExportRequest(
  projectId: string,
  exportRequestId: string,
  input: ResubmitExportRequestRequest
): Promise<ExportApiResult<ExportRequest>> {
  return requestExportApi<ExportRequest>(
    `/projects/${projectId}/export-requests/${exportRequestId}/resubmit`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(input)
    }
  );
}

export async function listExportRequests(
  projectId: string,
  filters: ExportRequestsFilters
): Promise<ExportApiResult<ExportRequestListResponse>> {
  return requestExportApi<ExportRequestListResponse>(
    `/projects/${projectId}/export-requests${toQueryString({
      status: filters.status,
      requesterId: filters.requesterId,
      candidateKind: filters.candidateKind,
      cursor: filters.cursor,
      limit: filters.limit
    })}`,
    {
      queryKey: queryKeys.exports.requests(projectId, filters)
    }
  );
}

export async function getExportRequest(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<ExportRequest>> {
  return requestExportApi<ExportRequest>(
    `/projects/${projectId}/export-requests/${exportRequestId}`,
    {
      queryKey: queryKeys.exports.request(projectId, exportRequestId)
    }
  );
}

export async function getExportRequestStatus(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<ExportRequestStatusResponse>> {
  return requestExportApi<ExportRequestStatusResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/status`,
    {
      queryKey: queryKeys.exports.requestStatus(projectId, exportRequestId)
    }
  );
}

export async function getExportRequestReleasePack(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<ExportRequestReleasePackResponse>> {
  return requestExportApi<ExportRequestReleasePackResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/release-pack`,
    {
      queryKey: queryKeys.exports.requestReleasePack(projectId, exportRequestId)
    }
  );
}

export async function getExportRequestValidationSummary(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<ExportRequestValidationSummaryResponse>> {
  return requestExportApi<ExportRequestValidationSummaryResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/validation-summary`,
    {
      queryKey: queryKeys.exports.requestValidationSummary(projectId, exportRequestId)
    }
  );
}

export async function getExportRequestProvenanceSummary(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<ExportRequestProvenanceSummaryResponse>> {
  return requestExportApi<ExportRequestProvenanceSummaryResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/provenance`,
    {
      queryKey: queryKeys.exports.requestProvenanceSummary(projectId, exportRequestId)
    }
  );
}

export async function listExportRequestProvenanceProofs(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<ExportProvenanceProofListResponse>> {
  return requestExportApi<ExportProvenanceProofListResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/provenance/proofs`,
    {
      queryKey: queryKeys.exports.requestProvenanceProofs(projectId, exportRequestId)
    }
  );
}

export async function getExportRequestCurrentProvenanceProof(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<ExportProvenanceProofDetailResponse>> {
  return requestExportApi<ExportProvenanceProofDetailResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/provenance/proof`,
    {
      queryKey: queryKeys.exports.requestProvenanceProofCurrent(projectId, exportRequestId)
    }
  );
}

export async function getExportRequestProvenanceProof(
  projectId: string,
  exportRequestId: string,
  proofId: string
): Promise<ExportApiResult<ExportProvenanceProofDetailResponse>> {
  return requestExportApi<ExportProvenanceProofDetailResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/provenance/proofs/${proofId}`,
    {
      queryKey: queryKeys.exports.requestProvenanceProof(
        projectId,
        exportRequestId,
        proofId
      )
    }
  );
}

export async function regenerateExportRequestProvenanceProof(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<RegenerateExportProvenanceProofResponse>> {
  return requestExportApi<RegenerateExportProvenanceProofResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/provenance/proofs/regenerate`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({})
    }
  );
}

export async function listExportRequestBundles(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<ExportDepositBundleListResponse>> {
  return requestExportApi<ExportDepositBundleListResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles`,
    {
      queryKey: queryKeys.exports.requestBundles(projectId, exportRequestId)
    }
  );
}

export async function createExportRequestBundle(
  projectId: string,
  exportRequestId: string,
  kind: "CONTROLLED_EVIDENCE" | "SAFEGUARDED_DEPOSIT"
): Promise<ExportApiResult<ExportDepositBundleMutationResponse>> {
  return requestExportApi<ExportDepositBundleMutationResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles${toQueryString({ kind })}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({})
    }
  );
}

export async function getExportRequestBundle(
  projectId: string,
  exportRequestId: string,
  bundleId: string
): Promise<ExportApiResult<ExportDepositBundleDetailResponse>> {
  return requestExportApi<ExportDepositBundleDetailResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}`,
    {
      queryKey: queryKeys.exports.requestBundle(projectId, exportRequestId, bundleId)
    }
  );
}

export async function getExportRequestBundleStatus(
  projectId: string,
  exportRequestId: string,
  bundleId: string
): Promise<ExportApiResult<ExportDepositBundleStatusResponse>> {
  return requestExportApi<ExportDepositBundleStatusResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/status`,
    {
      queryKey: queryKeys.exports.requestBundleStatus(
        projectId,
        exportRequestId,
        bundleId
      )
    }
  );
}

export async function listExportRequestBundleEvents(
  projectId: string,
  exportRequestId: string,
  bundleId: string
): Promise<ExportApiResult<ExportBundleEventsResponse>> {
  return requestExportApi<ExportBundleEventsResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/events`,
    {
      queryKey: queryKeys.exports.requestBundleEvents(
        projectId,
        exportRequestId,
        bundleId
      )
    }
  );
}

export async function cancelExportRequestBundle(
  projectId: string,
  exportRequestId: string,
  bundleId: string
): Promise<ExportApiResult<ExportDepositBundleMutationResponse>> {
  return requestExportApi<ExportDepositBundleMutationResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/cancel`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({})
    }
  );
}

export async function rebuildExportRequestBundle(
  projectId: string,
  exportRequestId: string,
  bundleId: string
): Promise<ExportApiResult<ExportDepositBundleMutationResponse>> {
  return requestExportApi<ExportDepositBundleMutationResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/rebuild`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({})
    }
  );
}

export async function startExportRequestBundleVerification(
  projectId: string,
  exportRequestId: string,
  bundleId: string
): Promise<ExportApiResult<ExportBundleVerificationRunMutationResponse>> {
  return requestExportApi<ExportBundleVerificationRunMutationResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/verify`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({})
    }
  );
}

export async function getExportRequestBundleVerification(
  projectId: string,
  exportRequestId: string,
  bundleId: string
): Promise<ExportApiResult<ExportBundleVerificationResponse>> {
  return requestExportApi<ExportBundleVerificationResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/verification`,
    {
      queryKey: queryKeys.exports.requestBundleVerification(
        projectId,
        exportRequestId,
        bundleId
      )
    }
  );
}

export async function getExportRequestBundleVerificationStatus(
  projectId: string,
  exportRequestId: string,
  bundleId: string
): Promise<ExportApiResult<ExportBundleVerificationStatusResponse>> {
  return requestExportApi<ExportBundleVerificationStatusResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/verification/status`,
    {
      queryKey: queryKeys.exports.requestBundleVerificationStatus(
        projectId,
        exportRequestId,
        bundleId
      )
    }
  );
}

export async function listExportRequestBundleVerificationRuns(
  projectId: string,
  exportRequestId: string,
  bundleId: string
): Promise<ExportApiResult<ExportBundleVerificationRunsResponse>> {
  return requestExportApi<ExportBundleVerificationRunsResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/verification-runs`,
    {
      queryKey: queryKeys.exports.requestBundleVerificationRuns(
        projectId,
        exportRequestId,
        bundleId
      )
    }
  );
}

export async function getExportRequestBundleVerificationRun(
  projectId: string,
  exportRequestId: string,
  bundleId: string,
  verificationRunId: string
): Promise<ExportApiResult<ExportBundleVerificationRunDetailResponse>> {
  return requestExportApi<ExportBundleVerificationRunDetailResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/verification/${verificationRunId}`,
    {
      queryKey: queryKeys.exports.requestBundleVerificationRun(
        projectId,
        exportRequestId,
        bundleId,
        verificationRunId
      )
    }
  );
}

export async function getExportRequestBundleVerificationRunStatus(
  projectId: string,
  exportRequestId: string,
  bundleId: string,
  verificationRunId: string
): Promise<ExportApiResult<ExportBundleVerificationRunStatusResponse>> {
  return requestExportApi<ExportBundleVerificationRunStatusResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/verification/${verificationRunId}/status`,
    {
      queryKey: queryKeys.exports.requestBundleVerificationRunStatus(
        projectId,
        exportRequestId,
        bundleId,
        verificationRunId
      )
    }
  );
}

export async function cancelExportRequestBundleVerificationRun(
  projectId: string,
  exportRequestId: string,
  bundleId: string,
  verificationRunId: string
): Promise<ExportApiResult<ExportBundleVerificationRunMutationResponse>> {
  return requestExportApi<ExportBundleVerificationRunMutationResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/verification/${verificationRunId}/cancel`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({})
    }
  );
}

export async function listExportRequestBundleProfiles(
  projectId: string,
  exportRequestId: string,
  bundleId?: string
): Promise<ExportApiResult<ExportBundleProfilesResponse>> {
  return requestExportApi<ExportBundleProfilesResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundle-profiles${toQueryString({
      bundleId
    })}`,
    {
      queryKey: queryKeys.exports.requestBundleProfiles(
        projectId,
        exportRequestId,
        bundleId
      )
    }
  );
}

export async function startExportRequestBundleValidation(
  projectId: string,
  exportRequestId: string,
  bundleId: string,
  profileId: string
): Promise<ExportApiResult<ExportBundleValidationRunMutationResponse>> {
  return requestExportApi<ExportBundleValidationRunMutationResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/validate-profile${toQueryString({
      profile: profileId
    })}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({})
    }
  );
}

export async function getExportRequestBundleValidationStatus(
  projectId: string,
  exportRequestId: string,
  bundleId: string,
  profileId: string
): Promise<ExportApiResult<ExportBundleValidationStatusResponse>> {
  return requestExportApi<ExportBundleValidationStatusResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/validation-status${toQueryString({
      profile: profileId
    })}`,
    {
      queryKey: queryKeys.exports.requestBundleValidationStatus(
        projectId,
        exportRequestId,
        bundleId,
        profileId
      )
    }
  );
}

export async function listExportRequestBundleValidationRuns(
  projectId: string,
  exportRequestId: string,
  bundleId: string,
  profileId: string
): Promise<ExportApiResult<ExportBundleValidationRunsResponse>> {
  return requestExportApi<ExportBundleValidationRunsResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/validation-runs${toQueryString({
      profile: profileId
    })}`,
    {
      queryKey: queryKeys.exports.requestBundleValidationRuns(
        projectId,
        exportRequestId,
        bundleId,
        profileId
      )
    }
  );
}

export async function getExportRequestBundleValidationRun(
  projectId: string,
  exportRequestId: string,
  bundleId: string,
  validationRunId: string,
  profileId?: string
): Promise<ExportApiResult<ExportBundleValidationRunDetailResponse>> {
  return requestExportApi<ExportBundleValidationRunDetailResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/validation-runs/${validationRunId}${toQueryString({
      profile: profileId
    })}`,
    {
      queryKey: queryKeys.exports.requestBundleValidationRun(
        projectId,
        exportRequestId,
        bundleId,
        validationRunId,
        profileId
      )
    }
  );
}

export async function getExportRequestBundleValidationRunStatus(
  projectId: string,
  exportRequestId: string,
  bundleId: string,
  validationRunId: string,
  profileId?: string
): Promise<ExportApiResult<ExportBundleValidationRunStatusResponse>> {
  return requestExportApi<ExportBundleValidationRunStatusResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/validation-runs/${validationRunId}/status${toQueryString({
      profile: profileId
    })}`,
    {
      queryKey: queryKeys.exports.requestBundleValidationRunStatus(
        projectId,
        exportRequestId,
        bundleId,
        validationRunId,
        profileId
      )
    }
  );
}

export async function cancelExportRequestBundleValidationRun(
  projectId: string,
  exportRequestId: string,
  bundleId: string,
  validationRunId: string,
  profileId?: string
): Promise<ExportApiResult<ExportBundleValidationRunMutationResponse>> {
  return requestExportApi<ExportBundleValidationRunMutationResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/validation-runs/${validationRunId}/cancel${toQueryString({
      profile: profileId
    })}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({})
    }
  );
}

export async function getExportRequestEvents(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<ExportRequestEventsResponse>> {
  return requestExportApi<ExportRequestEventsResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/events`,
    {
      queryKey: queryKeys.exports.requestEvents(projectId, exportRequestId)
    }
  );
}

export async function getExportRequestReviews(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<ExportRequestReviewsResponse>> {
  return requestExportApi<ExportRequestReviewsResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/reviews`,
    {
      queryKey: queryKeys.exports.requestReviews(projectId, exportRequestId)
    }
  );
}

export async function getExportRequestReviewEvents(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<ExportRequestReviewEventsResponse>> {
  return requestExportApi<ExportRequestReviewEventsResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/reviews/events`,
    {
      queryKey: queryKeys.exports.requestReviewEvents(projectId, exportRequestId)
    }
  );
}

export async function getExportRequestReceipt(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<ExportReceipt>> {
  return requestExportApi<ExportReceipt>(
    `/projects/${projectId}/export-requests/${exportRequestId}/receipt`,
    {
      queryKey: queryKeys.exports.requestReceipt(projectId, exportRequestId)
    }
  );
}

export async function listExportRequestReceipts(
  projectId: string,
  exportRequestId: string
): Promise<ExportApiResult<ExportReceiptListResponse>> {
  return requestExportApi<ExportReceiptListResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/receipts`,
    {
      queryKey: queryKeys.exports.requestReceipts(projectId, exportRequestId)
    }
  );
}

export async function listExportReviewQueue(
  projectId: string,
  filters: ExportReviewFilters
): Promise<ExportApiResult<ExportReviewQueueResponse>> {
  return requestExportApi<ExportReviewQueueResponse>(
    `/projects/${projectId}/export-review${toQueryString({
      status: filters.status,
      agingBucket: filters.agingBucket,
      reviewerUserId: filters.reviewerUserId
    })}`,
    {
      queryKey: queryKeys.exports.review(projectId, filters)
    }
  );
}

export async function claimExportRequestReview(
  projectId: string,
  exportRequestId: string,
  reviewId: string,
  input: ExportReviewEtagRequest
): Promise<ExportApiResult<ExportReviewActionResponse>> {
  return requestExportApi<ExportReviewActionResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/reviews/${reviewId}/claim`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(input)
    }
  );
}

export async function releaseExportRequestReview(
  projectId: string,
  exportRequestId: string,
  reviewId: string,
  input: ExportReviewEtagRequest
): Promise<ExportApiResult<ExportReviewActionResponse>> {
  return requestExportApi<ExportReviewActionResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/reviews/${reviewId}/release`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(input)
    }
  );
}

export async function startExportRequestReview(
  projectId: string,
  exportRequestId: string,
  input: ExportStartReviewRequest
): Promise<ExportApiResult<ExportReviewActionResponse>> {
  return requestExportApi<ExportReviewActionResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/start-review`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(input)
    }
  );
}

export async function decideExportRequest(
  projectId: string,
  exportRequestId: string,
  input: ExportDecisionRequest
): Promise<ExportApiResult<ExportReviewActionResponse>> {
  return requestExportApi<ExportReviewActionResponse>(
    `/projects/${projectId}/export-requests/${exportRequestId}/decision`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(input)
    }
  );
}
