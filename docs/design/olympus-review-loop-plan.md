# Olympus — Review loop, gates and Studio gaps

Status: plan for Cursor. Repo state reviewed: `main` @ `5ccf54f` (2026-10-07), after Olympus Studio C0–C7.
Prompts: `docs/design/cursor-prompts/` (one per phase, run in order). Background on the journeys and human checkpoints: `docs/design/olympus-journeys.md`.

This plan follows `olympus-chat-workspace-plan.md`. That plan kept the backend read-only. **This plan changes that rule for a fixed scope**: the backend changes listed in §3 are allowed; everything else in `core/`, `apps/control_api/`, `agents/` and `migrations/` stays as it is.

---

## 1. Why

A human checkpoint today can only approve or reject. "Request changes" stores a note and nothing else happens. The chat can explain cycle status but cannot see the spec, architecture or plan being reviewed. Several approval types the Studio expects are never created. The goal is a review loop like Claude Design: the agent's output is shown in the workspace, the reviewer discusses it in chat, asks for changes, gets a revised version with a diff, and approves.

## 2. Findings this plan fixes

| # | Finding | Evidence |
|---|---|---|
| G1 | Request changes and Reject only store the note. Only SCOPE rejection has a handler; no agent re-runs. | `handle_approval_decide` in `core/commands/handlers.py` |
| G2 | Regenerate endpoints take no feedback. | `POST /delivery-cycles/{c}/architecture/propose`, `/implementation-specs/generate`, `/change-interpretation/rerun` |
| G3 | The chat snapshot has overview, inbox, command catalog and turns; never the content under review. | `OrchestratorService.build_snapshot` |
| G4 | When a session has both ids, the snapshot uses the project overview, not the cycle overview (`if`/`elif`). | `build_snapshot` |
| G5 | `EXPECTED_BEHAVIOR`, `REPAIR_SPEC`, `READINESS`, `SPEC_DECISION`, `DEPLOYMENT` approvals are never created. Repair and remediation specs use `IMPLEMENTATION_SPEC`. | `ApprovalType` usage |
| G6 | Task plan acceptance has no role check and no approval. | `TaskPlanService.accept` |
| G7 | UNDERSPECIFIED / CONFLICTING bug classifications are accepted automatically; a model decides what "correct" means. | `DefectService.persist_expected_behavior` |
| G8 | Approval notes never reach later agents. Only clarification answers reach Kira's decompose prompt as "Prior decisions". | `product_context_for_task`, `core/runtime/profiles/kira.py` |
| G9 | A bug fix cannot retire a baseline that encodes the bug. Only feature-change releases supersede baselines. | `bug_fix_promotion.py` vs `feature_change_promotion.py` |
| G10 | Brownfield remediation writes baselines that pin behaviour a reviewer accepted only as a known gap. | `BrownfieldRemediationService` |
| G11 | An Atlas architecture delta is never persisted. `architecture_delta_resolved` needs an APPROVED `Architecture` with `kind="DELTA"`; nothing creates one, so only "decline" can pass the guard. | `FeatureChangeCompletionService.persist_from_execution` only emits `architecture_delta.proposed`; `core/intelligence/impact/guards.py` |
| G12 | No shared product-spec view. A greenfield PRD and a brownfield repo end in the same canonical model, but nothing renders that model as one document. The provenance the backend stores is not in the API: `FeatureSpec.promoted_from_id` and `derived_from_source_version_id`, AC `given`/`when`/`then`, and `Feature.origin`/`source_refs`. | `apps/control_api/routers/specs.py` `get_spec`; `product_model.py` `FeatureResponse` |
| G13 | The chat can propose only registered bus commands. Generating the architecture, implementation specs and task plan, re-running the change interpretation, proposing an architecture delta and creating a release are REST-only, so the chat can explain them but not propose them (was B-03 in `olympus-chat-workspace-plan.md`). | `core/commands/registry.py`, `core/commands/catalog.py` |
| S1 | Studio cannot register a repository, so brownfield cannot start. | no `POST /projects/{p}/repositories` in `src/api` |
| S2 | Studio review queue is read-only: no `POST /delivery-cycles/{c}/promotion-decisions`. | `BrownfieldBaselineStage.tsx` |
| S3 | Studio has no finding waive / remediate, architecture-delta propose / decline, defect proceed-unreproduced / reject. | `src/api/commands.ts` |
| S4 | `APPROVAL_TYPE_TO_STAGE` maps `IMPLEMENTATION_SPEC` → PLANNING and `ARCHITECTURE_DELTA` → ARCHITECTURE for every cycle type. Bug fix raises repair-spec approvals at ROOT_CAUSE and feature change raises architecture-delta approvals at IMPACT_ANALYSIS, so the Decision panel never shows them. | `apps/dashboard/lib/studio-spine.ts` |
| S5 | The Decision panel offers Request changes, but the backend does nothing with it (G1). | `components/studio/DecisionPanel.tsx` |
| D1 | `olympus-chat-workspace-plan.md` §5 lists EXPECTED_BEHAVIOR / REPAIR_SPEC / READINESS approvals that are never created, and treats plan acceptance as enforced. | §5 last paragraph |

