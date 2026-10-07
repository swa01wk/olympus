# Phase 13 — Specification Delta, Impact Engine, Hybrid Retrieval, Incremental Re-index and Staleness

## 1. Objective

Build the shared change-intelligence layer used by Feature Change (14) and Bug Fix (15) (ARCH §14.7, §21.4; TECH §13.3–13.4, §21):

- **SpecDelta**: a versioned, structured diff between FeatureSpec versions (added/modified/removed requirements, ACs and rules), plus ImplementationSpec `kind=DELTA` support.
- **ImpactEngine**: deterministic traversal from changed specs through SpecCodeLinks (GENERATED_LINEAGE / HUMAN_CONFIRMED / DISCOVERED with confidence) and CodeRelations (calls/imports/accesses/exposes/inherits, dependents and dependencies) to affected **CodeEntities, contracts/schemas, Tests and Behavioral Baselines**, each with a rationale path. Semantic retrieval expands candidates only when needed.
- **Hybrid retrieval**: structural → lexical → semantic (pgvector), with source-labeled, explainable results.
- **Verification obligation selection** from impact: impacted baselines and impacted tests. This replaces Phase 12's "all baselines" default with "impacted + policy floor".
- **Incremental canonical re-index** of changed files, provably equivalent to a full rebuild, plus **SpecCodeLink refresh**.
- **StalenessService**: STALE / REVALIDATION_REQUIRED for tasks, executions and baselines when authoritative inputs change.

## 2. Architectural Context

- **Position:** Intelligence plane → `core/intelligence/impact`, `code_index/retrieval`. Feature Change SPEC_DELTA → IMPACT_ANALYSIS; Bug Fix ROOT_CAUSE (code-path traversal); post-integration re-index.
- **Upstream:** 12 (baselines with `exercised_stable_keys`, BaselineSet), 08 (links, canonical service), 07 (index, retrieval), 05/06 (spec and ImplementationSpec versioning), 02 (`embedding` alias).
- **Downstream:** 14, 15, 16 (git push → staleness/re-index), 17 (Impact Explorer).
- **Invariants:**
  - 31–32: Feature Change uses a versioned spec delta; impact uses Spec-to-Code and dependency traversal.
  - 35: impacted baselines are revalidated.
  - 18: re-index consistency — changed entities and links reflect the new integrated SHA before final assurance.
  - Semantic retrieval never replaces structural truth.
  - Retrieval explainability.

## 3. Current Repository Assessment

Inspection on 2026-10-01: none of this exists.

### Existing
- (after 07) structural/lexical retrieval with `RetrievalHit.retrieval_source` — **EXTEND** (SEMANTIC).
- (after 08) full canonical rebuild per IC — **EXTEND** (incremental + equivalence check).
- (after 12) BASELINE_REQUIRED obligation source selecting all baselines — **REFACTOR** (impact-driven selection with policy floor).
- (after 01) Task STALE / REVALIDATION_REQUIRED edges defined but uncalled — **EXTEND** (StalenessService).

### Partial
- Guards `impact_assessment_complete` and `architecture_delta_resolved` are placeholders — **REPLACE**.

### Missing
- SpecDelta, ImpactAssessment, embeddings, semantic retrieval, incremental index, link refresh and staleness — **ADD**.

### Refactor / Migration Required
- Phase 12's obligation source becomes `select_baselines(cycle, impact_assessment)`.

## 4. Scope

