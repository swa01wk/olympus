# Phase 05 — Product Source Intake, Inbound Event Kernel and Product Model

## 1. Objective

Introduce the canonical product and specification hierarchy (ARCH §4.1–4.2, TECH §6):

- **ProductSource** (immutable versions);
- **Capability**, **Feature**;
- versioned **FeatureSpec** with child **Requirement / UserStory / AcceptanceCriterion**;
- **KnowledgeItem** (DECISION/ASSUMPTION now; FACT/INFERENCE/UNCERTAINTY used in Phase 11).

It also adds the **inbound integration kernel**: the common `InboundEvent` envelope, authentication, validation, normalization, idempotency → command (TECH §15.1/§15.3). Its first adapter is **product document upload**.

**Kira** performs live-LLM product decomposition into a reviewable proposal. Open questions become Clarifications, and an explicit human **Scope Approval** makes FeatureSpecs canonical. This covers the Greenfield path from PRD upload to an approved product/spec model (TECH T2).

## 2. Architectural Context

- **Position:** Intelligence/Context plane (product model) and inbound integration. Greenfield DISCOVERY → PRODUCT_MODEL → (scope approval) → ARCHITECTURE.
- **Upstream:** 01 (commands, approvals, guards), 02 (ModelRouter), 03 (ANALYSIS executions, clarifications, artifacts).
- **Downstream:** 06 (ImplementationSpecs from approved FeatureSpecs), 09 (AC evidence), 11 (recovered specs reuse FeatureSpec with `spec_kind=RECOVERED`), 13/14 (spec delta), 15 (expected behavior resolution, FeatureSpec amendment), 16 (more inbound adapters).
- **Invariants:**
  - 1: FeatureSpec = intended behavior.
  - 26: mandatory ACs require evidence; ACs carry `evidence_requirement`.
  - 25: approvals explicit.
  - Model opinion cannot create canonical state without validation and approval.
  - Inbound events cannot mutate canonical state outside the command path.
  - ProductSource text is provenance, not execution state.

## 3. Current Repository Assessment

Inspection on 2026-10-01: no product model, inbound or Kira code exists.

### Existing
- (after 01–03) approvals, guards (`product_source_ingested` and `scope_approved` are fail-closed placeholders), clarifications, artifacts, ANALYSIS execution path — **EXTEND**.

### Partial
- None.

### Missing
- Everything in §4 — **ADD**.

### Refactor / Migration Required
- Replace the Phase 01 `RequiredGuard` placeholders `product_source_ingested` and `scope_approved` with real guards — **REFACTOR** (placeholder removal).

## 4. Scope

1. Tables:
   - inbound: `integration_sources`, `inbound_events`;
   - product model: `product_sources`, `capabilities`, `features`, `feature_specs`, `requirements`, `user_stories`, `acceptance_criteria`, `product_decompositions`, `knowledge_items`, `scope_sets`, `scope_set_items`.
2. Inbound kernel: the `InboundEvent` envelope (TECH §15.1) and the `InboundService.receive(adapter, raw)` pipeline:
   1. authenticate (adapter-specific; for uploads, a bearer actor);
   2. validate;
   3. normalize;
   4. idempotency (`UNIQUE(source_type, source_id, event_id)`);
   5. translate to an Olympus command;
   6. dispatch via CommandBus;
   7. persist `inbound_events.command_log_id` and audit.
   Duplicate deliveries are acknowledged with the original result.
3. `DocumentUploadAdapter`:
   - accepts multipart (`.md`, `.txt`, `.pdf` via `pypdf`, `.docx` via `python-docx`) or JSON `{title, text}`;
   - stores the raw body content-addressed;
   - extracts normalized text (stored as an artifact);
   - command `ingest_product_source` creates a ProductSource version. The same `lineage_key` creates version N+1, and an identical content hash is a no-op duplicate.
