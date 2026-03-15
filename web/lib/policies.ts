import type {
  ActiveProjectPolicyResponse,
  CreatePolicyRollbackDraftRequest,
  CreateRedactionPolicyRequest,
  PolicyExplainabilityResponse,
  PolicyLineageResponse,
  PolicyCompareResponse,
  PolicyEventListResponse,
  PolicySnapshotResponse,
  PolicyUsageResponse,
  PolicyValidationResponse,
  RedactionPolicy,
  RedactionPolicyListResponse,
  UpdateRedactionPolicyRequest
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryCacheClass } from "./data/cache-policy";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type PoliciesApiResult<T> = ApiResult<T>;

async function requestPoliciesApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    cacheClass?: QueryCacheClass;
    expectNoContent?: boolean;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<PoliciesApiResult<T>> {
  return requestServerApi<T>({
    path,
    method: options?.method,
    headers: options?.headers,
    body: options?.body,
    expectNoContent: options?.expectNoContent,
    cacheClass: options?.cacheClass ?? "mutable-list",
    queryKey: options?.queryKey
  });
}

export async function listProjectPolicies(
  projectId: string
): Promise<PoliciesApiResult<RedactionPolicyListResponse>> {
  return requestPoliciesApi<RedactionPolicyListResponse>(
    `/projects/${projectId}/policies`,
    {
      queryKey: queryKeys.projects.policyList(projectId)
    }
  );
}

export async function getProjectActivePolicy(
  projectId: string
): Promise<PoliciesApiResult<ActiveProjectPolicyResponse>> {
  return requestPoliciesApi<ActiveProjectPolicyResponse>(
    `/projects/${projectId}/policies/active`,
    {
      queryKey: queryKeys.projects.policyActive(projectId)
    }
  );
}

export async function createProjectPolicy(
  projectId: string,
  payload: CreateRedactionPolicyRequest
): Promise<PoliciesApiResult<RedactionPolicy>> {
  return requestPoliciesApi<RedactionPolicy>(`/projects/${projectId}/policies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function getProjectPolicy(
  projectId: string,
  policyId: string
): Promise<PoliciesApiResult<RedactionPolicy>> {
  return requestPoliciesApi<RedactionPolicy>(
    `/projects/${projectId}/policies/${policyId}`,
    {
      queryKey: queryKeys.projects.policyDetail(projectId, policyId)
    }
  );
}

export async function listProjectPolicyEvents(
  projectId: string,
  policyId: string
): Promise<PoliciesApiResult<PolicyEventListResponse>> {
  return requestPoliciesApi<PolicyEventListResponse>(
    `/projects/${projectId}/policies/${policyId}/events`,
    {
      queryKey: queryKeys.projects.policyEvents(projectId, policyId)
    }
  );
}

export async function getProjectPolicyLineage(
  projectId: string,
  policyId: string
): Promise<PoliciesApiResult<PolicyLineageResponse>> {
  return requestPoliciesApi<PolicyLineageResponse>(
    `/projects/${projectId}/policies/${policyId}/lineage`,
    {
      queryKey: queryKeys.projects.policyLineage(projectId, policyId)
    }
  );
}

export async function getProjectPolicyUsage(
  projectId: string,
  policyId: string
): Promise<PoliciesApiResult<PolicyUsageResponse>> {
  return requestPoliciesApi<PolicyUsageResponse>(
    `/projects/${projectId}/policies/${policyId}/usage`,
    {
      queryKey: queryKeys.projects.policyUsage(projectId, policyId)
    }
  );
}

export async function getProjectPolicyExplainability(
  projectId: string,
  policyId: string
): Promise<PoliciesApiResult<PolicyExplainabilityResponse>> {
  return requestPoliciesApi<PolicyExplainabilityResponse>(
    `/projects/${projectId}/policies/${policyId}/explainability`,
    {
      queryKey: queryKeys.projects.policyExplainability(projectId, policyId)
    }
  );
}

export async function getProjectPolicySnapshot(
  projectId: string,
  policyId: string,
  rulesSha256: string
): Promise<PoliciesApiResult<PolicySnapshotResponse>> {
  return requestPoliciesApi<PolicySnapshotResponse>(
    `/projects/${projectId}/policies/${policyId}/snapshots/${encodeURIComponent(rulesSha256)}`,
    {
      queryKey: queryKeys.projects.policySnapshot(projectId, policyId, rulesSha256)
    }
  );
}

export async function updateProjectPolicy(
  projectId: string,
  policyId: string,
  payload: UpdateRedactionPolicyRequest
): Promise<PoliciesApiResult<RedactionPolicy>> {
  return requestPoliciesApi<RedactionPolicy>(
    `/projects/${projectId}/policies/${policyId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function compareProjectPolicy(
  projectId: string,
  policyId: string,
  options: {
    against?: string | null;
    againstBaselineSnapshotId?: string | null;
  }
): Promise<PoliciesApiResult<PolicyCompareResponse>> {
  const params = new URLSearchParams();
  const against = options.against?.trim();
  const againstBaseline = options.againstBaselineSnapshotId?.trim();
  if (against) {
    params.set("against", against);
  } else if (againstBaseline) {
    params.set("againstBaselineSnapshotId", againstBaseline);
  }
  const query = params.toString();
  return requestPoliciesApi<PolicyCompareResponse>(
    `/projects/${projectId}/policies/${policyId}/compare${query ? `?${query}` : ""}`,
    {
      queryKey: queryKeys.projects.policyCompare(projectId, policyId, {
        against: against ?? undefined,
        againstBaselineSnapshotId: againstBaseline ?? undefined
      })
    }
  );
}

export async function validateProjectPolicy(
  projectId: string,
  policyId: string,
  reason?: string | null
): Promise<PoliciesApiResult<PolicyValidationResponse>> {
  return requestPoliciesApi<PolicyValidationResponse>(
    `/projects/${projectId}/policies/${policyId}/validate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason ?? null })
    }
  );
}

export async function activateProjectPolicy(
  projectId: string,
  policyId: string,
  reason?: string | null
): Promise<PoliciesApiResult<RedactionPolicy>> {
  return requestPoliciesApi<RedactionPolicy>(
    `/projects/${projectId}/policies/${policyId}/activate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason ?? null })
    }
  );
}

export async function retireProjectPolicy(
  projectId: string,
  policyId: string,
  reason?: string | null
): Promise<PoliciesApiResult<RedactionPolicy>> {
  return requestPoliciesApi<RedactionPolicy>(
    `/projects/${projectId}/policies/${policyId}/retire`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason ?? null })
    }
  );
}

export async function createProjectPolicyRollbackDraft(
  projectId: string,
  policyId: string,
  payload: CreatePolicyRollbackDraftRequest
): Promise<PoliciesApiResult<RedactionPolicy>> {
  const fromPolicyId = payload.fromPolicyId.trim();
  const params = new URLSearchParams();
  params.set("fromPolicyId", fromPolicyId);
  return requestPoliciesApi<RedactionPolicy>(
    `/projects/${projectId}/policies/${policyId}/rollback-draft?${params.toString()}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: payload.reason ?? null })
    }
  );
}