1. Tables: `spec_deltas`, `impact_assessments`, `impact_items`, `embeddings` (pgvector), `staleness_events`.
2. **SpecDelta service** (deterministic): `compute(from_spec_version, to_spec_version) → SpecDelta`. It aligns by `lineage_key` for requirements/ACs/stories and by text for rules, constraints, inputs and outputs. It produces `added/modified/removed` lists with before/after values, and sets `acceptance_criteria.change_kind` on the new version. The delta is immutable and hashed. Approval(SPEC_DELTA) is pinned to the delta hash.
3. **ImplementationSpec DELTA**: an ImplementationSpec with `kind=DELTA`, `supersedes_id = parent ImplementationSpec version` and body describing *changed* components/apis/schemas/data_changes/required_tests/file_scope. The conformance validator (06) applies against the current approved Architecture. A violation produces `ARCHITECTURE_DELTA_REQUIRED`.
4. **ImpactEngine.assess(cycle, spec_delta | seed_entities, index_version)** (deterministic core):
   1. *Seed resolution:* changed FeatureSpec lineage → ACTIVE SpecCodeLinks (all origins, carrying confidence) → principal stable keys. For Bug Fix, seeds come from root-cause candidate entities (15).
   2. *Structural expansion:* BFS over the canonical index with relation-specific direction and depth from policy `impact.traversal`:
      - `CALLS` inbound depth 2 (callers) and outbound depth 1 (callees);
      - `IMPORTS` inbound depth 1;
      - `EXPOSES`/`USES_SCHEMA`/`MAPS_TO`/`ACCESSES` both directions depth 1;
      - `INHERITS` both directions depth 1.
      Each item records `impact_kind ∈ {DIRECT, TRANSITIVE}`, `path` (list of stable keys and relations) and confidence = product of edge confidences × link confidence.
   3. *Contracts/schemas:* SCHEMA, ROUTE, ORM_MODEL and TABLE items are flagged as `contract_surface=true`.
   4. *Tests:* tests with `VERIFIED_BY` to any impacted entity, plus tests linked to changed ACs via VERIFIES links.
   5. *Baselines:* ACTIVE baselines whose `exercised_stable_keys` ∩ impacted set ≠ ∅, **or** whose `feature_spec` lineage = a changed spec. Each records a reason.
   6. *Lexical expansion:* identifiers and nouns from added/modified AC text (deterministic tokenization) → lexical search → `retrieval_source=LEXICAL` items (`impact_kind=CANDIDATE`), only when structural seeds are < policy `impact.min_structural_seeds` or the delta introduces new terms not present in any linked entity name.
   7. *Semantic expansion:* pgvector similarity between the delta text embedding and entity embeddings. Items are added as `impact_kind=SEMANTIC_CANDIDATE` with `retrieval_source=SEMANTIC`, only if steps 1–6 gave fewer than policy thresholds or terminology mismatch is detected (zero lexical hits). They **never** create obligations alone; they surface for planner context and human review.
   8. *Architecture impact flag:* `architecture_delta_suggested = true` if any impacted entity is outside the components of the linked ImplementationSpecs **and** outside the Architecture's component directories, or if the delta introduces a new integration point.
   9. Persist the ImpactAssessment + items + a **verification selection**: impacted tests (obligations `reason=IMPACT_ASSESSMENT`) and impacted baselines (`reason=BASELINE_IMPACTED`), each with `source_refs` = item path. Policy floor `impact.baseline_floor ∈ {IMPACTED_ONLY, IMPACTED_PLUS_SMOKE, ALL}` (default `IMPACTED_PLUS_SMOKE`; smoke = baselines tagged `smoke` or one per feature).
5. **Embeddings**: `EmbeddingService` (ModelRouter `embedding` alias). Entity text = qualified name + signature + docstring + first N lines. Spec text = behavior + rules + ACs. Rows are keyed by `(subject_type, subject_key, content_hash, model)`. They are computed lazily for the canonical index and specs, and recomputed only for changed content hashes.
6. **Semantic retrieval** (`retrieval/semantic.py`) plus a **hybrid** orchestrator (`retrieval/hybrid.py`) implementing the ARCH §14.7 sequence:
   1. resolve Feature/Spec semantically;
   2. traverse SpecCodeLink;
   3. traverse calls/imports;
   4. traverse tests/baselines;
   5. return provenance and confidence.
   Exposed as `GET /code/search?mode=hybrid` and the internal `HybridRetrieval.resolve_feature(text)`, which Phases 14/15 use for feature/defect resolution.
