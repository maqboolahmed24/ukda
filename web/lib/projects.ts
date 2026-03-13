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

import { resolveApiOrigins } from "./bootstrap-content";
import { readSessionToken } from "./auth/session";
import { buildApiTraceHeaders, logServerDiagnostic } from "./telemetry";

export interface ProjectApiResult<T> {
  ok: boolean;
  status: number;
  data?: T;
  detail?: string;
}

async function requestProjectApi<T>(
  path: string,
  init?: RequestInit
): Promise<ProjectApiResult<T>> {
  const token = await readSessionToken();
  if (!token) {
    return {
      ok: false,
      status: 401,
      detail: "Authentication is required."
    };
  }

  const { internalOrigin } = resolveApiOrigins();
  const traceHeaders = await buildApiTraceHeaders();
  let response: Response;
  try {
    response = await fetch(`${internalOrigin}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${token}`,
        ...traceHeaders,
        ...(init?.headers ?? {})
      }
    });
  } catch (error) {
    logServerDiagnostic("project_api_fetch_failed", {
      path,
      method: init?.method ?? "GET",
      errorClass: error instanceof Error ? error.name : "unknown"
    });
    return {
      ok: false,
      status: 503,
      detail: "Project API is unavailable."
    };
  }

  if (response.status === 204) {
    return {
      ok: true,
      status: response.status
    };
  }

  let parsed: unknown;
  try {
    parsed = await response.json();
  } catch {
    parsed = undefined;
  }

  if (!response.ok) {
    const detail =
      typeof parsed === "object" &&
      parsed !== null &&
      "detail" in parsed &&
      typeof parsed.detail === "string"
        ? parsed.detail
        : "Request failed.";
    return {
      ok: false,
      status: response.status,
      detail
    };
  }

  if (response.status >= 500) {
    logServerDiagnostic("project_api_server_error", {
      path,
      method: init?.method ?? "GET",
      status: response.status
    });
  }

  return {
    ok: true,
    status: response.status,
    data: parsed as T
  };
}

export async function listMyProjects(): Promise<ProjectSummary[]> {
  const response = await requestProjectApi<ProjectListResponse>("/projects");
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
  return requestProjectApi<ProjectSummary>(`/projects/${projectId}`);
}

export async function getProjectWorkspace(
  projectId: string
): Promise<ProjectApiResult<ProjectSummary>> {
  return requestProjectApi<ProjectSummary>(`/projects/${projectId}/workspace`);
}

export async function getProjectMembers(
  projectId: string
): Promise<ProjectApiResult<ProjectMembersResponse>> {
  return requestProjectApi<ProjectMembersResponse>(
    `/projects/${projectId}/members`
  );
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
  return requestProjectApi<void>(
    `/projects/${projectId}/members/${memberUserId}`,
    {
      method: "DELETE"
    }
  );
}

export const projectRoleOptions: ProjectRole[] = [
  "PROJECT_LEAD",
  "RESEARCHER",
  "REVIEWER"
];
