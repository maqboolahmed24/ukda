import type {
  AdminIncident,
  AdminIncidentListResponse,
  AdminIncidentStatusResponse,
  AdminIncidentTimelineResponse,
  AdminRunbook,
  AdminRunbookContentResponse,
  AdminRunbookListResponse
} from "@ukde/contracts";

import { type ApiResult, requestServerApi } from "./data/api-client";
import type { QueryKey } from "./data/query-keys";
import { queryKeys } from "./data/query-keys";

export type LaunchOperationsApiResult<T> = ApiResult<T>;

async function requestLaunchOperationsApi<T>(
  path: string,
  options?: {
    body?: BodyInit | null;
    headers?: HeadersInit;
    method?: string;
    queryKey?: QueryKey;
  }
): Promise<LaunchOperationsApiResult<T>> {
  return requestServerApi<T>({
    path,
    method: options?.method,
    headers: options?.headers,
    body: options?.body,
    cacheClass: "operations-live",
    queryKey: options?.queryKey
  });
}

export async function listAdminRunbooks(): Promise<
  LaunchOperationsApiResult<AdminRunbookListResponse>
> {
  return requestLaunchOperationsApi<AdminRunbookListResponse>("/admin/runbooks", {
    queryKey: queryKeys.admin.runbooks()
  });
}

export async function getAdminRunbook(
  runbookId: string
): Promise<LaunchOperationsApiResult<AdminRunbook>> {
  const encoded = encodeURIComponent(runbookId);
  return requestLaunchOperationsApi<AdminRunbook>(`/admin/runbooks/${encoded}`, {
    queryKey: queryKeys.admin.runbookDetail(runbookId)
  });
}

export async function getAdminRunbookContent(
  runbookId: string
): Promise<LaunchOperationsApiResult<AdminRunbookContentResponse>> {
  const encoded = encodeURIComponent(runbookId);
  return requestLaunchOperationsApi<AdminRunbookContentResponse>(
    `/admin/runbooks/${encoded}/content`,
    {
      queryKey: queryKeys.admin.runbookContent(runbookId)
    }
  );
}

export async function listAdminIncidents(): Promise<
  LaunchOperationsApiResult<AdminIncidentListResponse>
> {
  return requestLaunchOperationsApi<AdminIncidentListResponse>("/admin/incidents", {
    queryKey: queryKeys.admin.incidents()
  });
}

export async function getAdminIncidentStatus(): Promise<
  LaunchOperationsApiResult<AdminIncidentStatusResponse>
> {
  return requestLaunchOperationsApi<AdminIncidentStatusResponse>(
    "/admin/incidents/status",
    {
      queryKey: queryKeys.admin.incidentStatus()
    }
  );
}

export async function getAdminIncident(
  incidentId: string
): Promise<LaunchOperationsApiResult<AdminIncident>> {
  const encoded = encodeURIComponent(incidentId);
  return requestLaunchOperationsApi<AdminIncident>(`/admin/incidents/${encoded}`, {
    queryKey: queryKeys.admin.incidentDetail(incidentId)
  });
}

export async function getAdminIncidentTimeline(
  incidentId: string
): Promise<LaunchOperationsApiResult<AdminIncidentTimelineResponse>> {
  const encoded = encodeURIComponent(incidentId);
  return requestLaunchOperationsApi<AdminIncidentTimelineResponse>(
    `/admin/incidents/${encoded}/timeline`,
    {
      queryKey: queryKeys.admin.incidentTimeline(incidentId)
    }
  );
}
