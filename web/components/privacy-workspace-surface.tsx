"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  DocumentRedactionFinding,
  DocumentRedactionPageReview,
  DocumentRedactionPreviewStatusResponse,
  DocumentRedactionRunPage,
  DocumentRedactionTimelineEvent,
  DocumentTranscriptionLineResult
} from "@ukde/contracts";
import {
  ModalDialog,
  SectionState,
  StatusChip,
  Toolbar
} from "@ukde/ui/primitives";

import {
  projectDocumentPrivacyPreviewPath,
  projectDocumentPrivacyWorkspacePath
} from "../lib/routes";

type PrivacyWorkspaceMode = "controlled" | "safeguarded";
type FindingDecisionMutationStatus =
  | "APPROVED"
  | "OVERRIDDEN"
  | "FALSE_POSITIVE";

type WorkspaceServerAction = (formData: FormData) => void | Promise<void>;

interface PrivacyWorkspaceSurfaceProps {
  canMutate: boolean;
  documentId: string;
  lineLoadError: string | null;
  lines: DocumentTranscriptionLineResult[];
  mode: PrivacyWorkspaceMode;
  nextUnresolvedHref: string | null;
  pageEvents: DocumentRedactionTimelineEvent[];
  pageHeight: number;
  pageNumber: number;
  pageReview: DocumentRedactionPageReview | null;
  pageReviewError: string | null;
  pageWidth: number;
  pages: DocumentRedactionRunPage[];
  policySnapshotJson: Record<string, unknown>;
  previewStatus: DocumentRedactionPreviewStatusResponse | null;
  previewStatusError: string | null;
  projectId: string;
  runId: string;
  selectedFindingId: string | null;
  selectedLineId: string | null;
  selectedPage: DocumentRedactionRunPage;
  selectedTokenId: string | null;
  serverError: string | null;
  serverNotice: string | null;
  showHighlights: boolean;
  findings: DocumentRedactionFinding[];
  findingsError: string | null;
  onPatchFindingAction: WorkspaceServerAction;
  onPatchPageReviewAction: WorkspaceServerAction;
}

function resolveFindingHighlightColor(anchorKind: string): {
  border: string;
  fill: string;
} {
  if (anchorKind === "AREA_MASK_BACKED") {
    return {
      border: "rgba(245, 166, 35, 0.95)",
      fill: "rgba(245, 166, 35, 0.22)"
    };
  }
  if (anchorKind === "TOKEN_LINKED") {
    return {
      border: "rgba(82, 169, 255, 0.95)",
      fill: "rgba(82, 169, 255, 0.22)"
    };
  }
  return {
    border: "rgba(160, 174, 196, 0.9)",
    fill: "rgba(160, 174, 196, 0.2)"
  };
}

function resolveReviewTone(
  status: string
): "danger" | "neutral" | "success" | "warning" {
  if (status === "APPROVED") {
    return "success";
  }
  if (status === "CHANGES_REQUESTED") {
    return "danger";
  }
  if (status === "IN_REVIEW") {
    return "warning";
  }
  return "neutral";
}

function toShortIso(value: string | null | undefined): string {
  if (!value) {
    return "N/A";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return "N/A";
  }
  return parsed.toISOString();
}

function resolveFindingLineId(
  finding: DocumentRedactionFinding
): string | null {
  return finding.geometry.lineId ?? finding.lineId ?? null;
}

function resolveFindingTokenId(
  finding: DocumentRedactionFinding
): string | null {
  return finding.geometry.tokenIds[0] ?? null;
}

function resolvePolicyDualReviewCategorySet(
  policySnapshotJson: Record<string, unknown>
): Set<string> {
  const candidates = new Set<string>();
  const queue: unknown[] = [policySnapshotJson];
  while (queue.length > 0) {
    const value = queue.shift();
    if (!value || typeof value !== "object") {
      continue;
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        queue.push(item);
      }
      continue;
    }
    const record = value as Record<string, unknown>;
    for (const [key, item] of Object.entries(record)) {
      const normalizedKey = key.trim().toLowerCase();
      const dualReviewKey =
        normalizedKey.includes("dual") ||
        normalizedKey.includes("second_review") ||
        normalizedKey.includes("secondreview");
      if (dualReviewKey && Array.isArray(item)) {
        for (const category of item) {
          if (typeof category === "string" && category.trim().length > 0) {
            candidates.add(category.trim().toUpperCase());
          }
        }
        continue;
      }
      if (dualReviewKey && item && typeof item === "object") {
        const categoryMap = item as Record<string, unknown>;
        for (const [category, required] of Object.entries(categoryMap)) {
          if (!required) {
            continue;
          }
          if (typeof category === "string" && category.trim().length > 0) {
            candidates.add(category.trim().toUpperCase());
          }
        }
        continue;
      }
      queue.push(item);
    }
  }
  return candidates;
}

