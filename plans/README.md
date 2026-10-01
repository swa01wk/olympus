# Olympus MVP — Implementation Plan Index and Cross-Cutting Conventions

This folder contains the sequenced implementation plans for the Olympus MVP. Together with the root-level `STATUS.md`, it is the implementation control system for the MVP.

Authoritative sources (repository root):

- `Olympus_MVP_Architecture_and_Implementation_Plan_v1.2.docx` — referred to as **ARCH** (semantic authority).
- `Olympus_MVP_Technical_Implementation_Specification_v1.0.docx` — referred to as **TECH** (implementation contract).

Every implementation agent MUST read, in order: this file, `STATUS.md`, then the phase file it is executing.

---

## 1. Repository Reality at Planning Time (2026-10-01)

| Item | Observation |
|---|---|
| Git state | Branch `main`, **no commits**. Remote `origin = git@github.com:swa01wk/olympus.git` (not reachable from the planning environment: `Permission denied (publickey)`). |
| Tracked/untracked content | Only the two `.docx` source documents. |
| Backend / frontend / migrations / tests / config / deployment | **None exist.** |
| LangGraph / AgentRuntime / ModelRouter / agents / Git utilities / ToolGateway / connectors | **None exist.** |

Consequence: every component in every phase is classified **ADD** relative to the current repository. Phase files also state the *expected state at phase start* (what earlier phases will have produced) and classify those artifacts as RETAIN / EXTEND / REFACTOR so the implementation agent knows what it may touch.

**Risk R-REMOTE:** if `origin/main` contains code that was not present locally, Phase 00 task 00.1 requires re-running the repository assessment before any scaffold is written. Do not overwrite remote history.

---

## 2. Source Precedence and Reconciliation Decisions

ARCH defines *what Olympus means*. TECH defines *how it is built*. Where they differ on a technical detail, TECH wins unless that would violate an ARCH invariant. All reconciliations are listed here so that no phase silently picks a side.

| ID | Topic | ARCH v1.2 | TECH v1.0 | Decision |
|---|---|---|---|---|
| D-01 | Database | SQLite locally, PostgreSQL-compatible semantics | PostgreSQL 16+ with pgvector, `FOR UPDATE SKIP LOCKED`, JSONB | **PostgreSQL 16 + pgvector everywhere** (local via Docker Compose, tests via Testcontainers). SQLite is not supported because scheduler admission requires `SKIP LOCKED` and the immutability triggers are PostgreSQL-specific. |
| D-02 | Greenfield states | DISCOVERY → REQUIREMENTS → ARCHITECTURE → … | DISCOVERY → PRODUCT_MODEL → ARCHITECTURE → … | **TECH states.** `PRODUCT_MODEL` covers the ARCH "REQUIREMENTS" stage (capabilities, features, specs, requirements, stories and ACs, plus scope approval). |
| D-03 | Brownfield states | RECON → BASELINE → READINESS → REMEDIATION? → READY | RECON → CODE_INDEX → RECOVERED_SPEC → BASELINE → READINESS → READY | **Union:** RECON → CODE_INDEX → RECOVERED_SPEC → BASELINE → READINESS → READY, with the loop READINESS ⇄ REMEDIATION. On reaching READY, `Project.readiness_state = READY_FOR_CHANGE`. |
| D-04 | Feature Change states | INTAKE → IMPACT_ANALYSIS → PLANNING → … | INTAKE → SPEC_DELTA → IMPACT_ANALYSIS → PLANNING → … | **TECH states** (SPEC_DELTA is explicit). |
| D-05 | Bug Fix states | TRIAGE → REPRODUCTION → ROOT_CAUSE → … | TRIAGE → REPRODUCTION → EXPECTED_BEHAVIOR → ROOT_CAUSE → … | **TECH states** (EXPECTED_BEHAVIOR is explicit; the clarification / specification-decision path lives there). |
| D-06 | Lifecycle API | `POST /delivery-cycles/{id}/transition` | `POST /delivery-cycles/{id}/commands/{command}` + command principle (§23.1) | **Command API only.** No raw transition or PATCH-status endpoint exists. |
| D-07 | SpecCodeLink origin | `GENERATED_FROM_TASK \| DISCOVERED` | `GENERATED_LINEAGE \| DISCOVERED \| HUMAN_CONFIRMED` | **TECH enum.** `GENERATED_FROM_TASK` is the same as `GENERATED_LINEAGE`. |
| D-08 | Module layout | `core/workflow`, `core/integrations/outbound` | `core/commands`, `core/state`, `core/runtime`, `core/tools`, `core/execution/{snapshots,leases,worktrees}` | **TECH layout**, plus ARCH's `core/traceability/{spec_code_links,lineage}` and `core/intelligence/code_index/{parsers,entities,relations,retrieval}`. Outbound connectors live in `core/integrations/connectors`. |
| D-09 | Endpoint lists | §20 list | §23 list | **Union** of both, with TECH naming where both name the same thing (`/sources/{id}/decompose`; `/sources/{id}/derive` is an alias). |
| D-10 | Observability | JSON logs + correlation IDs + SSE; OTel later | structlog/JSON + OpenTelemetry SDK + correlation IDs | JSON logs + correlation IDs + SSE from Phase 00/01. OTel traces arrive in Phase 18. |
| D-11 | Model aliases | — | Appendix A: `product_decomposition`, `architecture`, `repository_reasoning`, `implementation`, `review`, `verification_planning` | **Appendix A plus three additions:** `planning` (Kira ImplementationSpec/TaskPlan), `orchestration` (Orchestrator) and `embedding` (semantic retrieval). All may point to one model initially (Appendix A permits this). Flagged as open question Q-03. |
| D-12 | Agent work execution path | ANALYSIS / VERIFICATION / INTEGRATION / RELEASE work types (§5.2) | Kira/Atlas/Scout described as service flows | **All agent and engineering work runs as Executions of Tasks** through scheduler → worker → executor. Task has `origin`: `IMPLEMENTATION_PLAN` (CODE_CHANGE, must reference an approved ImplementationSpec), `REMEDIATION`, `REPAIR`, `CONTROL_PLANE` (ANALYSIS/VERIFICATION/INTEGRATION/RELEASE work governed by a referenced domain object such as a ProductSource or IntegrationCandidate). This gives every model call a snapshot, lease, audit trail and retry history. Flagged as Q-01. |
| D-13 | Executor kinds | "Executor" in the execution worker | AgentRuntime invocation | The execution worker supports `AGENT_RUNTIME` executors (LLM) and `DETERMINISTIC` executors (integration merge, test runs, release). No LLM participates in a DETERMINISTIC executor. |
| D-14 | Dependent task base commit | — | contract `base_commit` | TaskContract carries `base_policy` (`CYCLE_BASE` or `DEPENDENCY_INTEGRATION`). The **ExecutionSnapshot** records the resolved `base_commit` at scheduling time. Contract immutability is preserved because the policy is fixed and the resolved SHA lives in the snapshot. |
| D-15 | `delivery_cycle_events` | — | listed as a table in §5.1 | **SQL view** over `domain_events` filtered by `delivery_cycle_id` (Phase 01). One outbox table avoids duplicate event writes inside the transition transaction. |
| D-16 | Workspace storage root | "Git + per-execution worktrees" (§27) | §29.1 `OLYMPUS_STORAGE_ROOT`, `OLYMPUS_WORKTREE_ROOT`; §29.2 "workers need filesystem/Git workspace storage" | **`OLYMPUS_WORKSPACE_ROOT`** is the single configurable physical root for canonical RepositoryWorkspaces and ExecutionWorkspaces (layout §5.7). `OLYMPUS_WORKTREE_ROOT` is kept as an optional TECH-compatible override for the execution-worktree subtree only. `OLYMPUS_REPO_ROOT` is retired. Domain rows store logical locations only (§5.9). |
| D-17 | Repository entities | Project → repository context; "Git" as an external source (§20.2) | §5.1 lists no repository tables; §23 `POST /projects/{id}/repositories`; §29.2 "registered as an external Git repository, not embedded into Olympus domain state" | The Control Plane persists **repository metadata only**: `repositories`, `repository_workspaces`, `repository_revisions` (Phase 01) and `execution_workspaces` (Phase 04, replacing the earlier `worktrees` table). Source-code bytes stay in Git (§5.9). One unified Repository abstraction covers Greenfield (`GREENFIELD_MANAGED`) and Brownfield (`EXTERNAL_CLONE`). |

