import { PageHeader } from "../../../../../components/page-header";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import { getOperationsReadiness } from "../../../../../lib/operations";
import {
  adminCapacityTestsPath,
  adminOperationsAlertsPath,
  adminOperationsExportStatusPath,
  adminOperationsPath,
  adminOperationsTimelinesPath,
  adminPath,
  adminSecurityFindingsPath
} from "../../../../../lib/routes";
import { SectionState } from "@ukde/ui/primitives";

export const dynamic = "force-dynamic";

function toneForStatus(
  status: "PASS" | "FAIL" | "UNAVAILABLE"
): "success" | "critical" | "warning" {
  if (status === "PASS") {
    return "success";
  }
  if (status === "FAIL") {
    return "critical";
  }
  return "warning";
}

export default async function AdminOperationsReadinessPage() {
  const session = await requirePlatformRole(["ADMIN", "AUDITOR"]);
  const isAdmin = session.user.platformRoles.includes("ADMIN");
  const readinessResult = await getOperationsReadiness();

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform operations"
        secondaryActions={[
          { href: adminOperationsPath, label: "Operations overview" },
          { href: adminOperationsExportStatusPath, label: "Export status" },
          { href: adminOperationsTimelinesPath, label: "Timelines" },
          { href: adminOperationsAlertsPath, label: "Alerts" },
          { href: adminCapacityTestsPath, label: "Capacity tests" },
          { href: adminSecurityFindingsPath, label: "Security findings" },
          { href: adminPath, label: "Back to admin" }
        ]}
        summary="Canonical cross-phase readiness matrix with category evidence and release-blocking status."
        title="Production readiness"
      />

      {!readinessResult.ok || !readinessResult.data ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Readiness summary unavailable"
            description={readinessResult.detail ?? "Unknown failure"}
          />
        </section>
      ) : (
        <>
          <section className="sectionCard ukde-panel">
            <div className="auditIntegrityRow">
              <span className={`ukde-badge tone-${toneForStatus(readinessResult.data.overallStatus)}`}>
                {readinessResult.data.overallStatus}
              </span>
              <span className="ukde-badge">
                blocking failures {readinessResult.data.blockingFailureCount}
              </span>
              <span className="ukde-badge">
                categories {readinessResult.data.categoryCount}
              </span>
              <span className="ukde-badge">
                role {isAdmin ? "ADMIN" : "AUDITOR"}
              </span>
            </div>
            <p className="ukde-muted">{readinessResult.data.detail}</p>
            <p className="ukde-muted">
              Matrix {readinessResult.data.matrixVersion} generated{" "}
              {new Date(readinessResult.data.generatedAt).toISOString()}.
            </p>
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Blocking checks</h2>
            {readinessResult.data.blockers.length === 0 ? (
              <SectionState
                kind="success"
                title="No blocking failures"
                description="All blocking readiness checks are currently passing."
              />
            ) : (
              <div className="auditTableWrap">
                <table className="auditTable">
                  <thead>
                    <tr>
                      <th>Category</th>
                      <th>Check</th>
                      <th>Detail</th>
                      <th>Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {readinessResult.data.blockers.map((item) => (
                      <tr key={`${item.categoryId}-${item.checkId}`}>
                        <td>{item.categoryId}</td>
                        <td>{item.checkId}</td>
                        <td>{item.detail}</td>
                        <td>{item.evidencePath ?? "n/a"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="sectionCard ukde-panel">
            <h2>Category evidence</h2>
            {readinessResult.data.categories.length === 0 ? (
              <SectionState
                kind="degraded"
                title="No readiness categories available"
                description="Run the cross-phase readiness audit to populate machine-readable evidence."
              />
            ) : (
              <div className="auditTableWrap">
                <table className="auditTable">
                  <thead>
                    <tr>
                      <th>Category</th>
                      <th>Status</th>
                      <th>Policy</th>
                      <th>Checks</th>
                      <th>Evidence refs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {readinessResult.data.categories.map((category) => {
                      const evidenceRefs = category.checks.flatMap((check) =>
                        check.evidence.map((evidence) => evidence.path)
                      );
                      return (
                        <tr key={category.id}>
                          <td>
                            <strong>{category.title}</strong>
                            <p className="ukde-muted">{category.summary}</p>
                          </td>
                          <td>{category.status}</td>
                          <td>{category.blockingPolicy}</td>
                          <td>{category.checks.length}</td>
                          <td>
                            {evidenceRefs.length === 0 ? (
                              "n/a"
                            ) : (
                              <code>{Array.from(new Set(evidenceRefs)).join(", ")}</code>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
