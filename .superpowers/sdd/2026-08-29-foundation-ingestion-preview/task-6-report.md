# Task 6 — Manager import-preview interface

## RED → GREEN evidence

- RED: `pnpm --filter web exec playwright test e2e/import-preview.spec.ts` reached `/imports/new` and failed because the route returned 404; the test timed out while waiting for the accessible label `Arquivo CSV do SEMS+`.
- GREEN: after the interface was implemented, the same test passed: `1 passed` (the SEMS fixture produced `2 registros`, `2 válidos`, `0 inválidos`, `0 duplicados`, `Fonte real`, and `Identidade desconhecida`).

## Verification

- `pnpm --filter web exec playwright test e2e/import-preview.spec.ts` — passed, 1/1.
- `pnpm --filter web lint` — passed.
- `pnpm --filter web build` — passed; Next generated `/`, `/_not-found`, and `/imports/new`.
- Visual QA: inspected empty, desktop preview, and 390px preview. The narrow layout stacks the summary while retaining intentional horizontal scrolling for the classification ledger. A temporary screenshot test initially triggered a Next development hydration warning because Playwright hides carets by injecting `caret-color: transparent`; rerunning with `caret: "initial"` passed without the warning. The temporary test and all generated test artifacts were removed.

## Design decisions

- The page is an operations manager's audit surface, not a generic dashboard: the dominant artifact is a classification ledger that retains source-line context.
- Cyan marks verified operational evidence and coral marks the analyze action. Chrome uses restrained rules, data typography, and no decorative gradients.
- The flow clearly exposes empty/selected, loading, success, row-error, and retry states; keyboard focus is visible and reduced motion is respected.
- The default browser request goes through a same-origin `/api` rewrite, avoiding CORS coupling during local use; `NEXT_PUBLIC_API_URL` can still override it.

## Files

- `apps/web/src/app/imports/new/page.tsx`
- `apps/web/src/components/imports/import-dropzone.tsx`
- `apps/web/src/components/imports/preview-summary.tsx`
- `apps/web/src/components/imports/preview-table.tsx`
- `apps/web/e2e/import-preview.spec.ts`
- `apps/web/playwright.config.ts`
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/layout.tsx`
- `apps/web/src/app/globals.css`
- `apps/web/next.config.ts`
- `apps/web/package.json`
- `pnpm-lock.yaml`

## Limitations

- The default `pnpm --dir apps/web ...` invocation cannot resolve the root workspace package `@ev-chargeops/api-client` because `apps/web/pnpm-workspace.yaml` declares an isolated workspace. Equivalent root-workspace commands (`pnpm --filter web ...`) were used for verification.
- Port 3000 was already occupied by an unrelated local Next process, so Playwright is configured for isolated port 3102.

## Commit

- `1a3db57 feat: add SEMS import preview interface`
