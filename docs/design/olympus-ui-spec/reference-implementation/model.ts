// Olympus UI model — vocabulary shared by every component and screen.
// Fixture data (SupportDesk) lives in data.ts. Everything here is presentation
// vocabulary proposed for the UI; map to persisted types during implementation.

export type LaneId = 'intent' | 'work' | 'exec' | 'code' | 'evidence' | 'outcome';
export type ScreenId = 'S01' | 'S02' | 'S03' | 'S04' | 'S05' | 'S06' | 'S07' | 'S08' | 'S09' | 'S10' | 'INT' | 'AUD';
export type JourneyId = 'GF' | 'BF' | 'FC' | 'BG';
export type Tone = 'neutral' | 'active' | 'success' | 'attention' | 'failure' | 'future' | 'muted';
export type Prov = 'FACT' | 'INFERENCE' | 'UNCERTAINTY' | 'ASSUMPTION' | 'DECISION';
export type Lens = 'lifecycle' | 'trace' | 'impact' | 'blockers';

export const LANES: { id: LaneId; code: string; name: string; short: string; screen: ScreenId; question: string }[] = [
  { id: 'intent', code: 'IN', name: 'Intent & product', short: 'Intent', screen: 'S03', question: 'What is wanted, and which version is approved?' },
  { id: 'work', code: 'WK', name: 'Planned work', short: 'Work', screen: 'S04', question: 'What durable work exists, and why is it ready or blocked?' },
  { id: 'exec', code: 'EX', name: 'Executions', short: 'Execution', screen: 'S05', question: 'Which bounded attempts ran, and what did they produce?' },
  { id: 'code', code: 'CD', name: 'Canonical code', short: 'Code', screen: 'S06', question: 'What does the repository structurally contain, at which SHA?' },
  { id: 'evidence', code: 'EV', name: 'Evidence & decisions', short: 'Evidence', screen: 'S09', question: 'What proves it, and who decided?' },
  { id: 'outcome', code: 'OU', name: 'Outcome', short: 'Outcome', screen: 'S10', question: 'What was delivered, and is it eligible?' },
];
export const laneIndex = (id: LaneId) => LANES.findIndex((l) => l.id === id);

export const SCREENS: { id: ScreenId; num: string; name: string; mono: string; short: string; lane?: LaneId; lens?: Lens; route: string }[] = [
  { id: 'S01', num: '01', name: 'Project Overview', mono: 'PO', short: 'Project', route: '/projects/:projectId' },
  { id: 'S02', num: '02', name: 'Delivery Cycle', mono: 'MAP', short: 'Cycle map', route: '/projects/:projectId/cycles/:cycleId' },
  { id: 'S03', num: '03', name: 'Product / Specs', mono: 'IN', short: 'Specs', lane: 'intent', route: '/projects/:projectId/features/:featureId/specs/:version' },
  { id: 'S04', num: '04', name: 'Task DAG', mono: 'WK', short: 'Tasks', lane: 'work', route: '/cycles/:cycleId/tasks?selected=:taskId' },
  { id: 'S05', num: '05', name: 'Execution Inspector', mono: 'EX', short: 'Runs', lane: 'exec', route: '/executions/:executionId' },
  { id: 'S06', num: '06', name: 'Code Intelligence', mono: 'CD', short: 'Code', lane: 'code', route: '/projects/:projectId/code?index=:indexId&symbol=:symbolId' },
  { id: 'S07', num: '07', name: 'Traceability', mono: 'TR', short: 'Trace', lens: 'trace', route: '/projects/:projectId/lineage?selected=:entityId&cycle=:cycleId' },
  { id: 'S08', num: '08', name: 'Impact Explorer', mono: 'IM', short: 'Impact', lens: 'impact', route: '/cycles/:cycleId/impact' },
  { id: 'S09', num: '09', name: 'Assurance', mono: 'EV', short: 'Assure', lane: 'evidence', route: '/cycles/:cycleId/assurance?candidate=:candidateId' },
  { id: 'S10', num: '10', name: 'Release', mono: 'OU', short: 'Outcome', lane: 'outcome', route: '/cycles/:cycleId/outcome' },
];
export const screenById = (id: ScreenId) => SCREENS.find((s) => s.id === id)!;

