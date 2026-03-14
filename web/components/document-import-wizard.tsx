"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type {
  DocumentImportStatus,
  DocumentStatus,
  DocumentUploadSessionStatus,
  ProjectDocumentImportStatus,
  ProjectDocumentUploadSessionStatus
} from "@ukde/contracts";
import { InlineAlert, SectionState, StatusChip } from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";
import { projectDocumentPath, projectDocumentsPath } from "../lib/routes";

type ImportWizardStep = 1 | 2 | 3;

const TERMINAL_IMPORT_STATUSES: Set<DocumentImportStatus> = new Set([
  "ACCEPTED",
  "REJECTED",
  "FAILED",
  "CANCELED"
]);
const ACTIVE_UPLOAD_SESSION_STATUSES: Set<DocumentUploadSessionStatus> = new Set(
  ["ACTIVE", "ASSEMBLING"]
);
const DEFAULT_CHUNK_BYTES = 1024 * 1024;

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} bytes`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function resolveImportTone(
  value: DocumentImportStatus
): "danger" | "neutral" | "success" | "warning" {
  switch (value) {
    case "ACCEPTED":
      return "success";
    case "FAILED":
    case "REJECTED":
      return "danger";
    case "CANCELED":
      return "neutral";
    default:
      return "warning";
  }
}

function resolveDocumentTone(
  value: DocumentStatus
): "danger" | "neutral" | "success" | "warning" {
  switch (value) {
    case "READY":
      return "success";
    case "FAILED":
      return "danger";
    case "CANCELED":
      return "neutral";
    default:
      return "warning";
  }
}

function resolveUploadSessionTone(
  value: DocumentUploadSessionStatus
): "danger" | "neutral" | "success" | "warning" {
  switch (value) {
    case "COMPLETED":
      return "success";
    case "FAILED":
      return "danger";
    case "CANCELED":
      return "neutral";
    default:
      return "warning";
  }
}

function asImportStatusFromSession(
  session: ProjectDocumentUploadSessionStatus
): ProjectDocumentImportStatus {
  return {
    importId: session.importId,
    documentId: session.documentId,
    importStatus: session.importStatus,
    documentStatus: session.documentStatus,
    failureReason: session.failureReason,
    cancelAllowed: session.cancelAllowed,
    createdAt: session.createdAt,
    updatedAt: session.updatedAt
  };
}

function toHexDigest(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let output = "";
  for (const value of bytes) {
    output += value.toString(16).padStart(2, "0");
  }
  return output;
}

async function computeFileSha256(file: File): Promise<string | undefined> {
  if (
    typeof window === "undefined" ||
    !window.crypto ||
    !window.crypto.subtle
  ) {
    return undefined;
  }
  try {
    const payload = await file.arrayBuffer();
    const digest = await window.crypto.subtle.digest("SHA-256", payload);
    return toHexDigest(digest);
  } catch {
    return undefined;
  }
}

interface DocumentImportWizardProps {
  projectId: string;
}

export function DocumentImportWizard({ projectId }: DocumentImportWizardProps) {
  const [step, setStep] = useState<ImportWizardStep>(1);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isPreparing, setIsPreparing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isCanceling, setIsCanceling] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [importState, setImportState] = useState<ProjectDocumentImportStatus | null>(
    null
  );
  const [uploadSession, setUploadSession] =
    useState<ProjectDocumentUploadSessionStatus | null>(null);
  const [uploadedBytes, setUploadedBytes] = useState(0);

  const isReadOnly =
    importState?.importStatus === "SCANNING" ||
    importState?.importStatus === "ACCEPTED" ||
    importState?.importStatus === "REJECTED" ||
    importState?.importStatus === "FAILED" ||
    importState?.importStatus === "CANCELED";

  useEffect(() => {
    if (!importState) {
      return;
    }
    if (importState.importStatus !== "ACCEPTED") {
      return;
    }
    window.location.assign(projectDocumentPath(projectId, importState.documentId));
  }, [importState, projectId]);

  useEffect(() => {
    if (!importState) {
      return;
    }
    if (TERMINAL_IMPORT_STATUSES.has(importState.importStatus)) {
      return;
    }

    let active = true;
    const pollId = window.setInterval(async () => {
      const result = await requestBrowserApi<ProjectDocumentImportStatus>({
        cacheClass: "operations-live",
        path: `/projects/${projectId}/document-imports/${importState.importId}`
      });
      if (!active) {
        return;
      }
      if (!result.ok || !result.data) {
        setSubmitError(result.detail ?? "Import status polling failed.");
        return;
      }
      setImportState(result.data);
      setSubmitError(null);
    }, 1500);

    return () => {
      active = false;
      window.clearInterval(pollId);
    };
  }, [importState, projectId]);

  async function refreshSessionState(sessionId: string) {
    const response = await requestBrowserApi<ProjectDocumentUploadSessionStatus>({
      cacheClass: "operations-live",
      path: `/projects/${projectId}/documents/import/sessions/${sessionId}`
    });
    if (!response.ok || !response.data) {
      return null;
    }
    setUploadSession(response.data);
    setUploadedBytes(response.data.bytesReceived);
    return response.data;
  }

  async function completeSession(
    session: ProjectDocumentUploadSessionStatus
  ): Promise<void> {
    const completionResult =
      await requestBrowserApi<ProjectDocumentUploadSessionStatus>({
        method: "POST",
        path: `/projects/${projectId}/documents/import/sessions/${session.sessionId}/complete`
      });
    if (!completionResult.ok || !completionResult.data) {
      setSubmitError(
        completionResult.detail ??
          "Upload assembly failed. Resume is blocked until the session can be recovered."
      );
      return;
    }

    const completedSession = completionResult.data;
    setUploadSession(completedSession);
    setUploadedBytes(completedSession.bytesReceived);

    const importResult = await requestBrowserApi<ProjectDocumentImportStatus>({
      cacheClass: "operations-live",
      path: `/projects/${projectId}/document-imports/${completedSession.importId}`
    });
    if (importResult.ok && importResult.data) {
      setImportState(importResult.data);
      return;
    }
    setImportState(asImportStatusFromSession(completedSession));
  }

  async function uploadChunks(
    session: ProjectDocumentUploadSessionStatus
  ): Promise<void> {
    if (!selectedFile) {
      setSubmitError("Select a file before uploading.");
      return;
    }

    if (session.uploadStatus !== "ACTIVE") {
      setSubmitError(
        "Backend session cannot resume. Start a new upload session."
      );
      return;
    }

    setSubmitError(null);
    setIsUploading(true);
    setStep(3);
    let current = session;
    const chunkSize = Math.max(1, current.chunkSizeLimitBytes || DEFAULT_CHUNK_BYTES);
    const totalChunks = Math.ceil(selectedFile.size / chunkSize);
    let nextChunk = current.nextChunkIndex;

    while (nextChunk < totalChunks) {
      const offsetStart = nextChunk * chunkSize;
      const offsetEnd = Math.min(offsetStart + chunkSize, selectedFile.size);
      const blob = selectedFile.slice(offsetStart, offsetEnd);
      const payload = new FormData();
      payload.set("file", blob, `${selectedFile.name}.part-${nextChunk}`);

      const chunkResult =
        await requestBrowserApi<ProjectDocumentUploadSessionStatus>({
          method: "POST",
          path: `/projects/${projectId}/documents/import/sessions/${current.sessionId}/chunks?chunkIndex=${nextChunk}`,
          body: payload
        });
      if (!chunkResult.ok || !chunkResult.data) {
        setIsUploading(false);
        setSubmitError(
          chunkResult.detail ??
            "Upload was interrupted. Resume from the last acknowledged chunk."
        );
        return;
      }

      current = chunkResult.data;
      setUploadSession(current);
      setUploadedBytes(current.bytesReceived);
      nextChunk = current.nextChunkIndex;
    }

    setIsUploading(false);
    await completeSession(current);
  }

  async function handleStartUpload() {
    if (!selectedFile) {
      setSubmitError("Select a file before uploading.");
      return;
    }

    setSubmitError(null);
    setIsPreparing(true);
    setStep(3);
    const expectedSha256 = await computeFileSha256(selectedFile);
    const createResult = await requestBrowserApi<ProjectDocumentUploadSessionStatus>({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      path: `/projects/${projectId}/documents/import/sessions`,
      body: JSON.stringify({
        originalFilename: selectedFile.name,
        expectedSha256,
        expectedTotalBytes: selectedFile.size
      })
    });
    setIsPreparing(false);

    if (!createResult.ok || !createResult.data) {
      setSubmitError(createResult.detail ?? "Upload session creation failed.");
      return;
    }

    setUploadSession(createResult.data);
    setUploadedBytes(createResult.data.bytesReceived);
    await uploadChunks(createResult.data);
  }

  async function handleResumeUpload() {
    if (!uploadSession) {
      setSubmitError("No upload session is available to resume.");
      return;
    }
    const refreshed = await refreshSessionState(uploadSession.sessionId);
    if (!refreshed) {
      setSubmitError("Upload session could not be refreshed for resume.");
      return;
    }
    if (refreshed.uploadStatus !== "ACTIVE") {
      setSubmitError(
        `Backend session is ${refreshed.uploadStatus}. Start a new upload instead of forcing resume.`
      );
      return;
    }
    await uploadChunks(refreshed);
  }

  async function handleCancelImport() {
    setSubmitError(null);
    setIsCanceling(true);

    if (
      uploadSession &&
      ACTIVE_UPLOAD_SESSION_STATUSES.has(uploadSession.uploadStatus)
    ) {
      const result = await requestBrowserApi<ProjectDocumentUploadSessionStatus>({
        method: "POST",
        path: `/projects/${projectId}/documents/import/sessions/${uploadSession.sessionId}/cancel`
      });
      setIsCanceling(false);
      if (!result.ok || !result.data) {
        setSubmitError(result.detail ?? "Cancel request failed.");
        return;
      }
      setUploadSession(result.data);
      setImportState(asImportStatusFromSession(result.data));
      return;
    }

    if (!importState || !importState.cancelAllowed) {
      setIsCanceling(false);
      return;
    }
    const result = await requestBrowserApi<ProjectDocumentImportStatus>({
      method: "POST",
      path: `/projects/${projectId}/document-imports/${importState.importId}/cancel`
    });
    setIsCanceling(false);

    if (!result.ok || !result.data) {
      setSubmitError(result.detail ?? "Cancel request failed.");
      return;
    }
    setImportState(result.data);
  }

  const progressTotal = selectedFile?.size ?? uploadSession?.expectedTotalBytes ?? null;
  const progressPercent =
    progressTotal && progressTotal > 0
      ? Math.min(100, Math.round((uploadedBytes / progressTotal) * 100))
      : null;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Documents / Import</p>
        <h2>Controlled upload pipeline</h2>
        <p className="ukde-muted">
          Upload is validated server-side, stored in controlled raw storage,
          scanned, and then handed to document processing.
        </p>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Workflow steps</h3>
        <ol className="importStepper" aria-label="Import steps">
          <li aria-current={step === 1 ? "step" : undefined}>1. Select files</li>
          <li aria-current={step === 2 ? "step" : undefined}>
            2. Confirm metadata and destination project
          </li>
          <li aria-current={step === 3 ? "step" : undefined}>
            3. Upload and status
          </li>
        </ol>
      </section>

      {step === 1 ? (
        <section className="sectionCard ukde-panel importWizardPanel">
          <h3>Step 1: Select file</h3>
          <label className="projectForm" htmlFor="document-import-file">
            <span>Choose one file</span>
            <input
              id="document-import-file"
              className="projectInput"
              type="file"
              accept=".pdf,.tif,.tiff,.png,.jpg,.jpeg,application/pdf,image/tiff,image/png,image/jpeg"
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null;
                setSelectedFile(file);
                setSubmitError(null);
              }}
            />
          </label>
          <p className="ukde-muted">
            Allowed types: PDF, TIFF, PNG, JPG, JPEG. Validation does not rely
            on client MIME values.
          </p>
          <div className="buttonRow">
            <Link className="secondaryButton" href={projectDocumentsPath(projectId)}>
              Cancel
            </Link>
            <button
              className="primaryButton"
              type="button"
              onClick={() => setStep(2)}
              disabled={!selectedFile}
            >
              Next
            </button>
          </div>
        </section>
      ) : null}

      {step === 2 ? (
        <section className="sectionCard ukde-panel importWizardPanel">
          <h3>Step 2: Confirm upload metadata</h3>
          {!selectedFile ? (
            <SectionState
              kind="error"
              title="No file selected"
              description="Return to step 1 and select a file before upload."
            />
          ) : (
            <ul className="projectMetaList">
              <li>
                <span>Project</span>
                <strong>{projectId}</strong>
              </li>
              <li>
                <span>Filename</span>
                <strong>{selectedFile.name}</strong>
              </li>
              <li>
                <span>Size</span>
                <strong>{formatBytes(selectedFile.size)}</strong>
              </li>
              <li>
                <span>Client type</span>
                <strong>{selectedFile.type || "unknown"}</strong>
              </li>
            </ul>
          )}

          <div className="buttonRow">
            <button className="secondaryButton" type="button" onClick={() => setStep(1)}>
              Back
            </button>
            <Link className="secondaryButton" href={projectDocumentsPath(projectId)}>
              Cancel
            </Link>
            <button
              className="primaryButton"
              type="button"
              onClick={handleStartUpload}
              disabled={!selectedFile || isUploading || isPreparing}
            >
              {isPreparing
                ? "Preparing integrity check..."
                : isUploading
                  ? "Uploading..."
                  : "Upload"}
            </button>
          </div>
        </section>
      ) : null}

      {step === 3 ? (
        <section className="sectionCard ukde-panel importWizardPanel" aria-live="polite">
          <h3>Step 3: Upload and status</h3>
          {uploadSession ? (
            <>
              <div className="auditIntegrityRow">
                <StatusChip tone={resolveUploadSessionTone(uploadSession.uploadStatus)}>
                  {uploadSession.uploadStatus}
                </StatusChip>
                <StatusChip tone={resolveImportTone(uploadSession.importStatus)}>
                  {uploadSession.importStatus}
                </StatusChip>
                <StatusChip tone={resolveDocumentTone(uploadSession.documentStatus)}>
                  {uploadSession.documentStatus}
                </StatusChip>
              </div>
              <p className="ukde-muted">
                {uploadSession.uploadStatus === "ACTIVE"
                  ? isUploading
                    ? "Uploading chunks to controlled storage. Progress resumes from acknowledged chunks."
                    : "Upload session is active. Resume from the last acknowledged chunk."
                  : uploadSession.uploadStatus === "ASSEMBLING"
                    ? "Chunks received. Server is assembling and validating the upload."
                    : uploadSession.uploadStatus === "COMPLETED"
                      ? "Upload assembled and queued for scanner handoff."
                      : uploadSession.uploadStatus === "CANCELED"
                        ? "Upload session was canceled."
                        : "Upload session failed and requires a new attempt."}
              </p>
              {progressTotal ? (
                <p className="ukde-muted">
                  {`Transferred ${formatBytes(uploadedBytes)} of ${formatBytes(progressTotal)}${
                    progressPercent !== null ? ` (${progressPercent}%)` : ""
                  }.`}
                </p>
              ) : null}
              {uploadSession.failureReason ? (
                <InlineAlert title="Safe failure summary" tone="danger">
                  {uploadSession.failureReason}
                </InlineAlert>
              ) : null}
              <div className="buttonRow">
                {uploadSession.cancelAllowed ? (
                  <button
                    className="secondaryButton"
                    type="button"
                    onClick={handleCancelImport}
                    disabled={isCanceling || isUploading}
                  >
                    {isCanceling ? "Canceling..." : "Cancel"}
                  </button>
                ) : (
                  <button className="secondaryButton" type="button" disabled>
                    Cancel
                  </button>
                )}
                {uploadSession.uploadStatus === "ACTIVE" ? (
                  <button
                    className="secondaryButton"
                    type="button"
                    onClick={handleResumeUpload}
                    disabled={isUploading || isPreparing}
                  >
                    {isUploading ? "Uploading..." : "Resume upload"}
                  </button>
                ) : null}
                <Link className="secondaryButton" href={projectDocumentsPath(projectId)}>
                  Back to documents
                </Link>
                {importState && TERMINAL_IMPORT_STATUSES.has(importState.importStatus) ? (
                  <button
                    className="secondaryButton"
                    type="button"
                    onClick={() => {
                      setImportState(null);
                      setUploadSession(null);
                      setUploadedBytes(0);
                      setSelectedFile(null);
                      setSubmitError(null);
                      setStep(1);
                    }}
                    disabled={isReadOnly && importState.importStatus === "ACCEPTED"}
                  >
                    Start another import
                  </button>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <SectionState
                kind={submitError ? "error" : "loading"}
                title={submitError ? "Upload failed" : "Upload is pending"}
                description={
                  submitError
                    ? submitError
                    : "Upload status will appear after the API accepts the file."
                }
              />
              {submitError ? (
                <div className="buttonRow">
                  <button
                    className="secondaryButton"
                    type="button"
                    onClick={() => setStep(selectedFile ? 2 : 1)}
                  >
                    Back
                  </button>
                  <Link className="secondaryButton" href={projectDocumentsPath(projectId)}>
                    Back to documents
                  </Link>
                </div>
              ) : null}
            </>
          )}
        </section>
      ) : null}

      {submitError ? (
        <InlineAlert className="sectionCard ukde-panel" title="Import error" tone="danger">
          {submitError}
        </InlineAlert>
      ) : null}
    </main>
  );
}
