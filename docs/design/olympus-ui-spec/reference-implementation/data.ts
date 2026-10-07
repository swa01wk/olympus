// SupportDesk fixtures — illustrative only. IDs, SHAs, counts and code excerpts are
// design fixtures, not extracted records. The four cycles are the four MVP journeys.
import type { Journey, GNode, GEdge } from './model';

const n = (o: GNode) => o;
const e = (from: string, to: string, rel: string, extra: Partial<GEdge> = {}): GEdge => ({ from, to, rel, ...extra });

// ───────────────────────────── DC-001 · Greenfield Build ─────────────────────────────
const GF: Journey = {
  id: 'GF', cycle: 'DC-001', name: 'Greenfield Build', objective: 'Build SupportDesk from product intent',
  direction: 'Product → Code', outcome: 'Verified release R1',
  stages: [
    { k: 'DISCOVERY', lane: 'intent', out: 'Immutable ProductSource, version and hash' },
    { k: 'PRODUCT_MODEL', lane: 'intent', out: 'Capabilities, Features, FeatureSpecs, REQ / stories / ACs' },
    { k: 'ARCHITECTURE', lane: 'intent', out: 'Architecture baseline, contracts, ImplementationSpecs' },
    { k: 'PLANNING', lane: 'work', out: 'Validated DAG and compiled TaskContracts' },
    { k: 'DEVELOPMENT', lane: 'exec', out: 'Snapshots, leases, worktrees, candidate commits' },
    { k: 'INTEGRATION', lane: 'code', out: 'Exact integrated SHA and canonical index / links' },
    { k: 'ASSURANCE', lane: 'evidence', out: 'AC proof, independent review, deterministic gates' },
    { k: 'RELEASE', lane: 'outcome', out: 'Versioned R1 manifest and outcome bundle' },
    { k: 'COMPLETE', lane: 'outcome', out: 'R1 and complete lineage; deployment optional' },
  ],
  live: 4,
  focus: 'EX-104',
  defaults: { S03: 'SPEC-002', S04: 'TASK-104', S05: 'EX-104', S06: 'CODE-117', S07: 'CODE-117', S09: 'EV-AC', S10: 'R1' },
  base: { released: '—', releasedSha: '', target: 'R1', canonical: 'none yet', candidate: 'EX-103 · 7f2c1d9' },
  nodes: [
    n({ id: 'PS-001', lane: 'intent', kind: 'Source', ref: 'PS-001 v1', title: 'SupportDesk PRD', at: 0, st: [[0, 'recorded']], sub: 'sha256:4be1…9a0c', prov: 'FACT', authority: 'Uploaded by project operator', workspace: 'Product source store' }),
    n({ id: 'SPEC-001', lane: 'intent', kind: 'Feature spec', ref: 'SPEC-001 v1', title: 'Create ticket', at: 1, st: [[1, 'review'], [2, 'approved']], prov: 'DECISION', origin: 'DERIVED from PS-001 §3.1',
      attn: { review: 'SPEC-001 v1 and SPEC-002 v1 need scope review before architecture work starts' },
      why: { review: { summary: 'Kira proposed this behavioural contract from PS-001. Policy requires human scope approval before ImplementationSpecs are derived.', checks: [['Derived from versioned source', true, 'PS-001 v1 §3.1'], ['Open clarifications resolved', true, '0 open'], ['Scope approval recorded', false, 'APR-101 pending']], blocking: ['APR-101'], policy: 'spec.scope_approval@v1', inputs: 'PS-001 v1', next: 'Approve scope, or request changes to create SPEC-001 v2.' } } }),
    n({ id: 'SPEC-002', lane: 'intent', kind: 'Feature spec', ref: 'SPEC-002 v1', title: 'Update ticket status', at: 1, st: [[1, 'review'], [2, 'approved']], prov: 'DECISION', origin: 'DERIVED from PS-001 §3.2' }),
    n({ id: 'ARCH-001', lane: 'intent', kind: 'Architecture', ref: 'ARCH-001 v1', title: 'API → service → repo → DB', at: 2, st: [[2, 'review'], [3, 'approved']], prov: 'DECISION',
      attn: { review: 'ARCH-001 needs architecture approval before planning (policy arch.review@v1)' } }),
    n({ id: 'IMPL-001', lane: 'intent', kind: 'Impl spec', ref: 'IMPL-001 v1', title: 'Ticket API realization', at: 2, st: [[2, 'proposed'], [3, 'approved']] }),

    n({ id: 'TASK-101', lane: 'work', kind: 'Durable task', ref: 'TASK-101', title: 'API / data contract', at: 3, st: [[3, 'ready'], [4, 'completed']] }),
    n({ id: 'TASK-102', lane: 'work', kind: 'Durable task', ref: 'TASK-102', title: 'Ticket model & repository', at: 3, st: [[3, 'blocked'], [4, 'running'], [5, 'completed']] }),
    n({ id: 'TASK-103', lane: 'work', kind: 'Durable task', ref: 'TASK-103', title: 'Ticket API handlers', at: 3, st: [[3, 'blocked'], [4, 'running'], [5, 'completed']] }),
    n({ id: 'TASK-104', lane: 'work', kind: 'Durable task', ref: 'TASK-104', title: 'Integrate candidates', at: 3, st: [[3, 'blocked'], [5, 'completed']],
      why: { blocked: { summary: 'Scheduler eligibility is not met: integration waits for both candidate-producing tasks.', checks: [['status == READY', false, 'BLOCKED'], ['dependencies complete', false, 'TASK-102, TASK-103 running'], ['required artifacts exist', false, 'candidate commits pending'], ['contract versions match', true, 'TC-104 v1'], ['required approvals exist', true, 'APR-101, APR-102'], ['no blocking policy', true], ['no conflicting execution', true]], blocking: ['TASK-102', 'TASK-103'], policy: 'scheduler.eligibility@v1', inputs: 'IMPL-001 v1 · ARCH-001 v1', next: 'Recomputed automatically when TASK-102 and TASK-103 complete. No manual override.' } } }),

    n({ id: 'EX-101', lane: 'exec', kind: 'Attempt', ref: 'EX-101', title: 'Contract attempt', at: 4, st: [[4, 'completed']], sub: 'candidate 1c4e2aa', sha: '1c4e2aa' }),
    n({ id: 'EX-102', lane: 'exec', kind: 'Attempt', ref: 'EX-102', title: 'Model attempt 1', at: 4, st: [[4, 'failed']], sub: '3 unit tests failed', hist: 'Attempt 1 of TASK-102. Retained with SNAP-102 and test artifacts.',
      why: { failed: { summary: 'Attempt failed: 3 unit tests failed in tests/tickets/test_repository.py. The attempt, its snapshot and test artifacts are immutable history; the task was not auto-completed.', checks: [['Required outputs present', false, 'no candidate commit'], ['Tests passed', false, '3 failed / 41'], ['Retry permitted by policy', true, 'max_attempts = 3']], policy: 'retry.code_change@v1', next: 'EX-103 already created as a new attempt with SNAP-103.' } },
      cmds: { failed: [{ label: 'Create retry', cmd: 'POST /delivery-cycles/DC-001/commands/retry_task', enabled: false, reason: 'EX-103 is already the active attempt for TASK-102.' }] } }),
    n({ id: 'EX-103', lane: 'exec', kind: 'Attempt', ref: 'EX-103', title: 'Model attempt 2', at: 4, st: [[4, 'running'], [5, 'completed']], sub: 'worktree olympus/EX-103', sha: 'a1f0c22', workspace: 'olympus/EX-103',
      why: { running: { summary: 'Bounded writable attempt in an isolated worktree. Output stays provisional until integration.', checks: [['Lease held', true, 'worker-01 · heartbeat 3s'], ['Snapshot immutable', true, 'SNAP-103'], ['Tool actions within TC-102 v1 scope', true, '14 / 14 allowed']], policy: 'execution.lease@v1' } } }),
    n({ id: 'EX-104', lane: 'exec', kind: 'Attempt', ref: 'EX-104', title: 'Handlers attempt', at: 4, st: [[4, 'checkpointed'], [5, 'completed']], sub: 'waiting on CHK-012', workspace: 'olympus/EX-104', sha: 'a1f0c22',
      attn: { checkpointed: 'EX-104 is checkpointed: CHK-012 asks whether a CLOSED ticket can be reopened' },
      why: { checkpointed: { summary: 'Execution stopped at a durable checkpoint and released its runtime. Resume builds a continuation package from records, not the model transcript.', checks: [['Checkpoint persisted', true, 'CHK-012'], ['Artifacts and progress persisted', true], ['Runtime released', true, 'lease returned'], ['Question answered', false, 'awaiting operator']], blocking: ['CHK-012'], policy: 'escalation.ambiguous_requirement = ASK_HUMAN', inputs: 'TC-103 v1 · SPEC-002 v1', next: 'Answer CHK-012 → new SPEC-002 version if required → resume or replan under policy.' } },
      cmds: { checkpointed: [{ label: 'Answer CHK-012', cmd: 'POST /delivery-cycles/DC-001/commands/answer_checkpoint', dialog: 'checkpoint' }, { label: 'Request cancellation', cmd: 'POST /executions/EX-104/cancel' }] } }),

    n({ id: 'IC-001', lane: 'code', kind: 'Integration', ref: 'IC-001', title: 'Combined candidate', at: 5, st: [[5, 'integrated']], sub: '@ 9e31ab7', sha: '9e31ab7' }),
    n({ id: 'CODE-118', lane: 'code', kind: 'Route', ref: 'CODE-118', title: 'POST /tickets', at: 5, st: [[5, 'canonical']], prov: 'FACT', origin: 'GENERATED_LINEAGE' }),
    n({ id: 'CODE-117', lane: 'code', kind: 'Symbol', ref: 'CODE-117', title: 'TicketService.create', at: 5, st: [[5, 'canonical']], prov: 'FACT', origin: 'GENERATED_LINEAGE', sub: 'ticket_service.py' }),

    n({ id: 'APR-1', lane: 'evidence', kind: 'Approvals', ref: 'APR-101 · 102', title: 'Scope + architecture', at: 1, st: [[1, 'pending'], [3, 'approved']], stack: ['APR-101 Scope approval', 'APR-102 Architecture approval'] }),
    n({ id: 'EV-AC', lane: 'evidence', kind: 'AC proof', ref: 'EV-1xx', title: '12 mandatory ACs', at: 6, st: [[6, 'running'], [7, 'passed']], sub: 'target 9e31ab7' }),
    n({ id: 'WR-001', lane: 'evidence', kind: 'Warden review', ref: 'WR-001', title: 'Engineering review', at: 6, st: [[6, 'passed']], sub: '@ 9e31ab7' }),
    n({ id: 'GATE-001', lane: 'evidence', kind: 'Gate', ref: 'GATE-001', title: 'Deterministic gates', at: 6, st: [[6, 'blocked'], [7, 'passed']] }),
    n({ id: 'APR-103', lane: 'evidence', kind: 'Approval', ref: 'APR-103', title: 'Release approval', at: 7, st: [[7, 'pending'], [8, 'approved']], attn: { pending: 'Release approval APR-103 is waiting for you' } }),

    n({ id: 'R1', lane: 'outcome', kind: 'Outcome', ref: 'R1', title: 'First release', at: 7, st: [[7, 'approval-pending'], [8, 'released']], sub: 'pins 9e31ab7' }),
    n({ id: 'DEP-1', lane: 'outcome', kind: 'Deployment', ref: 'optional', title: 'Stratos deployment', at: 8, st: [[8, 'not-requested']] }),
  ],
  edges: [
    e('PS-001', 'SPEC-001', 'DERIVED_FROM'), e('PS-001', 'SPEC-002', 'DERIVED_FROM'),
    e('SPEC-001', 'IMPL-001', 'DERIVED_FROM'), e('SPEC-002', 'IMPL-001', 'DERIVED_FROM'), e('ARCH-001', 'IMPL-001', 'CONSTRAINS'),
    e('SPEC-001', 'APR-1', 'APPROVED_BY'), e('ARCH-001', 'APR-1', 'APPROVED_BY'),
    e('IMPL-001', 'TASK-101', 'DERIVED_FROM'), e('IMPL-001', 'TASK-102', 'DERIVED_FROM'), e('IMPL-001', 'TASK-103', 'DERIVED_FROM'), e('IMPL-001', 'TASK-104', 'DERIVED_FROM'),
    e('TASK-101', 'TASK-102', 'DEPENDS_ON'), e('TASK-101', 'TASK-103', 'DEPENDS_ON'), e('TASK-102', 'TASK-104', 'DEPENDS_ON'), e('TASK-103', 'TASK-104', 'DEPENDS_ON'),
    e('TASK-101', 'EX-101', 'EXECUTED_AS'), e('TASK-102', 'EX-102', 'EXECUTED_AS'), e('TASK-102', 'EX-103', 'EXECUTED_AS'), e('TASK-103', 'EX-104', 'EXECUTED_AS'),
    e('EX-101', 'IC-001', 'INTEGRATED_IN'), e('EX-103', 'IC-001', 'INTEGRATED_IN'), e('EX-104', 'IC-001', 'INTEGRATED_IN'),
    e('IC-001', 'CODE-117', 'CONTAINED_IN'), e('CODE-118', 'CODE-117', 'CALLS'), e('SPEC-001', 'CODE-117', 'IMPLEMENTS', { note: 'GENERATED_LINEAGE · confidence 1.0' }),
    e('CODE-117', 'EV-AC', 'VERIFIED_BY'), e('IC-001', 'WR-001', 'VERIFIED_BY'),
    e('EV-AC', 'GATE-001', 'EVALUATED_IN'), e('WR-001', 'GATE-001', 'EVALUATED_IN'),
    e('GATE-001', 'R1', 'GATES'), e('APR-103', 'R1', 'AUTHORIZES'), e('R1', 'DEP-1', 'DEPLOYED_AS'),
  ],
};

