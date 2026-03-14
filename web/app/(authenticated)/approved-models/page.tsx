import { redirect } from "next/navigation";

import { SectionState } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../lib/auth/session";
import { listApprovedModels } from "../../../lib/model-assignments";
import { listMyProjects } from "../../../lib/projects";

export const dynamic = "force-dynamic";

function checksumPreview(value: string): string {
  if (value.length <= 16) {
    return value;
  }
  return `${value.slice(0, 8)}…${value.slice(-8)}`;
}

export default async function ApprovedModelsPage({
  searchParams
}: Readonly<{
  searchParams: Promise<{ status?: string }>;
}>) {
  const [session, projects, modelsResult, query] = await Promise.all([
    requireCurrentSession(),
    listMyProjects(),
    listApprovedModels(),
    searchParams
  ]);

  const canCreate =
    session.user.platformRoles.includes("ADMIN") ||
    projects.some((project) => project.currentUserRole === "PROJECT_LEAD");

  if (!modelsResult.ok) {
    if (modelsResult.status === 403) {
      redirect("/projects?error=approved-models-access");
    }
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Approved model catalog unavailable"
          description={modelsResult.detail ?? "Catalog read failed."}
        />
      </main>
    );
  }

  const models = modelsResult.data?.items ?? [];
  const statusFlag =
    typeof query.status === "string" ? query.status.trim() : "";

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Platform model catalog</p>
        <h2>Approved internal models</h2>
        <p className="ukde-muted">
          Stable role-map catalog for transcription primary, fallback, and
          reviewer-assist deployments.
        </p>
      </section>

      {statusFlag === "created" ? (
        <section className="sectionCard ukde-panel">
          <p className="ukde-muted">Approved model created successfully.</p>
        </section>
      ) : null}

      {statusFlag === "create-failed" ? (
        <section className="sectionCard ukde-panel">
          <p className="ukde-muted">
            Approved model creation failed. Verify role and checksum inputs.
          </p>
        </section>
      ) : null}

      {canCreate ? (
        <section className="sectionCard ukde-panel">
          <h3>Add approved model</h3>
          <form action="/approved-models/create" className="jobsCreateForm" method="post">
            <label>
              Model type
              <select defaultValue="VLM" name="model_type">
                <option value="VLM">VLM</option>
                <option value="LLM">LLM</option>
                <option value="HTR">HTR</option>
              </select>
            </label>
            <label>
              Model role
              <select defaultValue="TRANSCRIPTION_PRIMARY" name="model_role">
                <option value="TRANSCRIPTION_PRIMARY">TRANSCRIPTION_PRIMARY</option>
                <option value="TRANSCRIPTION_FALLBACK">TRANSCRIPTION_FALLBACK</option>
                <option value="ASSIST">ASSIST</option>
              </select>
            </label>
            <label>
              Family
              <input name="model_family" required type="text" />
            </label>
            <label>
              Version
              <input name="model_version" required type="text" />
            </label>
            <label>
              Serving interface
              <select defaultValue="OPENAI_CHAT" name="serving_interface">
                <option value="OPENAI_CHAT">OPENAI_CHAT</option>
                <option value="OPENAI_EMBEDDING">OPENAI_EMBEDDING</option>
                <option value="ENGINE_NATIVE">ENGINE_NATIVE</option>
                <option value="RULES_NATIVE">RULES_NATIVE</option>
              </select>
            </label>
            <label>
              Engine family
              <input name="engine_family" required type="text" />
            </label>
            <label>
              Deployment unit
              <input name="deployment_unit" required type="text" />
            </label>
            <label>
              Artifact subpath
              <input name="artifact_subpath" required type="text" />
            </label>
            <label>
              SHA256 checksum
              <input
                maxLength={64}
                minLength={64}
                name="checksum_sha256"
                required
                type="text"
              />
            </label>
            <label>
              Runtime profile
              <input defaultValue="default" name="runtime_profile" required type="text" />
            </label>
            <label>
              Response contract version
              <input
                defaultValue="v1"
                name="response_contract_version"
                required
                type="text"
              />
            </label>
            <button className="projectPrimaryButton" type="submit">
              Create approved model
            </button>
          </form>
        </section>
      ) : null}

      <section className="sectionCard ukde-panel">
        {models.length === 0 ? (
          <SectionState
            kind="empty"
            title="No approved models"
            description="No approved model rows are currently available."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Role</th>
                  <th>Type</th>
                  <th>Family</th>
                  <th>Version</th>
                  <th>Engine</th>
                  <th>Interface</th>
                  <th>Runtime</th>
                  <th>Status</th>
                  <th>Checksum</th>
                </tr>
              </thead>
              <tbody>
                {models.map((model) => (
                  <tr key={model.id}>
                    <td>{model.id}</td>
                    <td>{model.modelRole}</td>
                    <td>{model.modelType}</td>
                    <td>{model.modelFamily}</td>
                    <td>{model.modelVersion}</td>
                    <td>{model.engineFamily}</td>
                    <td>{model.servingInterface}</td>
                    <td>{model.runtimeProfile}</td>
                    <td>{model.status}</td>
                    <td>{checksumPreview(model.checksumSha256)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
