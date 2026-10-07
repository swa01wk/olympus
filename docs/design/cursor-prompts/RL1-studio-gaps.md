# RL1 — Close the Studio gaps (frontend only)

Paste everything below the line into a new Cursor Composer chat (Agent mode). Work on a branch `rl1-studio-gaps`.

---

You are extending **Olympus Studio**, the chat + workspace operator UI in `apps/dashboard` (Next.js, TanStack Query). The Studio already drives a greenfield cycle end to end. Your job in this phase: make every journey drivable from the Studio, so a human never has to call the API by hand. **No backend changes in this phase.**

## Read first

1. `docs/design/olympus-review-loop-plan.md` — this phase fixes findings **S1–S5** and **D1** in §2.
2. `docs/design/olympus-chat-workspace-plan.md` — the Studio's layout and rules.
3. `apps/dashboard/AGENTS.md` — this Next.js version differs from your training data; read the guide it points to before writing code.
4. The routers named in each step, for exact request and response shapes.

## Rules

- **Do not edit** anything under `core/`, `apps/control_api/`, `apps/*_worker/`, `agents/` or `migrations/`. Every endpoint this phase needs already exists. Never invent an endpoint, field or enum value; read the router and its Pydantic model.
- **The UI never decides whether a step is allowed.** Advance buttons render `GET /delivery-cycles/{id}/next-transitions`. Don't re-implement guards.
- **Approvals are decided only in the Decision panel**, only by an actor with the `APPROVER` role (`useActorMe`). Actions the backend restricts to approvers are shown read-only to others, with the message "You need the APPROVER role to do this."
- **Every mutation shows its exact API call before it is sent** (reuse `lib/command-preview.ts`, `components/studio/workspace/StudioMutationAction.tsx`) and sends a fresh `Idempotency-Key` (`src/api/client.ts` does this).
- Reuse what exists: `src/api/resources.ts`, `src/api/commands.ts`, `src/api/query-keys.ts`, `src/api/hooks/use-journey-queries.ts`, `src/api/hooks/use-studio-mutations.ts`, `components/primitives/*`, `components/studio/*`. No new dependencies.
- Secrets: a credential value is sent once to `PUT /secrets/{name}` and never stored in state, storage, query cache or logs. Use a password input.

## How to work

1. Restate the step's goal and list the files you'll change. Then implement.
2. Add or update unit tests in `apps/dashboard/tests/unit` (mock `fetch`, assert method, path, query, body).
3. Run `npm run check` in `apps/dashboard` until green.
4. Stop after each step with: what changed, test results, anything left over. Wait for `next`.

---

## RL1.1 — Approval → stage mapping per cycle type (S4)

Problem: `apps/dashboard/lib/studio-spine.ts` maps `IMPLEMENTATION_SPEC` → `PLANNING` and `ARCHITECTURE_DELTA` → `ARCHITECTURE` for every cycle type. A bug fix raises its repair-spec approval (type `IMPLEMENTATION_SPEC`) at `ROOT_CAUSE`; a feature change raises `ARCHITECTURE_DELTA` at `IMPACT_ANALYSIS`. Neither stage gets a Decision panel today.

- Replace the flat `APPROVAL_TYPE_TO_STAGE` record with `approvalStage(approvalType, cycleType): string | null`:
  - `IMPLEMENTATION_SPEC` → `PLANNING` (GREENFIELD_BUILD, FEATURE_CHANGE, REMEDIATION), `ROOT_CAUSE` (BUG_FIX), `REMEDIATION` (BROWNFIELD_ONBOARDING).
  - `ARCHITECTURE_DELTA` → `IMPACT_ANALYSIS` (FEATURE_CHANGE).
  - `ARCHITECTURE` → `ARCHITECTURE` (GREENFIELD_BUILD), `BASELINE` (BROWNFIELD_ONBOARDING).
  - `PROMOTION` → `BASELINE`; `SPEC_DELTA` → `SPEC_DELTA`; `UNREPRODUCED_REPAIR` → `REPRODUCTION`; `FINDING_WAIVER` → `ASSURANCE`; `ACTION` → `DEVELOPMENT`; `RELEASE` → `RELEASE`; `SCOPE` → `PRODUCT_MODEL`.
  - `EXPECTED_BEHAVIOR` → `EXPECTED_BEHAVIOR` (BUG_FIX). Keep it: RL3 starts creating it.
  - Remove `REPAIR_SPEC`, `READINESS`, `SPEC_DECISION`, `DEPLOYMENT`; the backend never creates them (plan G5). Add a one-line comment saying so.
- Update `findPendingApprovalForStage`, `StageSpine`, `DecisionPanel` and every other caller to pass the cycle type.

