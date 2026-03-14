"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { TranscriptionRunStatus } from "@ukde/contracts";
import { InlineAlert } from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";
import { projectDocumentTranscriptionRunPath } from "../lib/routes";

interface DocumentTranscriptionRunActionsProps {
  canMutate: boolean;
  documentId: string;
  inputLayoutRunId?: string | null;
  inputPreprocessRunId?: string | null;
  isActiveProjection?: boolean;
  projectId: string;
  runId?: string;
  runStatus?: TranscriptionRunStatus;
}

type PendingAction =
  | "activate"
  | "cancel"
  | "create"
  | "fallback"
  | "rerun"
  | null;

function toOptionalString(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function DocumentTranscriptionRunActions({
  canMutate,
  documentId,
  inputLayoutRunId,
  inputPreprocessRunId,
  isActiveProjection = false,
  projectId,
  runId,
  runStatus
}: DocumentTranscriptionRunActionsProps) {
  const router = useRouter();
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [resolvedInputPreprocessRunId, setResolvedInputPreprocessRunId] = useState(
    inputPreprocessRunId ?? ""
  );
  const [resolvedInputLayoutRunId, setResolvedInputLayoutRunId] = useState(
    inputLayoutRunId ?? ""
  );
  const [engine, setEngine] = useState("VLM_LINE_CONTEXT");
  const [promptTemplateId, setPromptTemplateId] = useState("");

  async function triggerCreate() {
    setPendingAction("create");
    setError(null);
    setSuccess(null);
    const result = await requestBrowserApi<{ id: string }>({
      method: "POST",
      path: `/projects/${projectId}/documents/${documentId}/transcription-runs`,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        inputPreprocessRunId: toOptionalString(resolvedInputPreprocessRunId),
        inputLayoutRunId: toOptionalString(resolvedInputLayoutRunId),
        engine: toOptionalString(engine),
        promptTemplateId: toOptionalString(promptTemplateId)
      })
    });
    setPendingAction(null);
    if (!result.ok || !result.data) {
      setError(result.detail ?? "Transcription run creation failed.");
      return;
    }
    setSuccess("Transcription run queued.");
    router.push(projectDocumentTranscriptionRunPath(projectId, documentId, result.data.id));
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
      path: `/projects/${projectId}/documents/${documentId}/transcription-runs`,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        inputPreprocessRunId: toOptionalString(resolvedInputPreprocessRunId),
        inputLayoutRunId: toOptionalString(resolvedInputLayoutRunId),
        engine: toOptionalString(engine),
        promptTemplateId: toOptionalString(promptTemplateId),
        supersedesTranscriptionRunId: runId
      })
    });
    setPendingAction(null);
    if (!result.ok || !result.data) {
      setError(result.detail ?? "Transcription rerun request failed.");
      return;
    }
    setSuccess("Transcription rerun queued.");
    router.push(projectDocumentTranscriptionRunPath(projectId, documentId, result.data.id));
    router.refresh();
  }

  async function triggerFallback() {
    if (!runId) {
      return;
    }
    setPendingAction("fallback");
    setError(null);
    setSuccess(null);
    const fallbackEngine =
      engine === "KRAKEN_LINE" || engine === "TROCR_LINE" || engine === "DAN_PAGE"
        ? engine
        : "KRAKEN_LINE";
    const result = await requestBrowserApi<{ id: string }>({
      method: "POST",
      path: `/projects/${projectId}/documents/${documentId}/transcription-runs/fallback`,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        baseRunId: runId,
        engine: fallbackEngine
      })
    });
    setPendingAction(null);
    if (!result.ok || !result.data) {
      setError(result.detail ?? "Fallback run request failed.");
      return;
    }
    setSuccess("Fallback run queued.");
    router.push(projectDocumentTranscriptionRunPath(projectId, documentId, result.data.id));
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
      path: `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/cancel`
    });
    setPendingAction(null);
    if (!result.ok) {
      setError(result.detail ?? "Transcription cancel request failed.");
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
      path: `/projects/${projectId}/documents/${documentId}/transcription-runs/${runId}/activate`
    });
    setPendingAction(null);
    if (!result.ok) {
      setError(result.detail ?? "Transcription run activation failed.");
      return;
    }
    setSuccess("Transcription run activated.");
    router.refresh();
  }

  if (!canMutate) {
    return null;
  }

  return (
    <section className="sectionCard ukde-panel">
      <h3>Transcription run actions</h3>
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
          Input layout run ID
          <input
            type="text"
            maxLength={120}
            value={resolvedInputLayoutRunId}
            onChange={(event) => setResolvedInputLayoutRunId(event.target.value)}
            placeholder="Defaults to active layout projection"
          />
        </label>
        <label>
          Engine
          <select value={engine} onChange={(event) => setEngine(event.target.value)}>
            <option value="VLM_LINE_CONTEXT">VLM line context</option>
            <option value="REVIEW_COMPOSED">Review composed</option>
            <option value="KRAKEN_LINE">Kraken line</option>
            <option value="TROCR_LINE">TrOCR line</option>
            <option value="DAN_PAGE">DAN page</option>
          </select>
        </label>
        <label>
          Prompt template ID
          <input
            type="text"
            maxLength={160}
            value={promptTemplateId}
            onChange={(event) => setPromptTemplateId(event.target.value)}
            placeholder="Optional template identifier"
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
            {pendingAction === "create" ? "Queueing..." : "Run transcription"}
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
        {runId ? (
          <button
            className="secondaryButton"
            type="button"
            disabled={pendingAction !== null}
            onClick={() => {
              void triggerFallback();
            }}
          >
            {pendingAction === "fallback"
              ? "Queueing fallback..."
              : "Queue fallback"}
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
            disabled={pendingAction !== null}
            onClick={() => {
              void triggerActivate();
            }}
          >
            {pendingAction === "activate" ? "Activating..." : "Activate run"}
          </button>
        ) : null}
        {runId && runStatus === "SUCCEEDED" && isActiveProjection ? (
          <span className="ukde-muted">Run is already the active projection.</span>
        ) : null}
      </div>
      {error ? (
        <InlineAlert title="Transcription action failed" tone="danger">
          {error}
        </InlineAlert>
      ) : null}
      {success ? (
        <InlineAlert title="Transcription action completed" tone="success">
          {success}
        </InlineAlert>
      ) : null}
    </section>
  );
}
