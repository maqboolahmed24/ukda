import Link from "next/link";
import { redirect } from "next/navigation";

import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { getProjectWorkspace } from "../../../../../lib/projects";
import {
  listProjectPseudonymRegistryEntries
} from "../../../../../lib/pseudonym-registry";
import {
  projectPseudonymRegistryEntryEventsPath,
  projectPseudonymRegistryEntryPath,
  projectPseudonymRegistryPath,
  projectPoliciesPath
} from "../../../../../lib/routes";

export const dynamic = "force-dynamic";

function resolveStatusTone(
  status: "ACTIVE" | "RETIRED"
): "danger" | "neutral" | "success" | "warning" {
  return status === "ACTIVE" ? "success" : "neutral";
}

export default async function ProjectPseudonymRegistryPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string }>;
}>) {
  const { projectId } = await params;

  const [workspaceResult, entriesResult] = await Promise.all([
    getProjectWorkspace(projectId),
    listProjectPseudonymRegistryEntries(projectId)
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=pseudonym-registry-access");
  }

  if (!entriesResult.ok || !entriesResult.data) {
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Pseudonym registry unavailable"
          description={
            entriesResult.detail ?? "Pseudonym registry entries could not be loaded."
          }
        />
      </main>
    );
  }

  const entries = entriesResult.data.items;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Pseudonym registry</p>
        <h2>Controlled-only alias lineage</h2>
        <p className="ukde-muted">
          Deterministic aliases are scoped by project, policy, salt version, and alias strategy.
          This surface is read-only in v1.
        </p>
        <div className="buttonRow">
          <Link className="secondaryButton" href={projectPoliciesPath(projectId)}>
            Back to policies
          </Link>
          <Link className="secondaryButton" href={projectPseudonymRegistryPath(projectId)}>
            Refresh registry
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <SectionState
          kind="disabled"
          title="Controlled-only registry view"
          description="Registry entries are system-generated only. No manual create/edit/delete actions are exposed in Phase 7 v1."
        />
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Entries</h3>
        {entries.length === 0 ? (
          <SectionState
            kind="empty"
            title="No pseudonym registry entries"
            description="Entries appear after pseudonymized outputs are generated for this project."
          />
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Entry</th>
                  <th>Status</th>
                  <th>Alias</th>
                  <th>Policy</th>
                  <th>Salt</th>
                  <th>Strategy</th>
                  <th>Last used run</th>
                  <th>Events</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>
                      <Link href={projectPseudonymRegistryEntryPath(projectId, entry.id)}>
                        {entry.id}
                      </Link>
                    </td>
                    <td>
                      <StatusChip tone={resolveStatusTone(entry.status)}>{entry.status}</StatusChip>
                    </td>
                    <td>{entry.aliasValue}</td>
                    <td>{entry.policyId}</td>
                    <td>{entry.saltVersionRef}</td>
                    <td>{entry.aliasStrategyVersion}</td>
                    <td>{entry.lastUsedRunId ?? "n/a"}</td>
                    <td>
                      <Link
                        className="secondaryButton"
                        href={projectPseudonymRegistryEntryEventsPath(projectId, entry.id)}
                      >
                        View events
                      </Link>
                    </td>
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
