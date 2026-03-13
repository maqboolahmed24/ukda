export default function AdminHomePage() {
  return (
    <main className="homeLayout">
      <section
        className="sectionCard ukde-panel"
        aria-labelledby="admin-home-title"
      >
        <p className="ukde-eyebrow">Platform route</p>
        <h1 id="admin-home-title">Admin surfaces</h1>
        <p className="ukde-muted">
          Platform-role access is enforced server-side. This area is reserved
          for governance and operator surfaces.
        </p>
        <div className="buttonRow">
          <a className="secondaryButton" href="/admin/operations">
            Operations
          </a>
          <a className="secondaryButton" href="/admin/security">
            Security status
          </a>
          <a className="secondaryButton" href="/admin/audit">
            Audit viewer
          </a>
          <a className="secondaryButton" href="/admin/design-system">
            Design system gallery
          </a>
          <a className="secondaryButton" href="/projects">
            Back to projects
          </a>
        </div>
      </section>
    </main>
  );
}
