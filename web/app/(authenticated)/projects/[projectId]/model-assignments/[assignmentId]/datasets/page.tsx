import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { SectionState } from "@ukde/ui/primitives";

import {
  getProjectModelAssignment,
  listProjectModelAssignmentDatasets
} from "../../../../../../../lib/model-assignments";
import { getProjectWorkspace } from "../../../../../../../lib/projects";
import {
  projectModelAssignmentPath,
  projectModelAssignmentsPath
} from "../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

export default async function ProjectModelAssignmentDatasetsPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; assignmentId: string }>;
}>) {
  const { projectId, assignmentId } = await params;
  const [workspaceResult, assignmentResult, datasetsResult] = await Promise.all([
    getProjectWorkspace(projectId),
    getProjectModelAssignment(projectId, assignmentId),
    listProjectModelAssignmentDatasets(projectId, assignmentId)
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=model-assignment-datasets-access");
  }
  if (assignmentResult.status === 404) {
    notFound();
  }
  if (!assignmentResult.ok || !assignmentResult.data || !datasetsResult.ok) {
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Assignment datasets unavailable"
          description={
            assignmentResult.detail ??
            datasetsResult.detail ??
            "Dataset lineage could not be loaded."
          }
        />
      </main>
    );
  }

  const assignment = assignmentResult.data;
  const datasets = datasetsResult.data?.items ?? [];

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Training lineage</p>
        <h2>Assignment datasets</h2>
        <p className="ukde-muted">
          Auditable training dataset references linked to model assignment{" "}
          <strong>{assignment.id}</strong>.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectModelAssignmentsPath(projectId)}
          >
            Back to assignments
          </Link>
          <Link
            className="secondaryButton"
            href={projectModelAssignmentPath(projectId, assignment.id)}
          >
            Back to assignment detail
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        {datasets.length === 0 ? (
          <SectionState
            kind="empty"
            title="No datasets linked"
            description="No training datasets are currently linked to this assignment."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Kind</th>
                  <th>Page count</th>
                  <th>Storage key</th>
                  <th>SHA256</th>
                  <th>Created by</th>
                  <th>Created at</th>
                </tr>
              </thead>
              <tbody>
                {datasets.map((dataset) => (
                  <tr key={dataset.id}>
                    <td>{dataset.id}</td>
                    <td>{dataset.datasetKind}</td>
                    <td>{dataset.pageCount}</td>
                    <td>{dataset.storageKey}</td>
                    <td>{dataset.datasetSha256}</td>
                    <td>{dataset.createdBy}</td>
                    <td>{new Date(dataset.createdAt).toISOString()}</td>
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
