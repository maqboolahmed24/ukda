"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { PreprocessProfileId, PreprocessRunStatus } from "@ukde/contracts";
import { InlineAlert } from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";
import { projectDocumentPreprocessingRunPath } from "../lib/routes";

interface DocumentPreprocessRunActionsProps {
  canMutate: boolean;
  documentId: string;
  isActiveProjection?: boolean;
  projectId: string;
  runId?: string;
  runStatus?: PreprocessRunStatus;
}

type PendingAction = "activate" | "cancel" | "create" | "rerun" | null;

const ADVANCED_RISK_CONFIRMATION_COPY =
  "Advanced full-document preprocessing can remove faint handwriting details. Confirm only when stronger cleanup is necessary and compare review will follow.";

const PROFILE_DESCRIPTIONS: Record<PreprocessProfileId, string> = {
  BALANCED: "Safe default profile for deterministic grayscale cleanup.",
  CONSERVATIVE: "Lower-intensity cleanup for fragile scans and faint handwriting.",
  AGGRESSIVE: "Stronger cleanup with optional adaptive binarization.",
  BLEED_THROUGH:
    "Advanced show-through reduction; best results use paired recto/verso pages."
};

export function DocumentPreprocessRunActions({
  canMutate,
  documentId,
  isActiveProjection = false,
  projectId,
  runId,
  runStatus
}: DocumentPreprocessRunActionsProps) {
  const router = useRouter();
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [profileId, setProfileId] = useState<PreprocessProfileId>("BALANCED");
  const [advancedRiskConfirmed, setAdvancedRiskConfirmed] = useState(false);
  const [advancedRiskAcknowledgement, setAdvancedRiskAcknowledgement] =
    useState("");
  const advancedProfileSelected =
    profileId === "AGGRESSIVE" || profileId === "BLEED_THROUGH";

  useEffect(() => {
    if (!advancedProfileSelected) {
      setAdvancedRiskConfirmed(false);
      setAdvancedRiskAcknowledgement("");
    }
  }, [advancedProfileSelected]);

  async function triggerCreate() {
    if (advancedProfileSelected && !advancedRiskConfirmed) {
      setError("Confirm advanced full-document risk posture before queueing.");
      setSuccess(null);
      return;
    }
    setPendingAction("create");
    setError(null);
    setSuccess(null);
    const result = await requestBrowserApi<{ id: string }>({
      method: "POST",
      path: `/projects/${projectId}/documents/${documentId}/preprocess-runs`,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profileId,
        advancedRiskConfirmed: advancedProfileSelected
          ? advancedRiskConfirmed
          : undefined,
        advancedRiskAcknowledgement: advancedProfileSelected
          ? advancedRiskAcknowledgement.trim() || ADVANCED_RISK_CONFIRMATION_COPY
          : undefined
      })
    });
    setPendingAction(null);
    if (!result.ok || !result.data) {
      setError(result.detail ?? "Preprocessing run creation failed.");
      return;
    }
    setSuccess("Preprocessing run queued.");
    router.push(
      projectDocumentPreprocessingRunPath(projectId, documentId, result.data.id)
    );
    router.refresh();
  }

  async function triggerRerun() {
    if (!runId) {
      return;
    }
    if (advancedProfileSelected && !advancedRiskConfirmed) {
      setError("Confirm advanced full-document risk posture before queueing.");
      setSuccess(null);
      return;
    }
    setPendingAction("rerun");
    setError(null);
    setSuccess(null);
    const result = await requestBrowserApi<{ id: string }>({
      method: "POST",
      path: `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}/rerun`,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profileId,
        advancedRiskConfirmed: advancedProfileSelected
          ? advancedRiskConfirmed
          : undefined,
        advancedRiskAcknowledgement: advancedProfileSelected
          ? advancedRiskAcknowledgement.trim() || ADVANCED_RISK_CONFIRMATION_COPY
          : undefined
      })
    });
    setPendingAction(null);
    if (!result.ok || !result.data) {
      setError(result.detail ?? "Preprocessing rerun request failed.");
      return;
    }
    setSuccess("Rerun queued.");
    router.push(
      projectDocumentPreprocessingRunPath(projectId, documentId, result.data.id)
    );
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
      path: `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}/cancel`
    });
    setPendingAction(null);
    if (!result.ok) {
      setError(result.detail ?? "Preprocessing cancel request failed.");
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
      path: `/projects/${projectId}/documents/${documentId}/preprocess-runs/${runId}/activate`
    });
    setPendingAction(null);
    if (!result.ok) {
      setError(result.detail ?? "Preprocess run activation failed.");
      return;
    }
    setSuccess("Run activated for document projection.");
    router.refresh();
  }

  if (!canMutate) {
    return null;
  }

  return (
    <section className="sectionCard ukde-panel">
      <h3>Run actions</h3>
      <details className="preprocessRunAdvancedControls">
        <summary>Advanced profile controls</summary>
        <label>
          Profile
          <select
            value={profileId}
            onChange={(event) =>
              setProfileId(event.target.value as PreprocessProfileId)
            }
          >
            <option value="BALANCED">Balanced</option>
            <option value="CONSERVATIVE">Conservative</option>
            <option value="AGGRESSIVE">Aggressive (Advanced)</option>
            <option value="BLEED_THROUGH">Bleed-through (Advanced)</option>
          </select>
        </label>
        <p className="ukde-muted">{PROFILE_DESCRIPTIONS[profileId]}</p>
        {advancedProfileSelected ? (
          <>
            <p className="ukde-muted">{ADVANCED_RISK_CONFIRMATION_COPY}</p>
            <label className="qualityWizardChoice">
              <input
                type="checkbox"
                checked={advancedRiskConfirmed}
                onChange={(event) =>
                  setAdvancedRiskConfirmed(event.target.checked)
                }
              />
              I confirm advanced full-document processing for this run.
            </label>
            <label>
              Confirmation note (optional)
              <input
                type="text"
                maxLength={400}
                value={advancedRiskAcknowledgement}
                onChange={(event) =>
                  setAdvancedRiskAcknowledgement(event.target.value)
                }
                placeholder="Reason for stronger cleanup"
              />
            </label>
          </>
        ) : null}
      </details>
      <div className="buttonRow">
        {!runId ? (
          <button
            className="secondaryButton"
            type="button"
            disabled={
              pendingAction !== null ||
              (advancedProfileSelected && !advancedRiskConfirmed)
            }
            onClick={() => {
              void triggerCreate();
            }}
          >
            {pendingAction === "create" ? "Queueing..." : "Run preprocessing"}
          </button>
        ) : null}
        {runId ? (
          <button
            className="secondaryButton"
            type="button"
            disabled={
              pendingAction !== null ||
              (advancedProfileSelected && !advancedRiskConfirmed)
            }
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
        <InlineAlert title="Preprocessing action failed" tone="danger">
          {error}
        </InlineAlert>
      ) : null}
      {success ? (
        <InlineAlert title="Preprocessing action completed" tone="success">
          {success}
        </InlineAlert>
      ) : null}
    </section>
  );
}