Acceptance: unit tests for every (approval type, cycle type) pair above; a component test shows the Decision panel at `ROOT_CAUSE` for a BUG_FIX cycle with a pending `IMPLEMENTATION_SPEC` approval, and at `IMPACT_ANALYSIS` for a FEATURE_CHANGE cycle with a pending `ARCHITECTURE_DELTA` approval.

## RL1.2 — Repository registration and brownfield intake (S1)

Backend: `apps/control_api/routers/repositories.py`, `apps/control_api/routers/secrets.py`, `core/domain/enums.py` (`RepositoryProvider`, `RepositoryStatus`).

- `src/api/commands.ts`: `registerRepository(projectId, {name, provider, remote_url, default_branch?, credential_ref?})` → `POST /projects/{p}/repositories` (`source_type` defaults to `EXTERNAL_CLONE`; `credential_ref` defaults to `"none:"`); `putSecret(name, value)` → `PUT /secrets/{name}` `{value}` → returns `credential_ref`; `retryMaterialization(repositoryId)` → `POST /repositories/{id}/commands/retry_materialization`.
- `src/api/resources.ts`: `listProjectRepositories(projectId)` → `GET /projects/{p}/repositories`; `getRepository(id)`; `listMaterializations(id)` → `GET /repositories/{id}/materializations`.
- Brownfield intake in the Studio control panel ("New" → Brownfield onboarding) and `components/dialogs/IntakeFormDialog.tsx`:
  1. Pick an existing repository of the project, or register one: name, provider (`GITHUB`, `GITEA`, `GITLAB`, `BITBUCKET`, `LOCAL`), remote URL, default branch, and an optional access token (sent through `putSecret` with name `repo-<project-key>-<name>`; the returned `credential_ref` goes into the registration).
  2. Show materialization status until `READY` (poll `getRepository` every 3 s, and refresh on `repository.materialized` events). On failure show `status_reason`, the last materialization attempt's `error_class` / `error_detail`, and a Retry action.
  3. When `READY`, create the cycle: `POST /projects/{p}/delivery-cycles {type: "BROWNFIELD_ONBOARDING", objective, repository_id}` and open its Studio.
- The `RECON` stage view (`BrownfieldReconStage.tsx`) shows the repository card (provider, URL, default branch, canonical commit, status).

Acceptance: unit tests for the four new client functions; a component test walks register → materializing → READY → create cycle, and asserts the token never appears in the query cache.

## RL1.3 — Review-queue decisions (S2)

Backend: `apps/control_api/routers/promotion.py` (`PromotionDecisionRequest {subject_type, subject_id, decision, note?}`), `core/intelligence/recovered_specs/promotion.py` (`PromotionService.decide` and its per-subject branches), `core/intelligence/baselines/enums.py` (`PromotionDecisionType`).

- `src/api/commands.ts`: `recordPromotionDecision(cycleId, body)` → `POST /delivery-cycles/{c}/promotion-decisions`.
- `BrownfieldBaselineStage.tsx`: each review-queue item gets a decision control. Offer **only** the decisions `PromotionService.decide` accepts for that `subject_type`; derive the list by reading its branches, and keep it in one exported constant with a test. Expected shape (verify against the code before using):
  - `FEATURE_SPEC`: PROMOTE_AS_CANONICAL, CONFIRM_EXISTING, REJECT_AS_NOT_INTENDED, DEFER
  - `ARCHITECTURE`: APPROVE_AS_PROJECT_ARCHITECTURE, DEFER
  - `IMPLEMENTATION_SPEC`: PROMOTE_AS_CANONICAL, REJECT_AS_NOT_INTENDED, DEFER
  - `BASELINE`: ACTIVATE, REJECT_AS_NOT_INTENDED, DEFER
  - `UNCERTAINTY`: RESOLVE, ACCEPT_KNOWN_GAP, DEFER
- Decisions that require `APPROVER` in `promotion.py` (for example PROMOTE_AS_CANONICAL, APPROVE_AS_PROJECT_ARCHITECTURE, ACCEPT_KNOWN_GAP) are read-only for other actors.
- A note is required for REJECT_AS_NOT_INTENDED, DEFER and ACCEPT_KNOWN_GAP.
- Show each item's `detail`: citations and confidence for recovered specs and uncertainties, evidence for baselines. A filter: undecided / all.
- After a decision: invalidate the review queue, `next-transitions` and the inbox.

Acceptance: a test per subject type asserts the offered decisions; posting a decision sends the exact body; a non-approver sees approver-only decisions disabled with the role message.

## RL1.4 — Finding actions (S3)