Any further reconciliation discovered during implementation MUST be appended to the **Architecture Drift Log** in `STATUS.md` (see §9).

---

## 3. Phase Index

| Phase | File | Milestone (short) |
|---|---|---|
| 00 | `00-foundation-and-repository-scaffold.md` | Clean scaffold: DB + migrations + API health + test lanes + CI |
| 01 | `01-domain-model-and-control-plane-kernel.md` | Command-driven lifecycle with atomic audit; immutable TaskContract versions; Repository / RepositoryWorkspace / revision metadata model |
| 02 | `02-model-router-and-agent-runtime.md` | Live structured-output call through ModelRouter and LangGraphRuntime, with usage audit |
| 03 | `03-scheduler-execution-snapshot-and-lease.md` | READY ANALYSIS task → deterministic Execution + Snapshot + Lease → live runtime → Artifact; survives restart |
| 04 | `04-git-worktree-tool-gateway-and-governed-actions.md` | Governed repository materialization (Greenfield provisioning, external clone) → Forge in an isolated ExecutionWorkspace via ToolGateway → audited candidate commit |
| 05 | `05-product-source-intake-and-product-model.md` | Real PRD → live Kira decomposition → approved FeatureSpec scope |
| 06 | `06-architecture-implementation-spec-and-task-planning.md` | Approved architecture + ImplementationSpecs → validated Task DAG → compiled immutable TaskContracts |
| 07 | `07-code-intelligence-index.md` | Deterministic Python/FastAPI index of a repo at an exact SHA, queryable |
| 08 | `08-integration-candidate-canonical-index-and-traceability.md` | Candidate commits → IC integrated SHA → canonical repository revision + canonical index + GENERATED_LINEAGE links |
| 09 | `09-assurance-evidence-findings-and-gates.md` | Warden + Sentinel against the exact IC SHA → evidence → deterministic gates → remediation loop |
| 10 | `10-release-and-greenfield-journey.md` | **Journey 1:** PRD → verified Release R1 (live LLM) |
| 11 | `11-brownfield-discovery-and-recovered-specifications.md` | Registered external repo → clone at exact HEAD SHA → code graph → ObservedBehavior → Scout RecoveredSpecs (FACT/INFERENCE/UNCERTAINTY) |
| 12 | `12-behavioral-baselines-readiness-and-trusted-model.md` | **Journey 2:** baselines + promotion + readiness → READY_FOR_CHANGE |
| 13 | `13-spec-delta-impact-engine-and-hybrid-retrieval.md` | Spec delta → graph-derived ImpactAssessment with rationale; incremental re-index; staleness |
| 14 | `14-feature-change-journey.md` | **Journey 3:** change request → spec delta → impact → R2 |
| 15 | `15-bug-fix-journey.md` | **Journey 4:** defect → reproduction → root cause → repair → R3 |
| 16 | `16-external-integrations-and-reconciliation.md` | Signed webhooks, CI evidence, issue/PR/artifact/deploy connectors, reconciliation |
| 17 | `17-dashboard-and-operator-experience.md` | Thin Next.js command center + Orchestrator; approvals/traceability in the UI |
| 18 | `18-observability-security-and-recovery-hardening.md` | OTel tracing, LLM cost controls, security and failure-injection suites |
| 19 | `19-final-e2e-and-mvp-acceptance.md` | Four-journey chained demo from a clean environment; MVP_COMPLETE evaluation |

