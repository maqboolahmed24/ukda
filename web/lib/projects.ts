import type {
  AddProjectMemberRequest,
  ChangeProjectMemberRoleRequest,
  CreateProjectRequest,
  ProjectListResponse,
  ProjectMember,
  ProjectMembersResponse,
  ProjectSummary,
  ProjectRole
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryCacheClass } from "./data/cache-policy";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type ProjectApiResult<T> = ApiResult<T>;

async function requestProjectApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    cacheClass?: QueryCacheClass;
    expectNoContent?: boolean;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<ProjectApiResult<T>> {
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

export async function listMyProjects(): Promise<ProjectSummary[]> {
  const response = await requestProjectApi<ProjectListResponse>("/projects", {
    queryKey: queryKeys.projects.list()
  });
  if (!response.ok || !response.data) {
    return [];
  }
  return response.data.items;
}

export async function createProject(
  payload: CreateProjectRequest
): Promise<ProjectApiResult<ProjectSummary>> {
  return requestProjectApi<ProjectSummary>("/projects", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      name: payload.name,
      purpose: payload.purpose,
      intended_access_tier: payload.intendedAccessTier
    })
  });
}

export async function getProjectSummary(
  projectId: string
): Promise<ProjectApiResult<ProjectSummary>> {
  return requestProjectApi<ProjectSummary>(`/projects/${projectId}`, {
    queryKey: queryKeys.projects.detail(projectId)
  });
}

export async function getProjectWorkspace(
  projectId: string
): Promise<ProjectApiResult<ProjectSummary>> {
  return requestProjectApi<ProjectSummary>(`/projects/${projectId}/workspace`, {
    queryKey: queryKeys.projects.workspace(projectId)
  });
}

export async function getProjectMembers(
  projectId: string
): Promise<ProjectApiResult<ProjectMembersResponse>> {
  return requestProjectApi<ProjectMembersResponse>(`/projects/${projectId}/members`, {
    queryKey: queryKeys.projects.members(projectId)
  });
}

export async function addProjectMember(
  projectId: string,
  payload: AddProjectMemberRequest
): Promise<ProjectApiResult<ProjectMember>> {
  return requestProjectApi<ProjectMember>(`/projects/${projectId}/members`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      member_email: payload.memberEmail,
      role: payload.role
    })
  });
}

export async function changeProjectMemberRole(
  projectId: string,
  memberUserId: string,
  payload: ChangeProjectMemberRoleRequest
): Promise<ProjectApiResult<ProjectMember>> {
  return requestProjectApi<ProjectMember>(
    `/projects/${projectId}/members/${memberUserId}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ role: payload.role })
    }
  );
}

export async function removeProjectMember(
  projectId: string,
  memberUserId: string
): Promise<ProjectApiResult<void>> {
  return requestProjectApi<void>(`/projects/${projectId}/members/${memberUserId}`, {
    method: "DELETE",
    expectNoContent: true
  });
}

export const projectRoleOptions: ProjectRole[] = [
  "PROJECT_LEAD",
  "RESEARCHER",
  "REVIEWER"
];
