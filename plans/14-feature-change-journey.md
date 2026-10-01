# Phase 14 — Feature Change Journey (R2)

## 1. Objective

Implement and prove **Journey 3 — Feature Change** (ARCH §17, TECH §21): Change Request → resolve existing Feature → versioned FeatureSpec delta with new or modified ACs → approval → Spec-to-Code and dependency impact → architecture delta only if required → ImplementationSpec delta → Task DAG with impact-bounded scopes → TaskContracts → Forge executions → candidate commits → IC → incremental canonical re-index and link refresh → Sentinel verification of new ACs **plus impacted baselines** → Warden review → evidence → gates → **Release R2**, with new baselines recorded (BaselineSet B2).

The safe-delta rule applies: preserve the architecture unless the change genuinely requires otherwise.

## 2. Architectural Context

- **Position:** FEATURE_CHANGE lifecycle INTAKE → SPEC_DELTA → IMPACT_ANALYSIS → PLANNING → DEVELOPMENT → INTEGRATION → ASSURANCE → RELEASE → COMPLETE.
- **Upstream:** 13 (SpecDelta, ImpactEngine, HybridRetrieval, incremental re-index, staleness), 12 (READY_FOR_CHANGE, baselines), 06 (ImplementationSpec/TaskPlan/compiler), 08–10 (IC, assurance, release), 05 (inbound kernel).
- **Downstream:** 16 (issue-tracker inbound adapters map to the ChangeRequest command defined here), 17 (Impact Explorer, Change views), 19.
- **Invariants:**
  - 31: versioned spec delta.
  - 32: Spec-to-Code and dependency traversal for impact.
  - 35: impacted baselines revalidated.
  - 2–4: architecture delta only if required.
  - 15–18: candidate → IC → re-index before assurance.
  - Live LLM for change interpretation, planning, implementation, review and verification planning.

## 3. Current Repository Assessment

Inspection on 2026-10-01: none of this exists.

### Existing
- (after 13) SpecDelta, ImpactEngine, HybridRetrieval, incremental index, staleness — **RETAIN**.
- (after 06) `kira.implementation_spec`, `kira.task_plan`, compiler — **EXTEND** (delta mode, impact-bounded scope).
- (after 06) Atlas — **EXTEND** (`atlas.architecture_delta`).
- (after 05) inbound kernel — **EXTEND** (adapter `change_request_api`).

### Partial
- Guards `change_request_linked`, `project_change_ready` and `spec_delta_approved` are placeholders — **REPLACE**.

### Missing
- ChangeRequest, change interpretation, delta-mode planning, the feature-change orchestrator and the journey test — **ADD**.

### Refactor / Migration Required
- The compiler takes an optional ImpactAssessment and constrains `allowed_scope` to ImplementationSpec-delta `file_scope` ∩ (impacted files ∪ new files declared in the delta). Phase 06 behavior is unchanged when no IA is supplied.

## 4. Scope

1. Table `change_requests`. Inbound adapter `change_request_api` (operator/API source; idempotent) → command `intake_change_request` → ChangeRequest RECEIVED + FEATURE_CHANGE cycle (INTAKE) linked + a ProductSource version (`source_type=CHANGE_REQUEST`) holding the request text.
2. `project_change_ready` guard: `Project.readiness_state == READY_FOR_CHANGE` **or** the project has ≥1 RELEASED Greenfield release with an ACTIVE BaselineSet (Phase 12 release promotion).
3. **Kira change interpretation** (`kira.change_interpret`, live):
   - Input: change request text plus `HybridRetrieval.resolve_feature` candidates (top-k features/specs with their current approved FeatureSpec versions, AC lists and source labels) plus the project architecture summary.
   - Output `ChangeInterpretation`:
     - `resolution` ∈ {EXISTING_FEATURE, NEW_FEATURE_IN_CAPABILITY, NEW_CAPABILITY}, plus `feature_key` (must be one of the candidates if EXISTING);
     - `proposed_feature_spec` (full FeatureSpecBody for the next version);
     - requirement and AC changes (`added`/`modified`/`removed` with `lineage_key` for modified/removed);
     - open questions;
     - `architecture_change_expected` (bool + rationale).
   - Deterministic validation:
     - the feature key is in the candidates;
     - modified/removed lineage keys exist in the current version;
     - every added AC has `mandatory` and `evidence_requirement`;
     - removed mandatory ACs require an explicit note (they surface in the approval).
