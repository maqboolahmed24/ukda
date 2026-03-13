import Link from "next/link";

import { requirePlatformRole } from "../../../../../lib/auth/session";
import { getOperationsSlos } from "../../../../../lib/operations";

export const dynamic = "force-dynamic";

export default async function AdminOperationsSlosPage() {
  await requirePlatformRole(["ADMIN"]);
  const slosResult = await getOperationsSlos();

  return (
    <main className="homeLayout">
      <section
        className="sectionCard ukde-panel"
        aria-labelledby="operations-slos-title"
      >
        <p className="ukde-eyebrow">Platform operations</p>
        <h1 id="operations-slos-title">SLO baselines</h1>
        <p className="ukde-muted">
          Current process-level targets used for readiness and alert
          scaffolding.
        </p>
        <div className="buttonRow">
          <Link className="secondaryButton" href="/admin/operations">
            Overview
          </Link>
          <Link className="secondaryButton" href="/admin/operations/alerts">
            Alerts
          </Link>
          <Link className="secondaryButton" href="/admin/operations/timelines">
            Timelines
          </Link>
        </div>
      </section>

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