4. Product model services: `ProductSourceService`, `CapabilityService`, `FeatureService`, `FeatureSpecService` (versioning, approval, supersession) and `KnowledgeService`.
5. Kira decomposition:
   - Command `decompose_source(source_version_id, cycle_id)` creates a CONTROL_PLANE ANALYSIS Task with `agent_profile=kira.decompose` and `governing_ref=PRODUCT_SOURCE_VERSION`, issues its contract and marks it READY.
   - The scheduler runs it, and Kira returns `ProductDecomposition`.
   - A deterministic validator checks it, then `ProductModelService.persist_proposal` writes PROPOSED Capabilities, Features, FeatureSpecs (DRAFT→PROPOSED v1) and children, plus open questions as Clarifications.
6. Re-decomposition after clarification answers: a new Task/Execution whose context includes the DECISION KnowledgeItems. It produces a new `product_decompositions` row and supersedes un-approved proposals. Already-approved FeatureSpecs are never overwritten.
7. Operator editing: an operator can create a new DRAFT FeatureSpec version via the API (human-authored changes are versioned too).
8. Scope approval: command `request_scope_approval(cycle_id, feature_spec_version_ids)` creates a `scope_set` (immutable list of FeatureSpec versions + hash) and an Approval(SCOPE) with `subject=scope_set`. On APPROVED (same transaction): all FeatureSpecs in the set → APPROVED (immutable), and their Features/Capabilities → APPROVED.
9. Guards: `product_source_ingested` (the cycle has ≥1 ProductSource version linked) and `scope_approved` (latest scope_set APPROVED, subject hash matches, no OPEN blocking Clarifications for the cycle).
10. `RefResolver`s for PRODUCT_SOURCE_VERSION, FEATURE_SPEC, REQUIREMENT and ACCEPTANCE_CRITERION (Phase 03 registry).
11. SupportDesk PRD fixture `tests/fixtures/supportdesk/PRD.md`.

## 5. Out of Scope

- Architecture, ImplementationSpec and task planning (06).
- Git/issue/CI inbound adapters (16).
- Recovered specs (11) and spec deltas (13/14). The `spec_kind` enum includes RECOVERED, but nothing produces it yet.
- Embeddings for features/specs (13).

### Do Not Change
- Kira must not write to the DB. Only `ProductModelService` persists, and only after validation.
- An APPROVED FeatureSpec version is never edited. Changes always create a new version.
- Do not auto-approve scope. Policy `approvals_required.SCOPE` is `true`.

## 6. Domain / Data Model Changes

Migrations: `0009_p05_inbound_events.py` (TECH 012 partial), `0010_p05_product_sources_capabilities_features.py` (TECH 002), `0011_p05_feature_specs_requirements_stories_acs.py` (TECH 003) and `0012_p05_knowledge_scope.py`.

