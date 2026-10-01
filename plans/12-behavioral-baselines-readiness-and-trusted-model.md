# Phase 12 — Behavioral Baselines, Human Promotion, Readiness, Remediation and READY_FOR_CHANGE

## 1. Objective

Complete **Journey 2 — Brownfield Onboarding** (ARCH §16, §16.1, §21.3; TECH §20 steps 5–7). This phase adds:

- executable **BehavioralBaselines** (from existing tests, Sentinel-authored characterization checks and safe runtime API probes), executed deterministically against the exact repository SHA;
- explicit human **promotion decisions**: a RecoveredSpec becomes a CanonicalSpec, DISCOVERED links become HUMAN_CONFIRMED, and the recovered architecture becomes the approved project architecture;
- resolution of **UNCERTAINTIES**;
- a deterministic **ReadinessAssessment**, with a **REMEDIATION** loop when remediable;
- a versioned **BaselineSet** (B1) and `Project.readiness_state = READY_FOR_CHANGE`.

It also makes baselines a first-class release condition and obligation source for later journeys, and promotes Greenfield release ACs to baselines.

## 2. Architectural Context

- **Position:** Intelligence plane (baselines, trusted model) and Governance (promotion approvals, readiness). BROWNFIELD RECOVERED_SPEC → BASELINE → READINESS ⇄ REMEDIATION → READY.
- **Upstream:** 11 (recovered model, observed behaviors), 09 (Sentinel execute, evidence, obligations), 10 (release mechanism for remediation publication; eligibility registry), 06 (REMEDIATION ImplementationSpec path).
- **Downstream:** 13 (impacted baseline selection), 14/15 (baseline revalidation in R2/R3), 19.
- **Invariants:**
  - 29–30: Observed ≠ Recovered ≠ Canonical; recovered intent never silently canonical.
  - 35: impacted baselines must be revalidated (mechanism here; selection in 13).
  - 25: approvals explicit.
  - Mandatory evidence for baselines.
  - Deterministic readiness.

## 3. Current Repository Assessment

Inspection on 2026-10-01: none of this exists.

### Existing
- (after 11) PROPOSED recovered entities, DISCOVERED links, UNCERTAINTY items and the reconciliation report — **RETAIN**.
- (after 09) `sentinel.execute`, obligations registry, evidence — **EXTEND** (BASELINE subject, IC-less evidence at a repository SHA).
- (after 10) eligibility condition stub `required_behavioral_baselines_pass` — **REPLACE**.

### Partial
- Guards `baseline_review_complete`, `readiness_failed_remediable`, `remediation_integrated_and_reindexed` and `readiness_assessment_ready` are placeholders — **REPLACE**.

### Missing
- Baselines, baseline sets, promotion decisions, readiness, Sentinel characterization and remediation orchestration — **ADD**.

### Refactor / Migration Required
- `evidence.integration_candidate_id` is already nullable. Add a CHECK: `integration_candidate_id IS NOT NULL OR subject_type IN ('BASELINE','DEFECT')` (baseline/reproduction at a repository SHA).

## 4. Scope

1. Tables: `behavioral_baselines`, `baseline_sets`, `baseline_set_items`, `promotion_decisions`, `readiness_assessments`. Add `projects.active_baseline_set_id`.
2. **Baseline proposals** (BASELINE stage, SYSTEM):
   1. *Existing tests:* each passing test whose TEST_ASSERTED behaviors support a recovered AC with confidence ≥ MEDIUM → baseline proposal (`check_kind=EXISTING_TEST`, `check_ref=<node id>`).
   2. *Characterization:* for recovered ACs with confidence ≥ MEDIUM not covered by (a), `sentinel.characterize` (live) authors characterization checks (pytest overlay or API probe) capturing *current* behavior. These are validated (Phase 09 plan validator rules + assertion minimums).
   3. *Runtime probes where safe* (ARCH §16 table): for GET routes and idempotent POST routes against a temp DB, a probe recording `{status, response shape}`. Policy `brownfield.runtime_probes: safe_only` excludes DELETE/PATCH/PUT unless the route is covered by tests.
   Each proposal is a `BehavioralBaseline` PROPOSED, linked to its recovered spec/AC, its observed behaviors and the code stable keys it exercises (from VERIFIED_BY relations / probe route).
