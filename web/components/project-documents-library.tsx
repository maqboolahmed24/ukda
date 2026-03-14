"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  useTransition
} from "react";

import type {
  DocumentListSort,
  DocumentProcessingRunKind,
  DocumentProcessingRunStatus,
  DocumentTimelineResponse,
  DocumentStatus,
  ProjectDocument,
  ProjectDocumentPageListResponse,
  ProjectRole,
  SortDirection
} from "@ukde/contracts";
import { DataTable, DetailsDrawer, SectionState, StatusChip } from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";
import { projectDocumentPageImagePath } from "../lib/document-page-image";
import {
  projectDocumentIngestStatusPath,
  projectDocumentPath,
  projectDocumentsPath,
  withQuery
} from "../lib/routes";

const SEARCH_DEBOUNCE_MS = 280;
const DOCUMENT_PAGE_SIZE = 50;

const DOCUMENT_STATUS_TONES: Record<
  DocumentStatus,
  "danger" | "info" | "neutral" | "success" | "warning"
> = {
  UPLOADING: "warning",
  QUEUED: "warning",
  SCANNING: "warning",
  EXTRACTING: "warning",
  READY: "success",
  FAILED: "danger",
  CANCELED: "neutral"
};

const DOCUMENT_STATUS_OPTIONS: ReadonlyArray<DocumentStatus> = [
  "UPLOADING",
  "QUEUED",
  "SCANNING",
  "EXTRACTING",
  "READY",
  "FAILED",
  "CANCELED"
];

const DOCUMENT_SORT_OPTIONS: ReadonlyArray<DocumentListSort> = [
  "updated",
  "created",
  "name"
];

const DOCUMENT_DIRECTION_OPTIONS: ReadonlyArray<SortDirection> = ["desc", "asc"];

export interface ProjectDocumentsLibraryFilters {
  cursor: number;
  direction: SortDirection;
  from?: string;
  search?: string;
  sort: DocumentListSort;
  status?: DocumentStatus;
  to?: string;
  uploader?: string;
}

interface ProjectDocumentsLibraryProps {
  currentUserRole: ProjectRole | null;
  documents: ProjectDocument[];
  emptyState?: "no-results" | "zero";
  errorMessage?: string | null;
  filters: ProjectDocumentsLibraryFilters;
  nextCursor: number | null;
  projectId: string;
}

interface TimelineState {
  errorMessage: string | null;
  items: Array<{
    createdAt: string;
    failureReason: string | null;
    id: string;
    runKind: DocumentProcessingRunKind;
    startedAt: string | null;
    status: DocumentProcessingRunStatus;
  }>;
  phase: "idle" | "loading" | "ready" | "error";
}

interface ThumbnailPreviewState {
  errorMessage: string | null;
  imagePath: string | null;
  pageNumber: number | null;
  phase: "idle" | "loading" | "ready" | "error" | "empty";
}

function formatTimestamp(value: string): string {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return value;
  }
  return timestamp.toISOString();
}

function normalizeSearchValue(raw: string): string | undefined {
  const trimmed = raw.trim();
  return trimmed ? trimmed : undefined;
}

function normalizeOptionalInput(value: FormDataEntryValue | null): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

function resolveRunKindCopy(runKind: DocumentProcessingRunKind): string {
  switch (runKind) {
    case "UPLOAD":
      return "Upload";
    case "SCAN":
      return "Scan";
    case "EXTRACTION":
      return "Page extraction";
    case "THUMBNAIL_RENDER":
      return "Thumbnail rendering";
    default:
      return "Processing";
  }
}

function resolveRunStatusTone(
  status: DocumentProcessingRunStatus
): "danger" | "neutral" | "success" | "warning" {
  if (status === "SUCCEEDED") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "CANCELED") {
    return "neutral";
  }
  return "warning";
}

function toDocumentsLibraryHref(
  projectId: string,
  filters: ProjectDocumentsLibraryFilters
): string {
  return withQuery(projectDocumentsPath(projectId), {
    search: filters.search,
    status: filters.status,
    uploader: filters.uploader,
    from: filters.from,
    to: filters.to,
    sort: filters.sort,
    direction: filters.direction,
    cursor: filters.cursor > 0 ? filters.cursor : undefined
  });
}

