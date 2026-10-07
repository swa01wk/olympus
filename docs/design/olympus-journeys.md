# Olympus journeys — stages, inputs, outputs and human checkpoints

Reference for the four delivery journeys as the backend runs them at `main` @ `5ccf54f` (2026-10-07). Where a review-loop phase (`olympus-review-loop-plan.md`, RL1–RL4) changes behaviour, the change is marked **RLn**.

## 1. How a journey runs

A **delivery cycle** moves through a state machine (`core/state/machines.py`). Commands move it forward (`POST /delivery-cycles/{id}/commands/{command}` with `expected_state`), only when every guard passes. `GET /delivery-cycles/{id}/next-transitions` lists each allowed command with its guard results.

| Journey | Cycle type | States |
|---|---|---|
| Greenfield | `GREENFIELD_BUILD` | DISCOVERY → PRODUCT_MODEL → ARCHITECTURE → PLANNING → DEVELOPMENT → INTEGRATION → ASSURANCE → RELEASE → COMPLETE |
| Brownfield | `BROWNFIELD_ONBOARDING` | RECON → CODE_INDEX → RECOVERED_SPEC → BASELINE → READINESS ⇄ REMEDIATION → READY |
| Feature change | `FEATURE_CHANGE` | INTAKE → SPEC_DELTA → IMPACT_ANALYSIS → PLANNING → DEVELOPMENT → INTEGRATION → ASSURANCE → RELEASE → COMPLETE |
| Bug fix | `BUG_FIX` | TRIAGE → REPRODUCTION → EXPECTED_BEHAVIOR → ROOT_CAUSE → DEVELOPMENT → INTEGRATION → REGRESSION → ASSURANCE → RELEASE → COMPLETE |

Every stage has the same shape:

1. **Inputs**: versioned refs to specs, artifacts and approvals.
2. **Contract**: a Task with an issued TaskContract (objective, allowed scope, agent profile, required outputs).
3. **Run**: an agent or a deterministic executor.
4. **Output**: an artifact validated against a Pydantic schema.
5. **Guards**: sometimes waiting on a human.
6. **Transition**: its effects schedule the next stage's work.

Greenfield needs an explicit API call to start each agent stage. The other three journeys schedule most agent work through transition effects (`core/state/effects.py`).

| Agent | Profiles | Produces |
|---|---|---|
| Kira | `kira.decompose`, `.change_interpret`, `.implementation_spec` (feature, DELTA, REPAIR modes), `.task_plan`, `.defect_triage`, `.expected_behavior` | Product decomposition, change interpretation, implementation specs, task plans, triage, expected behaviour |
| Atlas | `atlas.propose_architecture`, `.architecture_delta` | Architecture and architecture deltas |
| Forge | `forge.implementation` | Commits inside the task's allowed scope, plus an AC→test mapping |
| Scout | `scout.survey`, `.recover_feature` | Repository survey and recovered feature specs, each claim cited |
| Sentinel | `sentinel.plan`, `.summarize`, `.characterize`, `.reproduce` | Verification plans, characterization checks, reproduction tests |
| Warden | `warden.review`, `.root_cause` | Review findings and root-cause hypotheses |
| Stratos | deterministic | Fast-forward, tag, push |
| Orchestrator | `orchestrator.converse` | Chat replies and command proposals |

The code index understands Python with FastAPI, SQLAlchemy, Pydantic and pytest, and integration runs `compileall` plus `pytest`. Projects must use that stack.

## 2. Greenfield: PRD → release

**Entry.** `POST /projects`, then `POST /projects/{p}/delivery-cycles {type: GREENFIELD_BUILD}`. This declares an empty managed repo, which must be READY with a canonical commit before PLANNING.

**Input.** A product document. Upload it with `POST /projects/{p}/sources?delivery_cycle_id=` as `.md`, `.txt`, `.pdf` or `.docx`, or as JSON `{title, text}`. The adapter extracts the text, stores the raw bytes content-addressed, and records a versioned `ProductSource`. Identical content is deduplicated; changed content becomes the next version.

