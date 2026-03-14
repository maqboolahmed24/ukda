import { redirect } from "next/navigation";
import type {
  DocumentListSort,
  DocumentStatus,
  SortDirection
} from "@ukde/contracts";
import { SectionState } from "@ukde/ui/primitives";

import {
  ProjectDocumentsLibrary,
  type ProjectDocumentsLibraryFilters
} from "../../../../../components/project-documents-library";
import { listProjectDocuments } from "../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../lib/projects";
import { projectDocumentsPath, withQuery } from "../../../../../lib/routes";
import {
  normalizeCursorParam,
  normalizeOptionalDateParam,
  normalizeOptionalEnumParam,
  normalizeOptionalTextParam
} from "../../../../../lib/url-state";

const DOCUMENT_SORT_OPTIONS: DocumentListSort[] = ["updated", "created", "name"];
const DOCUMENT_DIRECTION_OPTIONS: SortDirection[] = ["asc", "desc"];
const DOCUMENT_STATUS_OPTIONS: DocumentStatus[] = [
  "UPLOADING",
  "QUEUED",
  "SCANNING",
  "EXTRACTING",
  "READY",
  "FAILED",
  "CANCELED"
];

export const dynamic = "force-dynamic";

interface RawDocumentSearchParams {
  cursor?: string;
  direction?: string;
  from?: string;
  q?: string;
  search?: string;
  sort?: string;
  status?: string;
  to?: string;
  uploader?: string;
}

function hasActiveLibraryFilters(filters: ProjectDocumentsLibraryFilters): boolean {
  return Boolean(filters.search || filters.status || filters.uploader || filters.from || filters.to);
}

export default async function ProjectDocumentsPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<RawDocumentSearchParams>;
}>) {
  const { projectId } = await params;
  const rawQuery = await searchParams;

  const searchFilter = normalizeOptionalTextParam(rawQuery.search ?? rawQuery.q);
  const statusFilter = normalizeOptionalEnumParam(
    rawQuery.status,
    DOCUMENT_STATUS_OPTIONS
  );
  const uploaderFilter = normalizeOptionalTextParam(rawQuery.uploader);
  const fromFilter = normalizeOptionalDateParam(rawQuery.from);
  const toFilter = normalizeOptionalDateParam(rawQuery.to);
  const sortFilter = normalizeOptionalEnumParam(rawQuery.sort, DOCUMENT_SORT_OPTIONS);
  const directionFilter = normalizeOptionalEnumParam(
    rawQuery.direction,
    DOCUMENT_DIRECTION_OPTIONS
  );
  const cursor = normalizeCursorParam(rawQuery.cursor);

  const invalidDateRange = Boolean(fromFilter && toFilter && fromFilter > toFilter);
  const effectiveToFilter = invalidDateRange ? undefined : toFilter;

  const queryWasInvalid =
    typeof rawQuery.q === "string" ||
    (typeof rawQuery.search === "string" &&
      rawQuery.search !== (searchFilter ?? "")) ||
    (typeof rawQuery.status === "string" && !statusFilter) ||
    (typeof rawQuery.uploader === "string" &&
      rawQuery.uploader !== (uploaderFilter ?? "")) ||
    (typeof rawQuery.from === "string" && !fromFilter) ||
    (typeof rawQuery.to === "string" && !toFilter) ||
    invalidDateRange ||
    (typeof rawQuery.sort === "string" && !sortFilter) ||
    (typeof rawQuery.direction === "string" && !directionFilter) ||
    (typeof rawQuery.cursor === "string" && rawQuery.cursor !== String(cursor));

  const effectiveFilters: ProjectDocumentsLibraryFilters = {
    search: searchFilter,
    status: statusFilter,
    uploader: uploaderFilter,
    from: fromFilter,
    to: effectiveToFilter,
    sort: sortFilter ?? "updated",
    direction: directionFilter ?? "desc",
    cursor: cursor > 0 ? cursor : 0
  };

  if (queryWasInvalid) {
    redirect(
      withQuery(projectDocumentsPath(projectId), {
        search: effectiveFilters.search,
        status: effectiveFilters.status,
        uploader: effectiveFilters.uploader,
        from: effectiveFilters.from,
        to: effectiveFilters.to,
        sort: effectiveFilters.sort,
        direction: effectiveFilters.direction,
        cursor: effectiveFilters.cursor > 0 ? effectiveFilters.cursor : undefined
      })
    );
  }

  const [documentsResult, workspaceResult] = await Promise.all([
    listProjectDocuments(projectId, {
      search: effectiveFilters.search,
      status: effectiveFilters.status,
      uploader: effectiveFilters.uploader,
      from: effectiveFilters.from,
      to: effectiveFilters.to,
      sort: effectiveFilters.sort,
      direction: effectiveFilters.direction,
      cursor: effectiveFilters.cursor,
      pageSize: 50
    }),
    getProjectWorkspace(projectId)
  ]);

  const documents =
    documentsResult.ok && documentsResult.data ? documentsResult.data.items : [];
  const nextCursor =
    documentsResult.ok && documentsResult.data
      ? documentsResult.data.nextCursor
      : null;
  const emptyState = hasActiveLibraryFilters(effectiveFilters) ? "no-results" : "zero";
  const currentUserRole =
    workspaceResult.ok && workspaceResult.data
      ? workspaceResult.data.currentUserRole
      : null;

  return (
    <main className="homeLayout">
      {!documentsResult.ok ? (
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Document library unavailable"
          description={
            documentsResult.detail ??
            "Document rows could not be loaded for this project."
          }
        />
      ) : (
        <ProjectDocumentsLibrary
          currentUserRole={currentUserRole}
          documents={documents}
          emptyState={emptyState}
          filters={effectiveFilters}
          nextCursor={nextCursor}
          projectId={projectId}
        />
      )}
    </main>
  );
}