4. Spec delta creation: persist FeatureSpec v(n+1) as PROPOSED (children with `change_kind`) → `SpecDelta.compute(v(n), v(n+1))` → Approval(SPEC_DELTA) pinned to the delta hash → on APPROVED: FeatureSpec v(n+1) APPROVED, v(n) SUPERSEDED, StalenessService triggered.
5. Impact (`start_impact_analysis`): `ImpactEngine.assess(spec_delta)` against the **released/canonical** index.
6. **Architecture delta (conditional)**: if `ia.architecture_delta_suggested` or `interpretation.architecture_change_expected`:
   - `atlas.architecture_delta` (live) proposes an Architecture DELTA version (only the changed components, contracts and decisions);
   - conformance and consistency validation, then Approval(ARCHITECTURE_DELTA);
   - alternatively, a HUMAN records the decision "no architecture change".
   Guard `architecture_delta_resolved` (13).
7. **ImplementationSpec delta** (`kira.implementation_spec` with `mode=DELTA`, live):
   - Input: parent ImplementationSpec (GREENFIELD-generated or RECOVERED-promoted), the SpecDelta, ImpactAssessment items (STRUCTURAL items with paths) and the current Architecture (with delta).
   - Output: ImplementationSpecBody delta (`kind=DELTA`, `supersedes_id = parent`).
   - Conformance validator + **impact consistency check**: every DIRECT contract-surface impact item must be addressed (listed in components/apis/schemas/data_changes) or explicitly marked `unchanged_with_reason`. New files must be inside the architecture directory conventions.
   - Approval(IMPLEMENTATION_SPEC).
8. **TaskPlan** (`kira.task_plan`, live) from the approved delta, with impacted entities and selected tests as context. The validator additionally checks that `allowed_scope` ⊆ delta `file_scope` and that every added or modified mandatory AC is covered.
9. **Contracts**: compiler with the IA → `allowed_scope` bounded as in §3, `constraints` += "preserve behavior of impacted baselines: [keys]", and `verification_requirements` += `impacted_baselines`, `new_acceptance_tests`.
10. Development → IC → `promote_ic` (incremental) → link refresh → new GENERATED_LINEAGE links for changed principal symbols (now linked to FeatureSpec v(n+1) and ImplementationSpec delta).
11. Assurance obligations:
    - added/modified mandatory ACs (`AC_MANDATORY`);
    - unchanged mandatory ACs of the changed spec whose linked entities were changed (`AC_REVALIDATION`);
    - impacted baselines (`BASELINE_IMPACTED`, policy floor);
    - impacted tests (`IMPACT_ASSESSMENT`).
    Removed ACs' baselines → RETIRED via approval in the spec delta (no obligation).
12. Release R2: required gates INTEGRATION, WARDEN, SENTINEL, BASELINE. On release:
    - baselines for new mandatory ACs are promoted;
    - superseded baselines (modified ACs) → SUPERSEDED with a new version;
    - BaselineSet B(n+1);
    - ChangeRequest → DONE.
13. Feature-change orchestrator: deterministic SYSTEM sequencing of the above, the same pattern as Greenfield. Each step is a command; agents never trigger transitions.

## 5. Out of Scope

- External issue-tracker webhooks (16; they call `intake_change_request`).
- Multi-feature changes spanning more than 3 features in a single cycle. Policy `change.max_features_per_cycle=3` is enforced; split them.
- UI (17).

