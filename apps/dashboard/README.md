# Olympus dashboard (operator UI)

Control-plane-first frontend for the Olympus Control API. Implementation follows `docs/design/olympus-ui-spec/` and `docs/ui-implementation/`.

## Environment

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_OLYMPUS_API_URL` | Control API base URL (e.g. `http://127.0.0.1:8000`). Used from Phase 3 onward. |
| `NEXT_PUBLIC_OLYMPUS_API_TOKEN` | Bearer token for local dev (optional if you save via the Projects sign-in form). |

Copy `.env.local.example` to `.env.local` after seeding a token:

```bash
# from repo root — postgres running, migrations applied
uv run python -m apps.control_api.cli.seed_actor --name dev --roles OPERATOR,APPROVER
uv run uvicorn apps.control_api.main:app --reload
```

## Scripts

```bash
npm install
npm run dev          # http://localhost:3000
npm run check        # lint + typecheck + unit tests
npm run test:e2e     # Playwright (starts dev server; stubs Control API)
```

First-time e2e: `npx playwright install chromium`

## Structure

- `src/api/` — HTTP client, resources, TanStack Query hooks, SSE, `sendCommand`
- `src/control-plane/` — lane map, stage→lane, attention, `buildControlPlaneGraph`
- `src/adapters/` — backend status → UI presentation
- `components/primitives/` — design-system primitives
- `styles/tokens.css` — from `docs/design/olympus-ui-spec/tokens.json`

## Auth (Phase 3)

Use the sign-in form on `/projects`, set `NEXT_PUBLIC_OLYMPUS_API_TOKEN` in `.env.local`, or run `localStorage.setItem('olympus_api_token', '<token>')` in the browser console. Restart `npm run dev` after changing `.env.local`.
