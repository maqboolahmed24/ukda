import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import {
  getExportRequest,
  getExportRequestCurrentProvenanceProof,
  getExportRequestProvenanceProof,
  getExportRequestProvenanceSummary,
  listExportRequestProvenanceProofs
} from "../../../../../../../lib/exports";
import { getProjectSummary } from "../../../../../../../lib/projects";

export const dynamic = "force-dynamic";

function normalizeOptionalTextParam(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    const first = value.find((item) => typeof item === "string" && item.trim().length > 0);
    return first ? first.trim() : null;
  }
  if (typeof value === "string") {
    const normalized = value.trim();
    return normalized.length > 0 ? normalized : null;
  }
  return null;
}

export default async function ExportRequestProvenancePage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; exportRequestId: string }>;
  searchParams: Promise<{ proofId?: string | string[] }>;
}>) {
  const { projectId, exportRequestId } = await params;
  const query = await searchParams;
  const selectedProofId = normalizeOptionalTextParam(query.proofId);

  const [projectResult, requestResult, summaryResult, proofsResult, currentProofResult] =
    await Promise.all([
      getProjectSummary(projectId),
      getExportRequest(projectId, exportRequestId),
      getExportRequestProvenanceSummary(projectId, exportRequestId),
      listExportRequestProvenanceProofs(projectId, exportRequestId),
      getExportRequestCurrentProvenanceProof(projectId, exportRequestId)
    ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }

  if (!requestResult.ok || !requestResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Export request unavailable"
            description={requestResult.detail ?? "Request could not be loaded."}
          />
        </section>
      </main>
    );
  }

  const request = requestResult.data;
  const proofs = proofsResult.ok && proofsResult.data ? proofsResult.data.items : [];
  const summary = summaryResult.ok && summaryResult.data ? summaryResult.data : null;
  const currentProof =
    currentProofResult.ok && currentProofResult.data ? currentProofResult.data : null;

  const selectedProofResult =
    selectedProofId !== null
      ? await getExportRequestProvenanceProof(projectId, exportRequestId, selectedProofId)
      : currentProofResult;
  const selectedProof =
    selectedProofResult.ok && selectedProofResult.data ? selectedProofResult.data : null;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">Provenance summary</h1>
        <p className="ukde-muted">
          Export request <code>{request.id}</code> revision {request.requestRevision}
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}`}
          >
            Back to request
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/events`}
          >
            Request events
          </Link>
        </div>
      </section>

      {!summary ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Provenance summary unavailable"
            description={summaryResult.detail ?? "Provenance summary could not be loaded."}
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Current lineage anchor</h2>
          <p className="ukde-muted">Signature status: {summary.signatureStatus}</p>
          <p className="ukde-muted">
            Current proof id: {summary.currentProofId ? <code>{summary.currentProofId}</code> : "None"}
          </p>
          <p className="ukde-muted">
            Current attempt:{" "}
            {typeof summary.currentAttemptNumber === "number" ? summary.currentAttemptNumber : "None"}
          </p>
          <p className="ukde-muted">
            Root SHA-256: {summary.rootSha256 ? <code>{summary.rootSha256}</code> : "Unavailable"}
          </p>
          <p className="ukde-muted">
            Signature key ref:{" "}
            {summary.signatureKeyRef ? <code>{summary.signatureKeyRef}</code> : "Unavailable"}
          </p>
          <p className="ukde-muted">Proof attempts: {summary.proofAttemptCount}</p>
          <p className="ukde-muted">
            Manifest ref:{" "}
            {typeof summary.references.manifestId === "string" ? (
              <code>{summary.references.manifestId}</code>
            ) : (
              "None"
            )}
          </p>
          <p className="ukde-muted">
            Policy ref:{" "}
            {typeof summary.references.policySnapshotHash === "string" ? (
              <code>{summary.references.policySnapshotHash}</code>
            ) : (
              "None"
            )}
          </p>
        </section>
      )}

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Lineage nodes</h2>
        {summary && summary.lineageNodes.length > 0 ? (
          <div className="ukde-list">
            {summary.lineageNodes.map((node) => (
              <div className="ukde-list-item" key={`${node.artifactKind}:${node.stableIdentifier}`}>
                <p className="ukde-muted">
                  <strong>{node.artifactKind}</strong> <code>{node.stableIdentifier}</code>
                </p>
                <p className="ukde-muted">
                  Immutable reference <code>{node.immutableReference}</code>
                </p>
                <p className="ukde-muted">
                  Parents:{" "}
                  {node.parentReferences.length > 0 ? (
                    node.parentReferences.map((parent) => (
                      <code key={parent} style={{ marginRight: "0.5rem" }}>
                        {parent}
                      </code>
                    ))
                  ) : (
                    "None"
                  )}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <SectionState
            kind="loading"
            title="No lineage nodes"
            description="No canonical leaves are currently available for this request."
          />
        )}
      </section>

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Proof attempts</h2>
        {proofs.length === 0 ? (
          <SectionState
            kind="loading"
            title="No attempts yet"
            description="A proof attempt is generated once the request is approved."
          />
        ) : (
          <div className="ukde-list">
            {proofs.map((proof) => (
              <div className="ukde-list-item" key={proof.id}>
                <p className="ukde-muted">
                  Attempt {proof.attemptNumber} <code>{proof.id}</code>
                </p>
                <p className="ukde-muted">
                  Root <code>{proof.rootSha256}</code>
                </p>
                <p className="ukde-muted">
                  Supersedes: {proof.supersedesProofId ? <code>{proof.supersedesProofId}</code> : "None"}
                </p>
                <p className="ukde-muted">
                  Superseded by:{" "}
                  {proof.supersededByProofId ? <code>{proof.supersededByProofId}</code> : "Current"}
                </p>
                <Link
                  className="secondaryButton"
                  href={`/projects/${projectId}/export-requests/${request.id}/provenance?proofId=${encodeURIComponent(proof.id)}`}
                >
                  Open attempt
                </Link>
              </div>
            ))}
          </div>
        )}
      </section>

      {!selectedProof ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Selected proof unavailable"
            description={selectedProofResult.detail ?? "Proof detail could not be loaded."}
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Selected proof detail</h2>
          <p className="ukde-muted">
            Proof id <code>{selectedProof.proof.id}</code>
          </p>
          <p className="ukde-muted">
            Artifact key <code>{selectedProof.proof.proofArtifactKey}</code>
          </p>
          <p className="ukde-muted">
            Artifact SHA-256 <code>{selectedProof.proof.proofArtifactSha256}</code>
          </p>
          <pre className="ukde-json-panel">{JSON.stringify(selectedProof.artifact, null, 2)}</pre>
        </section>
      )}

      {currentProof && currentProof.proof.supersededByProofId !== null ? null : (
        <section className="sectionCard ukde-panel">
          <p className="ukde-muted">
            Regeneration is available via <code>POST /provenance/proofs/regenerate</code> for{" "}
            <code>ADMIN</code> users.
          </p>
        </section>
      )}
    </main>
  );
}