// ───────────────────────────── DC-002 · Brownfield Onboarding ─────────────────────────────
const BF: Journey = {
  id: 'BF', cycle: 'DC-002', name: 'Brownfield Onboarding', objective: 'Establish a trusted model of the existing repository',
  direction: 'Code → Product model', outcome: 'Trusted baseline B1 + READY_FOR_CHANGE',
  stages: [
    { k: 'RECON', lane: 'code', out: 'Immutable source reference and deterministic facts' },
    { k: 'CODE_INDEX', lane: 'code', out: 'AST / routes / schemas / tests at pinned SHA' },
    { k: 'RECOVERED_SPEC', lane: 'intent', out: 'ObservedBehaviour, RecoveredSpec proposals, discovered links' },
    { k: 'BASELINE', lane: 'evidence', out: 'Behavioural baselines and exact-repository-SHA proof' },
    { k: 'READINESS', lane: 'evidence', out: 'Human / evidence-backed promotions, readiness assessment' },
    { k: 'READY', lane: 'outcome', out: 'Trusted baseline B1 + READY_FOR_CHANGE; no new release' },
  ],
  live: 2,
  focus: 'REC-017',
  defaults: { S03: 'REC-017', S04: 'TASK-202', S05: 'EX-202', S06: 'CODE-117', S07: 'CODE-117', S09: 'RDY-001', S10: 'B1' },
  base: { released: 'R1', releasedSha: '9e31ab7', target: 'B1', canonical: 'IDX-002 @ 9e31ab7' },
  nodes: [
    n({ id: 'REPO-01', lane: 'code', kind: 'Repository', ref: 'REPO-01', title: 'SupportDesk @ main', at: 0, st: [[0, 'recorded']], sub: '@ 9e31ab7', prov: 'FACT', sha: '9e31ab7', authority: 'Registered by operator', workspace: 'Read-only repository' }),
    n({ id: 'IDX-002', lane: 'code', kind: 'Code index', ref: 'IDX-002', title: 'AST · routes · tests', at: 1, st: [[1, 'canonical']], sub: '214 symbols · 86 tests', prov: 'FACT', sha: '9e31ab7' }),
    n({ id: 'CODE-130', lane: 'code', kind: 'Route', ref: 'CODE-130', title: 'PATCH /tickets/{id}', at: 1, st: [[1, 'canonical']], prov: 'FACT', sha: '9e31ab7' }),
    n({ id: 'CODE-117', lane: 'code', kind: 'Symbol', ref: 'CODE-117', title: 'TicketService.update_status', at: 1, st: [[1, 'canonical']], prov: 'FACT', sha: '9e31ab7', sub: 'ticket_service.py' }),

    n({ id: 'OB-009', lane: 'intent', kind: 'Observed', ref: 'OB-009', title: 'Create defaults to OPEN', at: 2, st: [[2, 'observed']], prov: 'FACT', sub: 'test_create_ticket' }),
    n({ id: 'OB-011', lane: 'intent', kind: 'Observed', ref: 'OB-011', title: 'CLOSED update → HTTP 500', at: 2, st: [[2, 'not-blessed']], prov: 'FACT', sub: 'runtime probe',
      why: { 'not-blessed': { summary: 'Observed fact, but not intended behaviour. A 500 on a CLOSED ticket looks accidental; Olympus will not turn it into a baseline without a decision.', checks: [['Deterministically observed', true, 'probe @ 9e31ab7'], ['Supported by spec or test', false, 'no test asserts this'], ['Promoted to baseline', false, 'blocked by UNC-004']], blocking: ['UNC-004'], policy: 'brownfield.promotion@v1' } } }),
    n({ id: 'REC-017', lane: 'intent', kind: 'Recovered', ref: 'REC-017', title: 'Ticket lifecycle', at: 2, st: [[2, 'inferred'], [4, 'promoted']], prov: 'INFERENCE', conf: 0.84, origin: 'DISCOVERED', sha: '9e31ab7', authority: 'Scout proposal · Olympus record',
      attn: { inferred: 'REC-017 (confidence 0.84) needs evidence-backed review before it can become trusted intent' },
      why: { inferred: { summary: 'Scout reconstructed this from code, routes and tests. Observed behaviour does not establish intended product truth; promotion keeps the evidence and the reviewer.', checks: [['Supporting code / tests linked', true, '3 files · 6 tests'], ['Confidence ≥ policy floor (0.80)', true, '0.84'], ['Open uncertainties resolved', false, 'UNC-004'], ['Human or authoritative promotion', false]], blocking: ['UNC-004'], policy: 'brownfield.promotion@v1', inputs: 'IDX-002 @ 9e31ab7', next: 'Review evidence, request more evidence, reject, or promote with authority.' } },
      cmds: { inferred: [{ label: 'Review and promote', cmd: 'POST /delivery-cycles/DC-002/commands/promote_recovered_spec', dialog: 'approval' }, { label: 'Request more evidence', cmd: 'POST /delivery-cycles/DC-002/commands/request_evidence' }, { label: 'Reject inference', cmd: 'POST /delivery-cycles/DC-002/commands/reject_recovered_spec' }] } }),
    n({ id: 'UNC-004', lane: 'intent', kind: 'Uncertainty', ref: 'UNC-004', title: 'Are CLOSED tickets immutable?', at: 2, st: [[2, 'decision'], [4, 'resolved']], prov: 'UNCERTAINTY',
      attn: { decision: 'UNC-004 needs your decision: should updates to CLOSED tickets be rejected?' },
      why: { decision: { summary: 'Code allows the update path; the runtime probe returns 500; no spec or test states the intent. Olympus will not invent intended semantics.', checks: [['Authoritative spec found', false, 'none'], ['Executable test found', false, 'none'], ['Human decision recorded', false]], policy: 'brownfield.uncertainty@v1', next: 'Record a decision. It becomes DEC-004 and versions REC-017 into a canonical spec.' } },
      cmds: { decision: [{ label: 'Record decision', cmd: 'POST /delivery-cycles/DC-002/commands/record_decision', dialog: 'approval' }] } }),
    n({ id: 'SPEC-017', lane: 'intent', kind: 'Spec · trusted', ref: 'SPEC-017 v3', title: 'Ticket lifecycle (trusted)', at: 4, st: [[4, 'approved']], prov: 'DECISION', origin: 'HUMAN_CONFIRMED' }),

    n({ id: 'TASK-201', lane: 'work', kind: 'Analysis task', ref: 'TASK-201', title: 'Repository discovery', at: 0, st: [[0, 'running'], [1, 'completed']] }),
    n({ id: 'TASK-202', lane: 'work', kind: 'Analysis task', ref: 'TASK-202', title: 'Recover specifications', at: 1, st: [[1, 'ready'], [2, 'running'], [3, 'completed']] }),
    n({ id: 'TASK-203', lane: 'work', kind: 'Verify task', ref: 'TASK-203', title: 'Run baseline proposals', at: 2, st: [[2, 'blocked'], [3, 'running'], [4, 'completed']],
      why: { blocked: { summary: 'Baseline runs wait for the recovered specs they would verify. No feature build is implied by Brownfield work.', checks: [['dependencies complete', false, 'TASK-202 running'], ['required artifacts exist', false, 'baseline proposals'], ['no blocking policy', true]], blocking: ['TASK-202'], policy: 'scheduler.eligibility@v1' } } }),

    n({ id: 'EX-201', lane: 'exec', kind: 'Attempt', ref: 'EX-201', title: 'Deterministic discovery', at: 0, st: [[0, 'running'], [1, 'completed']], sub: 'no model · read-only' }),
    n({ id: 'EX-202', lane: 'exec', kind: 'Attempt', ref: 'EX-202', title: 'Scout recovery', at: 2, st: [[2, 'running'], [3, 'completed']], sub: 'read-only checkout', workspace: 'Read-only checkout @ 9e31ab7', sha: '9e31ab7' }),
    n({ id: 'EX-203', lane: 'exec', kind: 'Attempt', ref: 'EX-203', title: 'Baseline runs', at: 3, st: [[3, 'running'], [4, 'completed']], sub: 'isolated test workspace' }),

    n({ id: 'BL-1', lane: 'evidence', kind: 'Baselines', ref: 'BL-001…014', title: '14 baseline proposals', at: 3, st: [[3, 'proposed'], [4, 'passed']], stack: ['BL-001 POST /tickets → 201, OPEN', 'BL-004 status transitions', '… 12 more'] }),
    n({ id: 'DEC-004', lane: 'evidence', kind: 'Decision', ref: 'DEC-004', title: 'CLOSED rejects updates (409)', at: 4, st: [[4, 'decided']], prov: 'DECISION' }),
    n({ id: 'APR-201', lane: 'evidence', kind: 'Promotion', ref: 'APR-201', title: 'Knowledge review', at: 3, st: [[3, 'pending'], [4, 'approved']], attn: { pending: 'Promotion review APR-201 is waiting for you' } }),
    n({ id: 'RDY-001', lane: 'evidence', kind: 'Readiness', ref: 'RDY-001', title: 'Coverage · baselines · uncertainty', at: 4, st: [[4, 'not-ready'], [5, 'passed']] }),

    n({ id: 'R1', lane: 'outcome', kind: 'Release', ref: 'R1', title: 'Existing release', at: 0, st: [[0, 'unchanged']], sub: '@ 9e31ab7', sha: '9e31ab7' }),
    n({ id: 'B1', lane: 'outcome', kind: 'Baseline', ref: 'B1', title: 'Ready for change', at: 5, st: [[5, 'rfc']], sub: 'no new release' }),
  ],
  edges: [
    e('R1', 'REPO-01', 'PINS'),
    e('REPO-01', 'IDX-002', 'DERIVED_FROM'), e('IDX-002', 'CODE-130', 'CONTAINED_IN'), e('IDX-002', 'CODE-117', 'CONTAINED_IN'), e('CODE-130', 'CODE-117', 'CALLS'),
    e('TASK-201', 'EX-201', 'EXECUTED_AS'), e('EX-201', 'IDX-002', 'PRODUCED'), e('TASK-201', 'TASK-202', 'DEPENDS_ON'), e('TASK-202', 'TASK-203', 'DEPENDS_ON'),
    e('TASK-202', 'EX-202', 'EXECUTED_AS'), e('EX-202', 'REC-017', 'PRODUCED', { kind: 'inferred' }),
    e('CODE-117', 'OB-009', 'OBSERVED_IN'), e('CODE-130', 'OB-011', 'OBSERVED_IN'),
    e('CODE-117', 'REC-017', 'RECOVERED_FROM', { kind: 'inferred', conf: 0.84, note: 'DISCOVERED · confidence 0.84' }),
    e('OB-009', 'REC-017', 'DERIVED_FROM', { kind: 'inferred' }), e('OB-011', 'UNC-004', 'RAISES'), e('REC-017', 'UNC-004', 'HAS_UNCERTAINTY'),
    e('UNC-004', 'DEC-004', 'RESOLVED_BY'), e('DEC-004', 'SPEC-017', 'APPLIED_TO'), e('REC-017', 'SPEC-017', 'PROMOTED_FROM'), e('REC-017', 'APR-201', 'APPROVED_BY'),
    e('SPEC-017', 'BL-1', 'VERIFIED_BY'), e('TASK-203', 'EX-203', 'EXECUTED_AS'), e('EX-203', 'BL-1', 'PRODUCED'),
    e('BL-1', 'RDY-001', 'EVALUATED_IN'), e('UNC-004', 'RDY-001', 'EVALUATED_IN'), e('RDY-001', 'B1', 'GATES'),
  ],
};