7. **Incremental canonical re-index**: `CodeIndexer.build_incremental(parent_version, new_sha)`:
   1. `git diff --name-status parent_sha new_sha` → reparse changed/added files and drop deleted ones;
   2. copy entities of unchanged files (new rows with the same stable keys and content hashes);
   3. re-resolve **all** relations whose source or target module is in the changed set **or** imports a changed module;
   4. run the framework extractors for changed files plus route prefix composition globally.
   An equivalence guard compares `content_hash` with a full build in tests, and in production when policy `index.verify_incremental=true` (default true for MVP; sampling later). `CanonicalIndexService.promote_ic` uses incremental when the previous canonical/released version is an ancestor.
8. **SpecCodeLink refresh** after each canonical promotion:
   - a link whose stable key is missing in the new index → `STALE` + Finding `LINEAGE_LINK_STALE` (MAJOR when the link is HUMAN_CONFIRMED/GENERATED, MINOR when DISCOVERED);
   - an entity whose content hash changed → `last_confirmed_index_version_id` updated plus a `code_entity_changes` record;
   - new GENERATED_LINEAGE links come from Phase 08 materialization.
   `RefreshReport` is stored as an artifact.
9. **StalenessService** (deterministic, event-driven):
   - Tasks COMPLETED whose contract inputs reference a superseded spec, ImplementationSpec or Architecture version, in a cycle not yet RELEASED → `REVALIDATION_REQUIRED`.
   - QUEUED/LEASED executions whose snapshot base is no longer an ancestor of the cycle's current base, or whose contract was superseded → `STALE`.
   - ACTIVE baselines exercising entities changed in a new canonical index → `REVALIDATION_REQUIRED` until an obligation run PASSES at the new SHA.
   - Release condition `required_executions_not_stale` (10) now has real inputs.
   - Records are written to `staleness_events` with cause.
   - **Canonical revision changes** (README §5.9.9): the service subscribes to `repository.canonical_advanced` (causes `INTEGRATION_READY`, `EXTERNAL_SYNC`) and `repository.canonical_reverted`. For each open cycle bound to the repository, other than the cycle whose IC caused the advance:
     - QUEUED/LEASED Executions whose `snapshot.base_commit` is not an ancestor of the new `canonical_commit` → `STALE` (cause `CANONICAL_REVISION_CHANGED`);
     - Tasks whose ISSUED contract inputs reference a superseded canonical index version → `REVALIDATION_REQUIRED`;
     - READY CANDIDATE index versions built on a non-ancestor base → `DISCARDED`;
     - ImpactAssessments computed on a superseded canonical index → `STALE`, which makes the `impact_assessment_complete` guard fail until re-run;
     - ACTIVE baselines exercising entities changed between the old and new canonical revisions → `REVALIDATION_REQUIRED`;
     - a cycle whose pinned `base_sha` is no longer an ancestor of `canonical_commit` (revert or rewrite) gets a blocking Finding `CYCLE_BASE_DIVERGED`, and its next code-needing transition re-pins only through an explicit HUMAN `rebase_cycle` command.
     Nothing continues silently against an unexpected repository state.
10. Guards: `impact_assessment_complete` (latest IA for the cycle is COMPLETE and its spec delta hash matches the approved delta) and `architecture_delta_resolved` (if `architecture_delta_suggested`, either an approved Architecture DELTA version exists, or a HUMAN decision "no architecture change" (Approval(ARCHITECTURE_DELTA) with decision note) is recorded).

## 5. Out of Scope

- ChangeRequest intake and Kira change interpretation (14).
- Defect, reproduction and root cause (15). This phase provides seed-entity impact plus path queries that 15 uses.
- Git webhook-triggered staleness (16 wires events into this service).

### Do Not Change
- No obligation may be created solely from SEMANTIC or LEXICAL candidates.
- Do not delete STALE links. Mark them and keep the history.

## 6. Domain / Data Model Changes

