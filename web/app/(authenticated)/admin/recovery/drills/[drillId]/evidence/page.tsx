import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../../../components/page-header";
import { requirePlatformRole } from "../../../../../../../lib/auth/session";
import { getAdminRecoveryDrillEvidence } from "../../../../../../../lib/recovery";
import {
  adminRecoveryDrillDetailPath,
  adminRecoveryDrillsPath,
  adminRecoveryStatusPath
} from "../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

export default async function AdminRecoveryDrillEvidencePage({
  params
}: Readonly<{
  params: Promise<{ drillId: string }>;
}>) {
  await requirePlatformRole(["ADMIN"]);
  const { drillId } = await params;
  const evidenceResult = await getAdminRecoveryDrillEvidence(drillId);

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform recovery"
        meta={<StatusChip tone="danger">ADMIN</StatusChip>}
        secondaryActions={[
          { href: adminRecoveryDrillDetailPath(drillId), label: "Back to drill detail" },
          { href: adminRecoveryDrillsPath, label: "Recovery drills" },
          { href: adminRecoveryStatusPath, label: "Recovery status" }
        ]}
        summary="Evidence-backed drill payload and append-only event history."
        title={`Recovery evidence ${drillId}`}
      />

      {!evidenceResult.ok || !evidenceResult.data ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Recovery evidence unavailable"
            description={evidenceResult.detail ?? "Unable to load recovery drill evidence."}
          />
        </section>
      ) : (
        <>
          <section className="sectionCard ukde-panel">
            <ul className="projectMetaList">
              <li>
                <span>Drill ID</span>
                <strong>{evidenceResult.data.drillId}</strong>
              </li>
              <li>
                <span>Evidence storage key</span>
                <strong>{evidenceResult.data.evidenceStorageKey ?? "n/a"}</strong>
              </li>
              <li>
                <span>Evidence SHA-256</span>
                <strong>{evidenceResult.data.evidenceStorageSha256 ?? "n/a"}</strong>
              </li>
            </ul>
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Evidence payload</h2>
            <pre className="ukde-json-panel">
              {JSON.stringify(evidenceResult.data.evidence, null, 2)}
            </pre>
          </section>
        </>
      )}
    </main>
  );
}