export const STATUS: Record<string, { l: string; t: Tone; g: string }> = {
  recorded: { l: 'Recorded', t: 'success', g: '■' },
  observed: { l: 'Observed fact', t: 'success', g: '■' },
  proposed: { l: 'Proposed', t: 'neutral', g: '◇' },
  review: { l: 'Review required', t: 'attention', g: '‖' },
  approved: { l: 'Approved', t: 'success', g: '✓' },
  decided: { l: 'Decided', t: 'success', g: '✓' },
  ready: { l: 'Ready', t: 'active', g: '○' },
  blocked: { l: 'Blocked', t: 'attention', g: '⊘' },
  queued: { l: 'Queued', t: 'neutral', g: '…' },
  running: { l: 'Running', t: 'active', g: '●' },
  checkpointed: { l: 'Checkpointed', t: 'attention', g: '‖' },
  completed: { l: 'Completed', t: 'success', g: '■' },
  failed: { l: 'Failed', t: 'failure', g: '✕' },
  stale: { l: 'Stale', t: 'attention', g: '↻' },
  superseded: { l: 'Superseded', t: 'muted', g: '—' },
  integrating: { l: 'Integrating', t: 'active', g: '●' },
  canonical: { l: 'Canonical', t: 'success', g: '■' },
  provisional: { l: 'Provisional', t: 'neutral', g: '◇' },
  missing: { l: 'Missing', t: 'attention', g: '!' },
  passed: { l: 'Passed', t: 'success', g: '✓' },
  pending: { l: 'Pending', t: 'attention', g: '‖' },
  rejected: { l: 'Rejected', t: 'failure', g: '✕' },
  eligible: { l: 'Eligible', t: 'success', g: '✓' },
  'not-eligible': { l: 'Not eligible', t: 'neutral', g: '○' },
  'approval-pending': { l: 'Awaiting approval', t: 'attention', g: '‖' },
  released: { l: 'Released', t: 'success', g: '■' },
  baseline: { l: 'Released', t: 'success', g: '■' },
  reproduced: { l: 'Failure reproduced', t: 'failure', g: '✕' },
  inferred: { l: 'Proposed inference', t: 'attention', g: '◐' },
  decision: { l: 'Human decision', t: 'attention', g: '?' },
  'not-ready': { l: 'Not ready', t: 'attention', g: '○' },
  rfc: { l: 'READY_FOR_CHANGE', t: 'success', g: '✓' },
  'not-requested': { l: 'Not requested', t: 'neutral', g: '○' },
  future: { l: 'Future obligation', t: 'future', g: '○' },
  hypothesis: { l: 'Probable cause', t: 'attention', g: '◐' },
  promoted: { l: 'Promoted', t: 'success', g: '✓' },
  'not-blessed': { l: 'Not blessed', t: 'failure', g: '⊘' },
  unchanged: { l: 'Unchanged', t: 'neutral', g: '■' },
  bounded: { l: 'Bounded', t: 'success', g: '■' },
  resolved: { l: 'Resolved', t: 'success', g: '✓' },
  integrated: { l: 'Integrated', t: 'success', g: '■' },
  supported: { l: 'Supported', t: 'success', g: '✓' },
  denied: { l: 'Denied', t: 'failure', g: '⊘' },
  allowed: { l: 'Allowed', t: 'success', g: '✓' },
  historical: { l: 'Historical', t: 'muted', g: '—' },
  'n-a': { l: 'Not applicable', t: 'muted', g: '—' },
};

// Statuses that put a record in the attention queue, highest priority first.
export const ATTENTION_ORDER = ['checkpointed', 'decision', 'missing', 'review', 'pending', 'approval-pending', 'inferred', 'failed', 'blocked'];

export type Check = [string, boolean | null, string?]; // label, ok (null = n/a), detail
export type Why = {
  summary: string;
  checks?: Check[];
  blocking?: string[];
  policy?: string;
  inputs?: string;
  next?: string;
};
export type Cmd = { label: string; cmd: string; enabled?: boolean; reason?: string; dialog?: 'approval' | 'checkpoint' | 'intake' };

export type GNode = {
  id: string;
  lane: LaneId;
  kind: string; // type label, e.g. 'DURABLE TASK'
  ref: string; // ID · version shown on the node
  title: string;
  at: number; // stage index at which the record materializes
  st: [number, string][]; // stage index -> status transitions
  sub?: string; // secondary mono line (sha, counts)
  prov?: Prov;
  conf?: number;
  origin?: string; // GENERATED_LINEAGE | DISCOVERED | HUMAN_CONFIRMED | OBSERVED ...
  sha?: string; // commit scope
  authority?: string;
  workspace?: string;
  attn?: Record<string, string>; // status -> attention headline
  why?: Record<string, Why>; // status -> why
  cmds?: Record<string, Cmd[]>; // status -> commands
  impact?: 'direct' | 'inferred' | 'scope';
  stack?: string[]; // collapsed group members
  hist?: string; // historical note shown in inspector
};

export type GEdge = { from: string; to: string; rel: string; kind?: 'auth' | 'inferred'; conf?: number; note?: string };

export type Journey = {
  id: JourneyId;
  cycle: string;
  name: string;
  objective: string;
  direction: string;
  outcome: string;
  stages: { k: string; lane: LaneId; out: string }[];
  live: number;
  nodes: GNode[];
  edges: GEdge[];
  focus: string; // default selected node
  defaults: Partial<Record<ScreenId, string>>; // default selected record per drill-down
  base: { released: string; releasedSha: string; target: string; canonical: string; candidate?: string };
};