### Do Not Change
- Do not modify the APPROVED parent FeatureSpec. The delta always creates v(n+1).
- Do not widen `allowed_scope` beyond the ImplementationSpec delta.
- Do not skip impacted baseline obligations to make a release eligible.

## 6. Domain / Data Model Changes

Migration `0024_p14_change_requests.py` (TECH 009 change_requests).

```python
class ChangeRequest(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "change_requests"
    key: Mapped[str]
    project_id: Mapped[uuid.UUID]
    delivery_cycle_id: Mapped[uuid.UUID | None]
    title: Mapped[str]
    description: Mapped[str]
    source_type: Mapped[str]
    external_ref: Mapped[str | None]
    inbound_event_id: Mapped[uuid.UUID | None]
    product_source_id: Mapped[uuid.UUID]  # immutable text version
    status: Mapped[
        str
    ]  # RECEIVED | INTERPRETED | SPEC_APPROVED | IN_DELIVERY | DONE | REJECTED | CANCELLED
    resolved_feature_id: Mapped[uuid.UUID | None]
    spec_delta_id: Mapped[uuid.UUID | None]
    release_id: Mapped[uuid.UUID | None]
    __table_args__ = (UniqueConstraint("project_id", "source_type", "external_ref"),)
```

`ChangeInterpretation` schema:

```python
class AcChange(BaseModel):
    op: Literal["ADD", "MODIFY", "REMOVE"]
    lineage_key: str | None
    statement: str | None
    given: str | None
    when: str | None
    then: str | None
    mandatory: bool | None
    evidence_requirement: EvidenceRequirement | None
    rationale: str


class ChangeInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution: Literal["EXISTING_FEATURE", "NEW_FEATURE_IN_CAPABILITY", "NEW_CAPABILITY"]
    feature_key: str | None
    capability_key: str | None
    proposed_feature_spec: FeatureSpecBody
    requirement_changes: list[dict]
    acceptance_criteria_changes: list[AcChange]
    architecture_change_expected: bool
    architecture_rationale: str
    open_questions: list[Clarification]
    candidate_ranking_rationale: str
```

`ArchitectureDeltaProposal`: `{changed_components, added_components, changed_contracts, decisions, rationale, impact_refs}` → an Architecture version with `kind=DELTA`, `supersedes_id = current`.

## 7. State / Lifecycle Changes

FEATURE_CHANGE edges and guards (all guards registered and real after this phase):

| Edge | Guard | Orchestrated side effects |
|---|---|---|
| INTAKE → SPEC_DELTA | `change_request_linked`, `project_change_ready` | schedule `kira.change_interpret` |
| SPEC_DELTA → IMPACT_ANALYSIS | `spec_delta_approved`, `repository_ready_with_canonical_commit` (01) | `pin_base_sha` (01: `base_sha := canonical_commit`, normally the R1 released SHA); run ImpactEngine against the canonical index at that SHA |
| IMPACT_ANALYSIS → SPEC_DELTA | HUMAN | supersede delta |
| IMPACT_ANALYSIS → PLANNING | `impact_assessment_complete`, `architecture_delta_resolved` | ImplementationSpec delta (live) |
| PLANNING → DEVELOPMENT | `implementation_specs_approved`, `task_plan_accepted_contracts_issued` | admit tasks |
| DEVELOPMENT → INTEGRATION → ASSURANCE → RELEASE → COMPLETE | Greenfield guards plus BASELINE gate | IC, incremental re-index, refresh, assurance, release R2 |

ChangeRequest: RECEIVED → INTERPRETED → SPEC_APPROVED → IN_DELIVERY → DONE, with REJECTED / CANCELLED (owner `ChangeRequestService`, following the cycle).

## 8. API / Contract Changes