Dependency graph (no cycles; see `STATUS.md` §3–4):

```
00 → 01 ─┬→ 02 → 03 ─┬→ 04 ─┐
         │           └→ 05 ─┴→ 06 ─┐
         └→ 07 ────────────────────┴→ 08 → 09 → 10 → 11 → 12 → 13 ─┬→ 14 ─┐
                                                                    └→ 15 ─┴→ 16 ─┬→ 17 ─┐
                                                                                  └→ 18 ─┴→ 19
```

---

## 4. Target Repository Layout (end state)

```
olympus/
├── apps/
│   ├── control_api/            # FastAPI app, routers, auth, SSE
│   ├── scheduler_worker/       # eligibility + admission loop
│   ├── execution_worker/       # lease, snapshot, worktree, executor loop
│   └── dashboard/              # Next.js (Phase 17)
├── core/
│   ├── config/                 # settings, policy/model config loaders
│   ├── db/                     # engine, session, base, mixins, immutability helpers
│   ├── domain/                 # SQLAlchemy models + Pydantic domain schemas (by aggregate)
│   ├── commands/               # command bus, command log, idempotency
│   ├── state/                  # state machines, guard registry, transition service
│   ├── policy/                 # deterministic policy service + action policy
│   ├── repositories/           # RepositoryService, RepositoryRevisionService, WorkspaceLocator (01); materialization, credentials (04); sync (16)
│   ├── scheduler/              # eligibility, admission
│   ├── product_model/{sources,capabilities,features,specifications}/
│   ├── planning/               # architecture, implementation specs, task plan validation, contract compiler
│   ├── execution/{snapshots,leases,worktrees,executors}/
│   ├── runtime/                # agent_runtime.py, langgraph_runtime.py, model_router.py, providers/, prompts/
│   ├── tools/                  # ToolGateway, catalog, handlers, path/shell policy
│   ├── integration/            # IntegrationCandidate service
│   ├── assurance/              # evidence, obligations, findings, gates, remediation
│   ├── release/                # eligibility, manifest, release, delivery outcome
│   ├── traceability/{spec_code_links,lineage}/
│   ├── intelligence/{repository,code_index/{parsers,entities,relations,retrieval},recovered_specs,baselines,impact}/
│   ├── integrations/{inbound,connectors,reconciliation}/
│   └── observability/          # logging, correlation, tracing, metrics
├── agents/{orchestrator,kira,atlas,scout,forge,warden,sentinel,stratos}/
│   └── <agent>/{profile.py,schemas.py,graph.py,prompts/*.md}
├── config/                     # policy/default.yaml, models.yaml, model_pricing.yaml, shell_policy.yaml
├── migrations/                 # Alembic
├── tests/{unit,integration,workflow,journey,e2e,fixtures}/
├── docker-compose.yml, Dockerfile, Makefile, pyproject.toml, uv.lock, .env.example
├── plans/                      # this folder
└── STATUS.md
```

---

## 5. Cross-Cutting Conventions

### 5.1 Identity and keys

- Primary keys are UUIDv7 (`uuid6` package or app-generated) stored as `UUID`.
- Every user-facing aggregate also has a human-readable `key`, unique per project and generated from `project_sequences(project_id, sequence_name, next_value)` inside the creating transaction: Project `SUPPORTDESK`, `DC-001`, `TASK-001`, `TC-001` (versions written `TC-001:v2`), `EX-001`, `IC-001`, `EV-001`, `FND-001`, `APR-001`, `R1`, `CAP-001`, `FEAT-001`, `SPEC-FEAT-001`, `SPEC-IMPL-001`, `REQ-001`, `US-001`, `AC-001-01`, `BASELINE-001`, `CR-001`, `DEF-001`, `IA-001`.
- Versioned entities use `(lineage_key, version)` with `UNIQUE(project_id, lineage_key, version)`. The `lineage_key` (for example `SPEC-FEAT-001`) is stable across versions.

### 5.2 Immutability enforcement (two layers)

1. **Application guard:** repositories refuse updates to immutable rows and raise `ImmutableRecordError`.
2. **Database trigger:** a PostgreSQL `BEFORE UPDATE OR DELETE` trigger, `olympus_forbid_mutation()`, is created in Phase 01 and attached to immutable tables or immutable states. Covered tables include: issued `task_contracts`, `execution_snapshots`, terminal `executions` (status columns only), `evidence`, approved spec versions, `audit_events`, `domain_events` (except `published_at`), `release_manifests`, `inbound_events` (payload columns) and `model_calls`.

### 5.3 Transactions and events

- Every authoritative mutation goes through the domain service that owns it, inside one transaction: lock → verify expected state → guards → persist → append `domain_events` (outbox) + `audit_events`. The commit happens only after all of these succeed (TECH §5.3, §7.1).
- The outbox publisher (`core/observability/outbox.py`, Phase 01) publishes after commit to in-process subscribers and the SSE stream. Delivery is at-least-once; consumers are idempotent.
- Event names follow TECH §24.1 (`delivery_cycle.transitioned`, `execution.completed`, and so on). New events must use `<aggregate>.<past_tense_verb>` and be registered in `core/domain/events.py`.

