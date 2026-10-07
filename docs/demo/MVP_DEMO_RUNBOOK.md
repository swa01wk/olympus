# MVP Demo Runbook (Phase 19)

## Prerequisites

- Linux host with Docker (Phase 18 sandbox / `bwrap` in worker image).
- Live LLM credentials in `.env` (`OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY`).
- `OLYMPUS_ENV=journey`, `LLM_LIVE_TESTS=1`, `LLM_TEST_BUDGET_USD` ≥ Q-06 ceiling (default ≥ 5 until observed).
- Phase 16 integrations profile (Gitea, MinIO, CI runner, fault proxy).

### Environment flags

| Variable | Default | Meaning |
|---|---|---|
| `MVP_PLANNING_SEEDS=1` | off | Force legacy planning seeds (debug only; not Phase 19 sign-off). |
| `MVP_INJECT_DEFECT=1` | on | Q-05 defect injection attempt before DC-004. |
| `MVP_CHAOS=1` | off | Enable §4.6 fault injection (issue-close timeout via fault proxy). |
| `MVP_GITEA_REPO` | set by driver | Gitea repo name used for external defect push + sync. |

## Quick start

```bash
make mvp-env          # clean volumes, stack, migrate, seed actors, preflight
make mvp-demo         # chained run + chained journey + evaluator + matrix
make mvp-demo-chaos   # same with --chaos / MVP_CHAOS=1
make mvp-acceptance   # mvp-demo then fresh mvp-env + mvp-demo-chaos
```

Operator UI walkthrough for **R3 release approval (DC-004)** is supported via the rebuilt dashboard (`apps/dashboard`) and `--pause-before approve_release:DC-004`. Default CI still uses the chained pytest journey without a live browser.

## Manual steps

```bash
export OLYMPUS_HUMAN_TOKEN="$(./scripts/demo/bootstrap.sh | tail -2 | head -1)"
export OLYMPUS_VIEWER_TOKEN="$(./scripts/demo/bootstrap.sh | tail -1)"

# Terminal A — dashboard (port 3010 avoids Gitea on 3000)
cd apps/dashboard && NEXT_PUBLIC_OLYMPUS_API_URL=http://127.0.0.1:8000 npm run dev -- --port 3010

# Terminal B — pause before DC-004 R3 release approval
uv run python scripts/demo/run_mvp.py --pause-before approve_release:DC-004

# While paused, open var/olympus/demo/pause.json → dashboard_url (or use Playwright):
# Terminal C (optional)
cd apps/dashboard
export MVP_E2E_LIVE=1 OLYMPUS_HUMAN_TOKEN
npm run test:e2e -- tests/e2e/mvp-chained.spec.ts

# Or approve manually in the browser, then resume the driver:
uv run python scripts/demo/resume_mvp_pause.py
```

## Reports

- `var/olympus/reports/chained_run_<id>.json` — stage timings from driver.
- `var/olympus/reports/mvp_acceptance_<run_id>.json` — evaluator output.
- `var/olympus/reports/junit-*.xml` — matrix checker inputs.

## Troubleshooting

| Symptom | Check |
|---|---|
| Preflight fails on `FakeProvider` | `OLYMPUS_ENV` must be `journey`, not `local`. |
| Gitea unhealthy | `make integrations-wait`; Gitea uses host port **3000**. |
| Injector abort `NO_TARGET` | R2 code lacks a single recognizable HTTP 409 raise (Q-05); inspect `scripts/demo/chained/inject_defect.py` diagnostics. |
| Fingerprint mismatch at RB-* | Active executions still running; wait for quiescence. |
| Evaluator non-zero | Run with project UUID from chained journey logs; verify R1–R3 released. |

## Cost / duration

Expect roughly 1.5–4 hours and non-trivial LLM spend per full chained run (Q-06). Record run IDs and costs in `STATUS.md` § Phase 19 after successful `make mvp-acceptance`.

## Post-acceptance regression

After two green acceptance runs, run **`make verify-phases-live`** (P19-REG) before setting `MVP_COMPLETE` in `STATUS.md`.