| Stage | Work | Output | Human gate |
|---|---|---|---|
| Discovery → Product model | `kira.decompose` (`POST /sources/{s}/decompose`) | Capabilities, features, feature specs, requirements, user stories, given/when/then ACs, open questions | Clarifications (blocking ones stop scope approval); `SCOPE` approval |
| Architecture | `atlas.propose_architecture` (`POST …/architecture/propose`) | Stack, components, layers, dependency rules, decisions, contracts | `ARCHITECTURE` approval; entering PLANNING pins `base_sha` |
| Planning | `kira.implementation_spec` per feature, then `kira.task_plan` | Implementation specs (APIs, schemas, required tests per AC, file scope); task DAG | `IMPLEMENTATION_SPEC` approval each; plan acceptance (not enforced until **RL3**) |
| Development | `forge.implementation` per task, own worktree | Candidate commit + `ImplementationResult` | Forge's questions (clarifications pause the execution); `ACTION` approval for merges on R2/R3 tasks |
| Integration | deterministic merge in DAG order + `compileall` + `pytest` | Integration candidate with integrated SHA; conflicts → remediation tasks | — |
| Assurance | Sentinel verifies; Warden reviews | Evidence, findings; gates INTEGRATION, WARDEN, SENTINEL | `FINDING_WAIVER`, or remediate |
| Release | Stratos | Fast-forward, tag `olympus/release/R<n>`, push if a remote exists | `RELEASE` approval, pinned to the manifest hash |

**Output.**

- The default branch at the integrated SHA, tagged.
- A release manifest pinning the specs, architecture, ACs with evidence, gates and commits.
- A delivery outcome.
- Mandatory ACs promoted to active baselines. The project can now take feature changes and bug fixes.

## 3. Brownfield: repository → ready for change

**Entry.**

1. `POST /projects/{p}/repositories {name, provider, remote_url, default_branch?, credential_ref}`. Use `PUT /secrets/{name}` for a private repo's token.
2. Wait for READY.
3. Create a `BROWNFIELD_ONBOARDING` cycle with `repository_id`.

| Stage | Work | Output | Human gate |
|---|---|---|---|
| Code index | deterministic discovery + indexer | Languages, frameworks, entry points; canonical index | — |
| Recovered spec | existing tests run; `scout.survey`, then `scout.recover_feature` per feature | Recovered architecture, capabilities, features, inferences, uncertainties; specs whose every claim cites code or tests, with confidence | — |
| Baseline | `sentinel.characterize` per spec; baseline run at the onboarding commit | Baselines that pin today's behaviour (only GET probes run at onboarding) | Review queue: one decision per item (`POST /delivery-cycles/{c}/promotion-decisions`); each decision creates and decides its own approval |
| Readiness | deterministic scoring | Thresholds: principal coverage 0.8; review completion, baseline coverage and baseline pass 1.0; no blocking uncertainties; architecture approved | — (no approval) |
| Remediation | an approver signs off a remediation spec; Forge closes the gap | Reassessed readiness | Approver sign-off |

**Output.**

- No code change, no release.
- A canonical, cited model with active baselines.
- Project readiness `READY_FOR_CHANGE`.

Baselines resting on accepted known gaps become provisional in **RL3**.

## 4. Feature change: change request → release

**Entry.** `POST /projects/{p}/change-requests {title, description, external_ref?}` or an issue-tracker webhook. The project must be READY_FOR_CHANGE: through brownfield onboarding, or through a released greenfield build with an active baseline set.

| Stage | Work | Output | Human gate |
|---|---|---|---|
| Spec delta | `kira.change_interpret` | Existing feature / new feature / new capability; AC adds, changes and removes; whether architecture is expected to change; a spec delta against the approved spec | `SPEC_DELTA` approval (auto-requested); impact analysis then starts itself |
| Impact analysis | impact engine (structural, lexical, semantic) | Impacted code, tests, baselines, contracts; what to verify | `ARCHITECTURE_DELTA` when one is suggested: decline with a note (works today), or propose with Atlas (works from **RL2**) |
| Planning | `kira.implementation_spec` (DELTA), then `kira.task_plan` | Delta implementation specs, task plan | `IMPLEMENTATION_SPEC` approval; plan acceptance |
| Development → release | as greenfield, plus a BASELINE gate | Release | `FINDING_WAIVER`, `RELEASE` |