### 5.4 Command principle

- Clients issue commands (`approve_scope`, `start_planning`, `cancel_execution`, `approve_release` and so on). No endpoint lets a client set a lifecycle status field directly.
- Every mutating command accepts an `Idempotency-Key` header. `command_log(actor_id, idempotency_key)` is unique, and a replay returns the stored result.
- Every command records `actor_id` (HUMAN | AGENT | SYSTEM | INTEGRATION) and `correlation_id`.

### 5.5 Actors and authority

- AGENT actors can never: decide an Approval, finalize a Gate, compute release eligibility, transition a DeliveryCycle, or write canonical entities directly. Agents return structured proposals, and Olympus services validate and persist them.
- Python package boundaries are enforced with `import-linter` (Phase 00): `agents.*` must not import `core.db`, `core.domain.*.repository` or `core.state`; agents receive only runtime request objects and a ToolGateway client.

### 5.6 Configuration (env vars; TECH §29.1 plus additions)

```
DATABASE_URL=postgresql+psycopg://olympus:olympus@localhost:5432/olympus
OLYMPUS_ENV=local|test|integration|journey|production
OLYMPUS_STORAGE_ROOT=./var/olympus                    # content-addressed artifacts and source bodies (never project source-of-truth for code)
OLYMPUS_WORKSPACE_BACKEND=LOCAL_FILESYSTEM            # only backend in the MVP (D-16)
OLYMPUS_WORKSPACE_ROOT=./var/olympus/workspaces       # physical root for canonical RepositoryWorkspaces and ExecutionWorkspaces
OLYMPUS_WORKTREE_ROOT=                                # optional TECH §29.1 override for the execution-worktree subtree; empty = derive from OLYMPUS_WORKSPACE_ROOT
OLYMPUS_SECRET_KEY=                                   # Phase 16 `secret:` credential backend encryption key (SecretStr; never logged)
MODEL_PROVIDER=anthropic|openai
MODEL_DEFAULT=<model id>
MODEL_PRODUCT_REASONING= MODEL_PLANNING= MODEL_ARCHITECTURE_REASONING=
MODEL_REPOSITORY_REASONING= MODEL_CODE_IMPLEMENTATION= MODEL_CODE_REVIEW=
MODEL_VERIFICATION= MODEL_ORCHESTRATION= MODEL_EMBEDDING=
ANTHROPIC_API_KEY= OPENAI_API_KEY=
LLM_LIVE_TESTS=0|1
LLM_TEST_BUDGET_USD=5.00
RUNTIME_CHECKPOINT_SCHEMA=langgraph_runtime
GIT_PROVIDER=local|github
GITHUB_TOKEN= GITHUB_WEBHOOK_SECRET=
OLYMPUS_WEBHOOK_SECRETS_FILE=./config/webhook_secrets.local.yaml
OTEL_EXPORTER_OTLP_ENDPOINT=
```

### 5.7 Storage layout

```
$OLYMPUS_STORAGE_ROOT/artifacts/sha256/<aa>/<hash>        # content-addressed artifacts & product source bodies (evidence copies, not code truth)

$OLYMPUS_WORKSPACE_ROOT/                                   # LOCAL_FILESYSTEM workspace backend (illustrative physical layout)
  projects/
    <project_id>/
      repo/                                                # canonical RepositoryWorkspace — bare Git repository (Q-13); never written by agents
      worktrees/
        EX-101/                                            # ExecutionWorkspace (GIT_WORKTREE), branch olympus/EX-101 (writable)
        EX-102/                                            # ExecutionWorkspace, detached at a SHA (readonly / verification, with overlay)
```

The domain stores only the **logical location** (`projects/<project_id>/repo`, `projects/<project_id>/worktrees/<EX-key>`) and the storage backend. `WorkspaceLocator` (Phase 01, `core/repositories/workspace_locator.py`) is the only component that maps a logical location to a physical path. When `OLYMPUS_WORKTREE_ROOT` is set, `projects/<project_id>/worktrees/<EX-key>` resolves to `$OLYMPUS_WORKTREE_ROOT/<project_id>/<EX-key>` instead. Every process (control-api, scheduler-worker, execution-worker) must resolve the same root, so in containers the workspace root is a shared volume.

### 5.8 Migrations

- Alembic revisions are named `NNNN_<phase>_<topic>.py` (for example `0006_p03_executions_snapshots_leases.py`). Each phase owns the migrations listed in its plan.
- Parallel phases (07 alongside 02–06; 04 alongside 05; 14 alongside 15; 17 alongside 18) must rebase their `down_revision` onto the current head at merge time. Never create two heads on `main`.
- Every migration must support `upgrade` and `downgrade`, and is tested by `tests/integration/persistence/test_migrations.py` (upgrade head → downgrade base → upgrade head).

### 5.9 Repository ownership, materialization and revision model

This section is authoritative for every phase that touches repositories, workspaces, commits, code indexes or releases. Phase files reference it instead of restating it.

#### 5.9.1 Ownership split

| Owner | Owns |
|---|---|
| **Git storage** (the canonical RepositoryWorkspace on the workspace backend, plus any provider remote) | Source-code bytes: trees, blobs, commits, branches, tags. Greenfield-generated code, Brownfield code and every candidate/integrated/released commit live **only** here. |
| **Olympus Control Plane** (PostgreSQL) | Project → Repository relationship; repository identity; `source_type`; `provider`; `remote_url`; `default_branch`; `credential_ref`; repository lifecycle `status`; workspace identity and logical location; `registered_sha`; `canonical_commit`; `released_commit`; the append-only revision history; IntegrationCandidate references; Code Intelligence index references; release references; traceability; audit. |