function hasDisagreementMarkers(
  basisSecondaryJson: Record<string, unknown> | null
): boolean {
  if (!basisSecondaryJson || typeof basisSecondaryJson !== "object") {
    return false;
  }
  const queue: unknown[] = [basisSecondaryJson];
  while (queue.length > 0) {
    const value = queue.shift();
    if (!value || typeof value !== "object") {
      continue;
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        queue.push(item);
      }
      continue;
    }
    for (const [key, nested] of Object.entries(
      value as Record<string, unknown>
    )) {
      const normalized = key.trim().toLowerCase();
      if (
        normalized.includes("detector_disagreement") ||
        normalized.includes("detectordisagreement") ||
        normalized.includes("ambiguous_overlap") ||
        normalized.includes("ambiguousoverlap") ||
        normalized.includes("overlap_ambiguous")
      ) {
        if (
          nested === true ||
          nested === "true" ||
          nested === 1 ||
          nested === "1"
        ) {
          return true;
        }
      }
      if (
        normalized.includes("disagreement") ||
        normalized.includes("ambiguous")
      ) {
        if (
          nested === true ||
          nested === "true" ||
          nested === 1 ||
          nested === "1"
        ) {
          return true;
        }
      }
      queue.push(nested);
    }
  }
  return false;
}

function resolveHighRiskSignals(options: {
  finding: DocumentRedactionFinding;
  policySnapshotJson: Record<string, unknown>;
  targetStatus: FindingDecisionMutationStatus;
}): string[] {
  const { finding, policySnapshotJson, targetStatus } = options;
  const reasons: string[] = [];
  if (targetStatus === "FALSE_POSITIVE") {
    reasons.push("Decision changes finding to FALSE_POSITIVE");
  }
  if (
    finding.areaMaskId ||
    finding.geometry.anchorKind === "AREA_MASK_BACKED"
  ) {
    reasons.push("Finding is linked to a conservative area mask");
  }
  const dualReviewCategories =
    resolvePolicyDualReviewCategorySet(policySnapshotJson);
  if (dualReviewCategories.has(finding.category.trim().toUpperCase())) {
    reasons.push("Pinned policy marks this category as dual-review-required");
  }
  if (hasDisagreementMarkers(finding.basisSecondaryJson)) {
    reasons.push("Detector disagreement or ambiguous overlap is recorded");
  }
  if (finding.overrideRiskClassification === "HIGH") {
    reasons.push(
      "Finding is already classified as high-risk by the decision engine"
    );
  }
  return reasons;
}

function parseAssistSummary(finding: DocumentRedactionFinding): string | null {
  const basis = finding.basisSecondaryJson;
  if (!basis || typeof basis !== "object") {
    return null;
  }
  const summary = (basis as Record<string, unknown>).assistSummary;
  if (!summary || typeof summary !== "object") {
    return null;
  }
  const explanation = (summary as Record<string, unknown>).explanation;
  if (typeof explanation !== "string") {
    return null;
  }
  const normalized = explanation.trim();
  if (!normalized) {
    return null;
  }
  return normalized;
}

function parseGeneralizationExplanation(
  finding: DocumentRedactionFinding
): string | null {
  const basis = finding.basisSecondaryJson;
  if (!basis || typeof basis !== "object") {
    return null;
  }
  const explanation = (basis as Record<string, unknown>)
    .generalizationExplanation;
  if (!explanation || typeof explanation !== "object") {
    return null;
  }
  const summary = (explanation as Record<string, unknown>).summary;
  if (typeof summary !== "string") {
    return null;
  }
  const normalized = summary.trim();
  if (!normalized) {
    return null;
  }
  return normalized;
}

function parseGeneralizationGranularity(
  finding: DocumentRedactionFinding
): string | null {
  const basis = finding.basisSecondaryJson;
  if (!basis || typeof basis !== "object") {
    return null;
  }
  const transformation = (basis as Record<string, unknown>).transformation;
  if (!transformation || typeof transformation !== "object") {
    return null;
  }
  const sourceType = String(
    (transformation as Record<string, unknown>).sourceType ?? ""
  ).trim();
  const specificityApplied = String(
    (transformation as Record<string, unknown>).specificityApplied ?? ""
  ).trim();
  const specificityCeiling = String(
    (transformation as Record<string, unknown>).specificityCeiling ?? ""
  ).trim();
  if (!sourceType || !specificityApplied) {
    return null;
  }
  if (!specificityCeiling) {
    return `${sourceType} -> ${specificityApplied}`;
  }
  return `${sourceType} -> ${specificityApplied} (ceiling ${specificityCeiling})`;
}