// ───────────────────────────── DC-003 · Feature Change ─────────────────────────────
const FC: Journey = {
  id: 'FC', cycle: 'DC-003', name: 'Feature Change', objective: 'Add LOW, MEDIUM and HIGH ticket priority',
  direction: 'Product delta → Code delta', outcome: 'Regression-safe release R2',
  stages: [
    { k: 'INTAKE', lane: 'intent', out: 'ChangeRequest linked to existing project context' },
    { k: 'SPEC_DELTA', lane: 'intent', out: 'Versioned FeatureSpec / ImplementationSpec delta' },
    { k: 'IMPACT_ANALYSIS', lane: 'code', out: 'Affected code / contracts / obligations, rationale' },
    { k: 'PLANNING', lane: 'work', out: 'Validated tasks and immutable contracts' },
    { k: 'DEVELOPMENT', lane: 'exec', out: 'Attempt history, snapshots, worktrees, candidate commits' },
    { k: 'INTEGRATION', lane: 'code', out: 'Exact integrated candidate and refreshed links' },
    { k: 'ASSURANCE', lane: 'evidence', out: 'New proof, regression / baseline proof and gates' },
    { k: 'RELEASE', lane: 'outcome', out: 'R2 manifest and outcome' },
    { k: 'COMPLETE', lane: 'outcome', out: 'R2 becomes the persistent project baseline' },
  ],
  live: 6,
  focus: 'AC-011-03',
  defaults: { S03: 'SPEC-011', S04: 'TASK-104', S05: 'EX-204', S06: 'CODE-117', S07: 'CODE-117', S09: 'AC-011-03', S10: 'R2' },
  base: { released: 'R1', releasedSha: '9e31ab7', target: 'R2', canonical: 'IC-003 @ c83a12d', candidate: 'EX-204 · 4a871dc' },
  nodes: [
    n({ id: 'CR-004', lane: 'intent', kind: 'Change req.', ref: 'CR-004', title: 'Add ticket priority', at: 0, st: [[0, 'recorded']], sub: 'ISSUE-311 · tracker', prov: 'FACT' }),
    n({ id: 'SPEC-011', lane: 'intent', kind: 'Feature spec', ref: 'SPEC-011 v2', title: 'Ticket priority', at: 1, st: [[1, 'review'], [2, 'approved']], sub: 'v1 → v2 delta', prov: 'DECISION',
      attn: { review: 'SPEC-011 v2 delta needs review before impact analysis' } }),
    n({ id: 'IMPL-011', lane: 'intent', kind: 'Impl spec', ref: 'IMPL-011 v2', title: 'Priority realization', at: 1, st: [[1, 'proposed'], [2, 'approved']] }),
    n({ id: 'ARCH-001', lane: 'intent', kind: 'Architecture', ref: 'ARCH-001 v1', title: 'Unchanged · no delta', at: 0, st: [[0, 'approved']], prov: 'DECISION' }),

    n({ id: 'IA-003', lane: 'code', kind: 'Impact', ref: 'IA-003', title: '4 symbols · 6 tests', at: 2, st: [[2, 'bounded']], sub: '3 baselines selected', impact: 'scope' }),
    n({ id: 'CODE-117', lane: 'code', kind: 'Symbol', ref: 'CODE-117', title: 'TicketService', at: 0, st: [[0, 'canonical']], prov: 'FACT', impact: 'direct', sub: 'ticket_service.py' }),
    n({ id: 'CODE-140', lane: 'code', kind: 'Schema', ref: 'CODE-140', title: 'tickets table', at: 0, st: [[0, 'canonical']], prov: 'FACT', impact: 'direct' }),
    n({ id: 'CODE-152', lane: 'code', kind: 'Symbol', ref: 'CODE-152', title: 'NotificationFormatter', at: 0, st: [[0, 'canonical']], prov: 'INFERENCE', conf: 0.62, impact: 'inferred', sub: 'inferred impact 0.62' }),
    n({ id: 'IC-003', lane: 'code', kind: 'Integration', ref: 'IC-003', title: 'Combined candidate', at: 5, st: [[5, 'integrated']], sub: '@ c83a12d', sha: 'c83a12d' }),

    n({ id: 'TASK-101', lane: 'work', kind: 'Durable task', ref: 'TASK-101', title: 'API / data contract', at: 3, st: [[3, 'ready'], [4, 'completed']] }),
    n({ id: 'TASK-104', lane: 'work', kind: 'Durable task', ref: 'TASK-104', title: 'Persistence change', at: 3, st: [[3, 'blocked'], [4, 'running'], [5, 'completed']] }),
    n({ id: 'TASK-105', lane: 'work', kind: 'Durable task', ref: 'TASK-105', title: 'API handler', at: 3, st: [[3, 'blocked'], [4, 'completed']] }),
    n({ id: 'TASK-106', lane: 'work', kind: 'Durable task', ref: 'TASK-106', title: 'E2E test authoring', at: 3, st: [[3, 'blocked'], [5, 'completed']],
      why: { blocked: { summary: 'TASK-106 waits for TASK-104 and TASK-105: it needs both persisted priority and the handler contract.', checks: [['status == READY', false, 'BLOCKED'], ['dependencies complete', false, 'TASK-104 running'], ['required artifacts exist', true], ['contract versions match', true, 'TC-106 v1'], ['required approvals exist', true, 'APR-301'], ['no blocking policy', true], ['no conflicting execution', true]], blocking: ['TASK-104'], policy: 'scheduler.eligibility@v1', next: 'Eligibility recomputes when TASK-104 completes.' } } }),

    n({ id: 'EX-203', lane: 'exec', kind: 'Attempt', ref: 'EX-203', title: 'Persistence attempt 1', at: 4, st: [[4, 'stale']], sub: 'snapshot stale', hist: 'Attempt 1 of TASK-104. SNAP-203 pinned TC-104 v1; contract was revised to v2.',
      why: { stale: { summary: 'Pinned inputs differ from authoritative versions: SNAP-203 pinned TC-104 v1, but TC-104 is now v2 after the spec delta was clarified. Output cannot be integrated.', checks: [['Snapshot inputs current', false, 'TC-104 v1 ≠ v2'], ['Attempt retained', true, 'immutable']], policy: 'execution.staleness@v1', next: 'EX-204 created with SNAP-204 against TC-104 v2.' } } }),
    n({ id: 'EX-204', lane: 'exec', kind: 'Attempt', ref: 'EX-204', title: 'Persistence attempt 2', at: 4, st: [[4, 'running'], [5, 'completed']], sub: 'candidate 4a871dc', sha: '9e31ab7', workspace: 'olympus/EX-204' }),
    n({ id: 'EX-205', lane: 'exec', kind: 'Attempt', ref: 'EX-205', title: 'API handler attempt', at: 4, st: [[4, 'completed']], sub: 'candidate 77d0b3e' }),
    n({ id: 'EX-206', lane: 'exec', kind: 'Attempt', ref: 'EX-206', title: 'E2E authoring attempt', at: 5, st: [[5, 'completed']], sub: 'candidate 2e61f04' }),

    n({ id: 'APR-301', lane: 'evidence', kind: 'Approval', ref: 'APR-301', title: 'Spec delta approval', at: 1, st: [[1, 'pending'], [2, 'approved']] }),
    n({ id: 'EV-5', lane: 'evidence', kind: 'Evidence', ref: 'EV-501 · 601–603', title: 'Unit + impacted baselines', at: 6, st: [[6, 'passed']], sub: '@ c83a12d', stack: ['EV-501 new unit behaviour', 'EV-601 BL-001 default OPEN', 'EV-602 BL-004 transitions', 'EV-603 BL-009 list ordering'] }),
    n({ id: 'AC-011-03', lane: 'evidence', kind: 'Mandatory proof', ref: 'AC-011-03', title: 'E2E at integrated SHA', at: 6, st: [[6, 'missing'], [7, 'passed']], sub: 'no result @ c83a12d',
      attn: { missing: 'Release blocked: AC-011-03 has no E2E evidence at c83a12d, and release approval APR-302 is pending' },
      why: { missing: { summary: 'Mandatory acceptance criterion without its required evidence type. An E2E result exists only at 4a871dc (provisional EX-204 worktree) — old-SHA proof is history and cannot satisfy the current target.', checks: [['Obligation selected', true, 'IA-003 → AC-011-03'], ['Evidence type E2E present', false], ['Evidence SHA == c83a12d', false, 'only 4a871dc'], ['Model assertion accepted', null, 'never substitutes']], blocking: ['GATE-003', 'R2'], policy: 'assurance.mandatory_ac@v2', inputs: 'SPEC-011 v2 · IC-003', next: 'Request exact-target verification. Sentinel runs E2E against c83a12d.' } } }),
    n({ id: 'WR-003', lane: 'evidence', kind: 'Warden review', ref: 'WR-003', title: 'Engineering review', at: 6, st: [[6, 'passed']], sub: '@ c83a12d · 0 blocking' }),
    n({ id: 'GATE-003', lane: 'evidence', kind: 'Gate', ref: 'GATE-003', title: 'Deterministic gates', at: 6, st: [[6, 'blocked'], [7, 'passed']],
      why: { blocked: { summary: 'Olympus finalizes gates from evidence and policy. Warden and Sentinel recommend; they do not set this state.', checks: [['Candidate READY', true, 'IC-003'], ['Evidence SHA == integrated SHA', true, 'c83a12d'], ['Mandatory coverage complete', false, '11 / 12 ACs'], ['Blocking findings == 0', true], ['Policy applied', true, 'gate.release@v2']], blocking: ['AC-011-03'], policy: 'gate.release@v2', inputs: 'IC-003 @ c83a12d', next: 'Recomputed when AC-011-03 evidence lands.' } } }),
    n({ id: 'APR-302', lane: 'evidence', kind: 'Approval', ref: 'APR-302', title: 'Release approval', at: 6, st: [[6, 'pending'], [8, 'approved']], attn: { pending: 'Release approval APR-302 is waiting. Approval cannot replace missing proof' } }),

    n({ id: 'R1', lane: 'outcome', kind: 'Baseline', ref: 'R1', title: 'Current baseline', at: 0, st: [[0, 'baseline'], [8, 'historical']], sub: '@ 9e31ab7', sha: '9e31ab7' }),
    n({ id: 'R2', lane: 'outcome', kind: 'Outcome', ref: 'R2', title: 'Target release', at: 6, st: [[6, 'not-eligible'], [7, 'approval-pending'], [8, 'released']], sub: 'pins c83a12d',
      why: { 'not-eligible': { summary: 'Release eligibility is a server computation over the manifest. Two predicates are unmet.', checks: [['manifest valid', true], ['candidate is current', true, 'IC-003'], ['required gates pass', false, 'GATE-003 blocked'], ['required approvals exist', false, 'APR-302 pending'], ['executions not stale', true], ['blocking findings == 0', true], ['mandatory ACs have evidence', false, 'AC-011-03'], ['impacted baselines pass', true, 'EV-601…603']], blocking: ['AC-011-03', 'APR-302'], policy: 'release.eligibility@v3', inputs: 'IC-003 @ c83a12d', next: 'Execute release stays disabled until every predicate passes.' } },
      cmds: { 'not-eligible': [{ label: 'Execute release', cmd: 'POST /releases/R2/execute', enabled: false, reason: '2 eligibility predicates unmet' }] } }),
  ],
  edges: [
    e('CR-004', 'SPEC-011', 'DERIVED_FROM'), e('SPEC-011', 'IMPL-011', 'DERIVED_FROM'), e('ARCH-001', 'IMPL-011', 'CONSTRAINS'), e('SPEC-011', 'APR-301', 'APPROVED_BY'),
    e('SPEC-011', 'IA-003', 'ASSESSED_IN'), e('IA-003', 'CODE-117', 'AFFECTS'), e('IA-003', 'CODE-140', 'AFFECTS'), e('IA-003', 'CODE-152', 'AFFECTS', { kind: 'inferred', conf: 0.62, note: 'semantic expansion · 0.62' }),
    e('CODE-117', 'CODE-140', 'ACCESSES'),
    e('IMPL-011', 'TASK-101', 'DERIVED_FROM'), e('IMPL-011', 'TASK-104', 'DERIVED_FROM'), e('IMPL-011', 'TASK-105', 'DERIVED_FROM'), e('IMPL-011', 'TASK-106', 'DERIVED_FROM'),
    e('TASK-101', 'TASK-104', 'DEPENDS_ON'), e('TASK-101', 'TASK-105', 'DEPENDS_ON'), e('TASK-104', 'TASK-106', 'DEPENDS_ON'), e('TASK-105', 'TASK-106', 'DEPENDS_ON'),
    e('TASK-104', 'EX-203', 'EXECUTED_AS'), e('TASK-104', 'EX-204', 'EXECUTED_AS'), e('TASK-105', 'EX-205', 'EXECUTED_AS'), e('TASK-106', 'EX-206', 'EXECUTED_AS'),
    e('EX-204', 'IC-003', 'INTEGRATED_IN'), e('EX-205', 'IC-003', 'INTEGRATED_IN'), e('EX-206', 'IC-003', 'INTEGRATED_IN'),
    e('IC-003', 'CODE-117', 'CONTAINED_IN'),
    e('IC-003', 'EV-5', 'VERIFIED_BY'), e('IC-003', 'AC-011-03', 'VERIFIED_BY', { note: 'obligation unmet' }), e('IC-003', 'WR-003', 'VERIFIED_BY'),
    e('EV-5', 'GATE-003', 'EVALUATED_IN'), e('AC-011-03', 'GATE-003', 'EVALUATED_IN'), e('WR-003', 'GATE-003', 'EVALUATED_IN'),
    e('GATE-003', 'R2', 'GATES'), e('APR-302', 'R2', 'AUTHORIZES'), e('R1', 'R2', 'SUCCEEDED_BY'),
  ],
};

