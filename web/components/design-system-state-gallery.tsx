"use client";

import { useState } from "react";

import {
  DetailsDrawer,
  InlineAlert,
  SectionState,
  SkeletonLines,
  StatusChip
} from "@ukde/ui/primitives";

type DrawerPreviewMode = "loading" | "empty";

export function DesignSystemStateGallery() {
  const [drawerMode, setDrawerMode] = useState<DrawerPreviewMode>("loading");
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <section className="sectionCard ukde-panel dsSection">
      <div className="sectionHeading">
        <p className="ukde-eyebrow">State language</p>
        <h2>Zero, empty, loading, error, success, and disabled patterns</h2>
        <p className="ukde-muted">
          These are shared primitives for route, page, section, drawer, and
          timeline feedback surfaces.
        </p>
      </div>

      <div className="ukde-grid" data-columns="2">
        <SectionState
          kind="zero"
          title="Import wizard: no file selected"
          description="Select files, confirm metadata, then start controlled upload."
        />
        <SectionState
          kind="loading"
          title="Import wizard: uploading and scanning"
          description="Current status: UPLOADING -> QUEUED -> SCANNING."
        >
          <SkeletonLines lines={3} />
        </SectionState>
        <SectionState
          kind="error"
          title="Import wizard: validation failed"
          description="The file did not pass upload validation. Resolve the issue and retry."
        />
        <SectionState
          kind="success"
          title="Import wizard: accepted"
          description="Upload is accepted. Follow-up status is available from document detail."
        />
      </div>

      <div className="ukde-grid" data-columns="2">
        <SectionState
          kind="empty"
          title="Document library empty"
          description="No documents are currently available for this project."
        />
        <SectionState
          kind="no-results"
          title="Document library no-results"
          description="No rows matched the current filters."
        />
        <SectionState
          kind="loading"
          title="Document library loading"
          description="Rows are loading while shell continuity is preserved."
        >
          <SkeletonLines lines={2} />
        </SectionState>
        <SectionState
          kind="error"
          title="Document library error"
          description="Rows could not be loaded. Retry once upstream services recover."
        />
      </div>

      <div className="ukde-grid" data-columns="2">
        <SectionState
          kind="loading"
          title="Viewer loading"
          description="Page image and metadata are loading."
        >
          <SkeletonLines lines={2} />
        </SectionState>
        <SectionState
          kind="error"
          title="Viewer error"
          description="Page assets are unavailable for this route."
        />
        <SectionState
          kind="loading"
          title="Ingest timeline loading"
          description="Attempt history is loading."
        >
          <SkeletonLines lines={2} />
        </SectionState>
        <SectionState
          kind="degraded"
          title="Ingest timeline degraded"
          description="Status endpoint is reachable but timeline payload is incomplete."
        />
      </div>

      <section className="sectionCard ukde-panel ukde-surface-raised">
        <p className="ukde-eyebrow">Job progress and safe failure</p>
        <div className="auditIntegrityRow">
          <StatusChip tone="info">RUNNING</StatusChip>
          <span className="ukde-muted">delivery attempts: 1/3</span>
        </div>
        <InlineAlert title="Safe failure summary" tone="danger">
          EXTRACTION_TIMEOUT: page extraction exceeded runtime guardrail.
        </InlineAlert>
      </section>

      <section className="sectionCard ukde-panel ukde-surface-raised">
        <p className="ukde-eyebrow">Drawer detail states</p>
        <p className="ukde-muted">
          Detail drawers can expose loading and empty states without breaking
          page context.
        </p>
        <div className="buttonRow">
          <button
            className="secondaryButton"
            onClick={() => {
              setDrawerMode("loading");
              setDrawerOpen(true);
            }}
            type="button"
          >
            Open loading drawer
          </button>
          <button
            className="secondaryButton"
            onClick={() => {
              setDrawerMode("empty");
              setDrawerOpen(true);
            }}
            type="button"
          >
            Open empty drawer
          </button>
        </div>
      </section>

      <DetailsDrawer
        description="State-ready detail surface"
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        title="Document detail drawer"
      >
        {drawerMode === "loading" ? (
          <SectionState
            kind="loading"
            title="Loading detail payload"
            description="Detail metadata is loading."
          >
            <SkeletonLines lines={2} />
          </SectionState>
        ) : (
          <SectionState
            kind="empty"
            title="No detail payload"
            description="No detail rows are available for the selected item."
          />
        )}
      </DetailsDrawer>
    </section>
  );
}