```python
class SpecStatus(StrEnum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class SpecKind(StrEnum):
    CANONICAL = "CANONICAL"
    RECOVERED = "RECOVERED"


class ModelOrigin(StrEnum):
    GREENFIELD = "GREENFIELD"
    RECOVERED = "RECOVERED"
    HUMAN = "HUMAN"
    CHANGE = "CHANGE"
    REPAIR = "REPAIR"


class EvidenceRequirement(StrEnum):
    EXECUTABLE = "EXECUTABLE"
    RUNTIME = "RUNTIME"
    EXECUTABLE_OR_RUNTIME = "EXECUTABLE_OR_RUNTIME"
    REVIEW_ALLOWED = "REVIEW_ALLOWED"


class KnowledgeClass(StrEnum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    UNCERTAINTY = "UNCERTAINTY"
    DECISION = "DECISION"
    ASSUMPTION = "ASSUMPTION"


class ProductSource(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "product_sources"
    project_id: Mapped[uuid.UUID]
    lineage_key: Mapped[str]
    version: Mapped[int]
    source_type: Mapped[
        str
    ]  # PRD|BRD|SRS|BRIEF|FEATURE_LIST|USER_STORIES|ARCHITECTURE_NOTE|DESCRIPTION|ISSUE|CHANGE_REQUEST|DEFECT_REPORT|JSON
    title: Mapped[str]
    mime_type: Mapped[str]
    content_hash: Mapped[str]
    raw_storage_ref: Mapped[str]
    text_artifact_id: Mapped[uuid.UUID]
    inbound_event_id: Mapped[uuid.UUID | None]
    created_by_actor_id: Mapped[uuid.UUID]
    __table_args__ = (
        UniqueConstraint("project_id", "lineage_key", "version"),
        UniqueConstraint("project_id", "lineage_key", "content_hash"),
    )


class Capability(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "capabilities"
    project_id: Mapped[uuid.UUID]
    key: Mapped[str]
    name: Mapped[str]
    description: Mapped[str]
    status: Mapped[str]  # PROPOSED | APPROVED | RETIRED
    origin: Mapped[ModelOrigin]
    source_refs: Mapped[list] = mapped_column(JSONB)  # [{product_source_version_id, section}]


class Feature(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "features"
    project_id: Mapped[uuid.UUID]
    capability_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("capabilities.id"))
    key: Mapped[str]
    name: Mapped[str]
    description: Mapped[str]
    status: Mapped[str]
    origin: Mapped[ModelOrigin]
    source_refs: Mapped[list] = mapped_column(JSONB)
    # Feature identity is stable across implementation refactors (ARCH §4.2)


class FeatureSpec(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "feature_specs"
    project_id: Mapped[uuid.UUID]
    feature_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("features.id"))
    lineage_key: Mapped[str]  # SPEC-FEAT-001
    version: Mapped[int]
    status: Mapped[SpecStatus]
    spec_kind: Mapped[SpecKind] = mapped_column(default=SpecKind.CANONICAL)
    body: Mapped[dict] = mapped_column(JSONB)  # FeatureSpecBody
    content_hash: Mapped[str]
    derived_from_source_version_id: Mapped[uuid.UUID | None]
    decomposition_id: Mapped[uuid.UUID | None]
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("feature_specs.id"))
    promoted_from_id: Mapped[uuid.UUID | None]  # Phase 12: CANONICAL promoted from RECOVERED
    approval_id: Mapped[uuid.UUID | None]
    __table_args__ = (UniqueConstraint("project_id", "lineage_key", "version"),)


class FeatureSpecBody(BaseModel):  # ARCH §14.2 feature_spec
    model_config = ConfigDict(extra="forbid")
    behavior: str
    summary: str
    inputs: list[str]
    outputs: list[str]
    rules: list[str]
    constraints: list[str] = []
    out_of_scope: list[str] = []


class AcceptanceCriterion(Base, UUIDPkMixin):
    __tablename__ = "acceptance_criteria"
    feature_spec_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feature_specs.id"), index=True)
    lineage_key: Mapped[str]  # AC-001-01 (stable across FeatureSpec versions)
    statement: Mapped[str]
    given: Mapped[str | None]
    when: Mapped[str | None]
    then: Mapped[str | None]
    mandatory: Mapped[bool]
    evidence_requirement: Mapped[EvidenceRequirement]
    requirement_keys: Mapped[list] = mapped_column(JSONB)
    change_kind: Mapped[
        str | None
    ]  # ADDED|MODIFIED|UNCHANGED|REMOVED vs previous version (Phase 13)
```

Requirement (key `REQ-…`, statement, kind FUNCTIONAL|NON_FUNCTIONAL|CONSTRAINT, priority MUST|SHOULD|COULD) and UserStory (key `US-…`, actor, goal, benefit) follow the same per-FeatureSpec-version pattern with stable `lineage_key`.