// ───────────────────────────── DC-004 · Bug Fix ─────────────────────────────
const BG: Journey = {
  id: 'BG', cycle: 'DC-004', name: 'Bug Fix', objective: 'Reject updates to CLOSED tickets safely',
  direction: 'Failure → Spec → Code path → Repair', outcome: 'Reproduced, repaired, regression-proven R3',
  stages: [
    { k: 'TRIAGE', lane: 'intent', out: 'Defect with source and severity context' },
    { k: 'REPRODUCTION', lane: 'evidence', out: 'REPRODUCTION evidence before repair' },
    { k: 'EXPECTED_BEHAVIOR', lane: 'intent', out: 'Expected behaviour with authoritative provenance' },
    { k: 'ROOT_CAUSE', lane: 'code', out: 'Reasoned cause hypothesis with trace + code evidence' },
    { k: 'DEVELOPMENT', lane: 'exec', out: 'Repair contract, attempt, worktree and candidate' },
    { k: 'INTEGRATION', lane: 'code', out: 'New integration candidate and refreshed links' },
    { k: 'REGRESSION', lane: 'evidence', out: 'After evidence bound to repaired candidate' },
    { k: 'ASSURANCE', lane: 'evidence', out: 'Warden / Sentinel results finalized by Olympus' },
    { k: 'RELEASE', lane: 'outcome', out: 'R3 manifest and outcome' },
    { k: 'COMPLETE', lane: 'outcome', out: 'Defect → failure → intent → repair → proof → R3' },
  ],
  live: 6,
  focus: 'EV-901',
  defaults: { S03: 'EXP-017', S04: 'TASK-402', S05: 'EX-402', S06: 'CODE-117', S07: 'DEF-017', S09: 'EV-951', S10: 'R3' },
  base: { released: 'R2', releasedSha: 'c83a12d', target: 'R3', canonical: 'IC-004 @ e5d1c04', candidate: 'EX-402 · 0b9e3f1' },
  nodes: [
    n({ id: 'DEF-017', lane: 'intent', kind: 'Defect', ref: 'DEF-017', title: 'CLOSED update → HTTP 500', at: 0, st: [[0, 'recorded']], sub: 'ISSUE-882 · S2', prov: 'FACT' }),
    n({ id: 'SPEC-017', lane: 'intent', kind: 'Spec · trusted', ref: 'SPEC-017 v3', title: 'Ticket lifecycle', at: 0, st: [[0, 'approved']], prov: 'DECISION', origin: 'HUMAN_CONFIRMED · DC-002' }),
    n({ id: 'EXP-017', lane: 'intent', kind: 'Expected', ref: 'AC-017-04', title: '409 Conflict, unchanged', at: 2, st: [[2, 'resolved']], prov: 'DECISION', origin: 'SPEC-017 v3 · DEC-004',
      why: { resolved: { summary: 'Expected behaviour resolved from the canonical spec promoted in DC-002. No checkpoint needed; nothing was invented.', checks: [['Canonical FeatureSpec searched', true, 'SPEC-017 v3 · AC-017-04'], ['Behavioural baseline searched', true, 'none for CLOSED'], ['ProductSource searched', true, 'PRD v1 silent'], ['Authoritative provenance', true, 'HUMAN_CONFIRMED · DEC-004']], policy: 'bugfix.expected_behaviour@v1' } } }),
    n({ id: 'IMPL-017R', lane: 'intent', kind: 'Repair spec', ref: 'IMPL-017r', title: 'Minimal repair boundary', at: 3, st: [[3, 'proposed'], [4, 'approved']] }),

    n({ id: 'TASK-401', lane: 'work', kind: 'Verify task', ref: 'TASK-401', title: 'Reproduce defect', at: 1, st: [[1, 'running'], [2, 'completed']] }),
    n({ id: 'TASK-402', lane: 'work', kind: 'Repair task', ref: 'TASK-402', title: 'Minimal repair', at: 4, st: [[4, 'running'], [5, 'completed']] }),
    n({ id: 'TASK-403', lane: 'work', kind: 'Verify task', ref: 'TASK-403', title: 'Regression test', at: 4, st: [[4, 'blocked'], [6, 'running'], [7, 'completed']] }),

    n({ id: 'EX-401', lane: 'exec', kind: 'Attempt', ref: 'EX-401', title: 'Reproduction run', at: 1, st: [[1, 'running'], [2, 'completed']], sub: 'read-only · diagnostic' }),
    n({ id: 'EX-402', lane: 'exec', kind: 'Attempt', ref: 'EX-402', title: 'Repair attempt', at: 4, st: [[4, 'running'], [5, 'completed']], sub: '1 denied tool action', sha: 'c83a12d', workspace: 'olympus/EX-402' }),
    n({ id: 'EX-403', lane: 'exec', kind: 'Attempt', ref: 'EX-403', title: 'Regression run', at: 6, st: [[6, 'running'], [7, 'completed']], sub: 'target e5d1c04' }),

    n({ id: 'CODE-130', lane: 'code', kind: 'Route', ref: 'CODE-130', title: 'PATCH /tickets/{id}', at: 0, st: [[0, 'canonical']], prov: 'FACT', impact: 'direct' }),
    n({ id: 'CODE-117', lane: 'code', kind: 'Symbol', ref: 'CODE-117', title: 'TicketService.update_status', at: 0, st: [[0, 'canonical']], prov: 'FACT', impact: 'direct', sub: 'failure path' }),
    n({ id: 'RC-004', lane: 'code', kind: 'Hypothesis', ref: 'RC-004', title: 'Missing CLOSED guard', at: 3, st: [[3, 'hypothesis'], [6, 'supported']], prov: 'INFERENCE', conf: 0.78, sub: 'p = 0.78',
      why: { hypothesis: { summary: 'Reasoned from the runtime trace and code graph. A probability is not a proven cause; the repair is still bounded to this path and must be proven by the original reproduction.', checks: [['Trace correlates to symbol', true, 'ticket_service.py:88'], ['Code path evidence linked', true, 'CODE-130 → CODE-117'], ['Cause proven', false, 'needs after-proof']], policy: 'bugfix.root_cause@v1' } } }),
    n({ id: 'IC-004', lane: 'code', kind: 'Integration', ref: 'IC-004', title: 'Repaired candidate', at: 5, st: [[5, 'integrated']], sub: '@ e5d1c04', sha: 'e5d1c04' }),

    n({ id: 'EV-901', lane: 'evidence', kind: 'Failure proof', ref: 'EV-901', title: 'HTTP 500 before repair', at: 1, st: [[1, 'reproduced']], sub: 'before @ c83a12d', sha: 'c83a12d', workspace: 'Reproduction diagnostic context',
      why: { reproduced: { summary: 'Failure reproduced before any repair. This is a successful investigation, not an acceptance PASS. It stays reachable after the fix.', checks: [['Reproduction steps executed', true, 'TASK-401 / EX-401'], ['Bound to exact SHA', true, 'c83a12d'], ['Observed result matches report', true, 'HTTP 500']], policy: 'bugfix.reproduce_first@v1' } } }),
    n({ id: 'EV-951', lane: 'evidence', kind: 'After-proof', ref: 'EV-951', title: 'Now returns 409', at: 6, st: [[6, 'passed']], sub: 'after @ e5d1c04', sha: 'e5d1c04' }),
    n({ id: 'EV-952', lane: 'evidence', kind: 'Regression', ref: 'EV-952', title: 'New regression test', at: 6, st: [[6, 'running'], [7, 'passed']], sub: '@ e5d1c04' }),
    n({ id: 'EV-96', lane: 'evidence', kind: 'Baseline proof', ref: 'EV-961…963', title: 'Impacted baselines', at: 6, st: [[6, 'queued'], [7, 'passed']], stack: ['EV-961 BL-004 transitions', 'EV-962 BL-007 update OPEN', 'EV-963 BL-011 list'] }),
    n({ id: 'GATE-004', lane: 'evidence', kind: 'Gates', ref: 'GATE-004', title: 'Warden · Sentinel → gates', at: 7, st: [[7, 'blocked'], [8, 'passed']] }),
    n({ id: 'APR-401', lane: 'evidence', kind: 'Approval', ref: 'APR-401', title: 'Release approval', at: 8, st: [[8, 'pending'], [9, 'approved']], attn: { pending: 'Release approval APR-401 is waiting for you' } }),

    n({ id: 'R2', lane: 'outcome', kind: 'Baseline', ref: 'R2', title: 'Current baseline', at: 0, st: [[0, 'baseline'], [9, 'historical']], sub: '@ c83a12d', sha: 'c83a12d' }),
    n({ id: 'R3', lane: 'outcome', kind: 'Outcome', ref: 'R3', title: 'Repair release', at: 8, st: [[8, 'approval-pending'], [9, 'released']], sub: 'pins e5d1c04' }),
  ],
  edges: [
    e('DEF-017', 'TASK-401', 'INVESTIGATED_BY'), e('TASK-401', 'EX-401', 'EXECUTED_AS'), e('EX-401', 'EV-901', 'PRODUCED'), e('DEF-017', 'EV-901', 'REPRODUCED_AS'),
    e('SPEC-017', 'EXP-017', 'DERIVED_FROM'), e('DEF-017', 'EXP-017', 'VIOLATES'),
    e('CODE-130', 'CODE-117', 'CALLS'), e('EV-901', 'RC-004', 'SUPPORTS', { kind: 'inferred', conf: 0.78 }), e('CODE-117', 'RC-004', 'LOCATED_IN', { kind: 'inferred' }),
    e('RC-004', 'IMPL-017R', 'SCOPES'), e('EXP-017', 'IMPL-017R', 'DERIVED_FROM'),
    e('IMPL-017R', 'TASK-402', 'DERIVED_FROM'), e('IMPL-017R', 'TASK-403', 'DERIVED_FROM'), e('TASK-402', 'TASK-403', 'DEPENDS_ON'),
    e('TASK-402', 'EX-402', 'EXECUTED_AS'), e('TASK-403', 'EX-403', 'EXECUTED_AS'), e('EX-402', 'IC-004', 'INTEGRATED_IN'), e('IC-004', 'CODE-117', 'CONTAINED_IN'),
    e('IC-004', 'EV-951', 'VERIFIED_BY'), e('EV-901', 'EV-951', 'REPROVED_BY'), e('EX-403', 'EV-952', 'PRODUCED'), e('IC-004', 'EV-96', 'VERIFIED_BY'),
    e('EV-951', 'GATE-004', 'EVALUATED_IN'), e('EV-952', 'GATE-004', 'EVALUATED_IN'), e('EV-96', 'GATE-004', 'EVALUATED_IN'),
    e('GATE-004', 'R3', 'GATES'), e('APR-401', 'R3', 'AUTHORIZES'), e('R2', 'R3', 'SUCCEEDED_BY'),
  ],
};

export const JOURNEYS: Journey[] = [GF, BF, FC, BG];
export const journeyById = (id: string) => JOURNEYS.find((j) => j.id === id || j.cycle === id)!;
