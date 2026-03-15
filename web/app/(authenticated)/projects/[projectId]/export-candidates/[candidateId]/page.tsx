import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import {
  getExportCandidate,
  getExportCandidateReleasePackPreview
} from "../../../../../../lib/exports";
import { getProjectSummary } from "../../../../../../lib/projects";
import { normalizeOptionalTextParam } from "../../../../../../lib/url-state";

export const dynamic = "force-dynamic";

export default async function ProjectExportCandidateDetailPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; candidateId: string }>;
  searchParams: Promise<{
    purposeStatement?: string;
    bundleProfile?: string;
  }>;
}>) {
  const { projectId, candidateId } = await params;
  const query = await searchParams;
  const purposeStatement = normalizeOptionalTextParam(query.purposeStatement);
  const bundleProfile = normalizeOptionalTextParam(query.bundleProfile);

  const [projectResult, candidateResult, previewResult] = await Promise.all([
    getProjectSummary(projectId),
    getExportCandidate(projectId, candidateId),
    getExportCandidateReleasePackPreview(projectId, candidateId, {
      purposeStatement: purposeStatement ?? undefined,
      bundleProfile: bundleProfile ?? undefined
    })
  ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }

  if (!candidateResult.ok || !candidateResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Candidate not available"
            description={candidateResult.detail ?? "Unknown failure"}
          />
          <div className="buttonRow">
            <Link
              className="secondaryButton"
              href={`/projects/${projectId}/export-candidates`}
            >
              Back to candidates
            </Link>
          </div>
        </section>
      </main>
    );
  }

  const candidate = candidateResult.data;
  const preview = previewResult.ok ? previewResult.data : null;
  const previewFiles = Array.isArray(preview?.releasePack?.files)
    ? preview.releasePack.files
    : [];

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">Export candidate detail</h1>
        <p className="ukde-muted">
          Candidate snapshots remain immutable and are resolved from pinned lineage.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-candidates`}
          >
            Back to candidates
          </Link>
          <Link
            className="projectPrimaryButton"
            href={`/projects/${projectId}/export-requests/new?candidateId=${encodeURIComponent(candidate.id)}`}
          >
            Create request
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <div className="detailGrid">
          <div>
            <h2 className="sectionTitle">Candidate</h2>
            <p className="ukde-muted">
              <code>{candidate.id}</code>
            </p>
            <p className="ukde-muted">Kind: {candidate.candidateKind}</p>
            <p className="ukde-muted">Source phase: {candidate.sourcePhase}</p>
            <p className="ukde-muted">Source artifact: {candidate.sourceArtifactKind}</p>
            <p className="ukde-muted">Eligibility: {candidate.eligibilityStatus}</p>
            <p className="ukde-muted">Candidate hash: {candidate.candidateSha256}</p>
          </div>
          <div>
            <h2 className="sectionTitle">Pinned lineage</h2>
            <p className="ukde-muted">Policy snapshot: {candidate.policySnapshotHash ?? "None"}</p>
            <p className="ukde-muted">
              Governance manifest hash: {candidate.governanceManifestSha256 ?? "None"}
            </p>
            <p className="ukde-muted">
              Governance ledger hash: {candidate.governanceLedgerSha256 ?? "None"}
            </p>
          </div>
        </div>
      </section>

      {!previewResult.ok || !preview ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Release-pack preview unavailable"
            description={previewResult.detail ?? "Unknown failure"}
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Release-pack preview</h2>
          <p className="ukde-muted">
            Risk {preview.riskClassification} ({preview.reviewPath}) ·
            {" "}
            {preview.requiresSecondReview ? "Second review required" : "Single review path"}
          </p>
          <p className="ukde-muted">
            Preview hash: <code>{preview.releasePackSha256}</code>
          </p>
          <p className="ukde-muted">
            Reason codes: {preview.riskReasonCodes.length ? preview.riskReasonCodes.join(", ") : "None"}
          </p>
          {previewFiles.length === 0 ? (
            <SectionState
              kind="empty"
              title="No files listed"
              description="The preview pack is pinned but does not expose file-level entries."
            />
          ) : (
            <table className="ukde-data-table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Size</th>
                  <th>Hash</th>
                </tr>
              </thead>
              <tbody>
                {previewFiles.slice(0, 20).map((item, index) => (
                  <tr key={`${index}-${String((item as Record<string, unknown>).fileName ?? "file")}`}>
                    <td>{String((item as Record<string, unknown>).fileName ?? "candidate-file")}</td>
                    <td>{String((item as Record<string, unknown>).fileSizeBytes ?? 0)}</td>
                    <td>
                      <code>{String((item as Record<string, unknown>).sha256 ?? "")}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </main>
  );
}