| Method | Path | Notes |
|---|---|---|
| POST | `/projects/{id}/change-requests` | via inbound kernel; `Idempotency-Key`; creates cycle |
| GET | `/projects/{id}/change-requests`, `/change-requests/{id}` | |
| GET | `/delivery-cycles/{id}/change-interpretation` | interpretation + candidates with retrieval labels |
| POST | `/delivery-cycles/{id}/change-interpretation/rerun` | HUMAN |
| GET | `/delivery-cycles/{id}/spec-delta` | |
| POST | `/delivery-cycles/{id}/architecture-delta/propose` | Atlas delta |
| POST | `/delivery-cycles/{id}/architecture-delta/decline` | HUMAN "no architecture change" decision |

Events: `change_request.received`, `change_request.interpreted`, `architecture_delta.proposed`, `architecture_delta.approved`, `architecture_delta.declined`, `change_request.done`.

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `core/product_model/changes/{service,interpretation,orchestrator,guards}.py` | ChangeRequest lifecycle, interpretation persistence, orchestration |
| `core/integrations/inbound/adapters/change_request_api.py` | inbound adapter |
| `agents/kira/prompts/change_interpret.md`, `schemas.py` | `kira.change_interpret` |
| `agents/kira/prompts/implementation_spec_delta.md` | delta mode prompt |
| `agents/atlas/prompts/architecture_delta.md`, `schemas.py` | `atlas.architecture_delta` |
| `core/planning/implementation_specs/delta.py` | EXTEND: impact consistency check |
| `core/planning/compiler.py` | EXTEND: IA-bounded scope + baseline constraints |
| `core/assurance/obligations.py` | EXTEND: `AC_REVALIDATION` source |
| `core/release/service.py` | EXTEND: baseline supersession/retirement on release |
| `apps/control_api/routers/changes.py` | REST |
| `tests/fixtures/supportdesk/change_priority.md`, `tests/fixtures/supportdesk/trusted_seed.yaml` | fixtures |
| `tests/journey/test_feature_change_supportdesk.py` | journey |

## 10. Development Tasks

- [ ] 14.1 Add migration `0024` and the ChangeRequest model and service.
- [ ] 14.2 Implement the `change_request_api` inbound adapter and the `intake_change_request` command (creates the ProductSource version + cycle).
- [ ] 14.3 Implement the `project_change_ready` and `change_request_linked` guards.
- [ ] 14.4 Implement the `kira.change_interpret` profile, schema, prompt v1 and validator.
- [ ] 14.5 Implement FeatureSpec v(n+1) persistence from the interpretation, then SpecDelta compute, Approval(SPEC_DELTA) and the `spec_delta_approved` guard.
- [ ] 14.6 Implement the `atlas.architecture_delta` profile and the decline path.
- [ ] 14.7 Implement the `kira.implementation_spec` DELTA mode and the impact consistency check.
- [ ] 14.8 Extend the TaskPlan validator and compiler for impact-bounded scope.
- [ ] 14.9 Add the `AC_REVALIDATION` obligation source.
- [ ] 14.10 Implement release-time baseline promotion, supersession and retirement plus BaselineSet versioning.
- [ ] 14.11 Implement the feature-change orchestrator.
- [ ] 14.12 Implement the trusted-project seed helper `tests/journey/seed.py::seed_trusted_project(repo_fixture, seed_yaml)`. It creates canonical FeatureSpecs (HUMAN-authored YAML inputs), an approved Architecture, HUMAN_CONFIRMED links (from YAML stable keys), baselines from existing tests (executed deterministically) and READY_FOR_CHANGE. These are human inputs only.
- [ ] 14.13 Add the REST routes and events.
- [ ] 14.14 Write the tests in §12, including the journey.

## 11. LLM-Dependent Tasks