export function PrivacyWorkspaceSurface({
  canMutate,
  documentId,
  findings,
  findingsError,
  lineLoadError,
  lines,
  mode,
  nextUnresolvedHref,
  onPatchFindingAction,
  onPatchPageReviewAction,
  pageEvents,
  pageHeight,
  pageNumber,
  pageReview,
  pageReviewError,
  pageWidth,
  pages,
  policySnapshotJson,
  previewStatus,
  previewStatusError,
  projectId,
  runId,
  selectedFindingId,
  selectedLineId,
  selectedPage,
  selectedTokenId,
  serverError,
  serverNotice,
  showHighlights
}: PrivacyWorkspaceSurfaceProps) {
  const router = useRouter();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogStatus, setDialogStatus] =
    useState<FindingDecisionMutationStatus>("OVERRIDDEN");
  const [dialogReason, setDialogReason] = useState("");
  const [dialogValidationError, setDialogValidationError] = useState<
    string | null
  >(null);
  const [localNotice, setLocalNotice] = useState<string | null>(null);
  const dialogReturnFocusRef = useRef<HTMLElement | null>(null);
  const lineButtonRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

  const selectedFinding = useMemo(() => {
    if (selectedFindingId) {
      return (
        findings.find((finding) => finding.id === selectedFindingId) ?? null
      );
    }
    if (selectedTokenId) {
      return (
        findings.find((finding) =>
          finding.geometry.tokenIds.includes(selectedTokenId)
        ) ?? null
      );
    }
    if (selectedLineId) {
      return (
        findings.find(
          (finding) => resolveFindingLineId(finding) === selectedLineId
        ) ?? null
      );
    }
    return null;
  }, [findings, selectedFindingId, selectedLineId, selectedTokenId]);

  const findingsForOverlay = selectedFinding ? [selectedFinding] : findings;

  const focusLineId = useMemo(() => {
    if (selectedLineId) {
      return selectedLineId;
    }
    if (selectedTokenId) {
      const tokenFinding = findings.find((finding) =>
        finding.geometry.tokenIds.includes(selectedTokenId)
      );
      if (tokenFinding) {
        return resolveFindingLineId(tokenFinding);
      }
    }
    if (selectedFinding) {
      return resolveFindingLineId(selectedFinding);
    }
    return null;
  }, [findings, selectedFinding, selectedLineId, selectedTokenId]);

  useEffect(() => {
    if (!focusLineId) {
      return;
    }
    const target = lineButtonRefs.current.get(focusLineId);
    if (!target) {
      return;
    }
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [focusLineId]);

  const navigate = (options: {
    findingId?: string | null;
    lineId?: string | null;
    mode?: PrivacyWorkspaceMode;
    page?: number;
    showHighlights?: boolean;
    tokenId?: string | null;
  }) => {
    const nextFindingId =
      options.findingId === null
        ? undefined
        : (options.findingId ?? selectedFindingId ?? undefined);
    const nextLineId =
      options.lineId === null
        ? undefined
        : (options.lineId ?? selectedLineId ?? undefined);
    const nextTokenId =
      options.tokenId === null
        ? undefined
        : (options.tokenId ?? selectedTokenId ?? undefined);
    const nextMode = options.mode ?? mode;
    const nextShowHighlights = options.showHighlights ?? showHighlights;

    const path = projectDocumentPrivacyWorkspacePath(projectId, documentId, {
      page: options.page ?? pageNumber,
      runId,
      findingId: nextFindingId,
      lineId: nextLineId,
      mode: nextMode,
      tokenId: nextTokenId
    });
    router.push(nextShowHighlights ? path : `${path}&highlights=off`, {
      scroll: false
    });
  };

  const selectedFindingLineId = selectedFinding
    ? resolveFindingLineId(selectedFinding)
    : null;
  const selectedFindingTokenId = selectedFinding
    ? resolveFindingTokenId(selectedFinding)
    : null;
  const highRiskSignals =
    selectedFinding !== null
      ? resolveHighRiskSignals({
          finding: selectedFinding,
          policySnapshotJson,
          targetStatus: dialogStatus
        })
      : [];

  const previewImagePath = projectDocumentPrivacyPreviewPath(
    projectId,
    documentId,
    runId,
    selectedPage.pageId
  );

  const unresolvedCount = selectedPage.unresolvedCount;
  const approvePageDisabled = !canMutate || unresolvedCount > 0 || !pageReview;

  const toolbarActions = [
    {
      id: "mode-controlled",
      label: "Controlled view",
      selected: mode === "controlled",
      onAction: () => {
        navigate({
          mode: "controlled",
          showHighlights,
          findingId: selectedFindingId,
          lineId: selectedLineId,
          tokenId: selectedTokenId
        });
      }
    },
    {
      id: "mode-safeguarded",
      label: "Safeguarded preview",
      selected: mode === "safeguarded",
      onAction: () => {
        navigate({
          mode: "safeguarded",
          showHighlights,
          findingId: selectedFindingId,
          lineId: selectedLineId,
          tokenId: selectedTokenId
        });
      }
    },
    {
      id: "previous-page",
      label: "Previous page",
      disabled: pageNumber <= 1,
      onAction: () => {
        navigate({
          page: Math.max(1, pageNumber - 1),
          findingId: null,
          lineId: null,
          tokenId: null
        });
      }
    },
    {
      id: "next-page",
      label: "Next page",
      disabled: pageNumber >= pages.length,
      onAction: () => {
        navigate({
          page: Math.min(pages.length, pageNumber + 1),
          findingId: null,
          lineId: null,
          tokenId: null
        });
      }
    },
    {
      id: "next-unresolved",
      label: "Next unresolved",
      disabled: !nextUnresolvedHref,
      onAction: () => {
        if (!nextUnresolvedHref) {
          setLocalNotice("No unresolved findings remain.");
          return;
        }
        router.push(nextUnresolvedHref, { scroll: false });
      }
    },
    {
      id: "toggle-highlights",
      label: showHighlights ? "Hide highlights" : "Show highlights",
      disabled: mode !== "safeguarded",
      pressed: showHighlights,
      onAction: () => {
        if (mode !== "safeguarded") {
          return;
        }
        navigate({ showHighlights: !showHighlights });
      }
    }
  ];

  return (
    <>
      {serverError ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="degraded"
            title="Workspace update blocked"
            description={serverError}
          />
        </section>
      ) : null}
      {serverNotice || localNotice ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="success"
            title="Workspace updated"
            description={
              serverNotice ?? localNotice ?? "Latest workspace state loaded."
            }
          />
        </section>
      ) : null}

      <section className="sectionCard ukde-panel privacyWorkspaceToolbarCard">
        <h3>Workspace toolbar</h3>
        <Toolbar actions={toolbarActions} label="Privacy review controls" />
        <div className="buttonRow privacyWorkspaceToolbarSupport">
          {mode === "safeguarded" && previewStatus?.status === "READY" ? (
            <a className="secondaryButton" href={previewImagePath}>
              Open preview asset
            </a>
          ) : null}
          <StatusChip tone={resolveReviewTone(selectedPage.reviewStatus)}>
            Page {pageNumber} · {selectedPage.reviewStatus}
          </StatusChip>
          <StatusChip tone={unresolvedCount > 0 ? "warning" : "success"}>
            Unresolved {unresolvedCount}
          </StatusChip>
        </div>
      </section>

      <section className="sectionCard ukde-panel privacyWorkspaceShellCard">
        <div className="privacyWorkspaceShell">
          <aside className="privacyWorkspaceRail" aria-label="Page queue">
            <h3>Pages</h3>
            <ul className="timelineList">
              {pages.map((page) => {
                const isCurrent = page.pageId === selectedPage.pageId;
                return (
                  <li key={page.pageId}>
                    <div className="auditIntegrityRow">
                      <span>Page {page.pageIndex + 1}</span>
                      <StatusChip tone={resolveReviewTone(page.reviewStatus)}>
                        {page.reviewStatus}
                      </StatusChip>
                    </div>
                    <p className="ukde-muted">
                      Findings {page.findingCount} · Unresolved{" "}
                      {page.unresolvedCount}
                    </p>
                    <div className="buttonRow">
                      <button
                        className="secondaryButton"
                        data-active={isCurrent ? "true" : undefined}
                        onClick={() => {
                          navigate({
                            page: page.pageIndex + 1,
                            findingId: null,
                            lineId: null,
                            tokenId: null
                          });
                        }}
                        type="button"
                      >
                        {isCurrent ? "Current page" : "Open page"}
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </aside>

          <div className="privacyWorkspaceCanvas" aria-label="Page canvas">
            <h3>Canvas</h3>
            <div
              aria-label="Privacy workspace canvas"
              className="privacyWorkspaceCanvasFrame"
              tabIndex={0}
            >
              {mode === "safeguarded" ? (
                previewStatus?.status === "READY" ? (
                  <img
                    alt={`Safeguarded preview for page ${pageNumber}`}
                    src={previewImagePath}
                    className="privacyWorkspaceImage"
                  />
                ) : (
                  <SectionState
                    kind="degraded"
                    title="Safeguarded preview not ready"
                    description={
                      previewStatusError ??
                      previewStatus?.failureReason ??
                      `Preview status is ${previewStatus?.status ?? "PENDING"}.`
                    }
                  />
                )
              ) : (
                <div className="privacyWorkspaceControlledPanel">
                  <p className="ukde-muted">
                    Controlled transcript source for page {pageNumber}
                  </p>
                  {lineLoadError ? (
                    <SectionState
                      kind="degraded"
                      title="Transcript context unavailable"
                      description={lineLoadError}
                    />
                  ) : lines.length === 0 ? (
                    <p className="ukde-muted">
                      No transcription lines available.
                    </p>
                  ) : (
                    <ul className="timelineList">
                      {lines.map((line) => (
                        <li key={line.lineId}>
                          <p>
                            <strong>{line.lineId}</strong>
                          </p>
                          <p className="ukde-muted">
                            {line.textDiplomatic || "(empty line)"}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
              {mode === "safeguarded" && showHighlights
                ? findingsForOverlay.flatMap((finding) =>
                    finding.geometry.boxes.map((box, index) => {
                      const palette = resolveFindingHighlightColor(
                        finding.geometry.anchorKind
                      );
                      return (
                        <div
                          key={`${finding.id}:${index}:${box.x}:${box.y}`}
                          title={`${finding.category} geometry`}
                          style={{
                            position: "absolute",
                            left: `${(box.x / pageWidth) * 100}%`,
                            top: `${(box.y / pageHeight) * 100}%`,
                            width: `${(box.width / pageWidth) * 100}%`,
                            height: `${(box.height / pageHeight) * 100}%`,
                            border: `1px solid ${palette.border}`,
                            background: palette.fill,
                            borderRadius: "0.2rem"
                          }}
                        />
                      );
                    })
                  )
                : null}
            </div>
          </div>

          <aside
            className="privacyWorkspaceInspector"
            aria-label="Transcript and findings"
          >
            <h3>Transcript and findings</h3>
            <div className="privacyWorkspaceSection">
              <h4>Finding actions</h4>
              {!selectedFinding ? (
                <p className="ukde-muted">
                  Select a finding to apply approve, override, or false-positive
                  actions.
                </p>
              ) : (
                <>
                  <ul className="projectMetaList">
                    <li>
                      <span>Finding</span>
                      <strong>{selectedFinding.id}</strong>
                    </li>
                    <li>
                      <span>Status</span>
                      <strong>{selectedFinding.decisionStatus}</strong>
                    </li>
                    <li>
                      <span>Decision etag</span>
                      <strong>{selectedFinding.decisionEtag}</strong>
                    </li>
                    <li>
                      <span>Anchor</span>
                      <strong>{selectedFinding.geometry.anchorKind}</strong>
                    </li>
                    <li>
                      <span>Line</span>
                      <strong>{selectedFindingLineId ?? "None"}</strong>
                    </li>
                    <li>
                      <span>Token</span>
                      <strong>{selectedFindingTokenId ?? "None"}</strong>
                    </li>
                  </ul>
                  {!canMutate ? (
                    <p className="ukde-muted">
                      Read-only role: finding decisions are restricted to
                      REVIEWER, PROJECT_LEAD, or ADMIN.
                    </p>
                  ) : null}
                  <div className="buttonRow">
                    <form action={onPatchFindingAction}>
                      <input name="runId" type="hidden" value={runId} />
                      <input
                        name="pageNumber"
                        type="hidden"
                        value={String(pageNumber)}
                      />
                      <input name="mode" type="hidden" value={mode} />
                      <input
                        name="highlights"
                        type="hidden"
                        value={showHighlights ? "on" : "off"}
                      />
                      <input
                        name="findingId"
                        type="hidden"
                        value={selectedFinding.id}
                      />
                      <input
                        name="decisionStatus"
                        type="hidden"
                        value="APPROVED"
                      />
                      <input
                        name="decisionEtag"
                        type="hidden"
                        value={selectedFinding.decisionEtag}
                      />
                      <input
                        name="returnLineId"
                        type="hidden"
                        value={selectedFindingLineId ?? ""}
                      />
                      <input
                        name="returnTokenId"
                        type="hidden"
                        value={selectedFindingTokenId ?? ""}
                      />
                      <button
                        className="secondaryButton"
                        disabled={!canMutate}
                        type="submit"
                      >
                        Approve finding
                      </button>
                    </form>
                    <button
                      className="secondaryButton"
                      disabled={!canMutate}
                      onClick={(event) => {
                        dialogReturnFocusRef.current = event.currentTarget;
                        setDialogStatus("OVERRIDDEN");
                        setDialogReason("");
                        setDialogValidationError(null);
                        setDialogOpen(true);
                      }}
                      type="button"
                    >
                      Override
                    </button>
                    <button
                      className="secondaryButton"
                      disabled={!canMutate}
                      onClick={(event) => {
                        dialogReturnFocusRef.current = event.currentTarget;
                        setDialogStatus("FALSE_POSITIVE");
                        setDialogReason("");
                        setDialogValidationError(null);
                        setDialogOpen(true);
                      }}
                      type="button"
                    >
                      False positive
                    </button>
                  </div>
                </>
              )}
            </div>

            <div className="privacyWorkspaceSection">
              <div className="auditIntegrityRow">
                <h4>Page approval</h4>
                <StatusChip tone={resolveReviewTone(selectedPage.reviewStatus)}>
                  {selectedPage.reviewStatus}
                </StatusChip>
              </div>
              {pageReviewError ? (
                <SectionState
                  kind="degraded"
                  title="Page review unavailable"
                  description={pageReviewError}
                />
              ) : pageReview ? (
                <>
                  <ul className="projectMetaList">
                    <li>
                      <span>Review etag</span>
                      <strong>{pageReview.reviewEtag}</strong>
                    </li>
                    <li>
                      <span>First reviewed by</span>
                      <strong>
                        {pageReview.firstReviewedBy ?? "Not reviewed"}
                      </strong>
                    </li>
                    <li>
                      <span>Second review</span>
                      <strong>{pageReview.secondReviewStatus}</strong>
                    </li>
                    <li>
                      <span>Requires second review</span>
                      <strong>
                        {pageReview.requiresSecondReview ? "Yes" : "No"}
                      </strong>
                    </li>
                  </ul>
                  <form action={onPatchPageReviewAction}>
                    <input name="runId" type="hidden" value={runId} />
                    <input
                      name="pageId"
                      type="hidden"
                      value={selectedPage.pageId}
                    />
                    <input
                      name="pageNumber"
                      type="hidden"
                      value={String(pageNumber)}
                    />
                    <input name="mode" type="hidden" value={mode} />
                    <input
                      name="highlights"
                      type="hidden"
                      value={showHighlights ? "on" : "off"}
                    />
                    <input
                      name="returnFindingId"
                      type="hidden"
                      value={selectedFinding?.id ?? ""}
                    />
                    <input
                      name="returnLineId"
                      type="hidden"
                      value={selectedLineId ?? selectedFindingLineId ?? ""}
                    />
                    <input
                      name="returnTokenId"
                      type="hidden"
                      value={selectedTokenId ?? selectedFindingTokenId ?? ""}
                    />
                    <input name="reviewStatus" type="hidden" value="APPROVED" />
                    <input
                      name="reviewEtag"
                      type="hidden"
                      value={pageReview.reviewEtag}
                    />
                    <button
                      className="secondaryButton"
                      disabled={approvePageDisabled}
                      type="submit"
                    >
                      Approve page
                    </button>
                  </form>
                  {approvePageDisabled ? (
                    <p className="ukde-muted">
                      {canMutate
                        ? unresolvedCount > 0
                          ? "Approve page is disabled until unresolved count reaches 0."
                          : "Page review projection unavailable."
                        : "Read-only role cannot approve page reviews."}
                    </p>
                  ) : null}
                </>
              ) : (
                <p className="ukde-muted">
                  Page review projection unavailable.
                </p>
              )}
            </div>

            <div className="privacyWorkspaceSection">
              <h4>Transcript</h4>
              {lineLoadError ? (
                <SectionState
                  kind="degraded"
                  title="Transcript context unavailable"
                  description={lineLoadError}
                />
              ) : lines.length === 0 ? (
                <p className="ukde-muted">No transcription lines available.</p>
              ) : (
                <ul
                  className="timelineList privacyWorkspaceTranscriptList"
                  aria-label="Transcript lines"
                >
                  {lines.map((line) => {
                    const isFocused = focusLineId === line.lineId;
                    return (
                      <li key={line.lineId}>
                        <button
                          aria-pressed={isFocused}
                          className="privacyWorkspaceListButton"
                          data-selected={isFocused ? "true" : undefined}
                          onClick={() => {
                            navigate({
                              findingId: null,
                              lineId: line.lineId,
                              tokenId: null
                            });
                          }}
                          ref={(element) => {
                            if (element) {
                              lineButtonRefs.current.set(line.lineId, element);
                            } else {
                              lineButtonRefs.current.delete(line.lineId);
                            }
                          }}
                          type="button"
                        >
                          <span className="privacyWorkspaceListTitle">
                            {line.lineId}
                          </span>
                          <span className="ukde-muted">
                            {line.textDiplomatic || "(empty line)"}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <div className="privacyWorkspaceSection">
              <h4>Findings</h4>
              {findingsError ? (
                <SectionState
                  kind="degraded"
                  title="Findings unavailable"
                  description={findingsError}
                />
              ) : findings.length === 0 ? (
                <p className="ukde-muted">No findings for this page.</p>
              ) : (
                <ul
                  className="timelineList privacyWorkspaceFindingList"
                  aria-label="Findings list"
                >
                  {findings.map((finding) => {
                    const isSelected = finding.id === selectedFinding?.id;
                    const assistSummary = parseAssistSummary(finding);
                    const generalizationExplanation =
                      parseGeneralizationExplanation(finding);
                    const generalizationGranularity =
                      parseGeneralizationGranularity(finding);
                    const findingHighRiskSignals = resolveHighRiskSignals({
                      finding,
                      policySnapshotJson,
                      targetStatus: "OVERRIDDEN"
                    });
                    return (
                      <li key={finding.id}>
                        <button
                          aria-pressed={isSelected}
                          className="privacyWorkspaceListButton"
                          data-selected={isSelected ? "true" : undefined}
                          onClick={() => {
                            navigate({
                              findingId: finding.id,
                              lineId: resolveFindingLineId(finding),
                              tokenId: resolveFindingTokenId(finding)
                            });
                          }}
                          type="button"
                        >
                          <span className="privacyWorkspaceListTitle">
                            {finding.category}
                          </span>
                          <span className="ukde-muted">
                            {finding.id} · {finding.decisionStatus} · Anchor{" "}
                            {finding.geometry.anchorKind}
                          </span>
                        </button>
                        <div className="buttonRow">
                          <button
                            className="secondaryButton"
                            onClick={() => {
                              navigate({
                                findingId: finding.id,
                                lineId: resolveFindingLineId(finding),
                                tokenId: resolveFindingTokenId(finding)
                              });
                            }}
                            type="button"
                          >
                            Open finding
                          </button>
                          <button
                            className="secondaryButton"
                            disabled={!resolveFindingLineId(finding)}
                            onClick={() => {
                              navigate({
                                findingId: null,
                                lineId: resolveFindingLineId(finding),
                                tokenId: null
                              });
                            }}
                            type="button"
                          >
                            Open line
                          </button>
                          <button
                            className="secondaryButton"
                            disabled={!resolveFindingTokenId(finding)}
                            onClick={() => {
                              navigate({
                                findingId: null,
                                lineId: resolveFindingLineId(finding),
                                tokenId: resolveFindingTokenId(finding)
                              });
                            }}
                            type="button"
                          >
                            Open token
                          </button>
                        </div>
                        {assistSummary ? (
                          <p className="ukde-muted">
                            Assist summary (non-authoritative): {assistSummary}
                          </p>
                        ) : null}
                        {generalizationExplanation ? (
                          <p className="ukde-muted">
                            Generalization rationale:{" "}
                            {generalizationExplanation}
                          </p>
                        ) : null}
                        {generalizationGranularity ? (
                          <p className="ukde-muted">
                            Policy granularity: {generalizationGranularity}
                          </p>
                        ) : null}
                        {findingHighRiskSignals.length > 0 ? (
                          <p className="ukde-muted">
                            High-risk override signals present. Second review
                            will be required later.
                          </p>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <div className="privacyWorkspaceSection">
              <h4>Page timeline</h4>
              {pageEvents.length === 0 ? (
                <p className="ukde-muted">No page events yet.</p>
              ) : (
                <ul className="timelineList">
                  {pageEvents.map((event) => (
                    <li key={`${event.sourceTable}:${event.eventId}`}>
                      <p>
                        <strong>{event.eventType}</strong>
                      </p>
                      <p className="ukde-muted">
                        {toShortIso(event.createdAt)} · {event.actorUserId}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="privacyWorkspaceSection">
              <h4>Deep-link context</h4>
              <ul className="projectMetaList">
                <li>
                  <span>Run</span>
                  <strong>{runId}</strong>
                </li>
                <li>
                  <span>Page</span>
                  <strong>{pageNumber}</strong>
                </li>
                <li>
                  <span>Finding</span>
                  <strong>{selectedFinding?.id ?? "None"}</strong>
                </li>
                <li>
                  <span>Line</span>
                  <strong>{focusLineId ?? "None"}</strong>
                </li>
                <li>
                  <span>Token</span>
                  <strong>{selectedTokenId ?? "None"}</strong>
                </li>
                <li>
                  <span>Highlights</span>
                  <strong>{showHighlights ? "Shown" : "Hidden"}</strong>
                </li>
                <li>
                  <span>Mode</span>
                  <strong>
                    {mode === "controlled"
                      ? "Controlled view"
                      : "Safeguarded preview"}
                  </strong>
                </li>
              </ul>
            </div>
          </aside>
        </div>
      </section>

      <ModalDialog
        description={
          dialogStatus === "FALSE_POSITIVE"
            ? "False-positive overrides are high-risk and require an explicit rationale."
            : "Overrides require a reviewer reason and append an immutable decision event."
        }
        footer={
          <div className="buttonRow">
            <button
              className="secondaryButton"
              onClick={() => setDialogOpen(false)}
              type="button"
            >
              Cancel
            </button>
            <button
              className="secondaryButton"
              type="submit"
              form="privacy-finding-reason-form"
              disabled={
                !selectedFinding ||
                !canMutate ||
                dialogReason.trim().length === 0
              }
            >
              Save decision
            </button>
          </div>
        }
        onClose={() => setDialogOpen(false)}
        open={dialogOpen}
        returnFocusRef={dialogReturnFocusRef}
        title={
          dialogStatus === "FALSE_POSITIVE"
            ? "Mark as false positive"
            : "Override finding"
        }
      >
        {!selectedFinding ? (
          <SectionState
            kind="empty"
            title="No finding selected"
            description="Choose a finding in the list, then retry override or false-positive actions."
          />
        ) : (
          <form
            action={onPatchFindingAction}
            id="privacy-finding-reason-form"
            onSubmit={(event) => {
              if (!dialogReason.trim()) {
                event.preventDefault();
                setDialogValidationError(
                  "Reason is required for override decisions."
                );
              }
            }}
          >
            <input name="runId" type="hidden" value={runId} />
            <input name="pageNumber" type="hidden" value={String(pageNumber)} />
            <input name="mode" type="hidden" value={mode} />
            <input
              name="highlights"
              type="hidden"
              value={showHighlights ? "on" : "off"}
            />
            <input name="findingId" type="hidden" value={selectedFinding.id} />
            <input name="decisionStatus" type="hidden" value={dialogStatus} />
            <input
              name="decisionEtag"
              type="hidden"
              value={selectedFinding.decisionEtag}
            />
            <input name="actionType" type="hidden" value="MASK" />
            <input
              name="returnLineId"
              type="hidden"
              value={selectedFindingLineId ?? ""}
            />
            <input
              name="returnTokenId"
              type="hidden"
              value={selectedFindingTokenId ?? ""}
            />
            <div className="privacyWorkspaceDialogBody">
              <p className="ukde-muted">
                {selectedFinding.id} · {selectedFinding.category} · current
                status {selectedFinding.decisionStatus}
              </p>
              {highRiskSignals.length > 0 ? (
                <div className="panelCard panelSubtle">
                  <p className="ukde-muted">
                    High-risk override detected. Prompt 64 will enforce
                    second-review completion for these decisions.
                  </p>
                  <ul className="timelineList">
                    {highRiskSignals.map((reason) => (
                      <li key={reason}>
                        <p className="ukde-muted">{reason}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <label
                className="ukde-muted"
                htmlFor="privacy-finding-reason-input"
              >
                Decision reason
              </label>
              <textarea
                id="privacy-finding-reason-input"
                name="reason"
                rows={5}
                value={dialogReason}
                onChange={(event) => {
                  setDialogReason(event.target.value);
                  if (dialogValidationError) {
                    setDialogValidationError(null);
                  }
                }}
                className="privacyWorkspaceReasonInput"
              />
              {dialogValidationError ? (
                <p className="ukde-muted" role="alert">
                  {dialogValidationError}
                </p>
              ) : null}
            </div>
          </form>
        )}
      </ModalDialog>
    </>
  );
}
