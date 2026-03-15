import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../../../../../lib/auth/session";
import {
  cancelExportRequestBundleValidationRun,
  getExportRequest,
  getExportRequestBundle,
  getExportRequestBundleValidationRun,
  getExportRequestBundleValidationStatus,
  listExportRequestBundleProfiles,
  listExportRequestBundleValidationRuns,
  startExportRequestBundleValidation
} from "../../../../../../../../../lib/exports";
import { getProjectSummary } from "../../../../../../../../../lib/projects";

export const dynamic = "force-dynamic";

function parseOptionalText(value: string | undefined): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : undefined;
}

function buildValidationHref(
  projectId: string,
  exportRequestId: string,
  bundleId: string,
  profileId: string,
  options?: {
    error?: string;
    notice?: string;
    runId?: string;
  }
): string {
  const params = new URLSearchParams();
  params.set("profile", profileId);
  if (options?.runId && options.runId.trim().length > 0) {
    params.set("runId", options.runId.trim());
  }
  if (options?.notice && options.notice.trim().length > 0) {
    params.set("notice", options.notice.trim());
  }
  if (options?.error && options.error.trim().length > 0) {
    params.set("error", options.error.trim());
  }
  return `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/validation?${params.toString()}`;
}

function resolveStatusTone(
  status: "CANCELED" | "FAILED" | "PENDING" | "QUEUED" | "READY" | "RUNNING" | "SUCCEEDED"
): "danger" | "neutral" | "success" | "warning" {
  if (status === "SUCCEEDED" || status === "READY") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "CANCELED") {
    return "neutral";
  }
  return "warning";
}

function canCancel(status: string): boolean {
  return status === "QUEUED" || status === "RUNNING";
}

export default async function ExportRequestBundleValidationPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; exportRequestId: string; bundleId: string }>;
  searchParams: Promise<{ error?: string; notice?: string; profile?: string; runId?: string }>;
}>) {
  const { projectId, exportRequestId, bundleId } = await params;
  const query = await searchParams;
  const session = await requireCurrentSession();
  const isAdmin = session.user.platformRoles.includes("ADMIN");

  const requestedProfile = parseOptionalText(query.profile);
  const selectedRunId = parseOptionalText(query.runId);
  const notice = parseOptionalText(query.notice);
  const error = parseOptionalText(query.error);

  const [projectResult, requestResult, bundleResult, profilesResult] = await Promise.all([
    getProjectSummary(projectId),
    getExportRequest(projectId, exportRequestId),
    getExportRequestBundle(projectId, exportRequestId, bundleId),
    listExportRequestBundleProfiles(projectId, exportRequestId, bundleId)
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
  if (!bundleResult.ok || !bundleResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Bundle unavailable"
            description={bundleResult.detail ?? "Bundle detail could not be loaded."}
          />
        </section>
      </main>
    );
  }
  if (!profilesResult.ok || !profilesResult.data || profilesResult.data.items.length === 0) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Bundle profiles unavailable"
            description={profilesResult.detail ?? "No bundle validation profiles were returned."}
          />
        </section>
      </main>
    );
  }

  const request = requestResult.data;
  const bundle = bundleResult.data.bundle;
  const profiles = profilesResult.data.items;
  const selectedProfileId =
    profiles.find((item) => item.id === requestedProfile)?.id ?? profiles[0].id;

  const [statusResult, runsResult, selectedRunResult] = await Promise.all([
    getExportRequestBundleValidationStatus(
      projectId,
      exportRequestId,
      bundleId,
      selectedProfileId
    ),
    listExportRequestBundleValidationRuns(
      projectId,
      exportRequestId,
      bundleId,
      selectedProfileId
    ),
    selectedRunId
      ? getExportRequestBundleValidationRun(
          projectId,
          exportRequestId,
          bundleId,
          selectedRunId,
          selectedProfileId
        )
      : Promise.resolve(null)
  ]);

  if (!statusResult.ok || !statusResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Validation status unavailable"
            description={statusResult.detail ?? "Validation status could not be loaded."}
          />
        </section>
      </main>
    );
  }

  const status = statusResult.data;
  const runs = runsResult.ok && runsResult.data ? runsResult.data.items : [];
  const selectedRun =
    (selectedRunResult && selectedRunResult.ok && selectedRunResult.data
      ? selectedRunResult.data.validationRun
      : null) ??
    status.latestAttempt ??
    null;

  async function triggerValidationAction(formData: FormData) {
    "use server";
    if (!isAdmin) {
      redirect(
        buildValidationHref(projectId, exportRequestId, bundleId, selectedProfileId, {
          error: "admin_only"
        })
      );
    }
    const profileId = String(formData.get("profileId") ?? "").trim();
    if (!profileId) {
      redirect(
        buildValidationHref(projectId, exportRequestId, bundleId, selectedProfileId, {
          error: "profile_required"
        })
      );
    }
    const result = await startExportRequestBundleValidation(
      projectId,
      exportRequestId,
      bundleId,
      profileId
    );
    if (!result.ok || !result.data) {
      redirect(
        buildValidationHref(projectId, exportRequestId, bundleId, profileId, {
          error: "validate_failed"
        })
      );
    }
    redirect(
      buildValidationHref(projectId, exportRequestId, bundleId, profileId, {
        notice: "validation_requested",
        runId: result.data.validationRun.id
      })
    );
  }

  async function cancelValidationAction(formData: FormData) {
    "use server";
    if (!isAdmin) {
      redirect(
        buildValidationHref(projectId, exportRequestId, bundleId, selectedProfileId, {
          error: "admin_only"
        })
      );
    }
    const runId = String(formData.get("runId") ?? "").trim();
    if (!runId) {
      redirect(
        buildValidationHref(projectId, exportRequestId, bundleId, selectedProfileId, {
          error: "run_required"
        })
      );
    }
    const result = await cancelExportRequestBundleValidationRun(
      projectId,
      exportRequestId,
      bundleId,
      runId,
      selectedProfileId
    );
    if (!result.ok || !result.data) {
      redirect(
        buildValidationHref(projectId, exportRequestId, bundleId, selectedProfileId, {
          runId,
          error: "cancel_failed"
        })
      );
    }
    redirect(
      buildValidationHref(projectId, exportRequestId, bundleId, selectedProfileId, {
        runId,
        notice: "validation_canceled"
      })
    );
  }

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">Bundle validation</h1>
        <p className="ukde-muted">
          Bundle <code>{bundle.id}</code> ({bundle.bundleKind}) profile{" "}
          <code>{selectedProfileId}</code>
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/bundles/${bundle.id}`}
          >
            Back to bundle
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/bundles/${bundle.id}/verification`}
          >
            Verification
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/bundles/${bundle.id}/events`}
          >
            Events
          </Link>
        </div>
      </section>

      {notice ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="success"
            title="Validation updated"
            description={
              notice === "validation_requested"
                ? "A new validation attempt has been appended."
                : "The selected validation attempt was canceled."
            }
          />
        </section>
      ) : null}

      {error ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Validation action failed"
            description={
              error === "admin_only"
                ? "Only ADMIN can start or cancel bundle validation runs."
                : error === "profile_required"
                ? "A validation profile is required."
                : error === "run_required"
                ? "A validation run id is required."
                : "Validation action could not be completed."
            }
          />
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Status</h2>
        <p className="ukde-muted">
          Bundle status: <StatusChip tone={resolveStatusTone(status.bundleStatus)}>{status.bundleStatus}</StatusChip>
        </p>
        <p className="ukde-muted">
          Verification projection:{" "}
          {status.verificationProjection ? status.verificationProjection.status : "PENDING"}
        </p>
        <p className="ukde-muted">
          Validation projection:{" "}
          {status.validationProjection ? status.validationProjection.status : "PENDING"}
        </p>
        <p className="ukde-muted">
          Last successful attempt:{" "}
          {status.lastSuccessfulAttempt ? (
            <code>{status.lastSuccessfulAttempt.id}</code>
          ) : (
            "None"
          )}
        </p>
        <p className="ukde-muted">
          In-flight attempt:{" "}
          {status.inFlightAttempt ? <code>{status.inFlightAttempt.id}</code> : "None"}
        </p>
      </section>

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Profile</h2>
        <div className="buttonRow">
          {profiles.map((profile) => (
            <Link
              key={profile.id}
              className="secondaryButton"
              href={buildValidationHref(
                projectId,
                exportRequestId,
                bundleId,
                profile.id
              )}
            >
              {profile.id}
            </Link>
          ))}
        </div>
        <p className="ukde-muted">
          {profiles.find((item) => item.id === selectedProfileId)?.description}
        </p>
        {isAdmin ? (
          <form action={triggerValidationAction} className="buttonRow">
            <input name="profileId" type="hidden" value={selectedProfileId} />
            <button className="secondaryButton" type="submit">
              Start validation
            </button>
          </form>
        ) : null}
      </section>

      {!runsResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Validation runs unavailable"
            description={runsResult.detail ?? "Validation runs could not be loaded."}
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Run history</h2>
          {runs.length === 0 ? (
            <SectionState
              kind="loading"
              title="No validation runs yet"
              description="Start a validation run to capture deposit-profile readiness evidence."
            />
          ) : (
            <div className="ukde-list">
              {runs.map((run) => (
                <div className="ukde-list-item" key={run.id}>
                  <p className="ukde-muted">
                    Attempt {run.attemptNumber} <code>{run.id}</code>
                  </p>
                  <p className="ukde-muted">
                    <StatusChip tone={resolveStatusTone(run.status)}>{run.status}</StatusChip>
                  </p>
                  <p className="ukde-muted">
                    Snapshot <code>{run.profileSnapshotSha256}</code>
                  </p>
                  <div className="buttonRow">
                    <Link
                      className="secondaryButton"
                      href={buildValidationHref(
                        projectId,
                        exportRequestId,
                        bundleId,
                        selectedProfileId,
                        { runId: run.id }
                      )}
                    >
                      Inspect
                    </Link>
                    {isAdmin && canCancel(run.status) ? (
                      <form action={cancelValidationAction}>
                        <input name="runId" type="hidden" value={run.id} />
                        <button className="secondaryButton" type="submit">
                          Cancel
                        </button>
                      </form>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {selectedRun ? (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Selected run evidence</h2>
          <p className="ukde-muted">
            Run <code>{selectedRun.id}</code> ({selectedRun.status})
          </p>
          <pre className="ukde-json-panel">{JSON.stringify(selectedRun.resultJson, null, 2)}</pre>
        </section>
      ) : null}
    </main>
  );
}

