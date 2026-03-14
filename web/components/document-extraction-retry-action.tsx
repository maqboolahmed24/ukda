"use client";

import { useState } from "react";
import { InlineAlert } from "@ukde/ui/primitives";

import { requestBrowserApi } from "../lib/data/browser-api-client";

interface DocumentExtractionRetryActionProps {
  documentId: string;
  projectId: string;
}

export function DocumentExtractionRetryAction({
  documentId,
  projectId
}: DocumentExtractionRetryActionProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleRetry() {
    setError(null);
    setSuccess(null);
    setIsSubmitting(true);
    const result = await requestBrowserApi({
      method: "POST",
      path: `/projects/${projectId}/documents/${documentId}/retry-extraction`
    });
    setIsSubmitting(false);
    if (!result.ok) {
      setError(result.detail ?? "Extraction retry request failed.");
      return;
    }
    setSuccess("Extraction retry was queued. Timeline polling will reflect the new attempt.");
  }

  return (
    <div className="buttonRow">
      <button
        className="secondaryButton"
        type="button"
        onClick={handleRetry}
        disabled={isSubmitting}
      >
        {isSubmitting ? "Queueing retry..." : "Retry extraction"}
      </button>
      {error ? (
        <InlineAlert title="Retry request failed" tone="danger">
          {error}
        </InlineAlert>
      ) : null}
      {success ? (
        <InlineAlert title="Retry queued" tone="success">
          {success}
        </InlineAlert>
      ) : null}
    </div>
  );
}
