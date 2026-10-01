# Olympus Dashboard

Operator console for the Olympus control plane (`apps/dashboard`).

## Data modes

- **fixture** (default): `NEXT_PUBLIC_OLYMPUS_DATA_MODE=fixture` — uses `lib/fixtures` only; banner shown.
- **live**: points HTTP adapters at `OLYMPUS_API_URL` via `/api/olympus` proxy (capabilities pending until control-api exists).

## Commands

```bash
npm install
npm run dev
npm run check              # lint + typecheck + unit tests
npm run test:e2e           # all @frontend-e2e specs (fixture UI; not backend E2E)
npm run test:e2e:journeys  # journey + journey-tagged cross-cutting specs only
npm run test:e2e:flake     # repeat-each=3 on dev server
npm run test:e2e:flake:prod # repeat-each=3 on prod build (sets OLYMPUS_DEMO_BUILD via Playwright webServer)
```

Run these from **`apps/dashboard`** (the package root). If your shell is already in that directory, do not run `cd apps/dashboard` again.

Production builds reject `fixture` mode unless `OLYMPUS_DEMO_BUILD=1` (Playwright sets this automatically when using `E2E_PROD=1` / CI prod webServer).

See [plans/frontend-ui-implementation.md](../../plans/frontend-ui-implementation.md) and `STATUS.md` §16.