## 3. Decisions

1. **Request changes revises.** A `CHANGES_REQUESTED` decision re-runs the agent that produced the subject, with the note and the previous output in the contract's `_snapshot`. The prompt says: revise, changing only what the feedback asks. The new version raises its own approval. The old approval stays `CHANGES_REQUESTED`.
2. **Chat sees the subject.** A turn may carry `focus: {subject_type, subject_id}`. The snapshot then includes that subject's content and its sources. A new intent `REVISION_NOTE_DRAFT` lets the chat draft a note that pre-fills the Decision panel. Chat still never decides an approval.
3. **Approvals are raised by the backend** as soon as an approvable artifact is saved: architecture, architecture delta, implementation spec (all kinds), spec delta (already), task plan, expected behaviour. Scope stays an explicit request because the reviewer picks the specs.
4. **Direct editing**: allowed for architecture and implementation specs, as a new human-authored version that passes the same validation as agent output and needs fresh approval. Task plans change only through Request changes.
5. **Task plans need a human approval** before contracts are issued.
6. **Underspecified or conflicting bugs need a human**: an `EXPECTED_BEHAVIOR` approval, which also lists the active baselines the expected behaviour contradicts. Approving confirms them; they are superseded at release.
7. **Approval notes reach later agents** as decisions in their context.
8. **Baselines built on accepted known gaps are provisional.** A provisional baseline that fails against a change is reported, not a gate failure, until a human confirms the behaviour.
9. **One product-spec view for both entry points.** The Studio renders a project's canonical model as a PRD-shaped document: capabilities, features, behaviour, rules and given/when/then ACs. Every rule shows where it came from: the PRD section for greenfield, the cited code or test and its confidence for brownfield, and accepted known gaps flagged.
10. **Chat can propose every stage's generate step.** The REST-only generate actions become bus commands with catalog entries, so the chat can propose them and the Studio runs them from a proposal card after a click.
11. **Backend scope**: the changes in this plan only. The Studio gaps (S1–S4) need no backend work; their endpoints exist.

## 4. Phases

| Phase | Scope | Prompt |
|---|---|---|
| RL1 | Studio gaps, frontend only: S1–S5, D1 | `cursor-prompts/RL1-studio-gaps.md` |
| RL2 | Revision loop, chat focus, auto-requested approvals, architecture-delta persistence, product-spec view, chat generate commands: G1–G4, G11–G13, decisions 1–3, 9–10 | `cursor-prompts/RL2-review-loop.md` |
| RL3 | Gates, edits, baselines: G5–G10, decisions 4–8 | `cursor-prompts/RL3-gates-edits-baselines.md` |
| RL4 | Prove it: journey tests without hidden fallbacks, live four-journey run through the Studio | `cursor-prompts/RL4-prove-it.md` |

Done-when per phase:
- **RL1**: all four journeys can be driven from the Studio without calling the API by hand (architecture-delta *propose* excepted until RL2).
- **RL2**: on a greenfield ARCHITECTURE checkpoint, Request changes with a note produces v2 that changes only what the note asked, shown as a diff with a fresh approval; the chat answers a question about the architecture from its content; the product-spec view renders a greenfield and a brownfield project in the same shape with provenance; the chat proposes "generate the architecture" and the Studio runs it from the card.
- **RL3**: a bug fix whose expected behaviour contradicts an onboarding baseline reaches release with a human-confirmed expected behaviour and that baseline superseded, not waived.
- **RL4**: `scripts/acceptance/evaluate_mvp.py` passes on a clean database with live workers, with no fallback flag set.