// Subject of a relation sentence. Edges point downstream; the sentence reads from the persisted record.
const SUBJ_TO = new Set(['DERIVED_FROM', 'IMPLEMENTS', 'DEPENDS_ON', 'RECOVERED_FROM', 'OBSERVED_IN', 'PROMOTED_FROM', 'CONTAINED_IN', 'LOCATED_IN']);
export const sentence = (e: GEdge) => (SUBJ_TO.has(e.rel) ? [e.to, e.rel, e.from] : [e.from, e.rel, e.to]);

export function statusAt(n: GNode, stage: number): string {
  if (stage < n.at) return 'future';
  let s = n.st[0]?.[1] ?? 'recorded';
  for (const [i, v] of n.st) if (i <= stage) s = v;
  return s;
}
export const meta = (s: string) => STATUS[s] ?? { l: s, t: 'neutral' as Tone, g: '·' };

export function whyFor(j: Journey, n: GNode, stage: number): Why {
  const s = statusAt(n, stage);
  const w = n.why?.[s];
  if (w) return w;
  const sk = j.stages[n.at]?.k ?? '';
  switch (s) {
    case 'future':
      return {
        summary: `Not materialized. This obligation becomes an authoritative record during ${sk}; it is never drawn as completed before then.`,
        checks: [[`Cycle reached ${sk}`, false], ['Upstream records materialized', false]],
        next: 'No command available until the obligation materializes.',
      };
    case 'completed':
      return { summary: 'Required outputs exist and were validated by Olympus. Completion was not taken from the producer’s declaration.', checks: [['Required outputs present', true], ['Output schema validated', true], ['Scope verification passed', true]] };
    case 'passed':
      return { summary: 'Executable or review evidence recorded against the exact target SHA and finalized by Olympus.', checks: [['Evidence targets current SHA', true], ['Result normalized by Olympus', true]] };
    case 'approved':
    case 'decided':
      return { summary: 'An explicit, attributable human decision recorded through the approval command. Never inferred from conversation.', checks: [['Decision recorded via command', true], ['Expected version matched', true]] };
    case 'recorded':
    case 'observed':
      return { summary: 'Immutable, versioned record. It is provenance, not execution state.', checks: [['Content hash recorded', true], ['Source attribution recorded', true]] };
    case 'canonical':
      return { summary: 'Derived deterministically from the exact integrated or repository SHA. Canonical structure does not make discovered intent canonical.', checks: [['Index SHA matches scope', true], ['Deterministic extractor', true]] };
    case 'blocked':
      return { summary: 'Scheduler eligibility not met.', checks: [['status == READY', false], ['dependencies complete', false]] };
    default:
      return { summary: meta(s).l + '.' };
  }
}

export function cmdsFor(j: Journey, n: GNode, stage: number): Cmd[] {
  const s = statusAt(n, stage);
  if (n.cmds?.[s]) return n.cmds[s];
  const c = j.cycle;
  switch (s) {
    case 'running':
      if (n.lane === 'exec') return [{ label: 'Request cancellation', cmd: `POST /executions/${n.id}/cancel` }];
      return [];
    case 'failed':
      return [{ label: 'Create policy-compliant retry', cmd: `POST /delivery-cycles/${c}/commands/retry_task`, reason: 'Creates a new Execution and snapshot; this attempt stays immutable.' }];
    case 'review':
      return [
        { label: 'Review & approve', cmd: `POST /specs/${n.id}/approve`, dialog: 'approval' },
        { label: 'Request changes', cmd: `POST /delivery-cycles/${c}/commands/request_spec_changes` },
      ];
    case 'pending':
      return [{ label: 'Review approval', cmd: `POST /approvals/${n.id}/decision`, dialog: 'approval' }];
    case 'missing':
      return [{ label: 'Request exact-target verification', cmd: `POST /delivery-cycles/${c}/commands/request_verification` }];
    case 'checkpointed':
      return [{ label: 'Answer checkpoint question', cmd: `POST /delivery-cycles/${c}/commands/answer_checkpoint`, dialog: 'checkpoint' }];
    default:
      return [];
  }
}

export function attentionFor(j: Journey, stage: number) {
  const items: { n: GNode; s: string; text: string; rank: number }[] = [];
  for (const n of j.nodes) {
    const s = statusAt(n, stage);
    const rank = ATTENTION_ORDER.indexOf(s);
    if (rank < 0) continue;
    const text = n.attn?.[s];
    if (!text) continue;
    items.push({ n, s, text, rank });
  }
  items.sort((a, b) => a.rank - b.rank);
  return items;
}

export function neighbours(j: Journey, id: string) {
  const ins = j.edges.filter((e) => e.to === id);
  const outs = j.edges.filter((e) => e.from === id);
  return { ins, outs };
}

export function lineage(j: Journey, id: string) {
  const up = new Set<string>(), down = new Set<string>();
  const walk = (cur: string, dir: 'up' | 'down', seen: Set<string>) => {
    for (const e of j.edges) {
      const next = dir === 'up' ? (e.to === cur ? e.from : null) : e.from === cur ? e.to : null;
      if (next && !seen.has(next)) { seen.add(next); walk(next, dir, seen); }
    }
  };
  walk(id, 'up', up); walk(id, 'down', down);
  return { up, down };
}