Rules:
- No control-plane table stores source-file bodies as canonical state. Code tables hold SHAs, paths, spans, content hashes and structural metadata only. Content-addressed artifacts (diff artifacts, Sentinel check files, reproduction tests, model transcripts under the retention policy) are **evidence copies** referenced by hash. They are never read back as the project's code.
- Agents write code only into their assigned ExecutionWorkspace. Code reaches the project only as Git commits (candidate commit → IntegrationCandidate → canonical revision → release).
- For a `GREENFIELD_MANAGED` repository with no remote, the canonical RepositoryWorkspace is the **only** copy of the source bytes. Backups must therefore include the workspace root (Phase 18 RC-12), and Q-16 covers whether a remote is required before R1.

#### 5.9.2 Domain concepts

```
Repository                      (Phase 01; one per Project in the MVP — Q-11)
  id, project_id, name
  source_type:   GREENFIELD_MANAGED | EXTERNAL_CLONE
  provider:      LOCAL | GITHUB | GITEA | GITLAB | BITBUCKET     (GITLAB/BITBUCKET: reserved extension points, not implemented in the MVP)
  remote_url                    (no userinfo; file:// for LOCAL external sources; null for an unattached GREENFIELD_MANAGED repo)
  default_branch
  registered_sha                (immutable materialization baseline: Greenfield baseline commit, or the HEAD captured by clone)
  canonical_commit              (the authoritative project revision; written only by RepositoryRevisionService)
  released_commit               (latest released revision = default-branch ref; written only by RepositoryRevisionService)
  status:        PROVISIONING | CLONING | READY | SYNCING | ERROR
  workspace_id → RepositoryWorkspace
  credential_ref                (reference only, e.g. "env:GITEA_TOKEN", "secret:supportdesk-git"; never a secret value)
  created_at, updated_at

RepositoryWorkspace             (Phase 01 identity; Phase 04 materialization)
  id, repository_id
  workspace_type:   CANONICAL
  storage_backend:  LOCAL_FILESYSTEM
  logical_location  ("projects/<project_id>/repo"; relative, no "..", never a host path)
  materialized_commit           (the SHA most recently materialized/fetched and verified in the workspace)
  state:  PENDING | MATERIALIZING | READY | REFRESHING | MISSING | ERROR
  created_at, updated_at

ExecutionWorkspace              (Phase 04; replaces the earlier `worktrees` table)
  id, execution_id (unique), repository_id
  type:   GIT_WORKTREE
  mode:   WRITABLE | READONLY
  base_commit                   (== ExecutionSnapshot.base_commit)
  logical_location  ("projects/<project_id>/worktrees/<EX-key>")
  branch                        ("olympus/<EX-key>" for WRITABLE; null when detached READONLY)
  state:  CREATING | ACTIVE | RETAINED | REMOVED | ORPHANED
  created_at, updated_at, removed_at

RepositoryRevision              (Phase 01; append-only, immutable)
  id, repository_id, sequence, commit_sha
  cause:  MATERIALIZED | INTEGRATION_READY | RELEASED | EXTERNAL_SYNC | REVERTED
  integration_candidate_id?, release_id?, repository_event_id?, reverts_revision_id?
  canonical_index_version_id?, actor_id, correlation_id, created_at
```

The **canonical RepositoryWorkspace is a bare Git repository** (MVP default, Q-13). It has no working tree, so no process can edit files in it. Reads at a SHA use `git cat-file` / `git ls-tree`, and every checkout is an ExecutionWorkspace (`git worktree add`) that shares its object store. Candidate commits therefore exist as objects and `olympus/<EX-key>` refs in the canonical object store, but they are **not** the canonical revision.

#### 5.9.3 Materialization (Phase 04 service; Greenfield wiring 06; Brownfield wiring 11; remote providers 16)

```
GREENFIELD_MANAGED                                   EXTERNAL_CLONE
Project created                                      User / integration registers repository
→ GREENFIELD cycle created → Repository declared     → Repository(status=CLONING, provider, remote_url, default_branch?, credential_ref)
  (status=PROVISIONING, provider=LOCAL)               → credential resolution (connector → credential provider; never persisted)
→ provisioning: git init --bare in canonical          → git clone --bare / fetch into the canonical RepositoryWorkspace
  RepositoryWorkspace                                 → branch resolution (default_branch or remote HEAD symref)
→ baseline commit (README.md, .gitignore, OLYMPUS.md) → exact HEAD SHA capture
→ registered_sha = canonical_commit = baseline SHA    → repository validation (connectivity, branch, size/LFS/submodule policy)
→ revision #1 (MATERIALIZED), status READY            → registered_sha = canonical_commit = HEAD; revision #1 (MATERIALIZED); READY
```

- Materialization is a deterministic SYSTEM operation performed by `RepositoryMaterializationService` through `ToolGateway.handle_system` → `git_local` (plus a provider connector for network transport in Phase 16). Every step is an audited ActionRequest/ConnectorAction with an idempotency key `repo:<repository_id>:<kind>:<attempt>`. A materialization loop in the scheduler-worker resumes interrupted attempts after a crash (adopting a complete workspace if HEAD and object connectivity verify, otherwise re-cloning).
- Failure → Repository `ERROR` + RepositoryWorkspace `ERROR` with a reason. Retry happens only via the `retry_materialization` command. A Repository that is not `READY` blocks every stage that needs code (guard `repository_ready_with_canonical_commit`, base-commit resolution `REPOSITORY_NOT_READY`).
- A registered external source (a fixture path or a remote) is **never written** by materialization or by any execution. Pushes to a remote are separate governed actions (Phase 16).