| Profile | Why | Inputs (source) | Output | Alias | Validation | Live test |
|---|---|---|---|---|---|---|
| `kira.change_interpret` | Interpreting product language against the existing feature model | CR text (ProductSource), hybrid candidates (DB/index), architecture summary | `ChangeInterpretation` | `product_decomposition` | candidate membership, lineage keys, AC completeness | `test_kira_change_interpret_live.py`: "Add ticket priority: LOW, MEDIUM, HIGH" resolves to the ticket creation/management feature (EXISTING) with ≥1 ADD AC mentioning priority |
| `atlas.architecture_delta` | Architectural change design when required | Architecture, IA contract surfaces, delta | `ArchitectureDeltaProposal` | `architecture` | refs to existing components; conformance | `test_atlas_delta_live.py` (fixture delta forcing a new integration point) |
| `kira.implementation_spec` (DELTA) | Technical realization of the delta | parent ImplementationSpec, delta, IA items, architecture | ImplementationSpec delta | `planning` | conformance + impact consistency | journey |
| `kira.task_plan` | Work decomposition | ImplementationSpec delta, IA | `TaskPlan` | `planning` | Phase 06 + scope bounds | journey |
| `forge` | Code delta | contracts | `ImplementationResult` | `implementation` | Phase 04 | journey |
| `warden.review` / `sentinel.plan` | Review / verification planning | IC diff + obligations | Phase 09 | `review` / `verification_planning` | Phase 09 | journey |

All of them go through the CONTROL_PLANE/IMPLEMENTATION_PLAN Task → worker → LangGraphRuntime → ModelRouter path, with costs in `model_calls`.

## 12. Testing Strategy

### Unit Tests
- Interpretation validator (unknown feature key, unknown lineage key, missing evidence requirement).
- Impact consistency check (unaddressed DIRECT contract surface → reject).
- Compiler scope bounding with the IA.

### Persistence Tests
- ChangeRequest idempotency (same external_ref / idempotency key → one CR, one cycle).
- Parent FeatureSpec immutable. v(n+1) children carry `change_kind`.

### Integration Tests (deterministic)
- The guard `project_change_ready` blocks a project that is not ready.
- Removing a mandatory AC requires a note and shows in the approval subject.
- BaselineSet versioning on a release with superseded baselines.

### Runtime / Live-LLM Tests
- The §11 live tests.

### E2E / Journey Tests (`journey`, live)
`test_feature_change_supportdesk.py`:
1. `seed_trusted_project(supportdesk_r1, trusted_seed.yaml)` → READY_FOR_CHANGE with B1 (human-authored inputs only).
2. POST change request `change_priority.md` → FEATURE_CHANGE cycle (INTAKE).
3. Live interpretation → FeatureSpec v2 (priority ACs) → SpecDelta → scripted HUMAN approval.
4. Impact: assert the IA includes the Ticket ORM model, tickets table, create schema, `POST /tickets` route and ≥1 impacted baseline, each with a path; and that ≥1 unrelated baseline is excluded under IMPACTED_ONLY (or included only as smoke under the default floor, with reason `SMOKE`).
5. Architecture delta: expected none. If suggested, the scripted HUMAN declines with a note (the test accepts either path and asserts the guard semantics).
6. ImplementationSpec delta (live) → approve → TaskPlan (live) → accept. Contracts' `allowed_scope` ⊆ delta `file_scope`.
7. Forge (live) → IC → incremental re-index. Assert canonical index SHA == integrated SHA, `content_hash` equals a full rebuild, and links refreshed (new GENERATED_LINEAGE to FeatureSpec v2).
8. Assurance (live Warden/Sentinel): new priority ACs have PASS evidence, impacted baselines have PASS evidence at the IC SHA, and gates PASS.
9. Release R2 (scripted HUMAN approval) → `main` == integrated SHA, BaselineSet B2 includes the priority baselines, and CR DONE.
10. `assert_live_llm_proof(cycle, [change_interpret, implementation_spec_delta, task_plan, forge, warden, sentinel_plan])`.
11. Lineage: from the new priority AC → Task → Execution → commit → IC → entity (`Ticket.priority` column / schema field) → test → Evidence → R2.
12. Restart → state unchanged.