**Output.**

- A new release and updated canonical specs.
- New AC baselines; the baselines of changed ACs are superseded.
- The change request becomes `DONE`, and a linked issue is closed.

## 5. Bug fix: defect report → release

**Entry.** `POST /projects/{p}/defects {title, description, external_ref?}`. Triage is scheduled immediately.

| Stage | Work | Output | Human gate |
|---|---|---|---|
| Triage | `kira.defect_triage` | Suspected features, ACs and baselines; severity S1–S4; reproduction plan | — (a human may reject the defect) |
| Reproduction | `sentinel.reproduce`, then a deterministic run at the affected commit | A failing test; up to 3 attempts | `UNREPRODUCED_REPAIR`, only through `/proceed-unreproduced` |
| Expected behaviour | `kira.expected_behavior` | SPECIFIED (cites ACs), UNDERSPECIFIED or CONFLICTING (proposes an AC), or NOT_A_DEFECT (stops) | None today; `EXPECTED_BEHAVIOR` approval from **RL3** |
| Root cause | `warden.root_cause`, impact engine, `kira.implementation_spec` (REPAIR) | Faulty code entities, explanation, fix outline; repair spec of at most 3 files | `IMPLEMENTATION_SPEC` approval, raised at ROOT_CAUSE |
| Regression | deterministic | Reproduction test passes on the fix and fails on the affected commit | — |
| Assurance → release | six gates: INTEGRATION, REPRODUCTION, REGRESSION, WARDEN, SENTINEL, BASELINE | Release with three extra eligibility checks | `FINDING_WAIVER`, `RELEASE` |

**Output.** A release with the fix, a regression baseline, the defect record, and the defect marked `RELEASED`.

A baseline that pins the bug blocks today; from **RL3** it is superseded when the human-approved expected behaviour contradicts it.

## 6. Two entry points, one model

Greenfield reaches the canonical model through decomposition and scope approval. Brownfield reaches it through Scout's cited recovery and item-by-item review. Feature change and bug fix read only from that model.

| Record | From a PRD | From a repo |
|---|---|---|
| Features | Kira reads the PRD | Scout reads routes, models and tests |
| Feature specs | Proposed, approved as one scope | Recovered with citations, promoted item by item |
| ACs | Written from PRD rules | Recovered from tests and code, with confidence |
| Architecture | Atlas proposes, human approves | Scout recovers, human approves as the project architecture |
| Open questions | Clarifications | Uncertainties |
| Code index | First integrated commit | Onboarding commit |
| Baselines | Mandatory ACs promoted at R1 | Characterization at onboarding, activated in review |
| Ready for change when | R1 released with active baselines | Readiness assessment passes |

From **RL2**, the Studio's "Product spec" view renders either kind of project as one PRD-shaped document, each rule showing its source.

## 7. Human in the loop

**Approvals.**

- An approval is pinned to its subject: type, id, version and content hash.
- Only a `HUMAN` actor with `APPROVER` decides it: `POST /approvals/{id}/decision {decision: APPROVED | REJECTED | CHANGES_REQUESTED, note}`.
- Guards accept only an approval whose hash matches the current content, so any edit needs a fresh approval.
- Policy: `config/policy/default.yaml` (`approvals_required`).
- Types actually created today: SCOPE, ARCHITECTURE, ARCHITECTURE_DELTA, IMPLEMENTATION_SPEC (including repair and remediation), SPEC_DELTA, UNREPRODUCED_REPAIR, PROMOTION, FINDING_WAIVER, ACTION, RELEASE.
- **RL3** adds EXPECTED_BEHAVIOR and TASK_PLAN.

