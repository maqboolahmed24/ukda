import Link from "next/link";
import { redirect } from "next/navigation";

import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { getProjectWorkspace } from "../../../../../../lib/projects";
import {
  getProjectPseudonymRegistryEntry
} from "../../../../../../lib/pseudonym-registry";
import {
  projectPseudonymRegistryEntryEventsPath,
  projectPseudonymRegistryPath
} from "../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function resolveStatusTone(
  status: "ACTIVE" | "RETIRED"
): "danger" | "neutral" | "success" | "warning" {
  return status === "ACTIVE" ? "success" : "neutral";
}

export default async function ProjectPseudonymRegistryEntryPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; entryId: string }>;
}>) {
  const { projectId, entryId } = await params;

  const [workspaceResult, entryResult] = await Promise.all([
    getProjectWorkspace(projectId),
    getProjectPseudonymRegistryEntry(projectId, entryId)
  ]);

  if (!workspaceResult.ok || !workspaceResult.data) {
    redirect("/projects?error=pseudonym-registry-access");
  }

  if (!entryResult.ok || !entryResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Registry entry unavailable"
            description={entryResult.detail ?? "Pseudonym registry entry could not be loaded."}
          />
          <div className="buttonRow">
            <Link className="secondaryButton" href={projectPseudonymRegistryPath(projectId)}>
              Back to registry
            </Link>
          </div>
        </section>
      </main>
    );
  }

  const entry = entryResult.data;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Pseudonym registry entry</p>
        <h2>{entry.id}</h2>
        <p className="ukde-muted">
          Deterministic alias mapping for one fingerprint scope. Raw identifiers are never stored.
        </p>
        <div className="buttonRow">
          <Link className="secondaryButton" href={projectPseudonymRegistryPath(projectId)}>
            Back to registry
          </Link>
          <Link
            className="secondaryButton"
            href={projectPseudonymRegistryEntryEventsPath(projectId, entry.id)}
          >
            View events
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <ul className="projectMetaList">
          <li>
            <span>Status</span>
            <strong>
              <StatusChip tone={resolveStatusTone(entry.status)}>{entry.status}</StatusChip>
            </strong>
          </li>
          <li>
            <span>Alias value</span>
            <strong>{entry.aliasValue}</strong>
          </li>
          <li>
            <span>Source fingerprint (HMAC)</span>
            <strong>{entry.sourceFingerprintHmacSha256}</strong>
          </li>
          <li>
            <span>Source run</span>
            <strong>{entry.sourceRunId}</strong>
          </li>
          <li>
            <span>Last used run</span>
            <strong>{entry.lastUsedRunId ?? "n/a"}</strong>
          </li>
          <li>
            <span>Policy</span>
            <strong>{entry.policyId}</strong>
          </li>
          <li>
            <span>Salt version</span>
            <strong>{entry.saltVersionRef}</strong>
          </li>
          <li>
            <span>Alias strategy</span>
            <strong>{entry.aliasStrategyVersion}</strong>
          </li>
          <li>
            <span>Supersedes</span>
            <strong>{entry.supersedesEntryId ?? "n/a"}</strong>
          </li>
          <li>
            <span>Superseded by</span>
            <strong>{entry.supersededByEntryId ?? "n/a"}</strong>
          </li>
        </ul>
      </section>
    </main>
  );
}
