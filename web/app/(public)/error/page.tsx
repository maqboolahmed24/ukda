import Link from "next/link";

import { PageState } from "@ukde/ui/primitives";

import { loginPath, projectsPath } from "../../../lib/routes";

export default function SafeErrorPage() {
  return (
    <main className="homeLayout">
      <PageState
        className="routeErrorState ukde-panel"
        description="This fallback keeps browser-visible details sanitized while preserving deterministic navigation recovery."
        eyebrow="Safe error route"
        kind="error"
        title="Route recovery surface"
      >
        <div className="buttonRow">
          <Link className="secondaryButton" href={projectsPath}>
            Open projects
          </Link>
          <Link className="secondaryButton" href={loginPath}>
            Open login
          </Link>
        </div>
      </PageState>
    </main>
  );
}