Migration `0023_p13_spec_deltas_impact_embeddings_staleness.py` (TECH 009 impact_assessments).

```python
class SpecDelta(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "spec_deltas"
    key: Mapped[str]
    project_id: Mapped[uuid.UUID]
    delivery_cycle_id: Mapped[uuid.UUID]
    feature_id: Mapped[uuid.UUID]
    from_spec_id: Mapped[uuid.UUID | None]
    to_spec_id: Mapped[uuid.UUID]
    changes: Mapped[dict] = mapped_column(
        JSONB
    )  # {requirements:{added,modified,removed}, acceptance_criteria:{...}, rules:{...}, inputs/outputs:{...}}
    content_hash: Mapped[str]
    approval_id: Mapped[uuid.UUID | None]
    status: Mapped[str]  # PROPOSED | APPROVED | REJECTED | SUPERSEDED


class ImpactAssessment(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "impact_assessments"
    key: Mapped[str]
    delivery_cycle_id: Mapped[uuid.UUID]
    index_version_id: Mapped[uuid.UUID]
    commit_sha: Mapped[str]
    seed_kind: Mapped[str]  # SPEC_DELTA | DEFECT_ROOT_CAUSE | MANUAL
    spec_delta_id: Mapped[uuid.UUID | None]
    seed_refs: Mapped[list] = mapped_column(JSONB)
    status: Mapped[str]  # RUNNING | COMPLETE | SUPERSEDED
    architecture_delta_suggested: Mapped[bool]
    summary: Mapped[dict] = mapped_column(JSONB)
    policy_version_id: Mapped[uuid.UUID]
    content_hash: Mapped[str]


class ImpactItem(Base, UUIDPkMixin):
    __tablename__ = "impact_items"
    impact_assessment_id: Mapped[uuid.UUID] = mapped_column(index=True)
    item_type: Mapped[str]  # CODE_ENTITY | TEST | BASELINE | CONTRACT | SPEC
    ref: Mapped[str]  # stable key / baseline lineage key / spec key
    impact_kind: Mapped[str]  # DIRECT | TRANSITIVE | CANDIDATE | SEMANTIC_CANDIDATE
    retrieval_source: Mapped[str]  # STRUCTURAL | LEXICAL | SEMANTIC
    path: Mapped[list] = mapped_column(JSONB)  # [{from, relation, to}]
    confidence: Mapped[float]
    contract_surface: Mapped[bool]
    rationale: Mapped[str]
    selected_for_verification: Mapped[bool]


class Embedding(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "embeddings"
    subject_type: Mapped[str]
    subject_key: Mapped[str]
    repository_id: Mapped[uuid.UUID | None]
    content_hash: Mapped[str]
    model: Mapped[str]
    dim: Mapped[int]
    vector: Mapped[list[float]] = mapped_column(
        Vector(dim=None)
    )  # pgvector; dimension fixed by config (e.g. 1536)
    __table_args__ = (UniqueConstraint("subject_type", "subject_key", "content_hash", "model"),)
```

Other changes:
- `staleness_events`: id, subject_type, subject_id, from_status, to_status, cause_type, cause_ref, created_at.
- An HNSW index on `embeddings.vector` (`vector_cosine_ops`).

## 7. State / Lifecycle Changes

- SpecDelta: PROPOSED → APPROVED (Approval(SPEC_DELTA), hash-pinned) | REJECTED → SUPERSEDED.
- ImpactAssessment: RUNNING → COMPLETE → SUPERSEDED (spec delta or index changed).
- Task: COMPLETED → REVALIDATION_REQUIRED, and STALE → READY after a new contract version (StalenessService + ContractService).
- Execution: QUEUED/LEASED → STALE.
- Baseline: ACTIVE → REVALIDATION_REQUIRED → ACTIVE.
- SpecCodeLink: ACTIVE → STALE.
- FEATURE_CHANGE edges activated here:
  - IMPACT_ANALYSIS → PLANNING (`impact_assessment_complete`, `architecture_delta_resolved`);
  - IMPACT_ANALYSIS → SPEC_DELTA (`revise_spec_delta`).