### Failure / Recovery Tests
- A baseline failing in the IC (fixture: Forge's change accidentally breaks default OPEN, simulated by a deterministic post-commit patch in a variant test) → BASELINE gate FAIL → remediation → new IC → PASS.

### Commands
```
make check
LLM_LIVE_TESTS=1 uv run pytest -m "live_llm or journey" --live-required tests/integration/live_llm/change tests/journey/test_feature_change_supportdesk.py -s
```

## 13. Milestone

**Journey 3 complete.** The change request "Add ticket priority: LOW, MEDIUM, HIGH" is resolved by live Kira to the existing SupportDesk feature and becomes an approved, versioned FeatureSpec delta. Graph-derived impact analysis bounds an approved ImplementationSpec delta and task scopes. Live Forge produces the code delta, which is integrated and incrementally re-indexed with refreshed lineage. New ACs and every impacted baseline pass against the exact integrated SHA, and a deterministically eligible, human-approved **Release R2** is produced with BaselineSet B2.

## 14. Acceptance Criteria

- [ ] A ChangeRequest is ingested idempotently through the inbound kernel and linked to exactly one FEATURE_CHANGE cycle.
- [ ] The change creates FeatureSpec v(n+1) and a hash-pinned approved SpecDelta. The parent version is unchanged.
- [ ] Impacted code, tests and baselines are selected via SpecCodeLinks and CodeRelations, with recorded paths and reasons.
- [ ] An architecture delta occurs only when suggested or expected, and is approved or explicitly declined by a human.
- [ ] Task `allowed_scope` is bounded by the ImplementationSpec delta and impact.
- [ ] The cycle starts from the repository's exact canonical revision (`base_sha` pinned from `canonical_commit`). All Forge work runs in isolated ExecutionWorkspaces from that base. At IC READY, `canonical_commit` advances to the integrated SHA, and the canonical index is re-indexed incrementally at that SHA before assurance, with links refreshed.
- [ ] New and modified mandatory ACs and all selected impacted baselines have PASS evidence at the IC SHA.
- [ ] Release R2 is eligible only with BASELINE, SENTINEL, WARDEN and INTEGRATION gates PASS.
- [ ] The Feature Change journey test passes live with LLM proof for all model-dependent stages.
- [ ] Lineage from the change request to R2 and back from changed code to FeatureSpec v2 is queryable.

## 15. Exit Criteria

- §14 green, with the journey run recorded in `STATUS.md`.
- Journey Readiness → Feature Change = COMPLETE (pending Phase 19).
- No FEATURE_CHANGE guard placeholders remain.

## 16. Dependencies

### Depends On
- 13.

### Blocks
- 16.

### Can Run In Parallel With
- 15 (Bug Fix).
  - Both depend only on 13 (plus earlier phases).
  - 14 owns `core/product_model/changes`, `kira.change_interpret`, `atlas.architecture_delta` and the IA-bounded compiler extension.
  - 15 owns `core/product_model/defects`, `core/assurance/reproduction` and the root-cause profiles.
  - Shared touchpoints are the obligation-source registry and the release service. Coordinate via separate registration functions and serialize merges of `core/release/service.py` and the migrations.

## 17. Risks / Implementation Notes

- **Seeded trusted project in the journey test:** it uses human-authored inputs (canonical specs, links, baselines), which is allowed under the LLM policy. The chained Phase 19 demo replaces the seed with the real Greenfield + Brownfield outputs.
- **Model risk:** feature resolution may pick the wrong feature. Mitigate with candidate constraints and human approval of the delta.
- **Data migration in SupportDesk:** adding a column needs a default value for existing rows. The ImplementationSpec delta must include `data_changes` with defaults. Warden checks it.
- **Deferred:** external tracker linkage (16).

## 18. Deliverables

- Code: `core/product_model/changes/*`, inbound adapter, Kira/Atlas delta profiles, compiler/obligation/release extensions.
- Migration: `0024`.
- APIs/events: §8.
- Fixtures: `change_priority.md`, `trusted_seed.yaml`, `tests/journey/seed.py`.
- Tests: §12, including the Feature Change journey.