#### 5.9.4 Unified post-materialization model

Once a canonical RepositoryWorkspace is `READY`, Greenfield and Brownfield use **one** execution architecture. There is no separate Greenfield or Brownfield execution system:

```
Canonical RepositoryWorkspace (canonical_commit)
→ ExecutionWorkspace (GIT_WORKTREE at snapshot.base_commit)      [04]
→ TaskContract → Execution                                       [01, 03, 06]
→ Candidate Commit on olympus/<EX-key>                           [04]
→ IntegrationCandidate → integrated_sha                          [08]
→ canonical revision advanced to integrated_sha                  [08]
→ canonical Code Intelligence index at integrated_sha            [08, 13]
→ Assurance (Warden, Sentinel, Evidence at integrated_sha)       [09]
→ Release (default branch ff + tag at integrated_sha)            [10, 16]
```

The DeliveryCycle `base_sha` is **pinned** from `Repository.canonical_commit` by the first transition that needs code, guarded by `repository_ready_with_canonical_commit`:
- GREENFIELD `start_planning`;
- BROWNFIELD `start_code_index`;
- FEATURE_CHANGE `start_impact_analysis`;
- BUG_FIX `start_reproduction`;
- REMEDIATION `start_planning` (INTAKE → PLANNING).

#### 5.9.5 Canonical revision rule

```
EX-221 → candidate commit AAA ┐
EX-222 → candidate commit BBB ├→ IntegrationCandidate IC-003 → integrated_sha DEF
EX-223 → candidate commit CCC ┘
```

- AAA, BBB and CCC are **not** canonical project state. They never appear in `repository_revisions`, the canonical index pointer, evidence, manifests or SpecCodeLinks of `GENERATED_LINEAGE` authority.
- Only when IC-003 reaches `READY` does `RepositoryRevisionService.advance(cause=INTEGRATION_READY)` set `canonical_commit = DEF`. This happens in **one transaction** with the canonical index pointer move to the CANONICAL index built at DEF and IC → READY (Phase 08). Repository policy `repository.canonical_advance_on: INTEGRATION_READY` is the MVP default and the only supported value.
- Warden and Sentinel target DEF. Every Evidence row references DEF. Gate finalization requires `Repository.canonical_commit == IC.integrated_sha` (Phase 09).
- Release R2 references IC-003 / DEF. Stratos fast-forwards the default branch to DEF and tags it. `RepositoryRevisionService` records `RELEASED` and sets `released_commit = DEF` (Phase 10).
- The **canonical revision** is the assurance/development target. The **released revision** is the default-branch ref. They are equal after every completed release.
- `canonical_commit` changes only through the governed transitions above, plus:
  - `EXTERNAL_SYNC`: Phase 16 adoption of a classified external fast-forward (Q-10);
  - `REVERTED`: a cycle whose IC holds an unreleased canonical revision is CANCELLED/FAILED, so the revision returns to the previous released/adopted revision (Phase 08).
- While one cycle's IC holds an unreleased canonical revision, another cycle cannot create an IC (`CANONICAL_REVISION_HELD`, Q-12).
- Merge conflicts never advance anything. They become a Finding plus remediation work (Phase 08).

#### 5.9.6 Candidate vs canonical Code Intelligence index

| | Candidate index | Canonical index |
|---|---|---|
| Represents | an ExecutionWorkspace's candidate commit (or an ad-hoc SHA for inspection) | exactly `Repository.canonical_commit` (an IC `integrated_sha`, a Brownfield `registered_sha`, or an adopted external SHA) |
| `kind` / `source` | `CANDIDATE` / `EXECUTION` | `CANONICAL` / `INTEGRATION_CANDIDATE`, `REPOSITORY_SNAPSHOT`, `EXTERNAL_PUSH`, `RELEASE` |
| Lifetime | temporary; DISCARDED after integration | current until the canonical revision moves; then SUPERSEDED (released versions are retained) |
| Use | inspection, per-execution entity changes, impact preview | project truth: product-to-code lineage, impact, assurance context, release manifests |
| Pointer | never referenced by `repository_index_pointers` | `repository_index_pointers.canonical_index_version.commit_sha == repositories.canonical_commit` |

Indexes are always built from Git objects at an exact SHA (Phase 07). Uncommitted ExecutionWorkspace changes are never indexed.

#### 5.9.7 Repository connectors

`RepositoryConnector` responsibilities. Every mutating or network operation crosses `ToolGateway` as an ActionRequest:

