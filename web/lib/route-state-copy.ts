export interface RouteStateCopy {
  eyebrow: string;
  title: string;
  summary: string;
  retryLabel?: string;
}

export const routeLoadingCopy = {
  app: {
    eyebrow: "Loading app",
    title: "Preparing secure shell",
    summary: "The shell mounts first while route content streams."
  },
  public: {
    eyebrow: "Loading public route",
    title: "Preparing public surface",
    summary: "Public routes load without dropping global shell continuity."
  },
  authenticated: {
    eyebrow: "Loading authenticated route",
    title: "Preparing authenticated surface",
    summary: "Session and shell context stay mounted while content resolves."
  },
  admin: {
    eyebrow: "Loading admin route",
    title: "Preparing admin surface",
    summary: "Governance and operations surfaces stream in place."
  },
  project: {
    eyebrow: "Loading project route",
    title: "Preparing project workspace",
    summary: "Project context remains mounted while section data resolves."
  },
  projectDocuments: {
    eyebrow: "Loading documents route",
    title: "Preparing document surface",
    summary: "Document routes preserve project ancestry while data loads."
  },
  projectDocument: {
    eyebrow: "Loading document detail",
    title: "Preparing document details",
    summary: "Document context loads inside the existing project shell."
  },
  projectViewer: {
    eyebrow: "Loading viewer route",
    title: "Preparing viewer workspace",
    summary: "Viewer URL state is restored before content is shown."
  },
  projectDocumentIngestStatus: {
    eyebrow: "Loading ingest status route",
    title: "Preparing ingest timeline",
    summary:
      "Processing runs are restored before recovery actions are presented."
  }
} as const satisfies Record<string, RouteStateCopy>;

export const routeErrorCopy = {
  app: {
    eyebrow: "Route boundary",
    title: "The route hit an unexpected boundary.",
    summary:
      "A safe fallback was rendered. Internal exception details stay server-side.",
    retryLabel: "Retry route"
  },
  public: {
    eyebrow: "Route boundary",
    title: "Public route failed to load",
    summary:
      "The public route could not complete. Retry or move to a known route.",
    retryLabel: "Retry route"
  },
  authenticated: {
    eyebrow: "Route boundary",
    title: "Authenticated route failed",
    summary:
      "Authenticated shell context was preserved while this route failed.",
    retryLabel: "Retry route"
  },
  admin: {
    eyebrow: "Route boundary",
    title: "Admin route failed",
    summary:
      "Admin access controls remain in effect. Retry after the issue is resolved.",
    retryLabel: "Retry route"
  },
  project: {
    eyebrow: "Project route boundary",
    title: "Project surface failed to load",
    summary:
      "The project shell remains mounted. Retry this route or return to overview.",
    retryLabel: "Retry route"
  },
  projectDocuments: {
    eyebrow: "Route boundary",
    title: "Document route failed",
    summary:
      "Document route content failed while project shell context stayed mounted.",
    retryLabel: "Retry route"
  },
  projectViewer: {
    eyebrow: "Route boundary",
    title: "Viewer route failed",
    summary:
      "Viewer route failed while project and document URL context were preserved.",
    retryLabel: "Retry route"
  },
  projectDocumentIngestStatus: {
    eyebrow: "Route boundary",
    title: "Ingest-status route failed",
    summary:
      "Ingest timeline loading failed while project and document context stayed mounted.",
    retryLabel: "Retry route"
  }
} as const satisfies Record<string, RouteStateCopy>;

export const routeNotFoundCopy = {
  root: {
    eyebrow: "Not found",
    title: "Route not found",
    summary: "The requested route does not exist or is no longer available."
  },
  admin: {
    eyebrow: "Not found",
    title: "Admin route not found",
    summary: "The requested admin route was not found or is not available."
  },
  project: {
    eyebrow: "Not found",
    title: "Project route not found",
    summary: "The project route cannot be resolved for the current session."
  },
  projectDocument: {
    eyebrow: "Not found",
    title: "Document not found",
    summary: "The selected document route is unavailable."
  }
} as const satisfies Record<string, RouteStateCopy>;

export const routeStateCopyCatalog = {
  loading: routeLoadingCopy,
  error: routeErrorCopy,
  notFound: routeNotFoundCopy
} as const;
