# State Copy Guidelines

> Status: Active baseline (Prompt 15)
> Scope: Microcopy rules for loading/empty/error/success and operational feedback

State copy in UKDE must stay calm, exact, and trustworthy.

## Required Tone

- Serious, minimal, and operational
- No hype, no celebratory fluff, no blame
- No internal stack traces, secret IDs, or unsafe technical leakage

## Copy Structure

Every state should have:

1. Short exact title (what happened)
2. One sentence describing current condition (what is known)
3. One next step when available (what to do next)

## Copy Rules by State

- `loading`
  - Confirm what is loading.
  - Do not imply fake progress.
- `empty` and `zero`
  - Explain why no records are shown.
  - Offer first action when applicable.
- `no-results`
  - Tie the message to current filters or search.
  - Suggest broadening filters.
- `error`
  - Explain safe impact in user terms.
  - Keep internals in logs.
  - Offer retry/recovery route.
- `success`
  - Confirm result without derailing workflow.
  - Keep language restrained.
- `disabled`
  - Explain intentional unavailability and phase/environment reason.
- `unauthorized`
  - Explain role requirement or access boundary.

## Success Signal Rule

When actions change durable page state:

- show an inline or page-level success signal
- do not rely on toast alone
- keep resulting context visible (for example a created object now listed)

## Safe Error Rule

- Prefer precise safe wording over generic “something went wrong”.
- Include actionable recovery guidance when possible.
- Preserve sanitized fallback links (`/projects`, `/login`, `/error`) where relevant.

## Source of Reusable Route Copy

- `web/lib/route-state-copy.ts`
- `web/lib/route-state-copy.test.ts` snapshots
