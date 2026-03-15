import Link from "next/link";
import { redirect } from "next/navigation";
import type {
  ProjectRole,
  ProjectSearchHit,
  SessionResponse
} from "@ukde/contracts";

import { InlineAlert, SectionState, StatusChip } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../lib/auth/session";
import { getProjectWorkspace } from "../../../../../lib/projects";
import { buildWorkspacePathFromSearchHit, getProjectSearch } from "../../../../../lib/search";
import {
  buildSearchReturnQuery,
  buildSearchSnippetPreview,
  describeSearchHitProvenance,
  groupSearchHitsByDocument,
  parseOptionalInt,
  parseOptionalText
} from "../../../../../lib/search-ui";
import { projectOverviewPath, projectSearchPath } from "../../../../../lib/routes";

export const dynamic = "force-dynamic";

function canUseProjectSearch(
  session: SessionResponse,
  projectRole: ProjectRole | null | undefined
): boolean {
  const platformRoles = new Set(session.user.platformRoles);
  if (platformRoles.has("ADMIN")) {
    return true;
  }
  if (platformRoles.has("AUDITOR")) {
    return false;
  }
  return (
    projectRole === "PROJECT_LEAD" ||
    projectRole === "RESEARCHER" ||
    projectRole === "REVIEWER"
  );
}

function renderSnippet(
  hit: ProjectSearchHit,
  queryText: string
) {
  const preview = buildSearchSnippetPreview(hit, queryText);

  return (
    <p className="projectSearchSnippet">
      {preview.prefixEllipsis ? <span className="projectSearchEllipsis">…</span> : null}
      {preview.segments.map((segment, index) =>
        segment.highlighted ? (
          <mark className="projectSearchSnippetMark" key={`seg-mark-${index}`}>
            {segment.text}
          </mark>
        ) : (
          <span key={`seg-text-${index}`}>{segment.text}</span>
        )
      )}
      {preview.suffixEllipsis ? <span className="projectSearchEllipsis">…</span> : null}
    </p>
  );
}

