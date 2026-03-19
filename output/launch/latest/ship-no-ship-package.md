# Ship / No-Ship Launch Package

- Generated at: `2026-03-19T00:21:11.354963+00:00`
- Decision: `SHIP`

## Evidence status
- `readiness`: `PASS`
- `goLiveRehearsal`: `COMPLETED`
- `releaseGate`: `PASS`
- `incidentTabletop`: `COMPLETED`
- `modelRollbackRehearsal`: `COMPLETED`
- `capacity`: `PASS`
- `security`: `PASS`
- `sloOps`: `PASS`
- `exportNoBypass`: `PASS`

## Blocking findings
- None

## No-go criteria
- `no-go-readiness-blockers`: Any blocking failure in readiness matrix or release gate blocks ship.
- `no-go-missing-rehearsals`: Go-live rehearsal, incident tabletop, and model rollback rehearsal must all be COMPLETED.
- `no-go-active-sev1-sev2`: Any unresolved SEV1/SEV2 incident blocks ship.

## Operational handover
- Launch day owner: `user-release-manager`
- On-call primary: `user-oncall-primary`
- On-call secondary: `user-oncall-secondary`
- Model service map owner: `user-model-platform-owner`
- Approved-model lifecycle owner: `user-model-governance-owner`
- Rollback execution owner: `user-model-ops-owner`
- Escalation path:
  - `L1` On-call primary (user-oncall-primary), SLA 15 min
  - `L2` On-call secondary (user-oncall-secondary), SLA 30 min
  - `L3` Platform + governance leadership (user-release-manager), SLA 45 min

## Post-launch guardrails
- `guardrail-ingest-through-export`: Ingest through export review path remains healthy (owner `user-release-manager`; trigger: Any smoke critical-flow check fails; rollback: Pause promotion and execute deployment rollback procedure)
- `guardrail-security-and-egress`: No-bypass egress and security findings posture remains green (owner `user-security-owner`; trigger: Critical/high finding without ACTIVE risk acceptance or egress denial regression failure; rollback: Block release approval and route to incident commander)
- `guardrail-model-rollback`: Primary transcription model rollback remains executable (owner `user-model-ops-owner`; trigger: SLO breach on primary transcription model with elevated fallback/error rate; rollback: Execute approved-model rollback playbook and open incident timeline)

## Runbook links
- `runbook-release-readiness` -> `docs/runbooks/release-readiness-evidence-and-blocker-policy.md`
- `runbook-production-launch-handover` -> `docs/runbooks/production-launch-handover-and-post-launch-guardrails.md`
- `runbook-deployment` -> `docs/runbooks/deployment-runbook.md`
- `runbook-backup-restore` -> `docs/runbooks/backup-restore-runbook.md`
- `runbook-key-rotation` -> `docs/runbooks/key-rotation-runbook.md`
- `runbook-provenance-replay` -> `docs/runbooks/provenance-replay-drill-and-bundle-validation-recovery.md`
