// Drill-down content per journey (live snapshot). Illustrative fixtures.
import type { JourneyId } from './model';

export type Contract = { objective: string; workType: string; inputs: string[]; base: string; allowed: string[]; constraints: string[]; prohibited: string[]; outputs: string[]; verification: string[]; escalation: string[]; version: string };
export type ExecEvent = [string, string, string, 'allowed' | 'denied' | 'platform' | 'failed' | 'passed']; // time, text, action, decision
export type ExecDetail = { task: string; attempt: string; contract: string; snapshot: string; base: string; capability: string; runtime: string; lease: string; workspace: string; snapHash: string; model: string; observed: string; tools: string[]; events: ExecEvent[]; diff?: [string, number, number][]; checkpoint?: { id: string; q: string; unknown: string; checked: string[]; answer: string; waiting: string }; history: { id: string; st: string; note: string }[] };

type Detail = {
  overview: { truth: [string, string, string][]; coverage: [string, number, number, string][]; cycles: { id: string; j: string; intent: string; outcome: string; st: string }[] };
  specs: { tree: { cap: string; items: [string, string, string][] }[]; mode: 'review' | 'recovered' | 'delta' | 'expected'; title: string; id: string; body: any; impl: { title: string; lines: string[]; status: string }; arch: { title: string; lines: string[]; note: string } };
  contracts: Record<string, Contract>;
  execs: Record<string, ExecDetail>;
  code: { scopes: { k: 'provisional' | 'canonical' | 'released'; label: string; ref: string; sha: string; note: string }[]; active: 'provisional' | 'canonical' | 'released'; tree: { file: string; symbols: [string, string?][] }[]; symbol: { name: string; file: string; kind: string; excerpt: string[]; delta?: string; relations: [string, string, string, string][]; links: { spec: string; origin: string; conf: string; evidence: string }[] }; banner: string };
  trace: { title: string; direction: string; chain: { layer: string; text: string; ids: string[]; rel?: string; prov?: string; hist?: string }[]; answer: string[] };
  impact: { mode: string; title: string; lead: string; directLabel: string; direct: [string, string, string][]; inferredLabel: string; inferred: [string, string, string][]; scope: { label: string; lines: string[] }[]; note: string };
  assurance: { mode: 'gates' | 'readiness' | 'repair'; target: string; banner: string; groups: { name: string; rows: [string, string, string, string, string?][] }[]; checks: [string, boolean | null, string?][]; findings: [string, string, string][]; note: string };
  release: { mode: 'release' | 'handoff'; id: string; title: string; manifest: [string, string][]; eligibility: [string, string, string][]; approvals: [string, string, string][]; truth: [string, string][]; history: [string, string, string][] };
};