export default async function ProjectSearchPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{
    cursor?: string;
    documentId?: string;
    pageNumber?: string;
    q?: string;
    selectedHit?: string;
    runId?: string;
    status?: string;
  }>;
}>) {
  const { projectId } = await params;
  const query = await searchParams;
  const q = parseOptionalText(query.q);
  const documentId = parseOptionalText(query.documentId);
  const runId = parseOptionalText(query.runId);
  const pageNumberRaw = parseOptionalInt(query.pageNumber);
  const pageNumber =
    typeof pageNumberRaw === "number" && pageNumberRaw > 0
      ? pageNumberRaw
      : undefined;
  const cursorRaw = parseOptionalInt(query.cursor);
  const cursor =
    typeof cursorRaw === "number" && cursorRaw > 0
      ? cursorRaw
      : 0;
  const selectedHitId = parseOptionalText(query.selectedHit);

  const [session, workspaceResult] = await Promise.all([
    requireCurrentSession(),
    getProjectWorkspace(projectId)
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=member-route");
  }
  if (!canUseProjectSearch(session, workspaceResult.data.currentUserRole)) {
    redirect(projectOverviewPath(projectId));
  }

  const searchResult = q
    ? await getProjectSearch(projectId, {
        cursor,
        documentId,
        limit: 25,
        pageNumber,
        q,
        runId
      })
    : null;

  const openFailed = query.status === "open-failed";
  const activeFilterLabels = [
    documentId ? `Document ${documentId}` : null,
    runId ? `Run ${runId}` : null,
    typeof pageNumber === "number" ? `Page ${pageNumber}` : null
  ].filter((item): item is string => Boolean(item));
  const clearFiltersHref = `${projectSearchPath(projectId)}?${buildSearchReturnQuery({ q })}`;
  const nextCursor =
    searchResult?.ok && searchResult.data
      ? searchResult.data.nextCursor
      : null;
  const groupedResults =
    searchResult?.ok && searchResult.data
      ? groupSearchHitsByDocument(searchResult.data.items)
      : [];
  const firstPageHref = `${projectSearchPath(projectId)}?${buildSearchReturnQuery({
    documentId,
    pageNumber,
    q,
    runId
  })}`;
  const nextPageHref =
    typeof nextCursor === "number"
      ? `${projectSearchPath(projectId)}?${buildSearchReturnQuery({
          cursor: nextCursor,
          documentId,
          pageNumber,
          q,
          runId
        })}`
      : null;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel projectSearchIntro">
        <p className="ukde-eyebrow">Controlled search</p>
        <h2>Project full-text search</h2>
        <p className="ukde-muted">
          Search the active project search index and jump to exact transcription context with
          token or fallback provenance preserved.
        </p>
        {q ? (
          <Link className="projectSearchSkipLink" href="#project-search-results">
            Skip to results
          </Link>
        ) : null}
      </section>

      {openFailed ? (
        <InlineAlert title="Could not open result" tone="danger">
          Result-open request failed. Try running the search again.
        </InlineAlert>
      ) : null}

      <section className="sectionCard ukde-panel projectSearchQueryCard">
        <h3 id="project-search-query-title">Query and filters</h3>
        <form action="" aria-labelledby="project-search-query-title" className="projectSearchQueryForm" method="get">
          <label className="documentsFilterField" htmlFor="project-search-q">
            Query text
            <input
              className="projectInput"
              defaultValue={q ?? ""}
              id="project-search-q"
              name="q"
              required
              type="text"
            />
          </label>
          <label className="documentsFilterField" htmlFor="project-search-document">
            Document ID (optional)
            <input
              className="projectInput"
              defaultValue={documentId ?? ""}
              id="project-search-document"
              name="documentId"
              type="text"
            />
          </label>
          <label className="documentsFilterField" htmlFor="project-search-run">
            Run ID (optional)
            <input
              className="projectInput"
              defaultValue={runId ?? ""}
              id="project-search-run"
              name="runId"
              type="text"
            />
          </label>
          <label className="documentsFilterField" htmlFor="project-search-page">
            Page number (optional)
            <input
              className="projectInput"
              defaultValue={pageNumber ?? ""}
              id="project-search-page"
              min={1}
              name="pageNumber"
              type="number"
            />
          </label>
          <div className="projectSearchFormActions">
            <button className="projectPrimaryButton" type="submit">
              Search
            </button>
            {activeFilterLabels.length > 0 && q ? (
              <Link className="projectSecondaryButton" href={clearFiltersHref}>
                Clear filters
              </Link>
            ) : null}
            <Link className="projectSecondaryButton" href={projectSearchPath(projectId)}>
              Clear all
            </Link>
          </div>
        </form>
        {activeFilterLabels.length > 0 ? (
          <div className="projectSearchActiveFilters" aria-live="polite">
            {activeFilterLabels.map((label) => (
              <StatusChip key={label} tone="info">
                {label}
              </StatusChip>
            ))}
          </div>
        ) : null}
      </section>

      {!q ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="zero"
            title="Start an exact project search"
            description="Enter a query and optional filters to search the currently active index generation."
          />
        </section>
      ) : !searchResult?.ok || !searchResult.data ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Search unavailable"
            description={
              searchResult?.detail ??
              "Search request failed. Retry with the same query or adjust filters."
            }
          />
        </section>
      ) : searchResult.data.items.length === 0 ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="no-results"
            title="No matching hits"
            description="No hits were found in the active index for this query/filter set."
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel projectSearchResultsCard" id="project-search-results">
          <div className="projectSearchResultsHeader">
            <div>
              <h3>Results</h3>
              <p className="ukde-muted">
                Active index: <strong>{searchResult.data.searchIndexId}</strong>
              </p>
            </div>
            <StatusChip tone="neutral">
              {searchResult.data.items.length} hit{searchResult.data.items.length === 1 ? "" : "s"}
            </StatusChip>
          </div>
          <p className="projectSearchKeyboardHint ukde-muted">
            Tab to an <strong>Open</strong> link and press Enter to jump into transcription workspace.
          </p>

          <div className="projectSearchResultGroups" role="list">
            {groupedResults.map((group) => (
              <section className="projectSearchResultGroup" key={group.documentId} role="listitem">
                <header className="projectSearchGroupHeader">
                  <h4>{group.documentId}</h4>
                  <StatusChip tone="info">
                    {group.items.length} hit{group.items.length === 1 ? "" : "s"}
                  </StatusChip>
                </header>
                <ol className="projectSearchCardList">
                  {group.items.map((item) => {
                    const highlighted = selectedHitId === item.searchDocumentId;
                    const openHref = buildWorkspacePathFromSearchHit(projectId, item);
                    return (
                      <li key={item.searchDocumentId}>
                        <article
                          className={`projectSearchResultCard${highlighted ? " is-selected" : ""}`}
                          data-source-kind={item.sourceKind}
                        >
                          <div className="projectSearchCardMeta">
                            <StatusChip tone="neutral">Page {item.pageNumber}</StatusChip>
                            <StatusChip tone="neutral">Run {item.runId}</StatusChip>
                            {item.lineId ? <StatusChip tone="info">Line {item.lineId}</StatusChip> : null}
                            {item.tokenId ? <StatusChip tone="success">Token {item.tokenId}</StatusChip> : null}
                            <StatusChip tone="warning">
                              {item.sourceKind}:{item.sourceRefId}
                            </StatusChip>
                          </div>
                          {renderSnippet(item, q)}
                          <p className="projectSearchProvenance ukde-muted">
                            {describeSearchHitProvenance(item)}
                          </p>
                          <a
                            aria-label={`Open hit in workspace for document ${item.documentId} page ${item.pageNumber}`}
                            className="projectSecondaryButton"
                            href={openHref}
                          >
                            Open
                          </a>
                        </article>
                      </li>
                    );
                  })}
                </ol>
              </section>
            ))}
          </div>

          <div className="projectSearchPagination">
            {cursor > 0 ? (
              <Link className="projectSecondaryButton" href={firstPageHref}>
                First page
              </Link>
            ) : null}
            {nextPageHref ? (
              <Link className="projectSecondaryButton" href={nextPageHref}>
                Next page
              </Link>
            ) : null}
          </div>
        </section>
      )}
    </main>
  );
}
