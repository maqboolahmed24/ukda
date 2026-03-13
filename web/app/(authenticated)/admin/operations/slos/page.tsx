import { PageHeader } from "../../../../../components/page-header";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import { getOperationsSlos } from "../../../../../lib/operations";

export const dynamic = "force-dynamic";

export default async function AdminOperationsSlosPage() {
  await requirePlatformRole(["ADMIN"]);
  const slosResult = await getOperationsSlos();

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform operations"
        secondaryActions={[
          { href: "/admin/operations", label: "Overview" },
          { href: "/admin/operations/alerts", label: "Alerts" },
          { href: "/admin/operations/timelines", label: "Timelines" }
        ]}
        summary="Current process-level targets used for readiness and alert scaffolding."
        title="SLO baselines"
      />

      <section className="sectionCard ukde-panel">
        {!slosResult.ok || !slosResult.data ? (
          <p className="ukde-muted">
            SLO data unavailable: {slosResult.detail ?? "unknown"}
          </p>
        ) : (
          <div className="auditTableWrap">
            <table className="auditTable">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Target</th>
                  <th>Current</th>
                  <th>Status</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {slosResult.data.items.map((slo) => (
                  <tr key={slo.key}>
                    <td>{slo.name}</td>
                    <td>{slo.target}</td>
                    <td>{slo.current}</td>
                    <td>{slo.status}</td>
                    <td>{slo.detail}</td>
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