export const DETAIL: Record<JourneyId, Detail> = {
  GF: {
    overview: {
      truth: [['Released baseline', 'None yet', 'First release R1 is this cycle’s target'], ['Canonical assurance index', '—', 'Created when IC-001 integrates'], ['Product model', '2 features', 'SPEC-001 v1 · SPEC-002 v1 approved'], ['Behavioural baselines', '0', 'Greenfield proves new ACs instead']],
      coverage: [['Spec → code mapping', 0, 2, 'specs with principal symbols · none integrated yet'], ['Mandatory AC proof for R1', 0, 12, 'ACs with exact-SHA evidence'], ['Executable baseline coverage', 0, 0, 'no baselines exist yet']],
      cycles: [{ id: 'DC-001', j: 'Greenfield', intent: 'Build SupportDesk', outcome: 'R1 (target)', st: 'running' }],
    },
    specs: {
      tree: [{ cap: 'Ticket management', items: [['SPEC-001', 'Create ticket', 'approved'], ['SPEC-002', 'Update ticket status', 'approved']] }, { cap: 'Agent workspace', items: [['FEAT-003', 'Assign ticket', 'future']] }],
      mode: 'review', title: 'Update ticket status', id: 'SPEC-002 v1',
      body: {
        source: 'PS-001 v1 §3.2 — “Agents move tickets between OPEN, IN_PROGRESS and CLOSED.”',
        rules: ['status ∈ {OPEN, IN_PROGRESS, CLOSED}', 'transition OPEN → IN_PROGRESS → CLOSED', 'CLOSED is terminal — clarification CHK-012 open'],
        acs: [['AC-002-01', 'Valid transition persists new status', 'Unit + API evidence at integrated SHA'], ['AC-002-02', 'Invalid transition is rejected', 'API evidence at integrated SHA'], ['AC-002-03', 'Reopen behaviour for CLOSED', 'Blocked by CHK-012']],
        question: { id: 'CHK-012', text: 'Can a CLOSED ticket be reopened? PS-001 is silent; EX-104 is waiting.' },
      },
      impl: { title: 'IMPL-001 v1', status: 'approved', lines: ['TicketModel · TicketRepository · TicketService · TicketAPI', 'POST /tickets · PATCH /tickets/{id}', 'Persistence: tickets', 'Verification: unit · integration · API'] },
      arch: { title: 'ARCH-001 v1', lines: ['API → Service → Repository → PostgreSQL', 'FastAPI · Pydantic v2 · SQLAlchemy'], note: 'Architecture is project-wide. ImplementationSpecs realize it and cannot silently redefine it.' },
    },
    contracts: {
      'TASK-101': { version: 'TC-101 v1', objective: 'Define ticket API and data contract', workType: 'CODE_CHANGE', inputs: ['SPEC-001 v1', 'SPEC-002 v1', 'IMPL-001 v1'], base: 'a1f0c22', allowed: ['app/schemas/*', 'app/api/contracts.py', 'tests/contracts/*'], constraints: ['Pydantic v2 models only'], prohibited: ['Authentication changes', 'Release branch writes'], outputs: ['candidate_commit', 'changed_files', 'test_results'], verification: ['unit_tests'], escalation: ['architecture_change: REQUIRE_APPROVAL'] },
      'TASK-102': { version: 'TC-102 v1', objective: 'Implement ticket model and repository', workType: 'CODE_CHANGE', inputs: ['SPEC-001 v1', 'IMPL-001 v1', 'TC-101 output'], base: 'a1f0c22', allowed: ['app/models/*', 'app/repositories/*', 'tests/tickets/*'], constraints: ['default status OPEN'], prohibited: ['Authentication changes', 'Release branch writes'], outputs: ['candidate_commit', 'changed_files', 'test_results'], verification: ['unit_tests'], escalation: ['ambiguous_requirement: ASK_HUMAN'] },
      'TASK-103': { version: 'TC-103 v1', objective: 'Implement ticket API handlers', workType: 'CODE_CHANGE', inputs: ['SPEC-002 v1', 'IMPL-001 v1'], base: 'a1f0c22', allowed: ['app/api/tickets.py', 'app/services/*', 'tests/api/*'], constraints: ['preserve contract from TC-101'], prohibited: ['Authentication changes', 'Release branch writes'], outputs: ['candidate_commit', 'changed_files', 'test_results'], verification: ['unit_tests', 'api_tests'], escalation: ['ambiguous_requirement: ASK_HUMAN'] },
      'TASK-104': { version: 'TC-104 v1', objective: 'Integrate candidate commits into one candidate', workType: 'INTEGRATION', inputs: ['EX-101 1c4e2aa', 'EX-103 (pending)', 'EX-104 (pending)'], base: 'a1f0c22', allowed: ['merge_candidate'], constraints: ['deterministic merge order', 'conflicts become Findings'], prohibited: ['Silent conflict resolution'], outputs: ['integrated_sha'], verification: ['integration_checks'], escalation: ['conflict: CREATE_FINDING'] },
    },
    execs: {
      'EX-104': { task: 'TASK-103', attempt: 'Attempt 1', contract: 'TC-103 v1', snapshot: 'SNAP-104', base: 'a1f0c22', capability: 'Forge', runtime: 'LangGraphRuntime', lease: 'Released at checkpoint', workspace: 'olympus/EX-104 (retained)', snapHash: 'sha256:61de…02b9', model: 'implementation → alias forge-impl', observed: 'provider model id recorded per call · 3 calls · 18.2k in / 4.1k out', tools: ['repo.read', 'repo.write (scoped)', 'test.run', 'git.diff', 'system.create_checkpoint'],
        events: [['09:12', 'Snapshot SNAP-104 and lease created', 'platform', 'platform'], ['09:13', 'Worktree olympus/EX-104 provisioned at a1f0c22', 'git.worktree', 'allowed'], ['09:15', 'Read app/services/ticket_service.py', 'repo.read', 'allowed'], ['09:19', 'Wrote PATCH /tickets/{id} handler', 'repo.write', 'allowed'], ['09:21', 'Ambiguity: reopen semantics for CLOSED not in SPEC-002 v1', 'agent', 'platform'], ['09:21', 'Checkpoint CHK-012 created; artifacts persisted', 'system.create_checkpoint', 'allowed'], ['09:22', 'Runtime stopped; lease released', 'platform', 'platform']],
        diff: [['app/api/tickets.py', 64, 0], ['app/services/ticket_service.py', 22, 3]],
        checkpoint: { id: 'CHK-012', q: 'Can a CLOSED ticket be reopened by an agent?', unknown: 'Terminal-state semantics for CLOSED', checked: ['SPEC-002 v1 — silent', 'PS-001 v1 §3.2 — silent', 'ARCH-001 — not applicable'], answer: 'A decision that versions SPEC-002 (v2) or confirms CLOSED as terminal', waiting: 'EX-104 · TASK-103' },
        history: [{ id: 'EX-104', st: 'checkpointed', note: 'current · waiting on CHK-012' }] },
      'EX-103': { task: 'TASK-102', attempt: 'Attempt 2', contract: 'TC-102 v1', snapshot: 'SNAP-103', base: 'a1f0c22', capability: 'Forge', runtime: 'LangGraphRuntime', lease: 'worker-01 · heartbeat 3s ago', workspace: 'olympus/EX-103', snapHash: 'sha256:9a07…c3d1', model: 'implementation → alias forge-impl', observed: 'provider model id recorded per call · 5 calls', tools: ['repo.read', 'repo.write (scoped)', 'test.run', 'git.diff', 'git.commit'],
        events: [['09:31', 'Snapshot SNAP-103 and lease created', 'platform', 'platform'], ['09:32', 'Worktree olympus/EX-103 at a1f0c22', 'git.worktree', 'allowed'], ['09:36', 'Wrote app/models/ticket.py', 'repo.write', 'allowed'], ['09:40', 'Unit tests passed (41 / 41)', 'test.run', 'passed']],
        diff: [['app/models/ticket.py', 48, 0], ['app/repositories/ticket_repository.py', 57, 0], ['tests/tickets/test_repository.py', 92, 0]],
        history: [{ id: 'EX-102', st: 'failed', note: '3 unit tests failed · retained' }, { id: 'EX-103', st: 'running', note: 'current attempt' }] },
    },
    code: {
      scopes: [{ k: 'provisional', label: 'Provisional candidate', ref: 'EX-103', sha: '7f2c1d9', note: 'Execution-scoped. Disposable. Never canonical.' }, { k: 'canonical', label: 'Canonical assurance target', ref: 'IC-001', sha: '—', note: 'Created after integration.' }, { k: 'released', label: 'Released baseline', ref: '—', sha: '—', note: 'No release yet.' }],
      active: 'provisional',
      banner: 'Viewing a provisional execution index. These symbols are not part of any canonical project baseline until IC-001 integrates.',
      tree: [{ file: 'app/models/ticket.py', symbols: [['Ticket'], ['TicketStatus']] }, { file: 'app/repositories/ticket_repository.py', symbols: [['TicketRepository.save'], ['TicketRepository.get']] }, { file: 'app/services/ticket_service.py', symbols: [['TicketService.create', 'principal'], ['_validate_subject']] }],
      symbol: { name: 'TicketService.create', file: 'app/services/ticket_service.py', kind: 'METHOD · principal', excerpt: ['def create(self, customer_id, subject, description):', '    _validate_subject(subject)', '    ticket = Ticket(customer_id, subject, description, status=OPEN)', '    return self.repository.save(ticket)'], relations: [['IMPLEMENTS', 'SPEC-001 v1', 'GENERATED_LINEAGE', '1.0'], ['CALLS', 'TicketRepository.save', 'AST', '—'], ['CALLS', '_validate_subject (helper, inherits context)', 'AST', '—'], ['VERIFIED_BY', 'test_create_ticket', 'pytest discovery', '—']], links: [{ spec: 'SPEC-001 v1', origin: 'GENERATED_LINEAGE', conf: '1.0', evidence: 'TASK-102 · EX-103 · 7f2c1d9' }] },
    },
    trace: {
      title: 'Why does TicketService.create exist?', direction: 'Product → Code',
      chain: [
        { layer: 'Origin', text: 'SupportDesk PRD v1 §3.1', ids: ['PS-001'], rel: 'DERIVED_FROM', prov: 'FACT' },
        { layer: 'Specification', text: 'Create ticket → AC-001-01…03', ids: ['SPEC-001'], rel: 'DERIVED_FROM', prov: 'DECISION' },
        { layer: 'Realization', text: 'IMPL-001 v1 under ARCH-001 v1', ids: ['IMPL-001', 'ARCH-001'], rel: 'DERIVED_FROM' },
        { layer: 'Planned work', text: 'TASK-102 → TC-102 v1', ids: ['TASK-102'], rel: 'EXECUTED_AS' },
        { layer: 'Execution', text: 'EX-103 → SNAP-103 @ a1f0c22', ids: ['EX-103'], rel: 'PRODUCED', hist: 'EX-102 failed · retained' },
        { layer: 'Code', text: 'Candidate 7f2c1d9 → IC-001 (future)', ids: ['IC-001', 'CODE-117'], rel: 'VERIFIED_BY' },
        { layer: 'Proof', text: 'AC evidence → gate → approval (future)', ids: ['EV-AC', 'GATE-001', 'APR-103'], rel: 'GATES' },
        { layer: 'Outcome', text: 'R1 (not yet eligible)', ids: ['R1'] },
      ],
      answer: ['It realizes SPEC-001 v1 through an approved implementation boundary and an attributed execution.', 'Link origin: GENERATED_LINEAGE — Olympus created the code through traced Task → Execution → Commit lineage, so confidence is 1.0.', 'Failed attempt EX-102 and its snapshot stay reachable from this chain.'],
    },
    impact: {
      mode: 'Architecture / realization boundaries', title: 'IMPL-001 realizes 2 features inside 4 components', lead: 'Greenfield has no existing code to impact. The explorer shows what the architecture allows each ImplementationSpec to touch.',
      directLabel: 'Realization boundary (from ARCH-001 v1)', direct: [['TicketAPI → TicketService', 'API layer may call service only', 'ARCH-001 rule A2'], ['TicketService → TicketRepository', 'Service owns business rules', 'ARCH-001 rule A3'], ['TicketRepository → tickets', 'Only repositories access tables', 'ARCH-001 rule A4'], ['tests/* → all layers', 'Verification may read every layer', 'IMPL-001 verification']],
      inferredLabel: 'Open architecture questions', inferred: [['Soft delete for tickets?', 'Not in PS-001 · deferred to later cycle', 'ASSUMPTION'], ['Reopen CLOSED tickets?', 'CHK-012 · affects SPEC-002', 'UNCERTAINTY']],
      scope: [{ label: 'Components', lines: ['TicketModel', 'TicketRepository', 'TicketService', 'TicketAPI'] }, { label: 'Contracts', lines: ['POST /tickets', 'PATCH /tickets/{id}'] }, { label: 'Architecture delta', lines: ['ARCH-001 v1 — new baseline'] }],
      note: 'Architecture review is required by policy before planning. Approved in APR-102.',
    },
    assurance: {
      mode: 'gates', target: 'IC-001 · 9e31ab7', banner: 'Final proof targets IC-001 at 9e31ab7. Nothing has integrated yet at this stage.',
      groups: [{ name: 'Mandatory acceptance criteria', rows: [['AC-001-01 · valid request creates ticket', 'EV-101', '9e31ab7', 'future'], ['AC-001-02 · unique id returned', 'EV-102', '9e31ab7', 'future'], ['AC-002-01 · valid transition persists', 'EV-104', '9e31ab7', 'future'], ['… 9 more ACs', '—', '—', 'future']] }, { name: 'Independent review', rows: [['Warden engineering review', 'WR-001', '9e31ab7', 'future']] }],
      checks: [['Integration candidate READY', null, 'IC-001 not created'], ['Evidence SHA == integrated SHA', null], ['Mandatory coverage complete', null, '0 / 12'], ['Blocking findings == 0', null], ['Required approvals present', null]],
      findings: [], note: 'Gates are evaluated only after integration establishes the exact combined SHA.',
    },
    release: {
      mode: 'release', id: 'R1', title: 'R1 · first release',
      manifest: [['Delivery cycle', 'DC-001 · Greenfield Build'], ['Objective', 'Build SupportDesk'], ['Specifications', 'SPEC-001 v1 · SPEC-002 v1'], ['Integration candidate', 'IC-001 (not yet created)'], ['Integrated SHA', '—'], ['Evidence', '0 / 12 mandatory'], ['Approvals', 'APR-103 (future)'], ['Blocking findings', '—']],
      eligibility: [['manifest valid', 'future', ''], ['integration candidate is current', 'future', ''], ['required gates pass', 'future', ''], ['required approvals exist', 'future', ''], ['required executions not stale', 'future', ''], ['blocking findings == 0', 'future', ''], ['mandatory ACs have evidence', 'future', ''], ['required baselines pass', 'n-a', 'no baselines in Greenfield']],
      approvals: [['APR-101', 'Scope approval', 'approved'], ['APR-102', 'Architecture approval', 'approved'], ['APR-103', 'Release approval', 'future']],
      truth: [['Canonical assurance target', '—'], ['Current released baseline', 'none'], ['Deployment', 'Optional · not requested']],
      history: [],
    },
  },

  BF: {
    overview: {
      truth: [['Released baseline', 'R1', '9e31ab7 · unchanged by this cycle'], ['Canonical index', 'IDX-002', '@ 9e31ab7 · 214 symbols'], ['Product model', '1 recovered', 'REC-017 proposed · REC-018 proposed'], ['Behavioural baselines', '0 trusted', '14 proposals pending']],
      coverage: [['Spec → code mapping', 2, 9, 'routes with a recovered spec · DISCOVERED links'], ['Recovered intent promoted', 0, 2, 'recovered specs reviewed and trusted'], ['Executable baseline coverage', 0, 14, 'baseline proposals executed at 9e31ab7']],
      cycles: [{ id: 'DC-001', j: 'Greenfield', intent: 'Build SupportDesk', outcome: 'R1 · 9e31ab7', st: 'released' }, { id: 'DC-002', j: 'Brownfield', intent: 'Understand existing repository', outcome: 'B1 (target)', st: 'running' }],
    },
    specs: {
      tree: [{ cap: 'Ticket management (recovered)', items: [['REC-018', 'Ticket creation', 'inferred'], ['REC-017', 'Ticket lifecycle', 'inferred']] }, { cap: 'Unmapped routes', items: [['CODE-133', 'GET /reports/sla', 'future']] }],
      mode: 'recovered', title: 'Ticket lifecycle', id: 'REC-017',
      body: {
        rows: [
          ['Create sets status OPEN', 'FACT · test_create_ticket', 'INFERENCE · intended default', 'Pending promotion'],
          ['OPEN → IN_PROGRESS → CLOSED', 'FACT · route + enum', 'INFERENCE · 0.84', 'Pending promotion'],
          ['Update on CLOSED ticket', 'FACT · HTTP 500 (probe)', 'UNCERTAINTY · UNC-004', 'Needs decision'],
        ],
        evidence: ['app/services/ticket_service.py:72–96', 'app/api/tickets.py:40–58', 'tests/test_ticket_status.py (6 tests)'],
      },
      impl: { title: 'No ImplementationSpec', status: 'n-a', lines: ['Brownfield recovers behaviour; it does not plan a feature build.', 'Recovered architecture: ARCH-REC-001 (INFERENCE)'] },
      arch: { title: 'ARCH-REC-001 · recovered', lines: ['API → Service → Repository → PostgreSQL', 'Observed from imports and calls at 9e31ab7'], note: 'Recovered architecture is an inference until reviewed. Structural facts are canonical; their intent is not.' },
    },
    contracts: {
      'TASK-201': { version: 'TC-201 v1', objective: 'Deterministic repository discovery', workType: 'ANALYSIS', inputs: ['REPO-01 @ 9e31ab7'], base: '9e31ab7', allowed: ['read: **/*'], constraints: ['no model calls', 'deterministic parsers only'], prohibited: ['Any write', 'Network access'], outputs: ['code_index', 'structured_facts'], verification: ['schema / provenance checks'], escalation: [] },
      'TASK-202': { version: 'TC-202 v1', objective: 'Recover specifications from facts', workType: 'ANALYSIS', inputs: ['IDX-002 @ 9e31ab7', 'tests/*'], base: '9e31ab7', allowed: ['read: **/*', 'runtime probe: GET/PATCH sandbox'], constraints: ['label FACT / INFERENCE / UNCERTAINTY', 'attach provenance to every claim'], prohibited: ['Any write', 'Promoting intent'], outputs: ['recovered_specs', 'uncertainties', 'baseline_proposals'], verification: ['schema / provenance checks'], escalation: ['unknown_intent: CREATE_UNCERTAINTY'] },
      'TASK-203': { version: 'TC-203 v1', objective: 'Execute baseline proposals', workType: 'VERIFICATION', inputs: ['BL-001…014 proposals'], base: '9e31ab7', allowed: ['test workspace'], constraints: ['exact repository SHA'], prohibited: ['Source writes'], outputs: ['evidence'], verification: ['deterministic test evidence'], escalation: [] },
    },
    execs: {
      'EX-202': { task: 'TASK-202', attempt: 'Attempt 1', contract: 'TC-202 v1', snapshot: 'SNAP-202', base: '9e31ab7', capability: 'Scout', runtime: 'LangGraphRuntime', lease: 'worker-02 · heartbeat 2s ago', workspace: 'Read-only checkout @ 9e31ab7', snapHash: 'sha256:c2e8…7f10', model: 'analysis → alias scout-analysis', observed: 'provider model id recorded per call · 7 calls', tools: ['repo.read', 'index.query', 'probe.http (sandbox)'],
        events: [['14:02', 'Snapshot SNAP-202 created with IDX-002', 'platform', 'platform'], ['14:03', 'Queried 17 routes, 86 tests', 'index.query', 'allowed'], ['14:06', 'Probe PATCH /tickets/{id} on CLOSED → 500', 'probe.http', 'allowed'], ['14:07', 'Write attempt to tests/ blocked (read-only contract)', 'repo.write', 'denied'], ['14:09', 'Proposed REC-017 (0.84) with 3 files, 6 tests', 'artifact.create', 'allowed'], ['14:09', 'Raised UNC-004', 'artifact.create', 'allowed']],
        history: [{ id: 'EX-202', st: 'running', note: 'current · read-only' }] },
    },
    code: {
      scopes: [{ k: 'provisional', label: 'Provisional candidate', ref: '—', sha: '—', note: 'No writable execution in Brownfield.' }, { k: 'canonical', label: 'Canonical index', ref: 'IDX-002', sha: '9e31ab7', note: 'Deterministic, from the pinned repository SHA.' }, { k: 'released', label: 'Released baseline', ref: 'R1', sha: '9e31ab7', note: 'Same SHA. Not advanced by onboarding.' }],
      active: 'canonical',
      banner: 'Canonical structural facts at 9e31ab7. Links to intent are DISCOVERED and carry confidence until reviewed.',
      tree: [{ file: 'app/api/tickets.py', symbols: [['PATCH /tickets/{id}'], ['POST /tickets']] }, { file: 'app/services/ticket_service.py', symbols: [['TicketService.update_status', 'principal'], ['validate_transition']] }, { file: 'tests/test_ticket_status.py', symbols: [['test_open_to_in_progress'], ['test_in_progress_to_closed']] }],
      symbol: { name: 'TicketService.update_status', file: 'app/services/ticket_service.py', kind: 'METHOD · principal', excerpt: ['def update_status(self, ticket_id, status):', '    ticket = self.repository.get(ticket_id)', '    validate_transition(ticket.status, status)', '    ticket.status = status', '    return self.repository.save(ticket)'], relations: [['CALLED_BY', 'PATCH /tickets/{id}', 'AST', '—'], ['CALLS', 'validate_transition', 'AST', '—'], ['VERIFIED_BY', 'test_open_to_in_progress', 'pytest discovery', '—'], ['IMPLEMENTS', 'REC-017 (proposed)', 'DISCOVERED', '0.84']], links: [{ spec: 'REC-017', origin: 'DISCOVERED', conf: '0.84', evidence: 'EX-202 · route + 6 tests' }] },
    },
    trace: {
      title: 'What intent does update_status serve?', direction: 'Code → Product model',
      chain: [
        { layer: 'Existing release', text: 'R1 pins 9e31ab7', ids: ['R1'], rel: 'PINS', prov: 'FACT' },
        { layer: 'Repository', text: 'REPO-01 → IDX-002 @ 9e31ab7', ids: ['REPO-01', 'IDX-002'], rel: 'CONTAINED_IN', prov: 'FACT' },
        { layer: 'Code', text: 'PATCH /tickets/{id} → update_status', ids: ['CODE-130', 'CODE-117'], rel: 'OBSERVED_IN', prov: 'FACT' },
        { layer: 'Observed behaviour', text: 'OB-009 default OPEN · OB-011 CLOSED → 500', ids: ['OB-009', 'OB-011'], rel: 'RECOVERED_FROM', prov: 'FACT' },
        { layer: 'Recovered intent', text: 'REC-017 Ticket lifecycle · 0.84', ids: ['REC-017', 'UNC-004'], rel: 'PROMOTED_FROM', prov: 'INFERENCE' },
        { layer: 'Trusted intent', text: 'SPEC-017 v3 after DEC-004 (future)', ids: ['SPEC-017', 'DEC-004'], rel: 'VERIFIED_BY', prov: 'DECISION' },
        { layer: 'Baseline', text: 'BL-001…014 executed at 9e31ab7 (future)', ids: ['BL-1'], rel: 'EVALUATED_IN' },
        { layer: 'Readiness', text: 'RDY-001 → B1 READY_FOR_CHANGE (future)', ids: ['RDY-001', 'B1'] },
      ],
      answer: ['Direction is reversed: Brownfield starts from code and works back to intent.', 'Every link here is DISCOVERED with confidence and supporting code / test evidence. It becomes HUMAN_CONFIRMED only after review.', 'OB-011 is a fact about the code, not a fact about intent. It is not blessed as a baseline.'],
    },
    impact: {
      mode: 'Readiness gaps and unresolved uncertainty', title: '3 gaps block READY_FOR_CHANGE', lead: 'Brownfield does not change code. The explorer shows where the trusted model is incomplete.',
      directLabel: 'Coverage gaps (deterministic)', direct: [['GET /reports/sla', 'Route with no test and no recovered spec', 'IDX-002 route scan'], ['TicketService.merge', 'Principal symbol with no spec link', 'SpecCodeLink scan'], ['tickets.priority column', 'Schema field unused by any route', 'schema scan']],
      inferredLabel: 'Unresolved uncertainty', inferred: [['UNC-004 CLOSED immutability', 'Blocks REC-017 promotion and BL-004', 'UNCERTAINTY'], ['REC-018 SLA timer semantics', 'Confidence 0.71 < floor 0.80', 'INFERENCE']],
      scope: [{ label: 'Readiness predicates', lines: ['spec → code coverage ≥ 80% of routes', 'no critical uncertainty open', 'trusted baselines executed at 9e31ab7'] }, { label: 'Not in scope', lines: ['No new release', 'No feature build', 'No deployment'] }],
      note: 'Readiness gaps can create remediation work only under a separate, approved cycle.',
    },
    assurance: {
      mode: 'readiness', target: 'REPO-01 · 9e31ab7', banner: 'Brownfield readiness conditions — not release gates. Proof targets the exact repository SHA 9e31ab7.',
      groups: [{ name: 'Baseline proposals', rows: [['BL-001 POST /tickets → 201, OPEN', 'EV-601', '9e31ab7', 'future'], ['BL-004 status transitions', 'EV-604', '9e31ab7', 'future'], ['… 12 more', '—', '—', 'future']] }, { name: 'Promotion', rows: [['REC-017 Ticket lifecycle', 'APR-201', '9e31ab7', 'future'], ['UNC-004 CLOSED immutability', 'DEC-004', '—', 'decision']] }],
      checks: [['Canonical index at repository SHA', true, 'IDX-002 @ 9e31ab7'], ['Trusted baselines executed', false, '0 / 14'], ['Critical uncertainty resolved', false, 'UNC-004'], ['Recovered intent promoted with authority', false, '0 / 2'], ['Observed accidental behaviour excluded', true, 'OB-011 not blessed']],
      findings: [['UNC-004', 'Unknown intended behaviour for CLOSED updates', 'needs decision']], note: 'Readiness is a server computation over coverage, baseline evidence and unresolved uncertainty.',
    },
    release: {
      mode: 'handoff', id: 'B1', title: 'B1 · readiness handoff',
      manifest: [['Delivery cycle', 'DC-002 · Brownfield Onboarding'], ['Objective', 'Understand existing repository'], ['Repository', 'REPO-01 @ 9e31ab7'], ['Canonical index', 'IDX-002'], ['Trusted specs', '0 / 2 promoted'], ['Baselines', '0 / 14 executed'], ['Open uncertainties', 'UNC-004']],
      eligibility: [['canonical index matches repository SHA', 'passed', 'IDX-002 @ 9e31ab7'], ['coverage ≥ readiness floor', 'pending', '2 / 9 routes'], ['trusted baselines pass at SHA', 'future', ''], ['critical uncertainty resolved', 'decision', 'UNC-004'], ['recovered intent promoted', 'future', '']],
      approvals: [['APR-201', 'Knowledge promotion review', 'future']],
      truth: [['Existing release', 'R1 · 9e31ab7 · unchanged'], ['New release', 'None — Brownfield ends at readiness'], ['Deployment', 'Not applicable']],
      history: [['R1', 'DC-001', '9e31ab7']],
    },
  },

  FC: {
    overview: {
      truth: [['Released baseline', 'R1', '9e31ab7 · until R2 releases'], ['Canonical assurance index', 'IC-003', '@ c83a12d · re-indexed'], ['Product model', '9 features', '14 specs · SPEC-011 at v2'], ['Behavioural baselines', '14 trusted', 'B1 · 3 impacted by CR-004']],
      coverage: [['Spec → code mapping', 13, 14, 'specs with principal symbols at c83a12d'], ['Mandatory AC proof for R2', 11, 12, 'ACs with exact-SHA evidence'], ['Impacted baseline proof', 3, 3, 'baselines selected by IA-003']],
      cycles: [{ id: 'DC-001', j: 'Greenfield', intent: 'Build SupportDesk', outcome: 'R1 · 9e31ab7', st: 'released' }, { id: 'DC-002', j: 'Brownfield', intent: 'Understand existing repository', outcome: 'B1 · READY_FOR_CHANGE', st: 'rfc' }, { id: 'DC-003', j: 'Feature Change', intent: 'Add ticket priority', outcome: 'R2 (target)', st: 'running' }],
    },
    specs: {
      tree: [{ cap: 'Ticket management', items: [['SPEC-001', 'Create ticket', 'approved'], ['SPEC-011', 'Ticket priority', 'approved'], ['SPEC-017', 'Ticket lifecycle', 'approved']] }, { cap: 'Reporting', items: [['SPEC-021', 'SLA report', 'approved']] }],
      mode: 'delta', title: 'Ticket priority', id: 'SPEC-011 v2',
      body: {
        v1: ['subject', 'description', 'status = OPEN'],
        v2: ['subject', 'description', 'status = OPEN', '+ priority: LOW / MEDIUM / HIGH', '+ default: MEDIUM'],
        acs: [['AC-011-01', 'Priority accepted on create', 'Unit + API at integrated SHA'], ['AC-011-02', 'Default priority is MEDIUM', 'Unit at integrated SHA'], ['AC-011-03', 'Priority visible end-to-end', 'E2E at integrated SHA'], ['BL-001', 'Default status remains OPEN', 'Regression baseline']],
      },
      impl: { title: 'IMPL-011 v2', status: 'approved', lines: ['TicketModel · TicketService · API', 'Persistence: tickets.priority (enum)', 'Request contract: optional priority', 'Proof: unit · integration · E2E'] },
      arch: { title: 'ARCH-001 v1', lines: ['API → Service → Repository → PostgreSQL'], note: 'Architecture delta: none. A feature delta cannot silently redefine architecture.' },
    },
    contracts: {
      'TASK-101': { version: 'TC-101 v1', objective: 'Extend API / data contract with priority', workType: 'CODE_CHANGE', inputs: ['SPEC-011 v2', 'IMPL-011 v2'], base: '9e31ab7', allowed: ['app/schemas/*', 'tests/contracts/*'], constraints: ['optional field, default MEDIUM'], prohibited: ['Authentication changes', 'Release branch writes'], outputs: ['candidate_commit', 'changed_files', 'test_results'], verification: ['unit_tests'], escalation: [] },
      'TASK-104': { version: 'TC-104 v2', objective: 'Implement ticket priority persistence in bounded scope', workType: 'CODE_CHANGE', inputs: ['SPEC-011 v2', 'AC-011-01', 'AC-011-02', 'IA-003'], base: '9e31ab7', allowed: ['app/models/*', 'app/services/*', 'tests/tickets/*'], constraints: ['preserve existing API behaviour', 'preserve default OPEN state'], prohibited: ['Authentication changes', 'Release branch writes'], outputs: ['candidate_commit', 'changed_files', 'test_results'], verification: ['new_acceptance_tests', 'impacted_baselines', 'unit_tests'], escalation: ['architecture_change: REQUIRE_APPROVAL', 'ambiguous_requirement: ASK_HUMAN'] },
      'TASK-105': { version: 'TC-105 v1', objective: 'Accept priority in API handler', workType: 'CODE_CHANGE', inputs: ['SPEC-011 v2', 'TC-101 output'], base: '9e31ab7', allowed: ['app/api/tickets.py', 'tests/api/*'], constraints: ['backwards-compatible request'], prohibited: ['Authentication changes'], outputs: ['candidate_commit', 'test_results'], verification: ['api_tests'], escalation: [] },
      'TASK-106': { version: 'TC-106 v1', objective: 'Author E2E test for AC-011-03', workType: 'CODE_CHANGE', inputs: ['AC-011-03'], base: '9e31ab7', allowed: ['tests/e2e/*'], constraints: ['test only'], prohibited: ['Source writes outside tests/'], outputs: ['candidate_commit'], verification: ['test lint'], escalation: [] },
    },
    execs: {
      'EX-204': { task: 'TASK-104', attempt: 'Attempt 2', contract: 'TC-104 v2', snapshot: 'SNAP-204', base: '9e31ab7', capability: 'Forge', runtime: 'LangGraphRuntime', lease: 'worker-02 · heartbeat active', workspace: 'olympus/EX-204', snapHash: 'sha256:8c21…17ae', model: 'implementation → alias forge-impl', observed: 'provider model id recorded per call · 4 calls · 22.6k in / 3.8k out', tools: ['repo.read', 'repo.write (scoped)', 'test.run', 'git.diff', 'git.commit'],
        events: [['10:42', 'Snapshot SNAP-204 and lease created', 'platform', 'platform'], ['10:43', 'Worktree olympus/EX-204 at 9e31ab7', 'git.worktree', 'allowed'], ['10:44', 'Allowed file inspected: app/models/ticket.py', 'repo.read', 'allowed'], ['10:47', 'Unit tests failed; evidence retained', 'test.run', 'failed'], ['10:49', 'Implementation corrected in allowed scope', 'repo.write', 'allowed'], ['10:52', 'Unit tests passed (48 / 48)', 'test.run', 'passed'], ['10:53', 'Candidate commit 4a871dc', 'git.commit', 'allowed']],
        diff: [['app/models/ticket.py', 14, 1], ['app/services/ticket_service.py', 19, 2], ['migrations/0007_priority.py', 21, 0], ['tests/tickets/test_priority.py', 66, 0]],
        history: [{ id: 'EX-203', st: 'stale', note: 'SNAP-203 pinned TC-104 v1 · retained' }, { id: 'EX-204', st: 'running', note: 'current attempt' }] },
    },
    code: {
      scopes: [{ k: 'provisional', label: 'Provisional candidate', ref: 'EX-204', sha: '4a871dc', note: 'Execution-scoped. Disposable.' }, { k: 'canonical', label: 'Canonical assurance target', ref: 'IC-003', sha: 'c83a12d', note: 'Exact integrated SHA. Final gates target this.' }, { k: 'released', label: 'Released baseline', ref: 'R1', sha: '9e31ab7', note: 'Does not advance on integration.' }],
      active: 'canonical',
      banner: 'Canonical assurance index advanced to c83a12d. Released baseline remains R1 at 9e31ab7 until R2 is executed.',
      tree: [{ file: 'app/models/ticket.py', symbols: [['Ticket', 'Δ'], ['TicketPriority', 'new']] }, { file: 'app/services/ticket_service.py', symbols: [['TicketService.update_priority', 'principal · new'], ['validate_priority', 'new']] }, { file: 'app/api/tickets.py', symbols: [['POST /tickets', 'Δ']] }],
      symbol: { name: 'TicketService.update_priority', file: 'app/services/ticket_service.py', kind: 'METHOD · principal · new at c83a12d', delta: '4 symbols re-indexed incrementally at c83a12d · 2 SpecCodeLinks refreshed', excerpt: ['def update_priority(self, ticket, priority):', '    validate_priority(priority)', '    ticket.priority = priority', '    return self.repository.save(ticket)'], relations: [['IMPLEMENTS', 'SPEC-011 v2', 'GENERATED_LINEAGE', '1.0'], ['CALLS', 'TicketRepository.save', 'AST', '—'], ['ACCESSES', 'tickets.priority', 'schema', '—'], ['VERIFIED_BY', 'test_update_priority', 'pytest discovery', '—']], links: [{ spec: 'SPEC-011 v2', origin: 'GENERATED_LINEAGE', conf: '1.0', evidence: 'TASK-104 · EX-204 · 4a871dc → IC-003' }] },
    },
    trace: {
      title: 'Why does update_priority exist?', direction: 'Product delta → Code delta',
      chain: [
        { layer: 'Origin', text: 'CR-004 · requested ticket priority (ISSUE-311)', ids: ['CR-004'], rel: 'DERIVED_FROM', prov: 'FACT' },
        { layer: 'Specification', text: 'SPEC-011 v1 → v2 · AC-011-01…03', ids: ['SPEC-011', 'APR-301'], rel: 'ASSESSED_IN', prov: 'DECISION' },
        { layer: 'Impact', text: 'IA-003 · 4 symbols · 6 tests · 3 baselines', ids: ['IA-003'], rel: 'DERIVED_FROM' },
        { layer: 'Planned work', text: 'IMPL-011 v2 → TASK-104 → TC-104 v2', ids: ['IMPL-011', 'TASK-104'], rel: 'EXECUTED_AS' },
        { layer: 'Execution', text: 'EX-204 → SNAP-204 @ 9e31ab7', ids: ['EX-204'], rel: 'INTEGRATED_IN', hist: 'EX-203 stale · retained' },
        { layer: 'Code', text: 'Candidate 4a871dc → IC-003 @ c83a12d', ids: ['IC-003', 'CODE-117'], rel: 'VERIFIED_BY' },
        { layer: 'Proof', text: 'EV-501 · EV-601…603 · AC-011-03 missing → GATE-003', ids: ['EV-5', 'AC-011-03', 'GATE-003'], rel: 'GATES' },
        { layer: 'Outcome', text: 'R2 · not eligible', ids: ['R2'] },
      ],
      answer: ['It realizes SPEC-011 v2 through an approved implementation boundary and an attributed execution.', 'Relationship origin: GENERATED_LINEAGE. A Brownfield equivalent would read DISCOVERED + confidence + source evidence, then HUMAN_CONFIRMED after review.', 'Stale attempt EX-203 and superseded TC-104 v1 remain reachable.'],
    },
    impact: {
      mode: 'Affected symbols / contracts / tests / baselines', title: 'Ticket priority affects 4 principal symbols', lead: 'Spec delta → structural paths → bounded change and verification. Direct impact comes from persisted relations; inferred expansion is labelled and carries rationale.',
      directLabel: 'Direct structural impact', direct: [['SPEC-011 → TicketService', 'Persisted IMPLEMENTS link', 'SpecCodeLink'], ['TicketService → TicketRepository', 'CALLS relationship', 'AST'], ['TicketRepository → tickets schema', 'ACCESSES relationship', 'schema'], ['test_update_priority', 'VERIFIED_BY relation', 'pytest'], ['BL-001 / BL-004 / BL-009', 'Preserve impacted existing behaviour', 'baseline selection']],
      inferredLabel: 'Inferred expansion (semantic)', inferred: [['NotificationFormatter', 'Formats ticket fields in e-mails; “priority” appears in template copy', '0.62'], ['GET /reports/sla', 'Sorts by urgency; may want priority', '0.41 · below floor, excluded']],
      scope: [{ label: 'Allowed paths', lines: ['app/models/ticket.py', 'app/services/ticket_service.py', 'app/api/tickets.py', 'tests/tickets/'] }, { label: 'Selected verification', lines: ['AC-011-01…03 (new)', 'BL-001, BL-004, BL-009 (impacted)'] }, { label: 'Risk · architecture', lines: ['Risk tier: MEDIUM', 'Architecture delta: none'] }],
      note: 'Each selected verification obligation records why it was chosen.',
    },
    assurance: {
      mode: 'gates', target: 'IC-003 · c83a12d', banner: 'All final proof targets IC-003 at c83a12d. Old-SHA evidence remains history and cannot satisfy this target.',
      groups: [
        { name: 'New acceptance criteria', rows: [['AC-011-01 priority accepted on create', 'EV-501', 'c83a12d', 'passed'], ['AC-011-02 default MEDIUM', 'EV-502', 'c83a12d', 'passed'], ['AC-011-03 priority visible end-to-end', '—', 'c83a12d', 'missing', 'E2E only at 4a871dc (provisional) — historical']] },
        { name: 'Impacted baselines', rows: [['BL-001 default status OPEN', 'EV-601', 'c83a12d', 'passed'], ['BL-004 status transitions', 'EV-602', 'c83a12d', 'passed'], ['BL-009 list ordering', 'EV-603', 'c83a12d', 'passed']] },
        { name: 'Independent review', rows: [['Warden engineering review', 'WR-003', 'c83a12d', 'passed', '0 blocking · 2 advisory']] },
      ],
      checks: [['Current index matches candidate', true, 'c83a12d'], ['Independent engineering review passed', true, 'WR-003'], ['Mandatory acceptance evidence complete', false, '11 / 12'], ['Blocking findings == 0', true], ['Required approvals present', false, 'APR-302 pending']],
      findings: [['F-311', 'Advisory: priority enum not exposed in OpenAPI description', 'advisory'], ['F-312', 'Advisory: migration lacks down() path', 'advisory']],
      note: 'Finding → remediation Task → new Execution → integration → targeted verification. Model assertion cannot substitute for executable proof.',
    },
    release: {
      mode: 'release', id: 'R2', title: 'R2 · versioned outcome manifest',
      manifest: [['Delivery cycle', 'DC-003 · Feature Change'], ['Objective', 'Add ticket priority'], ['Specifications', 'SPEC-011 v2 · IMPL-011 v2'], ['Integration candidate', 'IC-003'], ['Integrated SHA', 'c83a12d'], ['Evidence', 'EV-501, 502, 601–603 · AC-011-03 missing'], ['Gates', 'Warden PASS · Sentinel incomplete'], ['Approvals', 'APR-301 ✓ · APR-302 pending'], ['Blocking findings', '0']],
      eligibility: [['manifest valid', 'passed', ''], ['integration candidate is current', 'passed', 'IC-003'], ['required executions not stale', 'passed', 'EX-203 superseded, not required'], ['Warden + blocking findings', 'passed', '0 blocking'], ['mandatory AC / baseline evidence', 'missing', 'AC-011-03 E2E'], ['required gates pass', 'blocked', 'GATE-003'], ['human release approval', 'pending', 'APR-302']],
      approvals: [['APR-301', 'Spec delta approval', 'approved'], ['APR-302', 'Release approval', 'pending']],
      truth: [['Canonical assurance target', 'c83a12d'], ['Current released baseline', 'R1 · 9e31ab7'], ['Deployment', 'Not requested — separate, optional']],
      history: [['R1', 'DC-001', '9e31ab7'], ['B1', 'DC-002', '9e31ab7 · no release']],
    },
  },

  BG: {
    overview: {
      truth: [['Released baseline', 'R2', 'c83a12d'], ['Canonical assurance index', 'IC-004', '@ e5d1c04 · repaired'], ['Product model', '9 features', 'SPEC-017 v3 governs the defect'], ['Behavioural baselines', '15 trusted', '3 impacted by DEF-017']],
      coverage: [['Spec → code mapping', 14, 14, 'specs with principal symbols at e5d1c04'], ['Defect proof for R3', 1, 2, 'original reproduction + regression test'], ['Impacted baseline proof', 0, 3, 'baselines queued at e5d1c04']],
      cycles: [{ id: 'DC-001', j: 'Greenfield', intent: 'Build SupportDesk', outcome: 'R1 · 9e31ab7', st: 'released' }, { id: 'DC-002', j: 'Brownfield', intent: 'Understand existing repository', outcome: 'B1 · READY_FOR_CHANGE', st: 'rfc' }, { id: 'DC-003', j: 'Feature Change', intent: 'Add ticket priority', outcome: 'R2 · c83a12d', st: 'released' }, { id: 'DC-004', j: 'Bug Fix', intent: 'Reject CLOSED updates safely', outcome: 'R3 (target)', st: 'running' }],
    },
    specs: {
      tree: [{ cap: 'Ticket management', items: [['SPEC-001', 'Create ticket', 'approved'], ['SPEC-011', 'Ticket priority', 'approved'], ['SPEC-017', 'Ticket lifecycle', 'approved']] }],
      mode: 'expected', title: 'Expected behaviour for DEF-017', id: 'AC-017-04',
      body: {
        observed: 'PATCH /tickets/{id} on a CLOSED ticket returns HTTP 500 (EV-901 @ c83a12d)',
        expected: 'Return 409 Conflict and leave the ticket unchanged',
        source: 'SPEC-017 v3 · AC-017-04 · HUMAN_CONFIRMED via DEC-004 in DC-002',
        checked: [['SPEC-017 v3 FeatureSpec', 'found AC-017-04', true], ['Behavioural baselines', 'none cover CLOSED updates', null], ['PS-001 v1 §3.2', 'silent', null]],
        fallback: 'If no authoritative source existed, Olympus would checkpoint and ask for a human or spec decision instead of inventing expected behaviour.',
      },
      impl: { title: 'IMPL-017r', status: 'approved', lines: ['Add CLOSED guard in TicketService.update_status', 'Return 409 via existing error mapper', 'No schema change · no API shape change', 'Proof: original reproduction + regression + baselines'] },
      arch: { title: 'ARCH-001 v1', lines: ['API → Service → Repository → PostgreSQL'], note: 'No architecture redesign. No unrelated feature work.' },
    },
    contracts: {
      'TASK-401': { version: 'TC-401 v1', objective: 'Reproduce DEF-017 at the released SHA', workType: 'VERIFICATION', inputs: ['DEF-017', 'ISSUE-882 steps'], base: 'c83a12d', allowed: ['test workspace', 'probe.http (sandbox)'], constraints: ['no source writes'], prohibited: ['Any repository write'], outputs: ['reproduction_evidence'], verification: ['deterministic runtime evidence'], escalation: [] },
      'TASK-402': { version: 'TC-402 v1', objective: 'Minimal repair: reject updates to CLOSED tickets', workType: 'CODE_CHANGE', inputs: ['AC-017-04', 'RC-004', 'IMPL-017r'], base: 'c83a12d', allowed: ['app/services/ticket_service.py', 'tests/tickets/*'], constraints: ['minimal change', 'no API shape change'], prohibited: ['Authentication changes', 'Unrelated refactors', 'Release branch writes'], outputs: ['candidate_commit', 'changed_files', 'test_results'], verification: ['original_reproduction', 'regression_test', 'impacted_baselines'], escalation: ['scope_expansion: REQUIRE_APPROVAL'] },
      'TASK-403': { version: 'TC-403 v1', objective: 'Run regression obligations at repaired SHA', workType: 'VERIFICATION', inputs: ['IC-004 @ e5d1c04', 'BL-004, BL-007, BL-011'], base: 'e5d1c04', allowed: ['test workspace'], constraints: ['exact integrated SHA'], prohibited: ['Source writes'], outputs: ['evidence'], verification: ['deterministic test evidence'], escalation: [] },
    },
    execs: {
      'EX-402': { task: 'TASK-402', attempt: 'Attempt 1', contract: 'TC-402 v1', snapshot: 'SNAP-402', base: 'c83a12d', capability: 'Forge', runtime: 'LangGraphRuntime', lease: 'Completed · lease returned', workspace: 'olympus/EX-402', snapHash: 'sha256:0f4b…a913', model: 'implementation → alias forge-impl', observed: 'provider model id recorded per call · 3 calls', tools: ['repo.read', 'repo.write (scoped)', 'test.run', 'git.diff', 'git.commit'],
        events: [['16:20', 'Snapshot SNAP-402 and lease created', 'platform', 'platform'], ['16:21', 'Worktree olympus/EX-402 at c83a12d', 'git.worktree', 'allowed'], ['16:23', 'Read ticket_service.py:72–96', 'repo.read', 'allowed'], ['16:26', 'Write app/auth/session.py — outside allowed_scope; logged, not retried wider', 'repo.write', 'denied'], ['16:27', 'Added CLOSED guard in update_status', 'repo.write', 'allowed'], ['16:29', 'Original reproduction now returns 409 (local)', 'test.run', 'passed'], ['16:30', 'Candidate commit 0b9e3f1', 'git.commit', 'allowed']],
        diff: [['app/services/ticket_service.py', 4, 0], ['tests/tickets/test_closed_update.py', 31, 0]],
        history: [{ id: 'EX-402', st: 'completed', note: 'candidate 0b9e3f1 · 1 denied action' }] },
    },
    code: {
      scopes: [{ k: 'provisional', label: 'Provisional candidate', ref: 'EX-402', sha: '0b9e3f1', note: 'Execution-scoped.' }, { k: 'canonical', label: 'Canonical assurance target', ref: 'IC-004', sha: 'e5d1c04', note: 'Repaired SHA. Final gates target this.' }, { k: 'released', label: 'Released baseline', ref: 'R2', sha: 'c83a12d', note: 'Failure reproduced here (EV-901).' }],
      active: 'canonical',
      banner: 'Before and after are explicit: failure at c83a12d (R2), repair at e5d1c04 (IC-004).',
      tree: [{ file: 'app/api/tickets.py', symbols: [['PATCH /tickets/{id}', 'failure path']] }, { file: 'app/services/ticket_service.py', symbols: [['TicketService.update_status', 'principal · Δ'], ['validate_transition']] }, { file: 'tests/tickets/test_closed_update.py', symbols: [['test_update_closed_returns_409', 'new']] }],
      symbol: { name: 'TicketService.update_status', file: 'app/services/ticket_service.py', kind: 'METHOD · principal · repaired at e5d1c04', delta: 'Failure path: PATCH /tickets/{id} → update_status → repository.save (no CLOSED guard at c83a12d)', excerpt: ['def update_status(self, ticket_id, status):', '    ticket = self.repository.get(ticket_id)', '+   if ticket.status == CLOSED:', '+       raise TicketConflict(ticket_id)', '    validate_transition(ticket.status, status)', '    ...'], relations: [['IMPLEMENTS', 'SPEC-017 v3', 'HUMAN_CONFIRMED', '1.0'], ['CALLED_BY', 'PATCH /tickets/{id}', 'AST', '—'], ['VERIFIED_BY', 'test_update_closed_returns_409', 'pytest discovery', '—'], ['LOCATED_IN ←', 'RC-004 cause hypothesis', 'INFERENCE', '0.78']], links: [{ spec: 'SPEC-017 v3', origin: 'HUMAN_CONFIRMED', conf: '1.0', evidence: 'DEC-004 · DC-002' }, { spec: 'IMPL-017r', origin: 'GENERATED_LINEAGE', conf: '1.0', evidence: 'TASK-402 · EX-402 · 0b9e3f1' }] },
    },
    trace: {
      title: 'From defect to proven repair', direction: 'Failure → Spec → Code path → Repair',
      chain: [
        { layer: 'Defect', text: 'DEF-017 · CLOSED update → 500 (ISSUE-882)', ids: ['DEF-017'], rel: 'REPRODUCED_AS', prov: 'FACT' },
        { layer: 'Failure evidence', text: 'EV-901 before repair @ c83a12d', ids: ['EV-901'], rel: 'VIOLATES', prov: 'FACT' },
        { layer: 'Expected behaviour', text: 'SPEC-017 v3 · AC-017-04 → 409', ids: ['SPEC-017', 'EXP-017'], rel: 'SCOPES', prov: 'DECISION' },
        { layer: 'Root cause', text: 'RC-004 missing CLOSED guard · p = 0.78', ids: ['RC-004', 'CODE-117'], rel: 'DERIVED_FROM', prov: 'INFERENCE' },
        { layer: 'Repair', text: 'IMPL-017r → TASK-402 → EX-402 → 0b9e3f1', ids: ['IMPL-017R', 'TASK-402', 'EX-402'], rel: 'INTEGRATED_IN', hist: '1 denied out-of-scope action · logged' },
        { layer: 'Code', text: 'IC-004 @ e5d1c04', ids: ['IC-004'], rel: 'VERIFIED_BY' },
        { layer: 'Proof', text: 'EV-951 now 409 · EV-952 regression · EV-961…963 baselines', ids: ['EV-951', 'EV-952', 'EV-96'], rel: 'GATES' },
        { layer: 'Outcome', text: 'R3 (future)', ids: ['R3'] },
      ],
      answer: ['Failure evidence EV-901 remains reachable after the repair. It is history, not a current result.', 'Root cause stays an INFERENCE (0.78). It is supported, not proven, by the original reproduction passing at e5d1c04.', 'The repair contract denied one out-of-scope write; the attempt did not retry wider.'],
    },
    impact: {
      mode: 'Probable cause + minimal repair scope', title: 'One faulty path, one guarded symbol', lead: 'Failure, expected behaviour and probable cause are shown separately. Probability is never presented as proven cause.',
      directLabel: 'Failure path (runtime trace + code graph)', direct: [['PATCH /tickets/{id}', 'Entry route in EV-901 trace', 'runtime trace'], ['→ TicketService.update_status', 'CALLS · ticket_service.py:88', 'AST'], ['→ TicketRepository.save', 'Unhandled IntegrityError on closed_at', 'runtime trace'], ['BL-004 · BL-007 · BL-011', 'Baselines touching update_status', 'baseline selection']],
      inferredLabel: 'Cause hypotheses (inference)', inferred: [['RC-004 missing CLOSED guard', 'Trace stops at closed_at constraint; no status check before save', '0.78'], ['RC-005 stale ORM session', 'Would also 500; not supported by trace timing', '0.09 · rejected']],
      scope: [{ label: 'Minimal repair scope', lines: ['app/services/ticket_service.py', 'tests/tickets/test_closed_update.py'] }, { label: 'Required proof', lines: ['Original reproduction passes at e5d1c04', 'New regression test', 'Impacted baselines'] }, { label: 'Excluded', lines: ['No API shape change', 'No architecture change'] }],
      note: 'Repair scope is bounded to the probable path; scope expansion requires approval.',
    },
    assurance: {
      mode: 'repair', target: 'IC-004 · e5d1c04', banner: 'After-proof targets IC-004 at e5d1c04. Before-failure evidence at c83a12d is retained and labelled historical.',
      groups: [
        { name: 'Original failure', rows: [['Reproduction · before repair', 'EV-901', 'c83a12d', 'reproduced', 'historical — cannot satisfy current target'], ['Original reproduction · after repair', 'EV-951', 'e5d1c04', 'passed']] },
        { name: 'Regression', rows: [['test_update_closed_returns_409', 'EV-952', 'e5d1c04', 'running']] },
        { name: 'Impacted baselines', rows: [['BL-004 status transitions', 'EV-961', 'e5d1c04', 'queued'], ['BL-007 update OPEN ticket', 'EV-962', 'e5d1c04', 'queued'], ['BL-011 list tickets', 'EV-963', 'e5d1c04', 'queued']] },
      ],
      checks: [['Current index matches candidate', true, 'e5d1c04'], ['Original failure now passes', true, 'EV-951'], ['Regression evidence present', null, 'EV-952 running'], ['Impacted baselines pass', null, 'queued'], ['Independent review (Warden / Sentinel)', null, 'starts in ASSURANCE'], ['Required approvals present', null, 'APR-401 future']],
      findings: [], note: 'No producer self-certification: Forge’s local 409 does not count. Only Sentinel evidence at e5d1c04 does.',
    },
    release: {
      mode: 'release', id: 'R3', title: 'R3 · repair release',
      manifest: [['Delivery cycle', 'DC-004 · Bug Fix'], ['Objective', 'Reject updates to CLOSED tickets'], ['Defect', 'DEF-017 · ISSUE-882'], ['Integration candidate', 'IC-004'], ['Integrated SHA', 'e5d1c04'], ['Evidence', 'EV-901 (before) · EV-951 · EV-952 · EV-961–963'], ['Approvals', 'APR-401 (future)'], ['Blocking findings', '0']],
      eligibility: [['manifest valid', 'future', ''], ['integration candidate is current', 'passed', 'IC-004'], ['original failure now passes', 'passed', 'EV-951'], ['regression evidence present', 'running', 'EV-952'], ['impacted baselines pass', 'queued', ''], ['required gates pass', 'future', ''], ['human release approval', 'future', 'APR-401']],
      approvals: [['APR-401', 'Release approval', 'future']],
      truth: [['Canonical assurance target', 'e5d1c04'], ['Current released baseline', 'R2 · c83a12d'], ['Deployment', 'Not requested — separate, optional']],
      history: [['R1', 'DC-001', '9e31ab7'], ['B1', 'DC-002', 'no release'], ['R2', 'DC-003', 'c83a12d']],
    },
  },
};
