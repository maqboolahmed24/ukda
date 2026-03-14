# Layout No-Silent-Drop Enforcement

## Rule
No layout run may be promoted while recall status is unresolved for any page.

## Resolved Page Classes
A page is considered explicitly resolved only when `page_recall_status` is one of:

- `COMPLETE`
- `NEEDS_RESCUE`
- `NEEDS_MANUAL_REVIEW`

## Additional Promotion Requirements
Resolved class alone is not enough for activation:

- persisted recall-check row must exist for every page
- no pending rescue candidates may remain
- `NEEDS_RESCUE` pages must include accepted rescue candidate coverage

## Operational Consequence
Activation is blocked with typed gate blockers until these rules pass. UI surfaces use blocker payloads directly and never infer readiness from run status alone.