Child rows of an APPROVED FeatureSpec are immutable (trigger keyed on the parent's status via a `locked` flag column set at approval).

Other tables:
- `inbound_events`: per TECH §15.1, plus status (RECEIVED|DUPLICATE|REJECTED|ACCEPTED|STALE), rejection_reason, command_log_id, actor_id. `UNIQUE(source_type, source_id, event_id)`. Payload stored by reference if larger than 64 KB.
- `integration_sources`: id, project_id?, source_type, name, auth_kind (BEARER|HMAC_SHA256|NONE_LOCAL), secret_ref (env/file key, never the secret), active.
- `product_decompositions`: id, delivery_cycle_id, product_source_version_id, execution_id, artifact_id, status (PROPOSED|SUPERSEDED|ACCEPTED), validation_report JSONB.
- `knowledge_items`: id, project_id, delivery_cycle_id?, class, statement, subject_refs JSONB, provenance JSONB `{origin: DETERMINISTIC|AGENT|HUMAN, agent_profile?, execution_id?, actor_id?}`, evidence_refs JSONB, confidence (HIGH|MEDIUM|LOW|NULL), status (ACTIVE|SUPERSEDED|REJECTED), blocking bool, supersedes_id.
- `scope_sets`: id, delivery_cycle_id, content_hash, created_by. `scope_set_items`: scope_set_id, feature_spec_id.

Kira output schema (TECH §6.2):

```python
class CapabilityDraft(BaseModel):
    ref: str
    name: str
    description: str
    source_sections: list[str]


class FeatureDraft(BaseModel):
    ref: str
    capability_ref: str
    name: str
    description: str
    source_sections: list[str]


class FeatureSpecDraft(BaseModel):
    ref: str
    feature_ref: str
    body: FeatureSpecBody


class RequirementDraft(BaseModel):
    ref: str
    feature_spec_ref: str
    statement: str
    kind: str
    priority: str


class UserStoryDraft(BaseModel):
    ref: str
    feature_spec_ref: str
    actor: str
    goal: str
    benefit: str


class AcceptanceCriterionDraft(BaseModel):
    ref: str
    feature_spec_ref: str
    statement: str
    given: str | None
    when: str | None
    then: str | None
    mandatory: bool
    evidence_requirement: EvidenceRequirement
    requirement_refs: list[str]


class Clarification(BaseModel):
    question: str
    context: str
    options: list[str] = []
    blocking: bool
    related_refs: list[str] = []


class ProductDecomposition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capabilities: list[CapabilityDraft]
    features: list[FeatureDraft]
    feature_specs: list[FeatureSpecDraft]
    requirements: list[RequirementDraft]
    user_stories: list[UserStoryDraft]
    acceptance_criteria: list[AcceptanceCriterionDraft]
    open_questions: list[Clarification]
    assumptions: list[str] = []
```

Deterministic validation rules (`core/product_model/validation.py`):
- All `*_ref` values resolve within the proposal, and refs are unique.
- Every Feature has exactly one FeatureSpec.
- Every FeatureSpec has ≥1 Requirement and ≥1 **mandatory** AC.
- Every AC references ≥1 Requirement of the same FeatureSpec.
- A mandatory AC whose evidence requirement is `REVIEW_ALLOWED` is rejected unless the AC is non-functional.
- Every `source_sections` entry is non-empty.

Violations are fed back to the model as a schema-retry (ModelRouter) when they are expressible as validation errors. Otherwise the Execution is FAILED(`VALIDATION_FAILED`).

## 7. State / Lifecycle Changes

- FeatureSpec: DRAFT → PROPOSED (persisted proposal) → APPROVED (scope approval) → SUPERSEDED (newer approved version). PROPOSED → REJECTED (scope approval rejected / superseded proposal). DRAFT/PROPOSED editable only by creating a new version (simpler immutability). Owner: `FeatureSpecService`.
- Capability/Feature: PROPOSED → APPROVED → RETIRED.
- Clarification: Phase 03 machine. Answering creates a DECISION KnowledgeItem.
- InboundEvent: RECEIVED → ACCEPTED | DUPLICATE | REJECTED | STALE.
- DeliveryCycle (GREENFIELD):
  - `start_product_modeling` (DISCOVERY → PRODUCT_MODEL) guarded by `product_source_ingested`.
  - `start_architecture` (PRODUCT_MODEL → ARCHITECTURE) guarded by `scope_approved`.
  - Rejecting the scope approval leaves the cycle in PRODUCT_MODEL.

## 8. API / Contract Changes

| Method | Path | Notes |
|---|---|---|
| POST | `/projects/{id}/sources` | multipart or JSON; header `Idempotency-Key`; via InboundService/DocumentUploadAdapter; `?delivery_cycle_id=` links to cycle |
| GET | `/projects/{id}/sources`, `/sources/{id}`, `/sources/{id}/content` | versions; raw + normalized text |
| POST | `/sources/{id}/decompose` (alias `/sources/{id}/derive`) | `{delivery_cycle_id}` → creates Kira ANALYSIS task; returns task + execution request |
| GET | `/delivery-cycles/{id}/decompositions`, `/decompositions/{id}` | proposal + validation report |
| GET | `/projects/{id}/capabilities`, `/projects/{id}/features`, `/features/{id}` | |
| GET | `/features/{id}/specs`, `/specs/{id}` | versions, ACs, requirements, stories |
| POST | `/features/{id}/specs` | operator-authored new DRAFT version |
| POST | `/delivery-cycles/{id}/scope/approval-request` | `{feature_spec_ids}` → scope_set + Approval(SCOPE) |
| POST | `/specs/{id}/approve` | convenience: request+decide single-spec approval (HUMAN APPROVER) — for spec versions outside scope sets (Phase 14 deltas) |
| GET | `/delivery-cycles/{id}/knowledge` | DECISION/ASSUMPTION items |
| POST | `/integrations/inbound/{source}` | generic inbound endpoint (adapters registered; `document_upload` available here too) |
| GET | `/integrations/inbound-events`, `/integrations/inbound-events/{id}` | |

Events: `inbound_event.received`, `inbound_event.duplicate`, `inbound_event.rejected`, `product_source.ingested`, `product_decomposition.proposed`, `feature_spec.proposed`, `feature_spec.approved`, `scope.approval_requested`, `scope.approved`, `knowledge_item.created`.

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `core/integrations/inbound/{envelope,service,registry}.py` | envelope, pipeline, adapter registry |
| `core/integrations/inbound/adapters/document_upload.py` | upload adapter + text extraction |
| `core/product_model/sources/service.py` | ProductSource versioning |
| `core/product_model/capabilities/service.py`, `features/service.py` | |
| `core/product_model/specifications/{service,versioning,scope}.py` | FeatureSpec versions, scope sets |
| `core/product_model/decomposition.py` | create Kira task; persist validated proposal |
| `core/product_model/validation.py` | deterministic proposal validator |
| `core/product_model/knowledge.py` | KnowledgeItems |
| `core/product_model/guards.py` | `product_source_ingested`, `scope_approved` |
| `core/product_model/refs.py` | RefResolvers |
| `agents/kira/{profile.py,schemas.py,graph.py,prompts/decompose.md}` | Kira decomposition |
| `apps/control_api/routers/{sources,product_model,specs,scope,inbound}.py` | REST |
| `tests/fixtures/supportdesk/PRD.md` | reference PRD |

## 10. Development Tasks

- [ ] 05.1 Add migrations `0009`–`0012` and models, plus the immutability triggers for ProductSource, approved FeatureSpec and locked children.
- [ ] 05.2 Implement the `InboundEvent` envelope, adapter registry and `InboundService` pipeline with idempotency and audit.
- [ ] 05.3 Implement `DocumentUploadAdapter` (md/txt/pdf/docx/json), content-addressed storage and the text artifact.
- [ ] 05.4 Implement `ProductSourceService` versioning (same hash → duplicate, new hash → version+1).
- [ ] 05.5 Implement the Capability, Feature, FeatureSpec and Knowledge services with versioning and approval rules.
- [ ] 05.6 Write `tests/fixtures/supportdesk/PRD.md`: SupportDesk ticket management, about 2 capabilities and 4–6 features (create ticket, list tickets, get ticket, update ticket status, close ticket), rules (subject/description required, default status OPEN, closed tickets cannot be modified; an update to a CLOSED ticket is rejected with HTTP 409 Conflict, which is the expected behavior Phase 15 resolves against) and NFR (FastAPI, SQLAlchemy, pytest, SQLite for the *SupportDesk app* is acceptable).
- [ ] 05.7 Implement the Kira `kira.decompose` profile, `ProductDecomposition` schema and prompt `decompose.md` v1. Context: normalized source text, project name, existing approved product model summary (empty for Greenfield) and DECISION items.
- [ ] 05.8 Implement the deterministic proposal validator and wire it into the output validator registry (`artifact:PRODUCT_DECOMPOSITION`).
- [ ] 05.9 Implement `ProductModelService.persist_proposal`, called by the worker post-validation hook (a platform service, not the agent): PROPOSED entities + Clarifications.
- [ ] 05.10 Implement the re-decomposition flow after clarification answers (supersede unapproved proposals).
- [ ] 05.11 Implement scope sets, Approval(SCOPE) and the on-approval cascade in a single transaction.
- [ ] 05.12 Replace the guard placeholders `product_source_ingested` and `scope_approved`.
- [ ] 05.13 Register the RefResolvers.
- [ ] 05.14 Add the REST routes and events.
- [ ] 05.15 Write the tests in §12.

## 11. LLM-Dependent Tasks

| Item | Detail |
|---|---|
| Why | Decomposing natural-language product intent into capabilities, features, specs and ACs is semantic reasoning |
| Input context | normalized ProductSource text (ContextItem kind TEXT, provenance SOURCE_DOCUMENT), project metadata, DECISION KnowledgeItems, existing approved features (for non-greenfield reuse) |
| Context source | the snapshot's `artifact_versions` (text artifact) + knowledge refs |
| Output schema | `ProductDecomposition` |
| Runtime / alias | `LangGraphRuntime` (single structured node + optional self-check node) / `product_decomposition` |
| Path | scheduler → worker → AgentRuntimeExecutor → LangGraphRuntime → ModelRouter → provider |
| Validation | Pydantic + deterministic validator (§6) |
| Retries | schema retries with validation errors (≤2); execution retry → new Execution |
| Failure handling | FAILED(`VALIDATION_FAILED`) with report artifact; operator may re-run decomposition |
| Cost/token logging | `model_calls` linked to the Kira execution |
| Live acceptance test | `tests/integration/live_llm/test_kira_decompose_supportdesk_live.py`: SupportDesk PRD → valid decomposition; asserts ≥1 capability, ≥3 features, every spec has a mandatory AC, and features cover "create ticket" and "update status" semantics (asserted by keyword presence in the feature name/description, case-insensitive, any of the synonyms) |

## 12. Testing Strategy

### Unit Tests
- Proposal validator: one test per rule (with hand-written invalid proposals as **validator inputs**; these are not used as journey proof).
- Version increment, duplicate-hash detection and scope-set hash stability.
- Text extraction for md, txt, docx and pdf fixtures.

### Persistence Tests
- An APPROVED FeatureSpec and its ACs cannot be updated (trigger).
- Duplicate inbound upload (same event id / idempotency key) gives one ProductSource and an `inbound_events.status=DUPLICATE` row.
- Scope approval cascade is atomic.

### Integration Tests
- Upload via `/projects/{id}/sources` creates an inbound event, a ProductSource v1 and an audit row. Re-upload of changed content creates v2, with v1 intact.
- The guard `start_product_modeling` fails without a source and succeeds with one.
- The guard `start_architecture` fails while an OPEN blocking clarification exists or while scope is unapproved, and fails if the scope set is approved but a spec in it has been superseded (hash mismatch).

### Runtime / Live-LLM Tests
- Live Kira decomposition of the SupportDesk PRD.
- Live clarification round: PRD variant `PRD_ambiguous.md` (omits the closed-ticket rule and states "closed tickets may be handled as appropriate"). Kira should emit ≥1 open question. If the model emits none, the test records a soft warning, not a failure, because model behavior varies. The answer, then re-decomposition, produces a new proposal, and the DECISION item is present in the second execution's snapshot.

### Workflow Tests
- Upload → decompose (live) → persist proposal → request scope approval → approve → cycle can `start_architecture`.

### Security Tests
- An AGENT actor cannot call `/scope/approval-request` decisions or `/specs/{id}/approve`.
- An unauthenticated inbound call is rejected (401) and recorded as `REJECTED` without command dispatch.

### Commands
```
make check
LLM_LIVE_TESTS=1 uv run pytest -m live_llm --live-required tests/integration/live_llm/test_kira_decompose_supportdesk_live.py
LLM_LIVE_TESTS=1 uv run pytest -m workflow --live-required tests/workflow/product_model
```

## 13. Milestone

A real PRD uploaded through the inbound document adapter becomes an immutable, versioned ProductSource. A live Kira execution decomposes it into a schema-validated proposal of Capabilities, Features, FeatureSpecs, Requirements, UserStories and ACs, and its open questions become durable Clarifications. After an explicit human Scope Approval, the FeatureSpecs become immutable APPROVED versions and the Greenfield DeliveryCycle can advance to ARCHITECTURE.

## 14. Acceptance Criteria

- [ ] ProductSource versions are immutable and content-addressed. A duplicate upload creates no new version.
- [ ] Every inbound upload produces an `inbound_events` row with correlation ID, idempotency handling and audit.
- [ ] Kira decomposition runs as an Execution through the live ModelRouter path.
- [ ] Invalid proposals are rejected by the deterministic validator before any canonical row is written.
- [ ] Every persisted FeatureSpec has ≥1 Requirement and ≥1 mandatory AC with an `evidence_requirement`.
- [ ] Open questions become Clarifications. Answers become DECISION KnowledgeItems and feed re-decomposition.
- [ ] Scope approval is an explicit HUMAN Approval pinned to a scope-set hash, and it atomically approves the FeatureSpecs.
- [ ] Approved FeatureSpecs are immutable. Edits create new versions.
- [ ] `start_architecture` is blocked until scope is approved and blocking clarifications are resolved.
- [ ] Kira has no write path to the DB (the import-linter contract passes).

## 15. Exit Criteria

- §14 green and the live Kira test passed (evidence recorded).
- The FeatureSpec/AC data model is frozen for 06, 09 and 11.
- The guard placeholders for this phase are removed.
- `STATUS.md`: Kira LLM readiness updated; integration tracker "document upload" set to IMPLEMENTED.

## 16. Dependencies

### Depends On
- 03: ANALYSIS executions, clarifications, artifacts (and transitively 01/02).

### Blocks
- 06.

### Can Run In Parallel With
- 04 (disjoint modules; see Phase 04 §16).
- 07.

## 17. Risks / Implementation Notes

- **Model risk:** decomposition granularity varies. The validator enforces structure, not taste, and humans review via scope approval.
- **Large PRDs:** chunk by headings if the source exceeds the context budget. MVP fixtures are small, so document the limit.
- **PDF/DOCX extraction quality:** store the extracted text as an artifact so reviewers can see exactly what Kira saw.
- **Clarification non-determinism:** the live clarification assertion is soft. The hard assertion is the persistence and resume mechanics.

## 18. Deliverables

- Code: `core/integrations/inbound/*`, `core/product_model/*`, `agents/kira/{decompose}`.
- Migrations: `0009`–`0012`.
- APIs/events: §8.
- Fixtures: `tests/fixtures/supportdesk/PRD.md`, `PRD_ambiguous.md`, document-format fixtures.
- Tests: §12 suites, including live Kira.