## 8. API / Contract Changes

| Method | Path | Notes |
|---|---|---|
| POST | `/features/{id}/spec-deltas` | `{from_spec_id, to_spec_id, delivery_cycle_id}` → compute |
| GET | `/spec-deltas/{id}` | |
| POST | `/spec-deltas/{id}/approval-request` | |
| POST | `/delivery-cycles/{id}/impact-assessments` | run engine (ARCH §20) |
| GET | `/impact-assessments/{id}` | items grouped by type with paths, sources, confidence, selection |
| GET | `/specs/{id}/impact` | (TECH §23) on-demand impact preview for a spec version against the canonical index |
| GET | `/code/search?mode=hybrid&q=` | hybrid results labeled by source |
| GET | `/repositories/{id}/code-index/canonical/refresh-report` | latest link refresh report |
| GET | `/delivery-cycles/{id}/staleness` | staleness events |
| POST | `/delivery-cycles/{id}/commands/rebase_cycle` | HUMAN (OPERATOR). Only while a `CYCLE_BASE_DIVERGED` Finding is open. Re-pins `base_sha := canonical_commit` (Phase 01 `pin_base_sha`), resolves the Finding, and marks every non-terminal Task `REVALIDATION_REQUIRED`. It is the only way a cycle's base changes outside its first code-needing transition. |

```python
class ImpactEngine:
    async def assess(self, cycle_id, *, spec_delta_id=None, seed_stable_keys=None, index_version_id) -> ImpactAssessment
class HybridRetrieval:
    async def resolve_feature(self, text: str, project_id) -> list[FeatureCandidate]     # spec/feature candidates with source labels
    async def search(self, q, index_version_id, modes=("STRUCTURAL","LEXICAL","SEMANTIC")) -> list[RetrievalHit]
class StalenessService:
    async def on_spec_superseded(...); async def on_canonical_index_changed(...); async def on_base_moved(...)
    async def on_canonical_revision_changed(self, repository_id, from_sha, to_sha, cause) -> StalenessReport   # README §5.9.9
```

Events: `spec_delta.computed`, `spec_delta.approved`, `impact.assessed`, `embedding.updated`, `code_index.updated` (incremental flag), `spec_code_link.stale`, `task.revalidation_required`, `execution.stale`, `baseline.revalidation_required`.

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `core/product_model/specifications/delta.py` | SpecDelta compute + approval |
| `core/planning/implementation_specs/delta.py` | DELTA ImplementationSpec support |
| `core/intelligence/impact/{engine,traversal,selection,architecture_flag}.py` | impact engine |
| `core/intelligence/code_index/retrieval/{semantic,hybrid}.py` | semantic + hybrid |
| `core/intelligence/code_index/embeddings.py` | EmbeddingService |
| `core/intelligence/code_index/incremental.py` | incremental build + equivalence |
| `core/traceability/spec_code_links/refresh.py` | link refresh |
| `core/intelligence/impact/staleness.py` | StalenessService |
| `core/assurance/obligations.py` | REFACTOR: impact-driven test/baseline selection |
| `core/intelligence/impact/guards.py` | guards |
| `apps/control_api/routers/{spec_deltas,impact}.py` | REST |
| `config/policy/default.yaml` | `impact:`, `index:` sections |

## 10. Development Tasks

