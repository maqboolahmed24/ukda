import type {
  ApprovedModel,
  ApprovedModelListResponse,
  ApprovedModelRole,
  ApprovedModelStatus,
  CreateApprovedModelRequest,
  CreateProjectModelAssignmentRequest,
  ProjectModelAssignment,
  ProjectModelAssignmentListResponse,
  TrainingDatasetListResponse
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryCacheClass } from "./data/cache-policy";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type ModelAssignmentsApiResult<T> = ApiResult<T>;

export interface ApprovedModelListFilters {
  modelRole?: ApprovedModelRole;
  status?: ApprovedModelStatus;
}

async function requestModelAssignmentsApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    cacheClass?: QueryCacheClass;
    expectNoContent?: boolean;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<ModelAssignmentsApiResult<T>> {
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

function toApprovedModelsQueryString(filters: ApprovedModelListFilters): string {
  const params = new URLSearchParams();
  if (typeof filters.modelRole === "string" && filters.modelRole.trim()) {
    params.set("modelRole", filters.modelRole.trim());
  }
  if (typeof filters.status === "string" && filters.status.trim()) {
    params.set("status", filters.status.trim());
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function listApprovedModels(
  filters: ApprovedModelListFilters = {}
): Promise<ModelAssignmentsApiResult<ApprovedModelListResponse>> {
  return requestModelAssignmentsApi<ApprovedModelListResponse>(
    `/approved-models${toApprovedModelsQueryString(filters)}`,
    {
      queryKey: queryKeys.models.approvedList(filters)
    }
  );
}

export async function createApprovedModel(
  payload: CreateApprovedModelRequest
): Promise<ModelAssignmentsApiResult<ApprovedModel>> {
  return requestModelAssignmentsApi<ApprovedModel>("/approved-models", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function listProjectModelAssignments(
  projectId: string
): Promise<ModelAssignmentsApiResult<ProjectModelAssignmentListResponse>> {
  return requestModelAssignmentsApi<ProjectModelAssignmentListResponse>(
    `/projects/${projectId}/model-assignments`,
    {
      queryKey: queryKeys.projects.modelAssignments(projectId)
    }
  );
}

export async function createProjectModelAssignment(
  projectId: string,
  payload: CreateProjectModelAssignmentRequest
): Promise<ModelAssignmentsApiResult<ProjectModelAssignment>> {
  return requestModelAssignmentsApi<ProjectModelAssignment>(
    `/projects/${projectId}/model-assignments`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function getProjectModelAssignment(
  projectId: string,
  assignmentId: string
): Promise<ModelAssignmentsApiResult<ProjectModelAssignment>> {
  return requestModelAssignmentsApi<ProjectModelAssignment>(
    `/projects/${projectId}/model-assignments/${assignmentId}`,
    {
      queryKey: queryKeys.projects.modelAssignmentDetail(projectId, assignmentId)
    }
  );
}

export async function listProjectModelAssignmentDatasets(
  projectId: string,
  assignmentId: string
): Promise<ModelAssignmentsApiResult<TrainingDatasetListResponse>> {
  return requestModelAssignmentsApi<TrainingDatasetListResponse>(
    `/projects/${projectId}/model-assignments/${assignmentId}/datasets`,
    {
      queryKey: queryKeys.projects.modelAssignmentDatasets(
        projectId,
        assignmentId
      )
    }
  );
}

export async function activateProjectModelAssignment(
  projectId: string,
  assignmentId: string
): Promise<ModelAssignmentsApiResult<ProjectModelAssignment>> {
  return requestModelAssignmentsApi<ProjectModelAssignment>(
    `/projects/${projectId}/model-assignments/${assignmentId}/activate`,
    {
      method: "POST"
    }
  );
}

export async function retireProjectModelAssignment(
  projectId: string,
  assignmentId: string
): Promise<ModelAssignmentsApiResult<ProjectModelAssignment>> {
  return requestModelAssignmentsApi<ProjectModelAssignment>(
    `/projects/${projectId}/model-assignments/${assignmentId}/retire`,
    {
      method: "POST"
    }
  );
}