Backend: `apps/control_api/routers/findings.py` (`GET /delivery-cycles/{c}/findings`), `apps/control_api/routers/assurance.py` (`POST /findings/{f}/waive` → `{approval_id}`, `POST /findings/{f}/remediate` → `{task_id}`), `config/policy/default.yaml` (`findings.blocking_severities`, `findings.blocking_categories`).

- `listFindings(cycleId)`, `waiveFinding(findingId)`, `remediateFinding(findingId)`.
- `IntegrationAssuranceStage.tsx`: a findings list (severity, category, title, file and line, status) with blocking ones marked in words, not colour only. Actions per open finding: **Waive** (raises a `FINDING_WAIVER` approval that then shows in the Decision panel at ASSURANCE) and **Remediate** (creates a remediation task; the Next step bar then offers `return_to_development`).

Acceptance: client tests; a component test shows Waive and Remediate on an open BLOCKER finding and neither on a waived one.

## RL1.5 — Architecture delta, feature change (S3)

Backend: `apps/control_api/routers/changes.py` (`POST /delivery-cycles/{c}/architecture-delta/propose`, `POST /delivery-cycles/{c}/architecture-delta/decline {note}`), `core/intelligence/impact/guards.py` (`architecture_delta_resolved`).

- `proposeArchitectureDelta(cycleId)`, `declineArchitectureDelta(cycleId, note)`.
- `ImpactAnalysisStage.tsx`: when the latest impact assessment has `architecture_delta_suggested: true`, show an "Architecture change suggested" panel with:
  - **Decline with note** (note required). The backend records and approves the decline in one call, so it needs `APPROVER`; read-only for others.
  - **Propose a delta**. Show this warning under it: "Atlas will propose a delta, but it can't be approved until the backend persists deltas (plan G11, phase RL2)."

Acceptance: client tests; a component test shows the panel only when `architecture_delta_suggested` is true.

## RL1.6 — Defect actions (S3)

Backend: `apps/control_api/routers/defects.py` (`POST /defects/{d}/proceed-unreproduced {reason}` → `{approval_id, status}`; `POST /defects/{d}/reject {reason?}`).

- `proceedUnreproduced(defectId, reason)`, `rejectDefect(defectId, reason?)`.
- `BugFixStage.tsx`: at REPRODUCTION, show **Proceed unreproduced** (reason required) when reproduction attempts are exhausted or failed; the resulting `UNREPRODUCED_REPAIR` approval shows in the Decision panel. At TRIAGE and later, **Reject defect** with an optional reason and a confirmation step built into the page.

Acceptance: client tests; component tests for both actions.

## RL1.7 — Request changes, interim behaviour (S5)

The backend stores a Request changes note but does not revise anything until RL2.

- `components/studio/DecisionPanel.tsx`: under Request changes, show: "Your note is recorded. The agent won't revise from it until revision support ships; to change this now, edit it (feature specs) or regenerate it." Keep the note required.
- After a `CHANGES_REQUESTED` decision, show the note in the stage view next to the subject, with author and time from `GET /audit?target_type=approval&target_id=<id>`.

Acceptance: a component test for the helper text and the note display.

## RL1.8 — Plan doc corrections (D1)

- `docs/design/olympus-chat-workspace-plan.md`: in §1 under Approvals add "Never created by the backend: EXPECTED_BEHAVIOR (until RL3), REPAIR_SPEC, READINESS, SPEC_DECISION, DEPLOYMENT. Repair and remediation specs use IMPLEMENTATION_SPEC." Rewrite §5's last paragraph to match RL1.1's mapping. In §5 PLANNING, say plan acceptance is not enforced by the backend until RL3.
- `docs/design/olympus-cursor-prompt-chat-workspace.md` C7b: replace "approver approves REPAIR_SPEC" with "approver approves the repair IMPLEMENTATION_SPEC"; replace "approver decides the EXPECTED_BEHAVIOR approval" with "(EXPECTED_BEHAVIOR approval from RL3 onward)"; replace "approver decides a READINESS approval if one is requested" with "no approval is requested".

## RL1.9 — Status

Add `STATUS.md` §17 "Review loop track (RL)" with a table `| Phase | State | Milestone | Blockers |` and rows RL1–RL4 (RL1 COMPLETE with the milestone summary, the rest NOT_STARTED). Add a dated changelog row.

## Phase acceptance

- `npm run check` green.
- With a live control API: create a brownfield cycle from the Studio (register → READY → cycle), work the review queue, and see a feature-change architecture-delta panel and a bug-fix repair-spec Decision panel, without calling the API outside the Studio.
- Report any step that needed a backend change as `BACKEND_GAP: <step>` instead of working around it.
