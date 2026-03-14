"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type {
  DocumentLayoutActivationGate,
  LayoutRunStatus
} from "@ukde/contracts";
import { InlineAlert } from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";
import { projectDocumentLayoutRunPath } from "../lib/routes";

interface DocumentLayoutRunActionsProps {
  canMutate: boolean;
  documentId: string;
  inputPreprocessRunId?: string | null;
  isActiveProjection?: boolean;
  projectId: string;
  runId?: string;
  runStatus?: LayoutRunStatus;
  activationGate?: DocumentLayoutActivationGate | null;
}

type PendingAction = "activate" | "cancel" | "create" | "rerun" | null;

function toOptionalString(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function DocumentLayoutRunActions({
  canMutate,
  documentId,
  inputPreprocessRunId,
  isActiveProjection = false,
  projectId,
  runId,
  runStatus,
  activationGate
}: DocumentLayoutRunActionsProps) {
  const router = useRouter();
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [resolvedInputPreprocessRunId, setResolvedInputPreprocessRunId] = useState(
    inputPreprocessRunId ?? ""
  );
  const [modelId, setModelId] = useState("");
  const [profileId, setProfileId] = useState("");
  const activationBlocked =
    Boolean(runId) &&
    runStatus === "SUCCEEDED" &&
    !isActiveProjection &&
    Boolean(activationGate) &&
    activationGate?.eligible === false;

  async function triggerCreate() {
    setPendingAction("create");
    setError(null);
    setSuccess(null);
    const result = await requestBrowserApi<{ id: string }>({
      method: "POST",
      path: `/projects/${projectId}/documents/${documentId}/layout-runs`,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        inputPreprocessRunId: toOptionalString(resolvedInputPreprocessRunId),
        modelId: toOptionalString(modelId),
        profileId: toOptionalString(profileId)
      })
    });
    setPendingAction(null);
    if (!result.ok || !result.data) {
      setError(result.detail ?? "Layout run creation failed.");
      return;
    }
    setSuccess("Layout run queued.");
    router.push(projectDocumentLayoutRunPath(projectId, documentId, result.data.id));
    router.refresh();
  }

  async function triggerRerun() {
    if (!runId) {
      return;
    }
    setPendingAction("rerun");
    setError(null);
    setSuccess(null);
    const result = await requestBrowserApi<{ id: string }>({
      method: "POST",
      path: `/projects/${projectId}/documents/${documentId}/layout-runs`,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        inputPreprocessRunId: toOptionalString(resolvedInputPreprocessRunId),
        modelId: toOptionalString(modelId),
        profileId: toOptionalString(profileId),
        parentRunId: runId,
        supersedesRunId: runId
      })
    });
    setPendingAction(null);
    if (!result.ok || !result.data) {
      setError(result.detail ?? "Layout rerun request failed.");
      return;
    }
    setSuccess("Layout rerun queued.");
    router.push(projectDocumentLayoutRunPath(projectId, documentId, result.data.id));
    router.refresh();
  }

  async function triggerCancel() {
    if (!runId) {
      return;
    }
    setPendingAction("cancel");
    setError(null);
    setSuccess(null);
    const result = await requestBrowserApi({
      method: "POST",
      path: `/projects/${projectId}/documents/${documentId}/layout-runs/${runId}/cancel`
    });
    setPendingAction(null);
    if (!result.ok) {
      setError(result.detail ?? "Layout cancel request failed.");
      return;
    }
    setSuccess("Run cancellation recorded.");
    router.refresh();
  }

  async function triggerActivate() {
    if (!runId) {
      return;
    }
    setPendingAction("activate");
    setError(null);
    setSuccess(null);
    const result = await requestBrowserApi({
      method: "POST",
      path: `/projects/${projectId}/documents/${documentId}/layout-runs/${runId}/activate`
    });
    setPendingAction(null);
    if (!result.ok) {
      setError(result.detail ?? "Layout run activation failed.");
      return;
    }
    setSuccess("Layout run activated.");
    router.refresh();
  }

  if (!canMutate) {
    return null;
  }

  return (
    <section className="sectionCard ukde-panel">
      <h3>Layout run actions</h3>
      <details className="preprocessRunAdvancedControls">
        <summary>Optional run context</summary>
        <label>
          Input preprocess run ID
          <input
            type="text"
            maxLength={120}
            value={resolvedInputPreprocessRunId}
            onChange={(event) =>
              setResolvedInputPreprocessRunId(event.target.value)
            }
            placeholder="Defaults to active preprocess projection"
          />
        </label>
        <label>
          Model ID
          <input
            type="text"
            maxLength={120}
            value={modelId}
            onChange={(event) => setModelId(event.target.value)}
            placeholder="Optional model selector"
          />
        </label>
        <label>
          Profile ID
          <input
            type="text"
            maxLength={120}
            value={profileId}
            onChange={(event) => setProfileId(event.target.value)}
            placeholder="Optional profile selector"
          />
        </label>
      </details>
      <div className="buttonRow">
        {!runId ? (
          <button
            className="secondaryButton"
            type="button"
            disabled={pendingAction !== null}
            onClick={() => {
              void triggerCreate();
            }}
          >
            {pendingAction === "create" ? "Queueing..." : "Run layout analysis"}
          </button>
        ) : null}
        {runId ? (
          <button
            className="secondaryButton"
            type="button"
            disabled={pendingAction !== null}
            onClick={() => {
              void triggerRerun();
            }}
          >
            {pendingAction === "rerun" ? "Queueing rerun..." : "Rerun"}
          </button>
        ) : null}
        {runId && (runStatus === "QUEUED" || runStatus === "RUNNING") ? (
          <button
            className="secondaryButton"
            type="button"
            disabled={pendingAction !== null}
            onClick={() => {
              void triggerCancel();
            }}
          >
            {pendingAction === "cancel" ? "Canceling..." : "Cancel run"}
          </button>
        ) : null}
        {runId && runStatus === "SUCCEEDED" && !isActiveProjection ? (
          <button
            className="secondaryButton"
            type="button"
            disabled={pendingAction !== null || activationBlocked}
            onClick={() => {
              void triggerActivate();
            }}
          >
            {pendingAction === "activate"
              ? "Activating..."
              : activationBlocked
                ? "Activation blocked"
                : "Activate run"}
          </button>
        ) : null}
        {runId && runStatus === "SUCCEEDED" && isActiveProjection ? (
          <span className="ukde-muted">Run is already the active projection.</span>
        ) : null}
      </div>
      {error ? (
        <InlineAlert title="Layout action failed" tone="danger">
          {error}
        </InlineAlert>
      ) : null}
      {success ? (
        <InlineAlert title="Layout action completed" tone="success">
          {success}
        </InlineAlert>
      ) : null}
      {activationBlocked && activationGate ? (
        <InlineAlert title="Activation blocked by gate checks" tone="warning">
          <p>
            Resolve every blocker before promotion. No silent fallback is allowed.
          </p>
          <ul>
            {activationGate.blockers.map((blocker) => (
              <li key={blocker.code}>
                <strong>{blocker.code}</strong>: {blocker.message}
                {blocker.pageNumbers.length > 0
                  ? ` (pages ${blocker.pageNumbers.join(", ")})`
                  : ""}
              </li>
            ))}
          </ul>
        </InlineAlert>
      ) : null}
      {runId && runStatus === "SUCCEEDED" && !isActiveProjection && activationGate ? (
        <InlineAlert title="Downstream impact" tone="neutral">
          {activationGate.downstreamImpact.transcriptionStateAfterActivation ===
          "NOT_STARTED"
            ? "No active transcription basis exists yet. Activation keeps downstream state at NOT_STARTED."
            : activationGate.downstreamImpact.transcriptionStateAfterActivation ===
                "CURRENT"
              ? "Activation preserves a CURRENT transcription basis for the same layout snapshot."
              : `Activation will mark downstream transcription STALE. ${
                  activationGate.downstreamImpact.reason ?? ""
                }`}
        </InlineAlert>
      ) : null}
    </section>
  );
}
