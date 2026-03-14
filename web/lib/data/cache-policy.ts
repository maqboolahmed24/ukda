export type QueryCacheClass =
  | "auth-critical"
  | "governance-event"
  | "mutable-list"
  | "operations-live"
  | "public-status";

export interface QueryCachePolicy {
  cacheClass: QueryCacheClass;
  description: string;
  fetchCache: RequestCache;
  optimistic: "never";
  pollIntervalMs: number | null;
  retryMaxAttempts: number;
}

// Governance and RBAC-sensitive reads remain network-only in Phase 0/1.
const NETWORK_ONLY = "no-store";

export const queryCachePolicy: Record<QueryCacheClass, QueryCachePolicy> = {
  "auth-critical": {
    cacheClass: "auth-critical",
    description:
      "Session and authorization truth. Never cache between requests.",
    fetchCache: NETWORK_ONLY,
    optimistic: "never",
    pollIntervalMs: null,
    retryMaxAttempts: 0
  },
  "governance-event": {
    cacheClass: "governance-event",
    description:
      "Audit/security/governance reads. Exact server truth wins over speculative freshness.",
    fetchCache: NETWORK_ONLY,
    optimistic: "never",
    pollIntervalMs: null,
    retryMaxAttempts: 1
  },
  "mutable-list": {
    cacheClass: "mutable-list",
    description:
      "Project and jobs lists mutate frequently and are invalidated on successful mutations.",
    fetchCache: NETWORK_ONLY,
    optimistic: "never",
    pollIntervalMs: null,
    retryMaxAttempts: 1
  },
  "operations-live": {
    cacheClass: "operations-live",
    description:
      "Live operational posture. Always fresh with optional short polling in client-only status widgets.",
    fetchCache: NETWORK_ONLY,
    optimistic: "never",
    pollIntervalMs: 4000,
    retryMaxAttempts: 0
  },
  "public-status": {
    cacheClass: "public-status",
    description:
      "Health/readiness checks for diagnostics. Read as live status rather than cached snapshots.",
    fetchCache: NETWORK_ONLY,
    optimistic: "never",
    pollIntervalMs: 5000,
    retryMaxAttempts: 0
  }
};

