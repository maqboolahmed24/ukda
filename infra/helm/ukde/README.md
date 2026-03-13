# UKDE Helm Skeleton

This chart is the lowest-churn deployment skeleton for Phase 0 Iteration 0.1.

- It is internal-only by default.
- It renders `preview`, `dev`, `staging`, and `prod` values sets.
- Preview namespaces follow the `ukde-pr-<number>` convention and are deployed only by internal self-hosted runners.
- It includes Phase 0.5 network-policy templates for deny-by-default egress with internal CIDR and DNS allowlist controls.
- It does not provision infrastructure. It only describes how the runtime services and baseline policies fit together.
