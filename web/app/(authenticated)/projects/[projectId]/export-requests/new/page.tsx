import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import {
  createExportRequest,
  getExportCandidate,
  getExportCandidateReleasePackPreview,
  getExportRequest,
  resubmitExportRequest
} from "../../../../../../lib/exports";
import { getProjectSummary } from "../../../../../../lib/projects";
import { normalizeOptionalTextParam } from "../../../../../../lib/url-state";

export const dynamic = "force-dynamic";

export default async function ProjectExportRequestNewPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{
    candidateId?: string;
    supersedesExportRequestId?: string;
    error?: string;
  }>;
}>) {
  const { projectId } = await params;
  const query = await searchParams;
  const candidateId = normalizeOptionalTextParam(query.candidateId);
  const supersedesExportRequestId = normalizeOptionalTextParam(
    query.supersedesExportRequestId
  );

  const [projectResult, candidateResult, supersededResult] = await Promise.all([
    getProjectSummary(projectId),
    candidateId ? getExportCandidate(projectId, candidateId) : Promise.resolve(null),
    supersedesExportRequestId
      ? getExportRequest(projectId, supersedesExportRequestId)
      : Promise.resolve(null)
  ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }

  const previewResult =
    candidateResult && candidateResult.ok && candidateResult.data
      ? await getExportCandidateReleasePackPreview(projectId, candidateResult.data.id)
      : null;

  const submitAction = async (formData: FormData) => {
    "use server";
    const currentProjectId = String(formData.get("projectId") ?? "").trim();
    const currentCandidateId = String(formData.get("candidateId") ?? "").trim();
    const currentPurpose = String(formData.get("purposeStatement") ?? "");
    const currentBundleProfile = String(formData.get("bundleProfile") ?? "").trim();
    const currentSupersedes = String(
      formData.get("supersedesExportRequestId") ?? ""
    ).trim();

    if (!currentProjectId || !currentCandidateId || !currentPurpose) {
      redirect(
        `/projects/${projectId}/export-requests/new?candidateId=${encodeURIComponent(currentCandidateId)}&error=missing-fields`
      );
    }

    if (currentSupersedes) {
      const result = await resubmitExportRequest(currentProjectId, currentSupersedes, {
        candidateSnapshotId: currentCandidateId,
        purposeStatement: currentPurpose,
        bundleProfile: currentBundleProfile || undefined
      });
      if (!result.ok || !result.data) {
        redirect(
          `/projects/${projectId}/export-requests/new?candidateId=${encodeURIComponent(currentCandidateId)}&supersedesExportRequestId=${encodeURIComponent(currentSupersedes)}&error=resubmit-failed`
        );
      }
      redirect(`/projects/${projectId}/export-requests/${result.data.id}`);
    }

    const result = await createExportRequest(currentProjectId, {
      candidateSnapshotId: currentCandidateId,
      purposeStatement: currentPurpose,
      bundleProfile: currentBundleProfile || undefined
    });
    if (!result.ok || !result.data) {
      redirect(
        `/projects/${projectId}/export-requests/new?candidateId=${encodeURIComponent(currentCandidateId)}&error=submit-failed`
      );
    }
    redirect(`/projects/${projectId}/export-requests/${result.data.id}`);
  };

  if (!candidateId) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="Choose a candidate first"
            description="Open this page from an eligible export candidate to submit a request."
          />
          <div className="buttonRow">
            <Link
              className="secondaryButton"
              href={`/projects/${projectId}/export-candidates`}
            >
              Browse candidates
            </Link>
          </div>
        </section>
      </main>
    );
  }

  if (!candidateResult || !candidateResult.ok || !candidateResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Candidate unavailable"
            description={candidateResult?.detail ?? "Candidate lookup failed."}
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
  const preview =
    previewResult && previewResult.ok && previewResult.data ? previewResult.data : null;
  const superseded =
    supersededResult && supersededResult.ok && supersededResult.data
      ? supersededResult.data
      : null;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">
          {superseded ? "Resubmit export request" : "New export request"}
        </h1>
        <p className="ukde-muted">
          Submission freezes a request-scoped release pack. Later review reads that
          immutable frozen pack.
        </p>
        {query.error ? (
          <SectionState
            kind="error"
            title="Submission failed"
            description={`Request could not be submitted (${query.error}).`}
          />
        ) : null}
      </section>

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Candidate selection</h2>
        <p className="ukde-muted">
          Candidate <code>{candidate.id}</code> ({candidate.candidateKind})
        </p>
        {superseded ? (
          <p className="ukde-muted">
            Supersedes request <code>{superseded.id}</code> revision{" "}
            {superseded.requestRevision}.
          </p>
        ) : null}
      </section>

      <section className="sectionCard ukde-panel">
        <form action={submitAction} className="ukde-form-stack">
          <input name="projectId" type="hidden" value={projectId} />
          <input name="candidateId" type="hidden" value={candidate.id} />
          <input
            name="supersedesExportRequestId"
            type="hidden"
            value={superseded?.id ?? ""}
          />

          <label className="ukde-form-label" htmlFor="purposeStatement">
            Purpose statement
          </label>
          <textarea
            className="ukde-input"
            defaultValue={superseded?.purposeStatement ?? ""}
            id="purposeStatement"
            name="purposeStatement"
            required
            rows={6}
          />

          <label className="ukde-form-label" htmlFor="bundleProfile">
            Bundle profile (optional)
          </label>
          <input
            className="ukde-input"
            defaultValue={superseded?.bundleProfile ?? ""}
            id="bundleProfile"
            name="bundleProfile"
            type="text"
          />

          <div className="buttonRow">
            <button className="projectPrimaryButton" type="submit">
              {superseded ? "Submit successor revision" : "Submit export request"}
            </button>
            <Link
              className="secondaryButton"
              href={`/projects/${projectId}/export-candidates/${candidate.id}`}
            >
              Back to candidate
            </Link>
          </div>
        </form>
      </section>

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Pinned release-pack preview</h2>
        {!preview ? (
          <SectionState
            kind="error"
            title="Preview unavailable"
            description={previewResult?.detail ?? "Preview lookup failed."}
          />
        ) : (
          <>
            <p className="ukde-muted">
              Risk {preview.riskClassification} ({preview.reviewPath}) ·{" "}
              {preview.requiresSecondReview
                ? "requires second review"
                : "single review path"}
            </p>
            <p className="ukde-muted">
              Reason codes:{" "}
              {preview.riskReasonCodes.length
                ? preview.riskReasonCodes.join(", ")
                : "None"}
            </p>
            <p className="ukde-muted">
              Preview hash <code>{preview.releasePackSha256}</code>
            </p>
          </>
        )}
      </section>
    </main>
  );
}