- [x] 13.1 Add migration `0025` and the models, plus the HNSW index.
- [x] 13.2 Implement SpecDelta compute (lineage-key alignment), `change_kind` marking and approval pinning.
- [x] 13.3 Implement ImplementationSpec DELTA support plus the conformance re-check.
- [x] 13.4 Implement traversal with policy-configured relation/direction/depth and path recording.
- [x] 13.5 Implement test and baseline selection with the policy floor and reasons.
- [x] 13.6 Implement lexical expansion gating.
- [x] 13.7 Implement `EmbeddingService` (batching, content-hash caching) and semantic retrieval.
- [x] 13.8 Implement `HybridRetrieval.resolve_feature` and `search` with source labels.
- [x] 13.9 Implement the architecture-delta heuristic.
- [x] 13.10 Implement ImpactAssessment persistence and obligation creation hooks (obligations created when the IC is READY using the cycle's latest IA).
- [x] 13.11 Implement the incremental index build with equivalence verification, and switch `promote_ic` to incremental.
- [x] 13.12 Implement link refresh and the refresh report.
- [x] 13.13 Implement `StalenessService` and subscriptions (`feature_spec.approved` superseding, `code_index.updated`, `integration.ready`, `repository.canonical_advanced`, `repository.canonical_reverted`), the `CYCLE_BASE_DIVERGED` Finding and the HUMAN `rebase_cycle` command.
- [x] 13.14 Replace guard placeholders `impact_assessment_complete` and `architecture_delta_resolved`.
- [x] 13.15 Add the REST routes and events.
- [x] 13.16 Write the tests in §12.

## 11. LLM-Dependent Tasks

| Item | Detail |
|---|---|
| Why | Semantic expansion requires embeddings when product terminology differs from code terminology. Traversal itself is deterministic. |
| Input | entity text, spec/delta text |
| Output | vectors (`EmbeddingResult`) |
| Runtime / alias | `ModelRouter.embed` / `embedding` (provider per Q-04) |
| Validation | dimension == configured; non-NaN |
| Retries / failure | transport retries. On failure, semantic expansion is skipped and recorded as `SEMANTIC_UNAVAILABLE` on the IA (deterministic impact still completes) |
| Cost logging | `model_calls` rows with `purpose=embedding` |
| Live test | `test_semantic_retrieval_live.py`: on `supportdesk_r1`, the query "close a support case" (no lexical overlap with "ticket"/"status") returns the status-update entities as SEMANTIC hits labeled `SEMANTIC` |

No chat-model calls in this phase. Change interpretation (Kira) is Phase 14.

## 12. Testing Strategy

### Unit Tests
- SpecDelta alignment: added AC, modified AC text, removed requirement and rule change.
- Traversal on a synthetic graph: depth limits, direction and confidence products.
- Baseline selection with each policy floor.
- Architecture-delta heuristic cases.

### Persistence Tests
- SpecDelta and ImpactAssessment immutability once COMPLETE/APPROVED.
- Embedding uniqueness per content hash.

### Integration Tests (deterministic, `supportdesk_r1` + spec fixtures)
- Delta "add priority field to tickets" (hand-authored FeatureSpec v2 as **input**) gives an IA that includes:
  - the `POST /tickets` route, `TicketCreate` schema, `Ticket` ORM model and `tickets` table as DIRECT/TRANSITIVE contract surfaces;
  - `test_create_ticket`;
  - baselines exercising ticket creation.
  Each item has a path. Baselines not touching tickets creation are excluded under IMPACTED_ONLY.
- Obligations are created only from STRUCTURAL items, and LEXICAL/SEMANTIC candidates have `selected_for_verification=false`.
- Incremental re-index after modifying two files equals the full build `content_hash`.
- Link refresh: renaming a principal method marks its link STALE plus a Finding. A modified method updates `last_confirmed`.
- Staleness: superseding an ImplementationSpec while a task is QUEUED marks the execution STALE. Changing an entity exercised by an ACTIVE baseline marks the baseline REVALIDATION_REQUIRED, and a PASS at the new SHA restores ACTIVE.
- Hybrid search labels: structural, lexical and semantic hits are distinguishable.
- `test_canonical_revision_staleness.py`:
  - cycle A is in DEVELOPMENT with a QUEUED execution based on `S0`. Cycle B's IC READY advances canonical to `S1`, a descendant: A's QUEUED execution stays valid, its tasks referencing the superseded canonical index → `REVALIDATION_REQUIRED`, and A's ImpactAssessment → STALE.
  - a simulated revert from `S1` back to `S0` for a cycle that pinned `S1`: `CYCLE_BASE_DIVERGED` is raised and the next code-needing transition is blocked until `rebase_cycle` re-pins to `S0`.
  - every effect writes a `staleness_events` row with `cause_type=CANONICAL_REVISION_CHANGED`.

### Runtime / Live-LLM Tests
- The §11 embedding live test.

### Commands
```
make check
uv run pytest tests/integration/impact tests/integration/code_index/test_incremental.py
LLM_LIVE_TESTS=1 uv run pytest -m live_llm --live-required tests/integration/live_llm/test_semantic_retrieval_live.py
```

## 13. Milestone

Given an approved, versioned FeatureSpec delta and the current canonical index, Olympus deterministically produces a persisted ImpactAssessment listing affected principal code entities, dependent symbols, contracts/schemas, tests and Behavioral Baselines. Every item carries a traversal path, retrieval source and confidence, and verification obligations are selected only from structural impact. Semantic expansion via live embeddings surfaces terminology-mismatched candidates without creating obligations. Incremental canonical re-indexing is provably equivalent to a full rebuild, with SpecCodeLinks refreshed and stale inputs flagged.

## 14. Acceptance Criteria

- [x] SpecDelta is computed deterministically between FeatureSpec versions, is immutable, and its approval is hash-pinned.
- [x] Impact is resolved primarily through SpecCodeLinks and CodeRelations, with recorded paths for every item.
- [x] Every impact item records `retrieval_source` (STRUCTURAL/LEXICAL/SEMANTIC) and confidence.
- [x] Only STRUCTURAL items create obligations. Each obligation records why it was chosen.
- [x] Impacted baselines are selected and the policy floor is applied.
- [x] Incremental re-index equals the full rebuild hash for tested changes.
- [x] After re-index, changed entities and SpecCodeLinks reflect the new SHA before assurance. Missing principal symbols produce STALE links and Findings.
- [x] StalenessService marks tasks, executions and baselines STALE/REVALIDATION_REQUIRED on authoritative input changes.
- [x] A canonical revision change (`repository.canonical_advanced` / `.canonical_reverted`) marks impacted TaskContracts, Executions, candidate indexes, ImpactAssessments and baselines of other open cycles with cause `CANONICAL_REVISION_CHANGED`. A cycle whose base diverged from the canonical revision is blocked until it is explicitly rebased.
- [x] An architecture delta is either approved or explicitly declined by a human before planning when suggested.
- [x] The semantic retrieval path uses the live `embedding` alias and degrades gracefully when unavailable.

## 15. Exit Criteria

- §14 green. The embedding provider decision (Q-04) is recorded in `STATUS.md`.
- `ImpactEngine`, `HybridRetrieval` and `StalenessService` interfaces frozen for 14/15/16.
- Guard placeholders for this phase removed.
- `STATUS.md` technical tracker Impact Analysis updated.

## 16. Dependencies

### Depends On
- 12: baselines and BaselineSet.
- 08, 07, 05/06 (complete).

### Blocks
- 14, 15.

### Can Run In Parallel With
- None.

## 17. Risks / Implementation Notes

- **Over-impact:** depth-2 caller traversal can explode in larger repos. Cap items per IA (policy) and prioritize by confidence.
- **Under-impact:** static call graph gaps. The lexical/semantic candidates surface them for Kira planning context and human review, without obligations.
- **Embedding model changes** invalidate vectors. Keying by `model` prevents mixing.
- **Equivalence check cost:** acceptable at MVP scale. Make it sampling-based later.

## 18. Deliverables

- Code: `core/intelligence/impact/*`, retrieval semantic/hybrid, embeddings, incremental indexer, link refresh, spec delta, ImplementationSpec delta.
- Migration: `0025_p13_spec_deltas_impact`.
- APIs/events: §8.
- Config: `impact:`, `index:` policy sections; embedding config in `config/models.yaml`.
- Tests: §12 suites.