3. **Baseline execution** (deterministic `sentinel.execute` reuse, VERIFICATION task, READONLY ExecutionWorkspace) at `cycle.base_sha` (or the remediation IC SHA). Either way, this is `Repository.canonical_commit` at execution time. Evidence has `subject_type=BASELINE` and `commit_sha` set. A baseline whose check FAILS at the base SHA cannot be activated; it creates an UNCERTAINTY ("existing behavior fails its own characterization").
4. **Review and promotion** (human; `PromotionService`). The review queue holds one item per recovered spec, recovered architecture, recovered ImplementationSpec, baseline and blocking uncertainty. Decisions:
   - Recovered FeatureSpec:
     - `PROMOTE_AS_CANONICAL` → new FeatureSpec row (`spec_kind=CANONICAL`, version 1 for new lineage or N+1 for a MATCHED existing lineage, `promoted_from_id`, APPROVED via Approval(PROMOTION)), plus children copied with `change_kind`; the recovered row stays PROPOSED → `PROMOTED` (immutable historical record);
     - `CONFIRM_EXISTING` (reconciliation MATCHED) → no new spec; record the decision; the recovered row → `CONFIRMED_EXISTING`;
     - `REJECT_AS_NOT_INTENDED` (for example, observed behavior is a defect) → recovered row REJECTED; optionally create a Defect intake suggestion (Phase 15 entity; stored as a KnowledgeItem DECISION with `suggested_defect=true` until 15);
     - `DEFER` → stays as an UNCERTAINTY (counts against readiness).
   - DISCOVERED SpecCodeLinks of a promoted spec → new link rows `origin=HUMAN_CONFIRMED`, `promoted_from_link_id`, confidence retained, `evidence_refs` including the discovery link. The DISCOVERED row is kept (`status=SUPERSEDED`), so discovery evidence is never discarded (TECH §14.1).
   - Recovered Architecture → `APPROVE_AS_PROJECT_ARCHITECTURE` (Approval(ARCHITECTURE)) → Architecture APPROVED (`kind=RECOVERED`). Required for later ImplementationSpec deltas.
   - Recovered ImplementationSpec → APPROVED (`kind=RECOVERED`) bound to the promoted canonical FeatureSpec version.
   - Baseline → `ACTIVATE` (HUMAN) or **auto-activate** when policy `baselines.auto_activate_on_pass=true` **and** its check PASSES at the base SHA **and** it is linked to a promoted or confirmed spec. This is the "strong deterministic evidence" path (ARCH §14.6). Baselines tied only to non-promoted recovered specs require HUMAN activation.
   - Uncertainty → `RESOLVE` (answer → DECISION KnowledgeItem) | `ACCEPT_KNOWN_GAP` (non-blocking thereafter, Approval(PROMOTION)).
5. **ReadinessAssessment** (deterministic, `ReadinessService.assess(cycle)`). Each metric is persisted with its threshold from policy `readiness:`:
   - `principal_coverage` = covered/total over ROUTE + ORM_MODEL entities with ≥1 ACTIVE HUMAN_CONFIRMED or GENERATED_LINEAGE link (default ≥ 0.8);
   - `review_completion` = decided/total review items (= 1.0);
   - `baseline_coverage` = promoted/confirmed features with ≥1 ACTIVE baseline (= 1.0);
   - `baseline_pass` = all ACTIVE baselines PASS at the assessed SHA;
   - `blocking_uncertainties_open` = 0;
   - `failing_existing_tests_unclassified` = 0;
   - `architecture_approved` = true.
   The result is READY or NOT_READY with reasons, and `remediable` = every failing metric is in {`baseline_coverage`, `principal_coverage`, `failing_existing_tests_unclassified` with a decision to remediate}.