export function ProjectDocumentsLibrary({
  currentUserRole,
  documents,
  emptyState = "zero",
  errorMessage = null,
  filters,
  nextCursor,
  projectId
}: ProjectDocumentsLibraryProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [searchText, setSearchText] = useState(filters.search ?? "");
  const deferredSearchText = useDeferredValue(searchText);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [multiSelectedDocumentIds, setMultiSelectedDocumentIds] = useState<string[]>([]);
  const [timelineState, setTimelineState] = useState<TimelineState>({
    phase: "idle",
    items: [],
    errorMessage: null
  });
  const [thumbnailPreviewState, setThumbnailPreviewState] =
    useState<ThumbnailPreviewState>({
      phase: "idle",
      imagePath: null,
      pageNumber: null,
      errorMessage: null
    });
  const [thumbnailPreviewFailed, setThumbnailPreviewFailed] = useState(false);
  const timelineRequestVersion = useRef(0);

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId]
  );

  const selectedForBulk = useMemo(
    () => documents.filter((document) => multiSelectedDocumentIds.includes(document.id)),
    [documents, multiSelectedDocumentIds]
  );

  const hasRows = documents.length > 0;
  const hasPreviousPage = filters.cursor > 0;
  const previousCursor = Math.max(filters.cursor - DOCUMENT_PAGE_SIZE, 0);
  const hasNextPage = typeof nextCursor === "number";
  const showMutationActionSlots =
    currentUserRole === "PROJECT_LEAD" || currentUserRole === "RESEARCHER";

  const activeFilterLabels = useMemo(() => {
    const labels: string[] = [];
    if (filters.search) {
      labels.push(`Search: "${filters.search}"`);
    }
    if (filters.status) {
      labels.push(`Status: ${filters.status}`);
    }
    if (filters.uploader) {
      labels.push(`Uploader: ${filters.uploader}`);
    }
    if (filters.from) {
      labels.push(`From: ${filters.from}`);
    }
    if (filters.to) {
      labels.push(`To: ${filters.to}`);
    }
    labels.push(
      `Sort: ${filters.sort === "name" ? "Name" : filters.sort === "created" ? "Date created" : "Date updated"} (${filters.direction.toUpperCase()})`
    );
    return labels;
  }, [filters.direction, filters.from, filters.search, filters.sort, filters.status, filters.to, filters.uploader]);

  useEffect(() => {
    setSearchText(filters.search ?? "");
  }, [filters.search]);

  useEffect(() => {
    const availableIds = new Set(documents.map((document) => document.id));
    setMultiSelectedDocumentIds((current) =>
      current.filter((documentId) => availableIds.has(documentId))
    );
    if (selectedDocumentId && !availableIds.has(selectedDocumentId)) {
      setSelectedDocumentId(null);
    }
  }, [documents, selectedDocumentId]);

  useEffect(() => {
    const normalizedDeferredSearch = normalizeSearchValue(deferredSearchText);
    if ((normalizedDeferredSearch ?? "") === (filters.search ?? "")) {
      return;
    }
    const timer = window.setTimeout(() => {
      startTransition(() => {
        router.replace(
          toDocumentsLibraryHref(projectId, {
            ...filters,
            search: normalizedDeferredSearch,
            cursor: 0
          }),
          { scroll: false }
        );
      });
    }, SEARCH_DEBOUNCE_MS);

    return () => window.clearTimeout(timer);
  }, [deferredSearchText, filters, projectId, router, startTransition]);

  useEffect(() => {
    if (!selectedDocumentId) {
      setTimelineState({
        phase: "idle",
        items: [],
        errorMessage: null
      });
      setThumbnailPreviewState({
        phase: "idle",
        imagePath: null,
        pageNumber: null,
        errorMessage: null
      });
      setThumbnailPreviewFailed(false);
      return;
    }

    const requestVersion = timelineRequestVersion.current + 1;
    timelineRequestVersion.current = requestVersion;
    setTimelineState({
      phase: "loading",
      items: [],
      errorMessage: null
    });
    setThumbnailPreviewState({
      phase: "loading",
      imagePath: null,
      pageNumber: null,
      errorMessage: null
    });
    setThumbnailPreviewFailed(false);

    void Promise.all([
      requestBrowserApi<DocumentTimelineResponse>({
        method: "GET",
        path: `/projects/${projectId}/documents/${selectedDocumentId}/timeline`,
        cacheClass: "operations-live"
      }),
      requestBrowserApi<ProjectDocumentPageListResponse>({
        method: "GET",
        path: `/projects/${projectId}/documents/${selectedDocumentId}/pages`,
        cacheClass: "operations-live"
      })
    ])
      .then(([timelineResult, pagesResult]) => {
        if (timelineRequestVersion.current !== requestVersion) {
          return;
        }

        if (!timelineResult.ok || !timelineResult.data) {
          setTimelineState({
            phase: "error",
            items: [],
            errorMessage:
              timelineResult.detail ??
              "Timeline events could not be loaded for this document."
          });
        } else {
          setTimelineState({
            phase: "ready",
            items: timelineResult.data.items.map((item) => ({
              id: item.id,
              runKind: item.runKind,
              status: item.status,
              failureReason: item.failureReason,
              startedAt: item.startedAt,
              createdAt: item.createdAt
            })),
            errorMessage: null
          });
        }

        if (!pagesResult.ok || !pagesResult.data) {
          setThumbnailPreviewState({
            phase: "error",
            imagePath: null,
            pageNumber: null,
            errorMessage:
              pagesResult.detail ??
              "Thumbnail preview could not be loaded for this document."
          });
          return;
        }

        const readyPage = pagesResult.data.items.find((page) => page.status === "READY");
        if (!readyPage) {
          setThumbnailPreviewState({
            phase: "empty",
            imagePath: null,
            pageNumber: null,
            errorMessage: null
          });
          return;
        }

        setThumbnailPreviewState({
          phase: "ready",
          imagePath: projectDocumentPageImagePath(
            projectId,
            selectedDocumentId,
            readyPage.id,
            "thumb"
          ),
          pageNumber: readyPage.pageIndex + 1,
          errorMessage: null
        });
      })
      .catch(() => {
        if (timelineRequestVersion.current !== requestVersion) {
          return;
        }
        setTimelineState({
          phase: "error",
          items: [],
          errorMessage: "Timeline events could not be loaded for this document."
        });
        setThumbnailPreviewState({
          phase: "error",
          imagePath: null,
          pageNumber: null,
          errorMessage: "Thumbnail preview could not be loaded for this document."
        });
      });
  }, [projectId, selectedDocumentId]);

  const navigateWithFilters = (
    nextFilters: ProjectDocumentsLibraryFilters,
    mode: "push" | "replace" = "push"
  ) => {
    startTransition(() => {
      const href = toDocumentsLibraryHref(projectId, nextFilters);
      if (mode === "replace") {
        router.replace(href, { scroll: false });
      } else {
        router.push(href, { scroll: false });
      }
    });
  };

  const toggleBulkSelection = (documentId: string, checked: boolean) => {
    setMultiSelectedDocumentIds((current) => {
      if (checked) {
        if (current.includes(documentId)) {
          return current;
        }
        return [...current, documentId];
      }
      return current.filter((candidate) => candidate !== documentId);
    });
  };

  return (
    <>
      <section className="sectionCard ukde-panel">
        <p className="ukde-muted">
          Controlled ingest inventory. Original bytes remain inside the secure
          environment and are never exposed through raw-download links.
        </p>
      </section>

      <section className="sectionCard ukde-panel" aria-labelledby="documents-filter-title">
        <h2 id="documents-filter-title">Search and filters</h2>
        <form
          className="documentsFilterBar"
          onSubmit={(event) => {
            event.preventDefault();
            const formData = new FormData(event.currentTarget);
            const nextStatus = normalizeOptionalInput(formData.get("status"));
            const nextSort = normalizeOptionalInput(formData.get("sort"));
            const nextDirection = normalizeOptionalInput(formData.get("direction"));
            const nextFilters: ProjectDocumentsLibraryFilters = {
              search: normalizeSearchValue(searchText),
              status: DOCUMENT_STATUS_OPTIONS.includes(nextStatus as DocumentStatus)
                ? (nextStatus as DocumentStatus)
                : undefined,
              uploader: normalizeOptionalInput(formData.get("uploader")),
              from: normalizeOptionalInput(formData.get("from")),
              to: normalizeOptionalInput(formData.get("to")),
              sort: DOCUMENT_SORT_OPTIONS.includes(nextSort as DocumentListSort)
                ? (nextSort as DocumentListSort)
                : "updated",
              direction: DOCUMENT_DIRECTION_OPTIONS.includes(nextDirection as SortDirection)
                ? (nextDirection as SortDirection)
                : "desc",
              cursor: 0
            };
            navigateWithFilters(nextFilters);
          }}
        >
          <div className="documentsFilterField">
            <label htmlFor="documents-search">Search</label>
            <input
              className="ukde-field"
              id="documents-search"
              name="search"
              onChange={(event) => {
                setSearchText(event.target.value);
              }}
              placeholder="Find by document name"
              value={searchText}
            />
          </div>

          <div className="documentsFilterField">
            <label htmlFor="documents-status">Status</label>
            <select
              className="ukde-select"
              defaultValue={filters.status ?? ""}
              id="documents-status"
              name="status"
            >
              <option value="">All statuses</option>
              {DOCUMENT_STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </div>

          <div className="documentsFilterField">
            <label htmlFor="documents-uploader">Uploader</label>
            <input
              className="ukde-field"
              defaultValue={filters.uploader ?? ""}
              id="documents-uploader"
              name="uploader"
              placeholder="Filter by uploader id"
            />
          </div>

          <div className="documentsFilterField">
            <label htmlFor="documents-from">From date</label>
            <input
              className="ukde-field"
              defaultValue={filters.from ?? ""}
              id="documents-from"
              name="from"
              type="date"
            />
          </div>

          <div className="documentsFilterField">
            <label htmlFor="documents-to">To date</label>
            <input
              className="ukde-field"
              defaultValue={filters.to ?? ""}
              id="documents-to"
              name="to"
              type="date"
            />
          </div>

          <div className="documentsFilterField">
            <label htmlFor="documents-sort">Sort</label>
            <select
              className="ukde-select"
              defaultValue={filters.sort}
              id="documents-sort"
              name="sort"
            >
              <option value="updated">Date updated</option>
              <option value="created">Date created</option>
              <option value="name">Name</option>
            </select>
          </div>

          <div className="documentsFilterField">
            <label htmlFor="documents-direction">Direction</label>
            <select
              className="ukde-select"
              defaultValue={filters.direction}
              id="documents-direction"
              name="direction"
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </div>

          <div className="documentsFilterField">
            <div className="documentsFilterActions">
              <button className="secondaryButton" disabled={isPending} type="submit">
                Apply filters
              </button>
              <button
                className="secondaryButton"
                disabled={isPending}
                onClick={() => {
                  setSearchText("");
                  navigateWithFilters(
                    {
                      search: undefined,
                      status: undefined,
                      uploader: undefined,
                      from: undefined,
                      to: undefined,
                      sort: "updated",
                      direction: "desc",
                      cursor: 0
                    },
                    "replace"
                  );
                }}
                type="button"
              >
                Reset
              </button>
            </div>
          </div>
        </form>

        <div className="documentsActiveFilters" aria-live="polite">
          {activeFilterLabels.map((label) => (
            <StatusChip key={label} tone="neutral">
              {label}
            </StatusChip>
          ))}
        </div>
      </section>

      {!hasRows && !errorMessage ? (
        <SectionState
          className="sectionCard ukde-panel"
          kind={emptyState}
          title={
            emptyState === "no-results"
              ? "No documents matched the current filters"
              : "No documents in this project yet"
          }
          description={
            emptyState === "no-results"
              ? "Adjust search text or filters to broaden this view."
              : "Import document is the only path to create new records in this library."
          }
        />
      ) : null}

      {multiSelectedDocumentIds.length > 0 ? (
        <section className="sectionCard ukde-panel" aria-live="polite">
          <div className="auditIntegrityRow">
            <strong>{multiSelectedDocumentIds.length} selected</strong>
            <div className="buttonRow">
              <button
                className="secondaryButton"
                onClick={() => setMultiSelectedDocumentIds([])}
                type="button"
              >
                Clear selection
              </button>
              {selectedForBulk[0] ? (
                <Link
                  className="secondaryButton"
                  href={projectDocumentPath(projectId, selectedForBulk[0].id)}
                >
                  Open first selected
                </Link>
              ) : null}
              {showMutationActionSlots ? (
                <button className="secondaryButton" disabled type="button">
                  Retry extraction (pending)
                </button>
              ) : null}
            </div>
          </div>
          <p className="ukde-muted">
            Bulk destructive mutations are intentionally deferred until stable server
            semantics are available.
          </p>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <DataTable
          caption="Project documents"
          columns={[
            {
              header: "Select",
              key: "select",
              renderCell: (row) => (
                <input
                  aria-label={`Select ${row.originalFilename}`}
                  checked={multiSelectedDocumentIds.includes(row.id)}
                  onChange={(event) => {
                    toggleBulkSelection(row.id, event.target.checked);
                  }}
                  onClick={(event) => {
                    event.stopPropagation();
                  }}
                  onKeyDown={(event) => {
                    event.stopPropagation();
                  }}
                  type="checkbox"
                />
              )
            },
            {
              header: "Name",
              key: "name",
              renderCell: (row) => row.originalFilename
            },
            {
              header: "Status",
              key: "status",
              renderCell: (row) => (
                <StatusChip tone={DOCUMENT_STATUS_TONES[row.status]}>
                  {row.status}
                </StatusChip>
              )
            },
            {
              header: "Pages",
              key: "pageCount",
              renderCell: (row) =>
                typeof row.pageCount === "number" ? String(row.pageCount) : "Pending"
            },
            {
              header: "Uploaded by",
              key: "createdBy",
              renderCell: (row) => row.createdBy
            },
            {
              header: "Date",
              key: "createdAt",
              renderCell: (row) => formatTimestamp(row.createdAt)
            }
          ]}
          emptyMessage="No documents are currently available for this view."
          emptyTitle="Document library empty"
          errorMessage={errorMessage}
          errorTitle="Document library unavailable"
          getRowId={(row) => row.id}
          onRowSelect={(row) => setSelectedDocumentId(row?.id ?? null)}
          pageSize={Math.max(documents.length, 1)}
          renderRowActions={(row) => (
            <Link className="ukde-link" href={projectDocumentPath(projectId, row.id)}>
              Open
            </Link>
          )}
          rows={documents}
        />
      </section>

      <section className="sectionCard ukde-panel">
        <div className="auditIntegrityRow">
          <span className="ukde-muted">
            Showing {documents.length} row{documents.length === 1 ? "" : "s"} from cursor{" "}
            {filters.cursor}
          </span>
          <div className="buttonRow">
            <button
              className="secondaryButton"
              disabled={!hasPreviousPage || isPending}
              onClick={() => {
                navigateWithFilters({ ...filters, cursor: previousCursor });
              }}
              type="button"
            >
              Previous page
            </button>
            <button
              className="secondaryButton"
              disabled={!hasNextPage || isPending}
              onClick={() => {
                if (typeof nextCursor !== "number") {
                  return;
                }
                navigateWithFilters({ ...filters, cursor: nextCursor });
              }}
              type="button"
            >
              Next page
            </button>
          </div>
        </div>
      </section>

      <DetailsDrawer
        description="Document metadata, timeline status, and next-step actions remain in project scope."
        onClose={() => setSelectedDocumentId(null)}
        open={Boolean(selectedDocument)}
        title="Document summary"
      >
        {selectedDocument ? (
          <>
            <div className="auditIntegrityRow">
              <StatusChip tone={DOCUMENT_STATUS_TONES[selectedDocument.status]}>
                {selectedDocument.status}
              </StatusChip>
            </div>
            <ul className="projectMetaList">
              <li>
                <span>Name</span>
                <strong>{selectedDocument.originalFilename}</strong>
              </li>
              <li>
                <span>Uploaded by</span>
                <strong>{selectedDocument.createdBy}</strong>
              </li>
              <li>
                <span>Created</span>
                <strong>{formatTimestamp(selectedDocument.createdAt)}</strong>
              </li>
              <li>
                <span>Updated</span>
                <strong>{formatTimestamp(selectedDocument.updatedAt)}</strong>
              </li>
              <li>
                <span>Pages</span>
                <strong>
                  {typeof selectedDocument.pageCount === "number"
                    ? selectedDocument.pageCount
                    : "Not extracted yet"}
                </strong>
              </li>
            </ul>

            <h3>Thumbnail preview</h3>
            {thumbnailPreviewState.phase === "loading" ? (
              <SectionState
                kind="loading"
                title="Loading thumbnail preview"
                description="Preview bytes are being loaded from the authenticated page-image route."
              />
            ) : thumbnailPreviewState.phase === "error" ? (
              <SectionState
                kind="degraded"
                title="Thumbnail preview unavailable"
                description={
                  thumbnailPreviewState.errorMessage ??
                  "Thumbnail preview could not be loaded for this document."
                }
              />
            ) : thumbnailPreviewState.phase === "empty" ? (
              <SectionState
                kind="empty"
                title="No thumbnail preview yet"
                description="Thumbnail preview becomes available after page extraction and rendering complete."
              />
            ) : thumbnailPreviewState.imagePath && !thumbnailPreviewFailed ? (
              <figure className="documentLibraryThumbnailPreview">
                <img
                  alt={`Thumbnail preview for page ${thumbnailPreviewState.pageNumber ?? "?"}`}
                  className="documentLibraryThumbnailImage"
                  onError={() => setThumbnailPreviewFailed(true)}
                  onLoad={() => setThumbnailPreviewFailed(false)}
                  src={thumbnailPreviewState.imagePath}
                />
                <figcaption>
                  Page {thumbnailPreviewState.pageNumber} via authenticated same-origin asset proxy.
                </figcaption>
              </figure>
            ) : (
              <SectionState
                kind="error"
                title="Thumbnail preview failed to render"
                description="Image delivery failed or your session may have expired. Refresh this route to re-authenticate and retry."
              />
            )}

            <h3>Processing timeline</h3>
            {timelineState.phase === "loading" ? (
              <SectionState
                kind="loading"
                title="Loading timeline"
                description="Processing runs are being loaded for this document."
              />
            ) : timelineState.phase === "error" ? (
              <SectionState
                kind="degraded"
                title="Timeline unavailable"
                description={
                  timelineState.errorMessage ??
                  "Processing runs could not be loaded for this document."
                }
              />
            ) : timelineState.items.length === 0 ? (
              <SectionState
                kind="empty"
                title="No processing runs yet"
                description="Timeline entries will appear after ingest attempts are recorded."
              />
            ) : (
              <ol className="timelineList">
                {timelineState.items.map((event) => (
                  <li key={event.id}>
                    <div className="auditIntegrityRow">
                      <StatusChip tone={resolveRunStatusTone(event.status)}>
                        {resolveRunKindCopy(event.runKind)}
                      </StatusChip>
                      <span className="ukde-muted">
                        {formatTimestamp(event.startedAt ?? event.createdAt)}
                      </span>
                    </div>
                    <p className="ukde-muted">Status: {event.status}</p>
                    {event.failureReason ? (
                      <p className="ukde-muted">{event.failureReason}</p>
                    ) : null}
                  </li>
                ))}
              </ol>
            )}

            <div className="buttonRow">
              <Link
                className="secondaryButton"
                href={projectDocumentPath(projectId, selectedDocument.id)}
              >
                Open document
              </Link>
              <Link
                className="secondaryButton"
                href={projectDocumentIngestStatusPath(
                  projectId,
                  selectedDocument.id,
                  {
                    page: thumbnailPreviewState.pageNumber ?? undefined
                  }
                )}
              >
                View ingest status
              </Link>
            </div>
          </>
        ) : null}
      </DetailsDrawer>
    </>
  );
}
