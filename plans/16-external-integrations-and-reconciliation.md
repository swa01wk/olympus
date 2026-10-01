# Phase 16 — External Integrations: Inbound Adapters, Outbound Connectors and Reconciliation

## 1. Objective

Complete the **inbound** and **outbound** integration models (ARCH §20; TECH §15–16):

- Authenticated, idempotent, source-version-aware inbound adapters for:
  - the **Git provider** (repository registration, push / default-branch events);
  - the **issue tracker** (change requests and defects);
  - **CI/test callbacks** (exact-SHA external evidence);
  - **operator API commands**.
- Governed, idempotent, auditable outbound connectors for:
  - **Git provider** (push branch/refs, PRs, merge status);
  - **CI trigger/status**;
  - **issue updates**;
  - **artifact publication**;
  - **deployment** (Stratos);
  - **allowlisted external HTTP APIs**.
- A **reconciliation subsystem**: unknown or partial outbound outcomes are resolved by querying provider state before any retry, missed or out-of-order inbound events are reconciled, and external repository drift is detected and routed into re-index and staleness.
- **Remote repository providers** for the unified Repository model (README §5.9.7–5.9.9):
  - `GITHUB`/`GITEA` `RepositoryConnector` implementations (network clone/fetch/push through `git_provider.<provider>`, used by Phase 04's materializer);
  - `SecretProvider` backends that resolve `Repository.credential_ref` / `connector_configs.secret_ref`;
  - `attach_remote` for `GREENFIELD_MANAGED` repositories;
  - governed adoption of external default-branch advances as `EXTERNAL_SYNC` canonical revisions (Q-10).
  `GITLAB`/`BITBUCKET` stay reserved extension points.

## 2. Architectural Context

- **Position:** the Integrations plane (`core/integrations/{inbound,outbound,connectors,reconciliation}`). It touches every journey at the edges.
- **Upstream:**
  - 05: InboundService, `integration_sources`, `inbound_events`.
  - 04: Connector protocol, `connector_actions`/`connector_results`, ToolGateway, `RepositoryConnector` / `CredentialResolver` protocols, `RepositoryMaterializationService`.
  - 01/08: Repository model, `RepositoryRevisionService`, canonical revision lock.
  - 13: StalenessService, incremental index.
  - 14/15: `intake_change_request`, `intake_defect`.
  - 10: Stratos release executor.
  - 09: EXTERNAL_CI evidence type.
- **Downstream:** 17 (Integration views), 18 (security hardening of secrets and webhooks), 19 (chained demo uses the external push for the defect, Q-05).
- **Invariants (ARCH §20.1–20.4, §22 acceptance):**
  - Inbound events are authenticated and attributed, idempotent and correlation-aware.
  - Events never bypass lifecycle, scope, approval or release policy.
  - Outbound mutations cross ToolGateway with execution identity, contract scope and policy.
  - Every mutating action carries an idempotency key.
  - Unknown results are reconciled before retry.
  - Protected-branch/release mutation is denied to implementation agents.
  - Every external mutation is traceable to project/cycle/task/execution/action/connector request/external id.
  - Connector secrets never enter agent context.

## 3. Current Repository Assessment

Inspection on 2026-10-01: none of this exists.

### Existing
- (after 05) InboundService pipeline, `document_upload`, `change_request_api`/`defect_report_api` adapters (14/15) — **RETAIN / EXTEND** (HMAC auth, source_version staleness, polling).
- (after 04) Connector protocol and registry, `git_local`, `connector_actions` with an UNKNOWN status, RECONCILIATION_REQUIRED ActionRequests — **EXTEND** (reconciler, external connectors).
- (after 10) Stratos local ff+tag — **EXTEND** (remote push + deployment, policy-gated).
- (after 09) EXTERNAL_CI evidence type — **EXTEND** (CI callback source).
- (after 01/04) Repository with `provider`, `remote_url`, `default_branch`, `credential_ref`; `RepositoryConnector` registry with GITHUB/GITEA registered as `NotConfigured`; `CredentialResolver` with `none:`/`env:` only — **EXTEND** (remote providers, `SecretProvider` backends).

### Partial
- `integration_sources.auth_kind` supports HMAC but no verifier — **EXTEND**.

### Missing
- Git provider/issue/CI/artifact/deploy/http connectors, webhook adapters, reconciliation items and worker loop, drift detection, external links and the connector config model — **ADD**.

### Refactor / Migration Required
- No repository schema refactor: `provider`, `remote_url`, `default_branch` and `credential_ref` already exist (Phase 01). Registration of `GITHUB`/`GITEA` `EXTERNAL_CLONE` repositories is enabled. The canonical RepositoryWorkspace (`projects/<project_id>/repo`) is then a bare clone of the remote with `origin` configured **without** credentials.
- `provider=LOCAL` repositories are unchanged.

## 4. Scope

### 4.1 Connector configuration and secrets
- Table `connector_configs` (per project): `connector`, `provider` (GITHUB | GITEA | LOCAL | HTTP), `base_url`, `secret_ref`, `enabled_actions`, `rate_limit`, `active`.
- `SecretProvider` (backends `env:`, `file:`, `secret:`; the last is an encrypted local secret store keyed by `OLYMPUS_SECRET_KEY`, Q-14) implements Phase 04's `CredentialResolver`. It resolves `Repository.credential_ref` and `connector_configs.secret_ref` (same grammar) only inside connector code. Secrets are redacted from logs, audit and artifacts.
- Secret **values** are written only through the write-only endpoint `PUT /secrets/{name}` (HUMAN OPERATOR). It stores the value in the `secret:` backend and returns the reference name, never the value. Repository and connector rows store only the reference.
- GitHub uses App installation tokens (short-lived) when configured, with a PAT fallback. Gitea uses an access token.

### 4.1a Remote repositories (README §5.9.7)
- **Registration of remote `EXTERNAL_CLONE` repositories** (`provider ∈ {GITHUB, GITEA}`, HTTPS `remote_url`, `credential_ref`):
  - `validate_registration` checks the URL shape, the provider and `credential_status`, and reads repository metadata through the provider API;
  - Phase 04's `materialize_external` then clones through `git_provider.<provider>.clone` (network transport, credential via askpass) and continues unchanged: branch resolution, HEAD capture, validation, revision #1.
- **`attach_remote`** (HUMAN OPERATOR, `GREENFIELD_MANAGED` only):
  - `{provider, remote_url, credential_ref}` → validate → governed `git_provider.push_release` of the current default branch and release tags (the remote must be empty, or equal to an ancestor of the default branch) → set `provider`/`remote_url`/`credential_ref` and register the webhook;
  - `source_type` stays `GREENFIELD_MANAGED`. Phase 19 Stage A uses this for Gitea.
- `GITLAB` / `BITBUCKET`: the enum values and `RepositoryConnector` protocol are the extension point. Registration returns 422 `PROVIDER_NOT_SUPPORTED`. No connector is implemented in the MVP.

### 4.2 Inbound adapters (all through `InboundService`; endpoint `POST /integrations/inbound/{source}`, alias `POST /integrations/events/{provider}` per ARCH)

| Adapter | Auth | Event types | Command / result | Staleness rule |
|---|---|---|---|---|
| `git_provider_webhook` (GitHub/Gitea) | HMAC-SHA256 (`X-Hub-Signature-256` / `X-Gitea-Signature`), replay window 5 min via the delivery timestamp | `push`, `create`/`delete` ref, `repository` (default-branch change) | `record_repository_event` → RepositoryEvent; if default-branch head changed: `RepositorySyncService.sync(repo)` | `before`/`after` SHAs; an event whose `after` is an ancestor of the known head gives STALE (recorded, no mutation) |
| `repository_registration` (API) | operator token | register/update remote | `register_repository` / `update_repository` + webhook registration (outbound `git_provider.ensure_webhook`) | — |
| `issue_tracker_webhook` (GitHub Issues/Gitea) | HMAC | `issues.opened`/`labeled`/`edited`/`closed`, `issue_comment` | label `olympus:change` → `intake_change_request(source_type=ISSUE_TRACKER, external_ref=<repo>#<n>)`; label `olympus:defect` → `intake_defect`; edit while cycle in INTAKE/TRIAGE → new ProductSource version; otherwise INFO (recorded, no mutation) | `updated_at` vs the last stored source_version |
| `ci_callback` | HMAC (per CI source) | `run.completed` | `ingest_external_ci_result` → validates the SHA is a known IC integrated SHA or release SHA **and** the correlation id matches a `ci.trigger_verification` action (or the policy allows unsolicited runs for that SHA) → Evidence `EXTERNAL_CI` with junit artifact → maps junit test ids to obligations → gate finalizer re-evaluation if the gate is not yet finalized | a run for an SHA superseded by a newer IC gives STALE |
| `operator_api` | bearer token (HUMAN actor) | approvals, clarifications, commands | existing typed commands; recorded as inbound events for correlation | — |

Common rules:
- unique `(source_type, source_id, event_id)` → DUPLICATE ACK (200) without re-dispatch;
- a bad signature → 401 REJECTED (row stored, payload hash only);
- a correlation id is assigned when missing.

### 4.3 Repository sync and drift (`RepositorySyncService`, `core/repositories/sync.py`)
1. Repository READY → SYNCING (Phase 01 machine). `git fetch --prune origin` into the canonical RepositoryWorkspace's `refs/remotes/origin/*` (governed `git_provider.fetch` connector action, SYSTEM, credential via `SecretProvider`). Fetch never writes protected local refs. Update `last_known_head_sha` and `last_synced_at`.
2. Classify the new remote default-branch head against the local default branch, which is the last released/adopted revision:
   - `OLYMPUS_RELEASE`: it equals a release SHA pushed by Olympus (correlated by connector action) → no-op;
   - `EXTERNAL_FAST_FORWARD`: an external commit on top of the local default branch;
   - `EXTERNAL_REWRITE`: not a descendant (force-push).
3. EXTERNAL cases:
   - persist a RepositoryEvent;
   - **adoption** (`EXTERNAL_FAST_FORWARD` with policy `repository.external_sync.adopt_fast_forward=true`, or `EXTERNAL_REWRITE` after HUMAN `acknowledge_rewrite`), in one transaction:
     - `git_local.fast_forward_ref` the local default branch to the new head (force-update only for an acknowledged rewrite);
     - `RepositoryRevisionService.advance(to_sha=new_head, cause=EXTERNAL_SYNC, refs={repository_event_id}, expected_current=canonical_commit)`;
     - if an IC holds an unreleased canonical revision, that IC → SUPERSEDED (its cycle gets the `EXTERNAL_DRIFT` Finding below), so the held revision is replaced and not silently merged;
   - build the canonical index for the new SHA (incremental from the previous canonical; `source=EXTERNAL_PUSH`) and promote it (`promote_repository_snapshot`, which requires `sha == canonical_commit`);
   - link refresh (13);
   - StalenessService `on_canonical_revision_changed` (13), which covers `on_canonical_index_changed` and `on_base_moved`;
   - Finding `EXTERNAL_DRIFT` (MAJOR, blocking release) for every non-terminal cycle whose IC base is no longer the canonical revision. Remediation is a rebase-and-re-integrate: a new IC from the new canonical revision, since Phase 08 sets `ic.base_sha := canonical_commit` (plus the DependencyBaseResolver).
   - `EXTERNAL_REWRITE` additionally gives a CRITICAL Finding and blocks releases. It is **never** adopted until a HUMAN acknowledges. Until then, `canonical_commit` and the local default branch are unchanged.
   - Repository SYNCING → READY (or ERROR with reason on fetch failure; code-needing guards then fail closed).
4. A polling fallback (`reconciliation.poll_repositories`, every N minutes) compares remote refs with known heads, so missed webhooks are reconciled.

### 4.4 Outbound connectors (all via ToolGateway; each action declares an idempotency-key template, a reconcile query, a result schema and a risk tier)

| Connector | Actions | Governance | Reconcile by |
|---|---|---|---|
| `git_provider` (github, gitea) | `fetch`, `push_branch` (`olympus/*` only), `push_release` (main ff + tag; **SYSTEM release executor only**, requires an ELIGIBLE+APPROVED release), `create_pull_request`, `update_pull_request`, `read_merge_status`, `ensure_webhook` | Implementation agents may push `olympus/<EX>` branches only if policy `outbound.git.push_candidate_branches=true`. Protected refs are denied by ToolGateway path/ref policy. | remote ref SHA equals the expected SHA; PR search by head branch |
| `ci` (`http_ci`, `github_actions`) | `trigger_verification(sha, ref, suite)`, `read_status(run_id)` | SHA must be a known IC/release SHA | run lookup by correlation id |
| `artifact` (`artifact_fs`, `artifact_s3`) | `publish(artifact_id)` → content-addressed URI, `read` | only typed artifacts linked to an execution/release | object exists with the matching hash |
| `issue_tracker` (github, gitea) | `post_comment`, `update_status`/`close`, `link_release` | the issue external_ref must be linked to the **current** cycle (`external_links`) | comment search by marker `<!-- olympus:idem=<key> -->` |
| `deployment` (`deploy_local`) | `deploy(release_id)`, `status`, `rollback(to_release_id)` | only releases with status RELEASED and eligibility ELIGIBLE; policy `release.deploy.require_approval=true` (Approval DEPLOYMENT) | the deployment marker file / health endpoint version |
| `http_generic` | `request(method, url, body)` | host + method allowlist in policy; mutating methods require an idempotency header | provider-specific or none (non-mutating only if no reconcile) |

- `deploy_local`: checks out the release tag into `$OLYMPUS_DEPLOY_ROOT/<project>/<release>`, `uv sync`, starts the app (uvicorn subprocess on a configured port), health-checks `/health`, and records a DeploymentRecord. Rollback restarts the previous release.
- **Stratos** extends the release execution: local ff+tag + `RELEASED` revision (10) → `git_provider.push_release` (if a remote exists; reconcile by remote ref SHA) → optional `deployment.deploy` → `issue_tracker` updates for linked issues.

### 4.5 Retry and reconciliation (`core/integrations/reconciliation`)
- Classification of connector outcomes:
  - `SUCCEEDED`;
  - `FAILED_RETRYABLE` (5xx/429/network before send) → retry with the **same** idempotency key, bounded exponential backoff (policy `outbound.retry`);
  - `FAILED_FINAL` (4xx validation/auth) → Action FAILED + Finding (`CONNECTOR_FAILURE`) or a BLOCKED task;
  - `UNKNOWN` (timeout after send, connection reset mid-response, partial multi-step) → `reconciliation_items` OPEN + ActionRequest RECONCILIATION_REQUIRED + the Execution checkpoints (WAITING_EXTERNAL; no runtime held).
- The reconciler loop (scheduler-worker) calls `connector.reconcile(ReconciliationRequest{idempotency_key, correlation_id, expected})`:
  - CONFIRMED_EXECUTED → result stored, action SUCCEEDED, the Execution resumes;
  - CONFIRMED_NOT_EXECUTED → safe re-execution with the same key;
  - STILL_UNKNOWN → backoff; after policy `reconciliation.max_attempts` → ESCALATED (HUMAN).
- Human endpoints: `POST /reconciliation/{id}/retry` (forces a reconcile query first) and `POST /reconciliation/{id}/resolve` (`{outcome, note}`), audited.
- Inbound reconciliation: out-of-order events are ordered by source_version, a stale event is recorded with no mutation, and repository polling covers missed events.

### 4.6 External links and traceability
`external_links` maps `(entity_type, entity_id) ↔ (provider, external_type, external_id, url)`, covering CR↔issue, Defect↔issue, IC↔PR, Release↔tag/deployment and Evidence↔CI run. Every connector action row carries project, cycle, task, execution, correlation id and external id. `GET /lineage/...` (08) includes external refs.

## 5. Out of Scope

- Cloud deployment targets (Kubernetes, ECS). Only `deploy_local` is in the MVP.
- Jira/Linear adapters. The adapter interface supports them; only GitHub/Gitea are implemented.
- OTel export of connector spans (18).

### Do Not Change
- Release eligibility logic (10/12/15). Remote push happens only after local release execution succeeds.
- No connector may be callable outside ToolGateway. The import-linter contract `connectors-only-via-gateway` is added.

## 6. Domain / Data Model Changes

Migration `0026_p16_integrations_reconciliation.py` (TECH 012 completion).

```python
class ConnectorConfig(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "connector_configs"
    project_id: Mapped[uuid.UUID | None]
    connector: Mapped[str]
    provider: Mapped[str]
    base_url: Mapped[str | None]
    secret_ref: Mapped[str | None]
    enabled_actions: Mapped[list] = mapped_column(JSONB)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    active: Mapped[bool]


class ReconciliationItem(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "reconciliation_items"
    key: Mapped[str]
    kind: Mapped[str]  # OUTBOUND_UNKNOWN | INBOUND_GAP | REPOSITORY_DRIFT
    connector_action_id: Mapped[uuid.UUID | None]
    repository_id: Mapped[uuid.UUID | None]
    status: Mapped[
        str
    ]  # OPEN | RECONCILING | RESOLVED_EXECUTED | RESOLVED_NOT_EXECUTED | ESCALATED | RESOLVED_MANUAL
    attempts: Mapped[int]
    next_attempt_at: Mapped[datetime | None]
    last_observation: Mapped[dict | None] = mapped_column(JSONB)
    correlation_id: Mapped[str]
    resolved_by_actor_id: Mapped[uuid.UUID | None]
    resolution_note: Mapped[str | None]


class RepositoryEvent(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "repository_events"
    repository_id: Mapped[uuid.UUID]
    inbound_event_id: Mapped[uuid.UUID | None]
    ref: Mapped[str]
    before_sha: Mapped[str | None]
    after_sha: Mapped[str]
    classification: Mapped[
        str
    ]  # OLYMPUS_RELEASE | EXTERNAL_FAST_FORWARD | EXTERNAL_REWRITE | NON_DEFAULT_REF | STALE
    processed_at: Mapped[datetime | None]


class ExternalLink(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "external_links"
    entity_type: Mapped[str]
    entity_id: Mapped[uuid.UUID]
    provider: Mapped[str]
    external_type: Mapped[str]
    external_id: Mapped[str]
    url: Mapped[str | None]
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "provider", "external_type", "external_id"),
    )


class DeploymentRecord(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "deployments"
    release_id: Mapped[uuid.UUID]
    target: Mapped[str]
    status: Mapped[str]  # REQUESTED|DEPLOYING|HEALTHY|FAILED|ROLLED_BACK
    connector_action_id: Mapped[uuid.UUID]
    health: Mapped[dict | None] = mapped_column(JSONB)
```

Other changes:
- `repositories`: + `last_known_head_sha` (observed remote head; **not** the canonical revision), `webhook_external_id`, `last_synced_at`. `provider`, `remote_url`, `default_branch` and `credential_ref` already exist from Phase 01.
- `repository_revisions`: FK `repository_event_id → repository_events.id`.
- `secrets` (backend `secret:` only): name (unique), ciphertext, created_at, rotated_at. No API returns ciphertext or value.
- `executions.status`: the WAITING_EXTERNAL substate is represented as CHECKPOINTED with `checkpoint.reason=WAITING_EXTERNAL` (no new state).

## 7. State / Lifecycle Changes

- ConnectorAction: PENDING → SUCCEEDED | FAILED_RETRYABLE → (retry) | FAILED_FINAL | UNKNOWN → (reconcile) SUCCEEDED | PENDING (confirmed not executed) | ESCALATED (via its ReconciliationItem).
- ReconciliationItem: OPEN → RECONCILING → RESOLVED_EXECUTED | RESOLVED_NOT_EXECUTED | ESCALATED → RESOLVED_MANUAL.
- Execution: RUNNING → CHECKPOINTED(WAITING_EXTERNAL) → (resume on resolution) RUNNING.
- Release (10): RELEASED → + deployment sub-status on DeploymentRecord (Release state unchanged; deployment is a separate record).
- Finding types added: `EXTERNAL_DRIFT`, `CONNECTOR_FAILURE`, `RECONCILIATION_ESCALATED`.

## 8. API / Contract Changes

| Method | Path | Notes |
|---|---|---|
| POST | `/integrations/inbound/{source}` and alias `/integrations/events/{provider}` | webhook entry |
| POST | `/repositories/{id}/webhooks` | register/ensure provider webhook (outbound) |
| POST | `/repositories/{id}/sync` | operator-triggered sync |
| POST | `/repositories/{id}/commands/attach_remote` | HUMAN OPERATOR; `GREENFIELD_MANAGED` only; `{provider, remote_url, credential_ref}` |
| POST | `/repositories/{id}/commands/acknowledge_rewrite` | HUMAN OPERATOR; adopts an `EXTERNAL_REWRITE` head as an `EXTERNAL_SYNC` revision |
| PUT | `/secrets/{name}` | HUMAN OPERATOR; write-only; response `{credential_ref: "secret:<name>"}` |
| GET | `/repositories/{id}/events` | repository events with classification |
| GET/POST | `/projects/{id}/connectors`, `/connectors/{id}/validate` | config + health (secrets write-only) |
| GET | `/connector-actions?cycle_id=&status=` | |
| GET | `/reconciliation`, `/reconciliation/{id}` | |
| POST | `/reconciliation/{id}/retry`, `/reconciliation/{id}/resolve` | HUMAN |
| GET | `/external-links?entity_type=&entity_id=` | |
| POST | `/releases/{id}/deploy`, `/releases/{id}/rollback` | approval-gated |
| GET | `/releases/{id}/deployments` | |

```python
class ReconciliationRequest(BaseModel):
    connector_action_id: uuid.UUID
    connector: str
    action: str
    idempotency_key: str
    correlation_id: str
    expected: dict


class ReconcileOutcome(StrEnum):
    CONFIRMED_EXECUTED = "CONFIRMED_EXECUTED"
    CONFIRMED_NOT_EXECUTED = "CONFIRMED_NOT_EXECUTED"
    STILL_UNKNOWN = "STILL_UNKNOWN"


class ExternalCiResult(BaseModel):
    run_id: str
    sha: str
    status: Literal["PASSED", "FAILED", "ERROR"]
    suite: str
    junit_ref: str | None
    correlation_id: str | None
    started_at: datetime
    finished_at: datetime
```

Events: `repository.event_received`, `repository.drift_detected`, `repository.synced`, `connector.retry_scheduled`, `connector.reconciliation_required`, `reconciliation.resolved`, `reconciliation.escalated`, `external_ci.ingested`, `deployment.started`, `deployment.healthy`, `deployment.failed`, `deployment.rolled_back`, `issue.updated`.

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `core/integrations/inbound/auth.py` | HMAC verifiers, replay window |
| `core/integrations/inbound/adapters/{git_provider_webhook,issue_tracker_webhook,ci_callback,repository_registration,operator_api}.py` | adapters |
| `core/repositories/sync.py` | RepositorySyncService + drift classification + adoption via `RepositoryRevisionService` |
| `core/repositories/remote.py` | remote registration validation, `attach_remote` |
| `core/integrations/connectors/{git_provider/{github,gitea},ci/{http_ci,github_actions},artifact/{fs,s3},issue_tracker/{github,gitea},deployment/local,http_generic}.py` | connectors |
| `core/integrations/connectors/secrets.py` | SecretProvider (`env`/`file`/`secret` backends; implements `CredentialResolver`) |
| `core/integrations/reconciliation/{service,worker,policies}.py` | reconciler |
| `core/integrations/outbound/notifications.py` | cycle-milestone → issue updates (subscriber) |
| `core/release/stratos.py` | EXTEND: remote push, deploy, issue linking |
| `apps/scheduler_worker/loops.py` | EXTEND: reconciler + repo polling loops |
| `apps/control_api/routers/{integrations,reconciliation,connectors,deployments}.py` | REST |
| `config/policy/default.yaml` | `outbound:`, `reconciliation:`, `inbound:` sections |
| `deploy/compose.test.yaml` | Gitea + MinIO + local CI runner services (test profile) |
| `tests/support/ci_runner/` | minimal real CI runner: receives trigger, checks out SHA, runs pytest, posts signed callback |
| `tests/support/faults.py` | fault-injecting HTTP proxy (timeout-after-forward, reset, 5xx) |

## 10. Development Tasks

- [ ] 16.1 Add migration `0026` and the models. Extend `repositories` (`last_known_head_sha`, `webhook_external_id`, `last_synced_at`), add the `repository_revisions.repository_event_id` FK and the `secrets` table.
- [ ] 16.2 Implement `SecretProvider` (as `CredentialResolver`), the write-only `PUT /secrets/{name}`, `connector_configs` CRUD (write-only secrets) and validation endpoints. Enable `GITHUB`/`GITEA` registration of `EXTERNAL_CLONE` repositories and `attach_remote` for `GREENFIELD_MANAGED` (§4.1a).
- [ ] 16.3 Implement the HMAC verifiers + replay window. Wire them into InboundService auth.
- [ ] 16.4 Implement the `git_provider_webhook` adapter + RepositoryEvent + staleness by ancestry.
- [ ] 16.5 Implement `RepositorySyncService` (SYNCING state, fetch, classify, `EXTERNAL_SYNC` adoption via `RepositoryRevisionService`, held-IC supersession, index, promote, refresh, staleness, drift findings, `acknowledge_rewrite`) + the polling loop.
- [ ] 16.6 Implement the `issue_tracker_webhook` adapter → CR/Defect intake + source version updates + `external_links`.
- [ ] 16.7 Implement the `ci_callback` adapter → EXTERNAL_CI evidence with SHA/correlation validation + junit mapping + finalizer re-evaluation.
- [ ] 16.8 Implement the `git_provider` connectors (GitHub, Gitea): all §4.4 actions + reconcile, plus the `RepositoryConnector` methods (`validate_registration`, `clone`, `fetch`, `push`) used by Phase 04's materializer; protected-ref denial in ToolGateway policy.
- [ ] 16.9 Implement the `ci` connectors (`http_ci` for the test runner; `github_actions` workflow_dispatch) + reconcile.
- [ ] 16.10 Implement the `artifact_fs` / `artifact_s3` connectors.
- [ ] 16.11 Implement the `issue_tracker` connectors + the cycle-milestone notification subscriber (scoped by `external_links`).
- [ ] 16.12 Implement the `deploy_local` connector + DeploymentRecord + approval + rollback.
- [ ] 16.13 Implement the `http_generic` connector with the allowlist.
- [ ] 16.14 Implement retry classification, the reconciliation service/worker, escalation and HUMAN endpoints, and Execution WAITING_EXTERNAL checkpoint/resume.
- [ ] 16.15 Extend Stratos: remote push, deploy, issue updates.
- [ ] 16.16 Add the import-linter contract `connectors-only-via-gateway`.
- [ ] 16.17 Add the test infrastructure: compose test profile, CI runner, fault proxy.
- [ ] 16.18 Write the tests in §12.

## 11. LLM-Dependent Tasks

No new LLM dependency in this phase. Integrations are deterministic platform concerns (ARCH §20.1).

The integration journey test (§12) re-runs the Phase 14 Feature Change flow, whose model-dependent stages use the live profiles already defined, with `assert_live_llm_proof`.

## 12. Testing Strategy

### Unit Tests
- HMAC verification (valid, invalid, expired timestamp).
- Outcome classification table (each HTTP/network case → class).
- Idempotency-key templates are deterministic.
- Drift classification (ancestor, descendant, unrelated).
- Comment marker parsing.

### Persistence Tests
- `inbound_events` uniqueness.
- ReconciliationItem transitions.
- `external_links` uniqueness.
- Secrets are never persisted in plaintext (scan of the test DB dump for the secret value).

### Connector Tests (`connector`; Gitea, MinIO and the CI runner via Testcontainers; fault proxy)
- `git_provider.push_branch` / `create_pull_request` against Gitea. A repeat with the same key gives no duplicate PR.
- **Timeout after forward** on `create_pull_request` → UNKNOWN → reconcile finds the PR → SUCCEEDED, exactly 1 PR.
- Timeout **before** forward → reconcile CONFIRMED_NOT_EXECUTED → re-execute → exactly 1 PR.
- 5xx ×2 then success → 3 attempts recorded with the same key.
- 401 → FAILED_FINAL + Finding.
- Issue comment idempotency via the marker under fault injection.
- `push_release` denied for a non-release executor; allowed for an ELIGIBLE+APPROVED release; reconcile by remote ref SHA.
- `deploy_local` deploy → HEALTHY; rollback → the previous release is healthy.
- `http_generic` denies a non-allowlisted host.

### Integration Tests
- Gitea push webhook (real delivery, signed) for an external commit → RepositoryEvent EXTERNAL_FAST_FORWARD → `EXTERNAL_SYNC` revision (`canonical_commit` = new head, `repository_event_id` set) → canonical index at the new SHA → impacted baselines REVALIDATION_REQUIRED → EXTERNAL_DRIFT Finding on an active cycle → release blocked until a new IC is rebased (new IC `base_sha ==` the adopted SHA).
- An external push while cycle A's IC holds an unreleased canonical revision: the adopted SHA replaces it, A's IC → SUPERSEDED, and A gets EXTERNAL_DRIFT. A's next IC integrates its candidates onto the adopted SHA.
- A force-push → EXTERNAL_REWRITE: `canonical_commit` and the local default branch are unchanged and a CRITICAL Finding is raised. After `acknowledge_rewrite`, an `EXTERNAL_SYNC` revision is recorded, and cycles whose base is not an ancestor get `CYCLE_BASE_DIVERGED` (13).
- Remote clone: register a Gitea repository with `credential_ref=secret:gitea-test` (value set via `PUT /secrets/gitea-test`). Materialization clones it, and the token appears in no DB column (dump scan), in no `.git/config`/remote URL of the canonical workspace and in no API response.
- `attach_remote`: a released GREENFIELD_MANAGED repository pushed to an empty Gitea repository leaves the remote default branch at `released_commit` and the release tags present, with `source_type` still `GREENFIELD_MANAGED`.
- Duplicate webhook delivery → DUPLICATE, a single sync.
- Out-of-order push (older `after`) → STALE, no mutation.
- Missed webhook (webhook disabled) → the polling loop detects the head change.
- Issue labeled `olympus:change` → ChangeRequest + FEATURE_CHANGE cycle. The same issue redelivered → one CR. An edit after the cycle leaves INTAKE → INFO, no new version.
- CI callback with an unknown SHA → REJECTED. A matching SHA + correlation → EXTERNAL_CI evidence linked to the IC and counted for the mapped obligations. A callback for a superseded IC → STALE.
- Execution waiting on a connector UNKNOWN is CHECKPOINTED, the worker holds no runtime, and resolution resumes it.

### Security Tests
- Unsigned or bad-signature webhooks give 401.
- An agent profile cannot call a connector directly (import-linter + runtime check).
- An implementation agent's `push_release`/protected-ref push is DENIED and audited.
- Secrets are absent from the agent context snapshot, logs and artifacts.

### E2E / Journey Tests (`journey`, live)
- `test_feature_change_via_issue_tracker.py`:
  - a Gitea issue "Add ticket priority…" labeled `olympus:change` drives the Phase 14 flow live;
  - the IC is published as a Gitea PR;
  - CI runner evidence is ingested for the IC SHA;
  - Release R2 is pushed to the Gitea `main` + tag;
  - the issue is commented and closed with a release link;
  - `deploy_local` is HEALTHY.
  - Fault injection on the issue-close call → reconciliation → exactly one close/comment.
  - `assert_live_llm_proof` for the Phase 14 stages.

### Commands
```
make check
docker compose -f docker-compose.yml -f deploy/compose.test.yaml --profile integrations up -d
uv run pytest -m "connector or integration" tests/connector tests/integration/integrations
LLM_LIVE_TESTS=1 uv run pytest -m journey --live-required tests/journey/test_feature_change_via_issue_tracker.py -s
```

## 13. Milestone

A SupportDesk change request filed as a real Gitea issue is ingested through a signed, idempotent webhook and delivered to Release R2. Olympus publishes the IC as a PR, ingests exact-SHA CI evidence, pushes the release ref and tag, deploys locally, and comments on and closes the issue, all as governed connector actions traceable from issue to deployment. Injected timeouts produce reconciled, single external effects. An external push to `main` is detected, re-indexed and turned into staleness and drift findings.

## 14. Acceptance Criteria

- [ ] Every inbound adapter (document upload, repository registration, Git webhook, issue/change event, defect event, CI/test event, operator command) authenticates the caller, persists the event id + source identity uniquely, and dispatches at most one command per event.
- [ ] Stale or out-of-order inbound events are recorded without mutating canonical state.
- [ ] External pushes to the default branch trigger canonical re-index, link refresh, staleness evaluation and EXTERNAL_DRIFT findings for affected cycles.
- [ ] An adopted external fast-forward changes `canonical_commit` only through a governed `EXTERNAL_SYNC` revision that references the RepositoryEvent. A rewrite is never adopted without HUMAN acknowledgement. Work never continues silently against the new state: affected work is marked stale or blocked.
- [ ] Remote `GITHUB`/`GITEA` repositories are registered and cloned through the shared materializer, with credentials resolved from `credential_ref` by `SecretProvider`. Credential values are never persisted in repository rows, Git config or remote URLs, and are never returned by any API. `GITLAB`/`BITBUCKET` are rejected as not supported.
- [ ] A `GREENFIELD_MANAGED` repository can attach a remote and publish its released default branch and tags through governed connector actions.
- [ ] CI evidence is accepted only for known IC/release SHAs with valid correlation, and counts toward the mapped obligations.
- [ ] Every outbound mutation (git push/PR, CI trigger, issue update, artifact publish, deployment, external HTTP) passes through ToolGateway with execution identity, scope and policy checks, and carries an idempotency key.
- [ ] Unknown outcomes create ReconciliationItems. No mutation is retried before provider state is queried, and fault-injection tests show exactly one external effect.
- [ ] Executions waiting on external outcomes are checkpointed without a live runtime and resume on resolution.
- [ ] Protected-branch/release mutation is denied to non-release executors.
- [ ] Every external mutation is traceable via `external_links` and connector action rows to project, cycle, task, execution, correlation id and external id.
- [ ] Connector secrets never appear in agent context, logs, audit or artifacts.
- [ ] The Feature Change via issue tracker journey passes live.

## 15. Exit Criteria

- §14 green.
- `STATUS.md` integration tracker rows updated with connector/status/contract/idempotency/retry/reconciliation/correlation/audit. Invariant "repository credentials are never stored/exposed in plaintext" checked for remote providers.
- Q-05 resolution path (external push) implemented and available to Phase 19.

## 16. Dependencies

### Depends On
- 14, 15 (CR/Defect intake commands).
- 10 (Stratos), 13 (sync/staleness), 04/05 (frameworks).

### Blocks
- 17, 18.

### Can Run In Parallel With
- None. 16 changes the release executor and inbound auth that 17 and 18 consume.

## 17. Risks / Implementation Notes

- **Provider API drift** (GitHub vs Gitea field differences): isolate them in provider adapters with contract tests per provider. GitHub contract tests run only with credentials (`connector_live` marker, optional in CI).
- **Webhook delivery to a local control-api** in tests: Gitea runs in the same compose network.
- **Canonical workspace vs remote:** the canonical RepositoryWorkspace's local default branch moves only via Stratos release ff (10) or governed `EXTERNAL_SYNC` adoption. The remote default branch is written only via `push_release` after the local ff. Fetch always uses `--prune` and targets `refs/remotes/origin/*` only.
- **Deploy_local port collisions:** allocate ports from a configured range and persist them on the DeploymentRecord.
- **Reconcile for `http_generic`:** non-reconcilable mutating calls are only permitted with policy `allow_unreconcilable=true` (default false).

## 18. Deliverables

- Code: inbound adapters/auth, `core/repositories/{sync,remote}.py`, connectors (git_provider, ci, artifact, issue_tracker, deployment, http_generic), SecretProvider, reconciliation subsystem, Stratos extension.
- Migration: `0026`.
- APIs/events: §8.
- Test infra: compose test profile (Gitea, MinIO, CI runner), fault proxy.
- Tests: §12, including the issue-tracker journey.