6. **Remediation loop**:
   1. READINESS → REMEDIATION → create an ImplementationSpec(`kind=REMEDIATION`) draft per gap (deterministic template: "add characterization tests for X" / "fix failing test Y" when decided) → Approval(IMPLEMENTATION_SPEC).
   2. A Kira TaskPlan (live, reusing `kira.task_plan`) creates REMEDIATION tasks → Forge → IC → canonical index at the IC SHA → baselines re-executed.
   3. **Publication:** the remediation IC is published through the standard Release mechanism (`cycle.type=BROWNFIELD_ONBOARDING`; required gates INTEGRATION, SENTINEL, BASELINE; Approval(RELEASE)). The repository's default branch and `released_commit` therefore reflect the trusted baseline, and the canonical revision history shows `INTEGRATION_READY` → `RELEASED` for the remediation IC. Then REMEDIATION → READINESS (reassess).
7. **BaselineSet and READY**: `declare_ready` (guard `readiness_assessment_ready`, which also requires `assessment.commit_sha == Repository.canonical_commit`) creates a BaselineSet B<n> (all ACTIVE baselines, SHA = the canonical commit, hash) and sets `project.active_baseline_set_id`, `Project.readiness_state = READY_FOR_CHANGE` and the DeliveryOutcome `result=READY_FOR_CHANGE`, all in one transaction.
8. **Baseline obligations for later cycles**: register the obligation source `BASELINE_REQUIRED`. For FEATURE_CHANGE / BUG_FIX / REMEDIATION cycles, by default select **all** ACTIVE baselines of the active BaselineSet, `gate_type=BASELINE` (Phase 13 narrows to impacted-plus-policy). Obligations record reason and source refs.
9. **Release condition**: replace the stub `required_behavioral_baselines_pass` with: all BASELINE obligations for the IC are SATISFIED. Add a `BASELINE` gate to policy `required_gates` for FEATURE_CHANGE, BUG_FIX and BROWNFIELD (remediation).
10. **Greenfield release promotion**: policy `release.promote_acs_to_baselines=true`. On RELEASED, mandatory ACs with PASS executable evidence become ACTIVE baselines (`source=RELEASE_PROMOTION`, check = the evidence's check ref), and a new BaselineSet version is created. This gives Greenfield-only projects baselines for R2.
11. Guards: `baseline_review_complete` (all baseline proposals and recovered items decided, or DEFERRED as uncertainty), `readiness_failed_remediable`, `remediation_integrated_and_reindexed` (remediation IC RELEASED and canonical/released pointer at its SHA) and `readiness_assessment_ready`.

## 5. Out of Scope

- Impact-based baseline selection (13).
- Defect entity creation from rejected recovered behavior (15; a suggestion KnowledgeItem only).
- UI review screens (17; this phase is API-only).

### Do Not Change
- Never auto-promote a RecoveredSpec to CANONICAL (policy key `promotion.recovered_spec_requires_human` is fixed `true`; changing it requires a drift entry).
- A baseline that fails at its base SHA cannot be ACTIVE.

## 6. Domain / Data Model Changes

Migration `0022_p12_baselines_promotion_readiness.py` (TECH 009 completion).

```python
class BaselineStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    FAILED_AT_BASE = "FAILED_AT_BASE"
    SUPERSEDED = "SUPERSEDED"
    RETIRED = "RETIRED"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"


class BehavioralBaseline(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "behavioral_baselines"
    project_id: Mapped[uuid.UUID]
    lineage_key: Mapped[str]
    version: Mapped[int]  # BASELINE-001:v1
    status: Mapped[BaselineStatus]
    source: Mapped[
        str
    ]  # BROWNFIELD_EXISTING_TEST | BROWNFIELD_CHARACTERIZATION | BROWNFIELD_RUNTIME_PROBE | RELEASE_PROMOTION | CHANGE | REPAIR
    given: Mapped[str]
    when: Mapped[str]
    then: Mapped[str]  # ARCH §16.1
    check_kind: Mapped[str]  # EXISTING_TEST | AUTHORED_TEST | API_PROBE
    check_ref: Mapped[str]
    check_artifact_id: Mapped[uuid.UUID | None]
    feature_spec_id: Mapped[uuid.UUID | None]
    ac_lineage_key: Mapped[str | None]
    observed_behavior_ids: Mapped[list] = mapped_column(JSONB)
    exercised_stable_keys: Mapped[list] = mapped_column(JSONB)  # for impact traversal (13)
    established_sha: Mapped[str]
    established_evidence_id: Mapped[uuid.UUID | None]
    activation: Mapped[str | None]  # HUMAN | AUTO_DETERMINISTIC
    __table_args__ = (UniqueConstraint("project_id", "lineage_key", "version"),)


class BaselineSet(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "baseline_sets"
    project_id: Mapped[uuid.UUID]
    key: Mapped[str]  # B1, B2...
    commit_sha: Mapped[str]
    content_hash: Mapped[str]
    delivery_cycle_id: Mapped[uuid.UUID]  # immutable


class PromotionDecision(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "promotion_decisions"
    delivery_cycle_id: Mapped[uuid.UUID]
    subject_type: Mapped[str]
    subject_id: Mapped[uuid.UUID]
    decision: Mapped[
        str
    ]  # PROMOTE_AS_CANONICAL | CONFIRM_EXISTING | REJECT_AS_NOT_INTENDED | DEFER | APPROVE_AS_PROJECT_ARCHITECTURE | ACTIVATE | RESOLVE | ACCEPT_KNOWN_GAP
    approval_id: Mapped[uuid.UUID | None]
    decided_by_actor_id: Mapped[uuid.UUID]
    note: Mapped[str | None]
    result_refs: Mapped[list] = mapped_column(
        JSONB
    )  # created canonical spec / links / baseline ids


class ReadinessAssessment(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "readiness_assessments"
    delivery_cycle_id: Mapped[uuid.UUID]
    commit_sha: Mapped[str]
    index_version_id: Mapped[uuid.UUID]  # commit_sha = Repository.canonical_commit at assessment
    canonical_revision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repository_revisions.id"))
    metrics: Mapped[list] = mapped_column(JSONB)  # [{name, value, threshold, ok}]
    result: Mapped[str]
    remediable: Mapped[bool]
    reasons: Mapped[list] = mapped_column(JSONB)
    policy_version_id: Mapped[uuid.UUID]  # immutable
```

Other changes:
- `baseline_set_items`: baseline_set_id, baseline_id.
- `feature_specs.status` gains the terminal values `PROMOTED` and `CONFIRMED_EXISTING` for RECOVERED rows only (CHECK).
- `spec_code_links.status` gains `SUPERSEDED`.

`sentinel.characterize` output:

```python
class CharacterizationCheck(BaseModel):
    recovered_ac_key: str
    given: str
    when: str
    then: str
    kind: Literal["AUTHORED_TEST", "API_PROBE"]
    test_code: str | None
    test_filename: str | None
    probe: ApiProbe | None
    exercised_entities: list[str]
    rationale: str


class CharacterizationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checks: list[CharacterizationCheck]
    skipped: list[dict]  # {recovered_ac_key, reason}
```

## 7. State / Lifecycle Changes

BROWNFIELD:

| Edge | Guard | Side effects |
|---|---|---|
| RECOVERED_SPEC → BASELINE (`start_baseline`) | `recovery_proposal_persisted` | baseline proposals (existing tests, characterization (live), probes) → baseline execution |
| BASELINE → READINESS (`start_readiness`) | `baseline_review_complete` | readiness assessment |
| READINESS → REMEDIATION (`start_remediation`) | `readiness_failed_remediable` | REMEDIATION ImplementationSpec drafts |
| REMEDIATION → READINESS (`reassess_readiness`) | `remediation_integrated_and_reindexed` | baselines re-executed at new SHA; reassess |
| READINESS → READY (`declare_ready`) | `readiness_assessment_ready` | BaselineSet; Project READY_FOR_CHANGE; DeliveryOutcome |

Rules:
- A non-remediable NOT_READY (for example, blocking uncertainties that need human answers) stays in READINESS until resolved and reassessed.
- Baseline machine: PROPOSED → ACTIVE (activation) | REJECTED | FAILED_AT_BASE. ACTIVE → REVALIDATION_REQUIRED (Phase 13, impacted code changed) → ACTIVE (passes at new SHA) | SUPERSEDED (new version via spec delta) | RETIRED (spec removal approved).
- Promotion: each decision is a HUMAN command. Decisions requiring Approval (PROMOTE_AS_CANONICAL, APPROVE_AS_PROJECT_ARCHITECTURE, ACCEPT_KNOWN_GAP) create and decide the Approval in the same command when the actor is an APPROVER.

## 8. API / Contract Changes

| Method | Path | Notes |
|---|---|---|
| GET | `/delivery-cycles/{id}/review-queue` | items with evidence, confidence, citations, reconciliation status |
| POST | `/delivery-cycles/{id}/promotion-decisions` | `{subject_type, subject_id, decision, note}` HUMAN APPROVER |
| GET | `/projects/{id}/baselines`, `/baselines/{id}` | with latest evidence |
| POST | `/baselines/{id}/activate` | HUMAN |
| GET | `/projects/{id}/baseline-sets`, `/baseline-sets/{id}` | |
| GET | `/delivery-cycles/{id}/readiness` | latest assessment; `?recompute=true` |
| GET | `/projects/{id}` | EXTEND: `readiness_state`, `active_baseline_set` |

Events: `baseline.proposed`, `baseline.executed`, `baseline.activated`, `baseline.failed_at_base`, `promotion.decided`, `feature_spec.promoted`, `spec_code_link.confirmed`, `readiness.assessed`, `baseline_set.created`, `project.ready_for_change`.

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `core/intelligence/baselines/{service,proposals,execution,sets}.py` | baseline lifecycle |
| `core/intelligence/baselines/probes.py` | safe runtime probe generation (deterministic templates for GET routes) |
| `core/intelligence/recovered_specs/promotion.py` | `PromotionService` |
| `core/intelligence/baselines/readiness.py` | `ReadinessService` (pure metrics + persistence) |
| `core/intelligence/baselines/remediation.py` | REMEDIATION ImplementationSpec drafting + orchestration |
| `core/intelligence/baselines/guards.py` | guards |
| `core/assurance/obligations.py` | EXTEND: `BASELINE_REQUIRED` source |
| `core/release/eligibility.py` | EXTEND: real baseline condition; required gates |
| `core/release/service.py` | EXTEND: release promotion of ACs to baselines |
| `agents/sentinel/prompts/characterize.md`, `schemas.py` | `sentinel.characterize` |
| `apps/control_api/routers/{baselines,promotion,readiness}.py` | REST |
| `tests/journey/test_brownfield_supportdesk.py` | journey |

## 10. Development Tasks

- [ ] 12.1 Add migration `0022`, the models and the CHECK constraints.
- [ ] 12.2 Implement baseline proposals from existing tests.
- [ ] 12.3 Implement the `sentinel.characterize` profile, schema and prompt v1, plus validation.
- [ ] 12.4 Implement safe runtime probe generation and policy gating.
- [ ] 12.5 Implement baseline execution at the repository SHA via `sentinel.execute` (evidence with `subject_type=BASELINE`), plus FAILED_AT_BASE handling.
- [ ] 12.6 Implement `PromotionService` with all decisions, approval wiring, canonical spec creation, link confirmation and architecture/ImplementationSpec approval.
- [ ] 12.7 Implement baseline activation (HUMAN + auto-deterministic per policy).
- [ ] 12.8 Implement the `ReadinessService` metrics and assessment persistence.
- [ ] 12.9 Implement remediation drafting, TaskPlan reuse, release publication and reassess.
- [ ] 12.10 Implement BaselineSet creation and the `declare_ready` side effects.
- [ ] 12.11 Register the `BASELINE_REQUIRED` obligation source and the `BASELINE` gate in policy. Replace the eligibility stub.
- [ ] 12.12 Implement release-time AC → baseline promotion for Greenfield.
- [ ] 12.13 Replace the four guard placeholders.
- [ ] 12.14 Add the REST routes and events.
- [ ] 12.15 Write the tests in §12, including the Brownfield journey.

## 11. LLM-Dependent Tasks

| Profile | Why | Inputs | Output | Alias | Validation | Live test |
|---|---|---|---|---|---|---|
| `sentinel.characterize` | Designing characterization checks for recovered behavior without existing tests | recovered ACs (≥ MEDIUM), observed behaviors, routes/schemas (index), code excerpts | `CharacterizationPlan` | `verification_planning` | routes/entities exist; assertion minimum; checks must PASS at base SHA to become activatable | `test_sentinel_characterize_live.py` |
| `kira.task_plan` (reuse) | Remediation work planning | REMEDIATION ImplementationSpecs | `TaskPlan` | `planning` | Phase 06 validator | workflow (remediation fixture) |
| `forge` (reuse) | Remediation code | compiled contracts | `ImplementationResult` | `implementation` | Phase 04/06 | workflow |

Promotion, readiness, activation rules and baseline execution are deterministic.

## 12. Testing Strategy

### Unit Tests
- Readiness metric functions and thresholds. Remediable classification.
- The promotion decision matrix (allowed decisions per subject type).
- Safe-probe policy filter.

### Persistence Tests
- A promoted canonical spec has `promoted_from_id`. The recovered row becomes PROMOTED (immutable). DISCOVERED links are retained as SUPERSEDED, and HUMAN_CONFIRMED links reference them.
- `declare_ready` atomicity (BaselineSet + project readiness + outcome).

### Integration Tests (deterministic, using a recovered-model fixture built by services from `supportdesk_r1`)
- An attempt to promote without the APPROVER role returns 403. A REJECT decision leaves no canonical spec.
- Auto-activation happens only when the check PASSES at the base SHA **and** the spec is promoted or confirmed.
- A baseline failing at the base SHA becomes FAILED_AT_BASE and produces an UNCERTAINTY.
- Readiness is NOT_READY with a blocking uncertainty, then READY after RESOLVE.
- Release promotion: a fixture Greenfield release creates ACTIVE baselines and BaselineSet B1.

### Runtime / Live-LLM Tests
- `sentinel.characterize` live on `supportdesk_r1` (escalate route excluded by policy or deferred).

### Workflow Tests (live)
- Remediation: `supportdesk_r1_low_tests` variant (tests removed for one feature) → NOT_READY (`baseline_coverage`) → REMEDIATION → live Kira/Forge add characterization tests → IC → gates → release publication → reassess → READY.

### E2E / Journey Tests (`journey`, live)
`test_brownfield_supportdesk.py`:
1. **Fresh project** `SUPPORTDESK-BF`, register `supportdesk_r1` (no prior product model). New processes, with the runtime checkpoint schema truncated before start.
2. RECON → CODE_INDEX → RECOVERED_SPEC (live Scout) → BASELINE (proposals; live characterization; execution).
3. Scripted human review from `tests/fixtures/supportdesk/brownfield_review.yaml`. Rules are expressed against deterministic properties, not model wording. For example:
   - promote recovered specs whose principal entities include a route with tests;
   - DEFER or `ACCEPT_KNOWN_GAP` for uncertainties on `/escalate`;
   - approve the recovered architecture.
4. READINESS → READY. Assertions:
   - `Project.readiness_state == READY_FOR_CHANGE`;
   - BaselineSet B1 exists with ≥ N ACTIVE baselines, all PASS at `registered_sha`;
   - every ACTIVE HUMAN_CONFIRMED link references a DISCOVERED link with evidence;
   - FACT/INFERENCE/UNCERTAINTY are distinguishable via the API;
   - no CANONICAL spec exists without a PROMOTION approval;
   - `assert_live_llm_proof(cycle, [scout_survey, scout_recover_feature, sentinel_characterize])`;
   - the context manifest proves isolation.
5. Restart workers/API → readiness, baselines and lineage are unchanged.

### Commands
```
make check
LLM_LIVE_TESTS=1 uv run pytest -m "workflow or journey" --live-required tests/workflow/brownfield tests/journey/test_brownfield_supportdesk.py -s
```

## 13. Milestone

**Journey 2 complete.** From a fresh Olympus context and an existing repository, Olympus establishes executable Behavioral Baselines that pass at the exact repository SHA. Through explicit human promotion decisions, it converts provenance-backed RecoveredSpecs into CanonicalSpecs and HUMAN_CONFIRMED lineage without discarding discovery evidence, resolves or accepts uncertainties, computes deterministic readiness (remediating where needed) and transitions the project to **READY_FOR_CHANGE** with BaselineSet B1.

## 14. Acceptance Criteria

- [ ] Every ACTIVE baseline has executable evidence PASS at its `established_sha`.
- [ ] A RecoveredSpec becomes CANONICAL only through an explicit HUMAN Approval(PROMOTION). No auto-promotion path exists.
- [ ] HUMAN_CONFIRMED links retain references to their DISCOVERED origin and evidence.
- [ ] Recovered behavior rejected as "not intended" never becomes canonical.
- [ ] Readiness is a deterministic, persisted assessment with metric thresholds from policy.
- [ ] NOT_READY with remediable gaps drives REMEDIATION through the standard Task, Contract, Forge, IC, gates and release path.
- [ ] `declare_ready` atomically creates a BaselineSet and sets `READY_FOR_CHANGE`.
- [ ] The Brownfield journey test passes live from a fresh context (no Greenfield conversation or runtime history).
- [ ] BASELINE obligations and the baseline release condition are active for FEATURE_CHANGE/BUG_FIX cycles.
- [ ] Greenfield releases promote passing mandatory ACs to baselines (policy-controlled).
- [ ] READY_FOR_CHANGE is declared only while `Repository.canonical_commit` equals the SHA at which the ReadinessAssessment and the ACTIVE baselines were evaluated. A canonical revision change in between (remediation IC, external sync) forces reassessment.

## 15. Exit Criteria

- §14 green, with the journey run recorded in `STATUS.md`.
- Journey Readiness → Brownfield = COMPLETE (pending Phase 19 re-run).
- No BROWNFIELD guard placeholders remain.
- `STATUS.md`: invariant "Brownfield inference cannot silently become canonical intent" checked; Behavioral Baselines tracker updated.

## 16. Dependencies

### Depends On
- 11.
- 09/10 (reused; already complete before 11).

### Blocks
- 13.

### Can Run In Parallel With
- None.

## 17. Risks / Implementation Notes

- **Characterization bias:** characterization captures *current* behavior, which may include defects. That is exactly why canonical promotion is human-gated and baselines link to decisions.
- **Remediation publication** uses the Release mechanism and consumes a release key (Q-08). The chained demo is designed so that no remediation is needed.
- **Runtime probe safety:** run against a temp DB in the verification workspace only, never against external services.
- **Deferred:** impact-based selection (13) and UI review (17).

## 18. Deliverables

- Code: `core/intelligence/baselines/*`, `core/intelligence/recovered_specs/promotion.py`, the `sentinel.characterize` profile, eligibility/obligation extensions.
- Migration: `0022`.
- APIs/events: §8.
- Fixtures: `brownfield_review.yaml`, `supportdesk_r1_low_tests`.
- Tests: §12, including the Brownfield journey.