**Clarifications.**

- Agents ask; a human answers through `POST /clarifications/{id}/answer`.
- The answer becomes a project decision. It resumes a paused execution or re-runs decomposition ("Prior decisions" in Kira's prompt).

**Review queue.** Brownfield only: one promotion decision per recovered item.

**Human-only commands.** `revise_product_model`, `revise_architecture`, `revise_spec_delta`, `cancel`.

**Chat.**

- `/orchestrator/sessions`: replies are asynchronous (`orchestrator.turn_completed`).
- Intents: EXPLAIN, ANSWER_CLARIFICATION, PROPOSE_COMMAND, NAVIGATE, OUT_OF_SCOPE.
- The chat never decides an approval (`APPROVAL_DECISION_REQUIRES_FORM`).
- From **RL2**:
  - it sees the subject under review (`focus`);
  - it drafts change notes (`REVISION_NOTE_DRAFT`);
  - it proposes generate steps.

**Review loop (from RL2).**

1. Output lands in the workspace with a pending approval.
2. The reviewer discusses it in chat.
3. The reviewer decides:
   - **Request changes** re-runs the producing agent with the note and the previous output. The new version gets its own approval and a diff.
   - **Edit directly** (architecture and implementation specs, **RL3**) creates a new version that needs fresh approval.
   - **Approve** unlocks the next transition.

### Checkpoints by journey

| Journey | Stage | Reviewed | Mechanism |
|---|---|---|---|
| Greenfield | Product model | Open questions; features, specs, ACs | Clarifications; `SCOPE` |
| Greenfield | Architecture | Stack, components, contracts | `ARCHITECTURE` |
| Greenfield, feature change | Planning | Implementation specs; task plan | `IMPLEMENTATION_SPEC`; plan acceptance (`TASK_PLAN` from **RL3**) |
| Greenfield | Development | Forge's questions; merges on R2/R3 tasks | Clarification; `ACTION` |
| All delivery journeys | Assurance | Blocking findings (BLOCKER, MAJOR) | `FINDING_WAIVER`, or remediate |
| All delivery journeys | Release | Manifest and eligibility | `RELEASE` |
| Brownfield | Baseline | Recovered specs, architecture, implementation specs, baselines, uncertainties | Review queue |
| Brownfield | Remediation | Gap-closing spec | Approver sign-off |
| Feature change | Spec delta | Interpretation and diff | `SPEC_DELTA` |
| Feature change | Impact analysis | Architecture flag | `ARCHITECTURE_DELTA` |
| Bug fix | Reproduction | Failed attempts | `UNREPRODUCED_REPAIR` |
| Bug fix | Expected behaviour | Classification, proposed AC, contradicted baselines | `EXPECTED_BEHAVIOR` (**RL3**) |
| Bug fix | Root cause | Hypothesis and repair spec | `IMPLEMENTATION_SPEC` |

## 8. Known limits today

These are fixed in the review-loop phases; see `olympus-review-loop-plan.md` §2 for evidence.

- **Revisions and notes:**
  - Request changes only stores the note (G1, G2).
  - Approval notes don't reach later agents (G8).
- **Chat:**
  - It can't see the content under review (G3, G4).
  - It can't propose generate steps (G13).
- **Gates:**
  - Task plan acceptance isn't enforced (G6).
  - Underspecified bugs are resolved without a human (G7).
- **Baselines:**
  - A bug fix can't retire a baseline that pins the bug (G9).
  - Onboarding can pin behaviour that was only accepted as a known gap (G10).
- **Architecture deltas:** a proposed delta can never be approved (G11).
- **Product spec:** there's no shared product-spec view, and the API hides provenance (G12).
- **Studio:**
  - It can't register repositories (S1).
  - It can't decide review-queue items (S2).
  - It can't act on findings, architecture deltas or defects (S3).
  - It misses the repair-spec and architecture-delta Decision panels (S4).
- **Journey tests:** live runs use fallbacks that fill in for stalled agents (RL4).
