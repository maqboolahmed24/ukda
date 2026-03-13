import { PageHeader } from "../../../components/page-header";

export default function AdminHomePage() {
  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform route"
        secondaryActions={[
          { href: "/admin/operations", label: "Operations" },
          { href: "/admin/security", label: "Security status" },
          { href: "/admin/audit", label: "Audit viewer" },
          { href: "/admin/design-system", label: "Design system gallery" },
          { href: "/projects", label: "Back to projects" }
        ]}
        summary="Platform-role access is enforced server-side for governance and operator surfaces."
        title="Admin surfaces"
      />
    </main>
  );
}