| Responsibility | MVP implementation | Phase |
|---|---|---|
| register (validate provider, URL, credential_ref shape) | `RepositoryService` + provider validation | 01 (LOCAL), 16 (remote) |
| clone / fetch | `git_local.clone_repository` / `git_local.fetch` (file:// origins); network transport + credentials via `git_provider.<github,gitea>` | 04, 16 |
| resolve branch / resolve HEAD / read metadata | `git_local.resolve_branch`, `resolve_commit`, `read_metadata` | 04 |
| checkout / create worktree | `WorktreeManager` (ExecutionWorkspace) | 04 |
| commit | `git.commit` tool (execution branch only) | 04 |
| merge / rebase | `git_local.merge_candidates` (merge `--no-ff`); rebase is not used in the MVP and is denied by policy | 04, 08 |
| fast-forward / tag (release) | `git_local.fast_forward_ref`, `create_tag` (Stratos only) | 04, 10 |
| push (when policy permits) | `git_provider.push_branch`, `push_release` | 16 |
| provider API (PR, webhook, merge status) | `git_provider.<github,gitea>` | 16 |
| GitLab / Bitbucket | provider enum values and `RepositoryConnector` protocol reserved; registration returns 422 `PROVIDER_NOT_SUPPORTED` | 16 (extension point) |

#### 5.9.8 Credentials

- `Repository.credential_ref` (and `connector_configs.secret_ref`, Phase 16) holds a **reference** in the form `<scheme>:<name>`, with scheme ∈ {`none`, `env`, `file`, `secret`}.
- The API rejects anything that looks like a secret value (token prefixes, PEM blocks, high-entropy strings) with 422, and it also rejects a `remote_url` that contains userinfo.
- `CredentialResolver` (protocol, Phase 04; `SecretProvider` backends, Phase 16) resolves the reference **only inside connector code**. It injects the credential per-process (for example `GIT_ASKPASS` or a header via env) and never writes it to `.git/config`, a remote URL, ActionRequest params, logs, snapshots, artifacts or agent context.
- API responses return `credential_ref` and a `credential_status` (`NOT_REQUIRED | CONFIGURED | MISSING | INVALID`), never the value.

#### 5.9.9 Synchronization and staleness

```
remote advances (webhook or poll)            [16]
→ governed fetch (Repository SYNCING)        [04 git_local.fetch / 16 git_provider.fetch]
→ classify new head (OLYMPUS_RELEASE | EXTERNAL_FAST_FORWARD | EXTERNAL_REWRITE | STALE)
→ adopt? (EXTERNAL_FAST_FORWARD only, policy) → RepositoryRevisionService.advance(EXTERNAL_SYNC) + canonical index at the new SHA
→ StalenessService.on_canonical_revision_changed   [13]
    TaskContracts/Tasks whose resolved inputs (canonical index version, base) are superseded → REVALIDATION_REQUIRED
    QUEUED/LEASED Executions whose snapshot.base_commit is not an ancestor of the new canonical revision → STALE
    CANDIDATE indexes based on a non-ancestor → DISCARDED; ImpactAssessments on a superseded index → STALE
    ACTIVE baselines exercising changed entities → REVALIDATION_REQUIRED
→ EXTERNAL_DRIFT / EXTERNAL_REWRITE Findings block release until a new IC is integrated from the new base
```

Work never silently continues against an unexpected repository state:
- the worker re-checks `Repository.status == READY` and that `snapshot.base_commit` exists in the canonical workspace before creating an ExecutionWorkspace (`REPOSITORY_NOT_READY` / `BASE_COMMIT_UNAVAILABLE`);
- `EXTERNAL_REWRITE` is never adopted without a HUMAN acknowledgement.

#### 5.9.10 Open repository / storage decisions

Working defaults live in `STATUS.md` §12. They do not change the ownership split or the unified workspace model.

| ID | Decision | Working default |
|---|---|---|
| Q-10 | Does adopting an external default-branch fast-forward as `canonical_commit` (`EXTERNAL_SYNC`) match ARCH §13.1? | Yes for the project baseline. Assurance still requires pointer == IC SHA at ASSURANCE entry. |
| Q-11 | One Repository per Project? | Yes for the MVP (`UNIQUE(project_id)`). Relax later with cycle-level selection; entity shape stays. |
| Q-12 | May two cycles hold unreleased canonical revisions at once? | No. `CANONICAL_REVISION_HELD`. Same-cycle remediation ICs are allowed and supersede. |
| Q-13 | Bare vs non-bare canonical RepositoryWorkspace? | Bare Git repository. Checkouts are ExecutionWorkspaces only. |
| Q-14 | Where do `credential_ref` values resolve? | Phase 04: `none:` / `env:`. Phase 16: plus `file:` and encrypted `secret:` (`OLYMPUS_SECRET_KEY`). External secret managers are post-MVP. |
| Q-15 | Non-local workspace backends / multi-host workers? | Out of MVP. `LOCAL_FILESYSTEM` under one shared `OLYMPUS_WORKSPACE_ROOT`. |
| Q-16 | Must a `GREENFIELD_MANAGED` repository have a remote before R1? | No. Journey 1 completes locally. Phase 16 `attach_remote` is optional; Phase 19 Stage A uses it for Gitea. RC-12 must back up the workspace root. |

---

## 6. Testing Conventions

### 6.1 Markers (registered in `pyproject.toml` in Phase 00)

`unit`, `persistence`, `integration`, `workflow`, `git`, `connector`, `connector_live`, `security`, `recovery`, `live_llm`, `journey`, `e2e`, `ui`.

### 6.2 Standard commands

```
make setup            # uv sync; pre-commit install
make db-up            # docker compose up -d postgres
make migrate          # uv run alembic upgrade head
make lint             # uv run ruff check . && uv run ruff format --check . && uv run lint-imports
make typecheck        # uv run mypy core apps agents
make test-unit        # uv run pytest -m unit
make test-persistence # uv run pytest -m persistence
make test-integration # uv run pytest -m "integration and not live_llm"
make test-live        # LLM_LIVE_TESTS=1 uv run pytest -m live_llm --live-required
make test-journey     # LLM_LIVE_TESTS=1 uv run pytest -m journey --live-required
make check            # lint + typecheck + unit + persistence + integration (deterministic lane)
```

### 6.3 Live-LLM policy enforcement (applies to every phase)

- `FakeProvider` (Phase 02) is the **only** permitted model stub. ModelRouter refuses to load it unless `OLYMPUS_ENV in {local, test}`. When `OLYMPUS_ENV` is `integration` or `journey`, the ModelRouter must refuse to construct `FakeProvider` (a startup error).
- `--live-required` (pytest plugin `tests/plugins/live_guard.py`, Phase 02) turns any **skipped** `live_llm`/`journey` test into a **failure**. A skipped live suite is never evidence.
- Journey tests call `assert_live_llm_proof(cycle_id, stages=[...])` (Phase 10 helper). For each model-dependent stage, it asserts that `model_calls` rows exist with `provider != "fake"`, a non-null `provider_request_id` and `status = SUCCEEDED`, correlated to the stage's execution.
- Mocks are allowed only for unit tests of: provider timeout, invalid JSON, malformed structured output, provider failure, network failure, retry logic, rate limiting, clock/heartbeat and filesystem failures, and connector transport (TECH §27.3).
- Hand-authored **input** fixtures (PRD text, a reference repository, defect reports) are allowed. Hand-authored **model output** fixtures are forbidden in integration, workflow, journey and e2e tests.

---

## 7. Reference Application: SupportDesk

The demo narrative is `PROJECT: SupportDesk` (ARCH §26.1).

| Fixture | Path (created in) | Purpose |
|---|---|---|
| SupportDesk PRD | `tests/fixtures/supportdesk/PRD.md` (Phase 05) | Greenfield input: ticket management (create, list, get, update status, close; default status OPEN; FastAPI + SQLAlchemy + pytest). |
| Brownfield reference repo | `tests/fixtures/repos/supportdesk_r1/` (Phase 07) | Hand-written Python FastAPI repository equivalent to an R1 SupportDesk. Tests copy it to a temp dir, run `git init` and commit it there (the external **origin**). They then register it as an `EXTERNAL_CLONE` Repository (`provider=LOCAL`, `remote_url=file://…`), so the canonical RepositoryWorkspace is a clone and the origin is never written (§5.9.3). Used for deterministic indexing, Brownfield, Feature Change and Bug Fix tests independent of Greenfield's non-deterministic output. |
| Seeded defect variant | `tests/fixtures/repos/supportdesk_defect_closed_update/` (Phase 15) or a patch on `supportdesk_r1` | "Updating a CLOSED ticket returns HTTP 500" (ARCH §18). |
| Change request | `tests/fixtures/supportdesk/change_priority.md` (Phase 14) | "Add ticket priority: LOW, MEDIUM, HIGH." |

The chained demo (Phase 19) runs DC-001 through DC-004 on one Project, starting from the real Greenfield output. Open question Q-05 covers how the defect is introduced in the chained demo.

---

## 8. Global Guardrails (apply to every phase)

Implementation agents MUST NOT:

1. Add any endpoint that sets a lifecycle/status field directly (no PATCH status).
2. Let any agent module import persistence or state-transition code.
3. Make LangGraph checkpoints, model transcripts or runtime memory a source of Project, DeliveryCycle, Task, Execution, Evidence, Gate, Approval, IntegrationCandidate or Release state.
4. Rewrite historical Execution, Evidence, Snapshot, AuditEvent or issued TaskContract rows.
5. Let Warden or Sentinel output set `Gate.status` or release eligibility.
6. Satisfy a mandatory AC with `MODEL_ASSESSMENT` or `STATIC_REVIEW` evidence when executable evidence is required.
7. Promote a RecoveredSpec, inference or observed behavior to canonical intent without a recorded promotion decision.
8. Allow any external mutation outside an `ActionRequest` through the ToolGateway.
9. Use canned or mocked LLM outputs as integration, workflow, journey or e2e proof.
10. Write to the canonical checkout, protected branches or release refs from implementation agents.
11. Introduce Redis, Celery, Neo4j, Kubernetes or a separate vector DB (TECH §2.1) without an approved drift entry.
12. Change an architectural invariant to make a test pass. Escalate instead (§9).
13. Store source-code bytes (generated or cloned) in control-plane tables as canonical state, or let any agent write code outside its assigned ExecutionWorkspace (§5.9.1).
14. Persist a credential value, or a machine-specific filesystem path, in a domain row or API payload. Store `credential_ref` and logical locations only (§5.9.2, §5.9.8).
15. Change `Repository.canonical_commit` or `released_commit` anywhere except `RepositoryRevisionService`, or let a candidate commit become the canonical revision without a READY IntegrationCandidate (§5.9.5).

---

## 9. Architecture Drift Protocol

If repository reality or implementation constraints conflict with a plan:

1. Identify the mismatch and the affected plan and invariant sections.
2. Determine whether a semantically equivalent implementation exists.
3. Prefer the smallest compatible adjustment.
4. Record it in `STATUS.md` → *Architecture Drift Log* (ID, phase, description, decision, invariant impact, approver).
5. If an invariant from `STATUS.md` §7 would change, set the phase to `BLOCKED` and escalate to the human owner. Do not encode the drift in code.

---

## 10. Phase Execution Protocol (for implementation agents)

1. Confirm in `STATUS.md` that every `Depends On` phase is `COMPLETE`.
2. Set the phase to `IN_PROGRESS` in `STATUS.md`.
3. Execute §10 *Development Tasks* in order, ticking each checkbox in the phase file. Tick the matching task-group item in `STATUS.md` Progress once every task in that group is done.
4. Run the phase's §12 commands. Every listed suite must pass. Live suites run with `--live-required`.
5. Verify every §14 acceptance criterion and every §15 exit criterion and record the evidence (test names, command output summary) in `STATUS.md` Notes.
6. Only then set the phase to `COMPLETE`, update Overall Status, Journey Readiness, Invariant Tracker, Integration Tracker and LLM Readiness.
