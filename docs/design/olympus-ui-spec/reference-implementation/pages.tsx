import { React, useState } from './react';
import { SCREENS, LANES, type ScreenId, type JourneyId } from './model';
import { JOURNEYS } from './data';
import { JourneySpine } from './shell';
import { StatusBadge, ProvenanceBadge, Button, Label, cx, Sha } from './primitives';
import { WhyPanel } from './inspector';

// Stage → surfaces, from the journey walkthroughs (UI Design Pack v1.0 §§19–25).
export const SURFACES: Record<JourneyId, Record<string, ScreenId[]>> = {
  GF: { DISCOVERY: ['S02', 'S03'], PRODUCT_MODEL: ['S03'], ARCHITECTURE: ['S08', 'S03'], PLANNING: ['S04'], DEVELOPMENT: ['S05'], INTEGRATION: ['S06'], ASSURANCE: ['S09'], RELEASE: ['S10'], COMPLETE: ['S01', 'S07'] },
  BF: { RECON: ['S02'], CODE_INDEX: ['S06'], RECOVERED_SPEC: ['S03', 'S07'], BASELINE: ['S09', 'S04'], READINESS: ['S09', 'S08'], READY: ['S10', 'S01'] },
  FC: { INTAKE: ['S02'], SPEC_DELTA: ['S03'], IMPACT_ANALYSIS: ['S08'], PLANNING: ['S04'], DEVELOPMENT: ['S05'], INTEGRATION: ['S06'], ASSURANCE: ['S09'], RELEASE: ['S10'], COMPLETE: ['S01', 'S07'] },
  BG: { TRIAGE: ['S02'], REPRODUCTION: ['S09', 'S05'], EXPECTED_BEHAVIOR: ['S03'], ROOT_CAUSE: ['S08'], DEVELOPMENT: ['S04', 'S05'], INTEGRATION: ['S06'], REGRESSION: ['S09'], ASSURANCE: ['S09'], RELEASE: ['S10'], COMPLETE: ['S07', 'S01'] },
};

export const VARIATION: Record<ScreenId, Record<JourneyId, string>> = {
  S01: { GF: 'No released baseline; R1 is the target', BF: 'Existing repo + R1; trusted baseline B1 is the target', FC: 'R1 baseline, R2 target', BG: 'R2 baseline, R3 target' },
  S02: { GF: 'Intent → new product / code → proof. Spine runs left to right.', BF: 'Code → recovered knowledge → readiness. Spine starts in Code and doubles back to Intent.', FC: 'Delta → impact → code → regression proof. One early hop to Code for impact.', BG: 'Failure → intended behaviour → repair → proof. Spine zig-zags Evidence ↔ Intent ↔ Code.' },
  S03: { GF: 'Decompose PRD; scope / architecture approval', BF: 'Observed vs recovered vs canonical intent', FC: 'Versioned behavioural / technical delta (v1 → v2)', BG: 'Resolve expected behaviour or checkpoint' },
  S04: { GF: 'Implementation and verification dependencies', BF: 'Discovery / reasoning / baseline work — no feature build', FC: 'Minimal impact-aware tasks', BG: 'Minimal bounded repair task(s)' },
  S05: { GF: 'Planning and writable attempts; checkpoints', BF: 'Read-only discovery / reasoning; isolated baseline runs', FC: 'Bounded code-change attempts; stale retry', BG: 'Reproduction, diagnostic and repair attempts; denied action' },
  S06: { GF: 'New integrated code; GENERATED_LINEAGE', BF: 'Existing canonical structure; DISCOVERED links', FC: 'Affected symbols and incremental re-index', BG: 'Failure path and repaired symbol; before / after SHA' },
  S07: { GF: 'Source → verified R1', BF: 'Code → recovered intent → baseline → readiness (reversed)', FC: 'Request and delta → safe R2', BG: 'Defect + before / after proof → R3' },
  S08: { GF: 'Architecture / implementation boundaries', BF: 'Readiness gaps and unresolved uncertainty', FC: 'Affected symbols / contracts / tests / baselines', BG: 'Probable cause + minimal repair scope' },
  S09: { GF: 'New mandatory AC proof and review', BF: 'Readiness conditions — not release gates', FC: 'New AC proof + impacted old behaviour', BG: 'Original failure now passes + regression + baselines' },
  S10: { GF: 'Verified R1 manifest; optional deployment', BF: 'Readiness handoff; no new release command', FC: 'Verified R2 manifest', BG: 'Verified R3 manifest' },
};

export function JourneyMatrix({ initial }: { initial?: JourneyId }) {
  const [col, setCol] = useState(initial ?? null as null | JourneyId);
  const [row, setRow] = useState(null as null | ScreenId);
  return (
    <div className="ol-page">
      <div className="ol-page-h">
        <Label>Journey × screen specification</Label>
        <h1 className="ol-title">Four journeys through the same ten screens</h1>
        <p className="ol-muted">Columns are the four SupportDesk cycles. Each cell says what the screen does in that journey; chips name the lifecycle stages where it is the primary surface. Select a column to focus it.</p>
      </div>
      <table className="ol-table ol-mx">
        <thead>
          <tr>
            <th className="ol-mx-corner">Screen</th>
            {JOURNEYS.map((j) => (
              <th key={j.id} className={cx('ol-mx-jh', col === j.id && 'is-on')}>
                <button type="button" onClick={() => setCol(col === j.id ? null : j.id)} aria-pressed={col === j.id}>
                  <span className="ol-id">{j.cycle}</span>
                  <span className="ol-mx-jn">{j.name}</span>
                  <span className="ol-small ol-muted">{j.direction}</span>
                  <JourneySpine journey={j} stage={j.stages.length - 1} width={250} height={52} />
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {SCREENS.map((s) => (
            <tr key={s.id} className={cx(row === s.id && 'is-row')} onMouseEnter={() => setRow(s.id)} onMouseLeave={() => setRow(null)}>
              <th className="ol-mx-rh">
                <span className="ol-id">S{s.num}</span>
                <span className="ol-mx-sn">{s.name}</span>
                <span className="ol-small ol-muted">{s.id === 'S02' ? 'Hub · all stages' : s.lane ? `Lane ${LANES.find((l) => l.id === s.lane)!.code} drill-down` : s.lens ? `${s.lens} lens drill-down` : 'Above the cycle'}</span>
              </th>
              {JOURNEYS.map((j) => {
                const stages = Object.entries(SURFACES[j.id]).filter(([, v]) => v.includes(s.id)).map(([k]) => k);
                return (
                  <td key={j.id} className={cx(col === j.id && 'is-col', col && col !== j.id && 'is-dim', stages.length === 0 && s.id !== 'S02' && 'is-quiet')}>
                    <div>{VARIATION[s.id][j.id]}</div>
                    <div className="ol-mx-st">
                      {s.id === 'S02' ? <span className="ol-mx-chip is-hub">every stage</span> : stages.length ? stages.map((k) => <span key={k} className="ol-mx-chip">{k.replace(/_/g, ' ')}</span>) : <span className="ol-mx-chip is-none">supporting</span>}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
          <tr className="ol-mx-sum">
            <th className="ol-mx-rh"><span className="ol-mx-sn">What changes</span></th>
            {JOURNEYS.map((j) => (
              <td key={j.id} className={cx(col === j.id && 'is-col', col && col !== j.id && 'is-dim')}>
                <ul className="ol-list ol-small">
                  <li>{j.stages.length} lifecycle stages</li>
                  <li>Starts in lane <span className="ol-id">{LANES.find((l) => l.id === j.stages[0].lane)!.code}</span></li>
                  <li>{j.id === 'BF' ? 'No release command — readiness handoff' : 'Release command after server eligibility'}</li>
                  <li>{j.outcome}</li>
                </ul>
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

// ───────── Navigation model diagram ─────────
export function NavigationModel() {
  const laneX = (i: number) => 228 + i * 124;
  const drill: [number, string, string][] = [[0, 'S03', 'Product / Specs'], [1, 'S04', 'Task DAG'], [2, 'S05', 'Execution Inspector'], [3, 'S06', 'Code Intelligence'], [4, 'S09', 'Assurance'], [5, 'S10', 'Release']];
  return (
    <div className="ol-page">
      <div className="ol-page-h">
        <Label>Information architecture</Label>
        <h1 className="ol-title">The cycle map is the hub. Everything else is one click away.</h1>
        <p className="ol-muted">Each lane opens its canonical drill-down. Trace and Impact are lenses on the same graph before they become full screens. Every drill-down keeps a lane mini-map and “Back to cycle map”, preserving project, cycle, selected object, version, index scope and target SHA.</p>
      </div>
      <div className="ol-navmodel">
        <svg width="1180" height="620" viewBox="0 0 1180 620" style={{ maxWidth: "100%", height: "auto" }} role="img" aria-label="Navigation model: Project Overview above the Delivery Cycle map; six lanes each open a drill-down; Trace and Impact lenses open Traceability and Impact Explorer.">
          <defs><marker id="nm-a" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" className="ol-ah-s" /></marker></defs>
          {/* overview */}
          <rect x="448" y="16" width="284" height="64" rx="8" className="nm-box" />
          <text x="590" y="42" textAnchor="middle" className="nm-t">S01 · Project Overview</text>
          <text x="590" y="62" textAnchor="middle" className="nm-s">released baseline · active cycle · attention</text>
          <path d="M590 80 L590 128" className="nm-l" markerEnd="url(#nm-a)" />
          <text x="600" y="108" className="nm-s">Open control-plane map</text>
          {/* hub */}
          <rect x="196" y="132" width="784" height="214" rx="10" className="nm-hub" />
          <text x="216" y="158" className="nm-t">S02 · Delivery Cycle — control-plane map</text>
          <text x="216" y="176" className="nm-s">lifecycle ribbon · attention · journey spine · six lanes · inspector</text>
          {LANES.map((l, i) => (
            <g key={l.id}>
              <rect x={laneX(i) - 54} y="192" width="108" height="136" rx="6" className="nm-lane" />
              <text x={laneX(i)} y="214" textAnchor="middle" className="nm-code">{l.code}</text>
              <text x={laneX(i)} y="232" textAnchor="middle" className="nm-s">{l.short}</text>
              <rect x={laneX(i) - 42} y="244" width="84" height="22" rx="4" className="nm-node" />
              <rect x={laneX(i) - 42} y="272" width="84" height="22" rx="4" className={i > 3 ? 'nm-node is-future' : 'nm-node'} />
              <rect x={laneX(i) - 42} y="300" width="84" height="22" rx="4" className={i > 2 ? 'nm-node is-future' : 'nm-node'} />
            </g>
          ))}
          <rect x="992" y="132" width="168" height="214" rx="10" className="nm-box" />
          <text x="1076" y="158" textAnchor="middle" className="nm-t">Inspector</text>
          {['state + reason', 'provenance + scope', 'relations', 'permitted commands', 'Open in … →'].map((t, i) => <text key={t} x="1008" y={186 + i * 26} className="nm-s">{t}</text>)}
          {/* drill-downs */}
          {drill.map(([i, id, name]) => (
            <g key={id}>
              <path d={`M${laneX(i)} 346 L${laneX(i)} 426`} className="nm-l" markerEnd="url(#nm-a)" />
              <rect x={laneX(i) - 58} y="430" width="116" height="62" rx="8" className="nm-box" />
              <text x={laneX(i)} y="455" textAnchor="middle" className="nm-t">{id}</text>
              <text x={laneX(i)} y="474" textAnchor="middle" className="nm-s">{name}</text>
              <path d={`M${laneX(i) - 34} 430 L${laneX(i) - 34} 350`} className="nm-l is-back" markerEnd="url(#nm-a)" />
            </g>
          ))}
          <text x="964" y="446" className="nm-s">solid ↓ lane header or “Open in …”</text>
          <text x="964" y="464" className="nm-s">opens the drill-down</text>
          <text x="964" y="488" className="nm-s is-back-t">dashed ↑ Back to cycle map</text>
          <text x="964" y="506" className="nm-s is-back-t">restores selection and position</text>
          {/* lenses */}
          <rect x="16" y="150" width="160" height="70" rx="8" className="nm-box is-lens" />
          <text x="96" y="178" textAnchor="middle" className="nm-t">Trace lens</text>
          <text x="96" y="198" textAnchor="middle" className="nm-s">→ S07 Traceability</text>
          <rect x="16" y="252" width="160" height="70" rx="8" className="nm-box is-lens" />
          <text x="96" y="280" textAnchor="middle" className="nm-t">Impact lens</text>
          <text x="96" y="300" textAnchor="middle" className="nm-s">→ S08 Impact Explorer</text>
          <path d="M196 186 L178 186" className="nm-l" markerEnd="url(#nm-a)" />
          <path d="M196 288 L178 288" className="nm-l" markerEnd="url(#nm-a)" />
          {/* utilities */}
          <g>
            <text x="16" y="548" className="nm-code">Global utilities — auxiliary, not journeys</text>
            {['New delivery cycle → intake', 'Ask Olympus → explanation + typed command', 'Integrations → inbound / outbound / reconcile', 'Audit → immutable history'].map((t, i) => (
              <g key={t}><rect x={16 + i * 288} y="562" width="276" height="40" rx="6" className="nm-box is-util" /><text x={30 + i * 288} y="587" className="nm-s">{t}</text></g>
            ))}
          </g>
        </svg>
      </div>
      <div className="ol-navrules">
        <div><Label>Preserved in every URL</Label><p className="ol-mono ol-small">project · cycle · selected object · version · index scope · target SHA</p></div>
        <div><Label>Selecting is not acting</Label><p className="ol-small">Clicking a node selects it. Commands appear only in the inspector or dialogs and go through the command API.</p></div>
        <div><Label>Not a wizard</Label><p className="ol-small">The ten screens are not a mandatory linear flow. The rail keeps direct navigation for expert users.</p></div>
      </div>
    </div>
  );
}

// ───────── Exception states gallery ─────────
const EXC: { t: string; st: string; reason: string; next: string; ui?: any }[] = [
  { t: 'Unknown expected behaviour', st: 'checkpointed', reason: 'Bug repair waits. Olympus does not invent intended semantics.', next: 'Resolve from canonical spec / baseline, or request a human decision.' },
  { t: 'Proposed Brownfield inference', st: 'inferred', reason: 'Confidence and code evidence shown; not canonical intent.', next: 'Review, request evidence, reject, or promote with authority.', ui: <ProvenanceBadge kind="INFERENCE" conf={0.84} /> },
  { t: 'Dependency blocked', st: 'blocked', reason: 'Unmet task / artifact / approval predicate listed with blocking IDs.', next: 'Open the blocker. Scheduling happens only after eligibility recomputes.' },
  { t: 'Out-of-scope tool action', st: 'denied', reason: 'Denied action logged with contract scope and policy.', next: 'Request a bounded scope change or approval. Never retried wider.', ui: <code className="ol-cmd-api">repo.write app/auth/session.py · outside allowed_scope</code> },
  { t: 'Execution failed / timed out', st: 'failed', reason: 'Attempt and artifacts retained; task not auto-completed.', next: 'Inspect the failure; create a policy-compliant retry.' },
  { t: 'Checkpoint / lease expiry', st: 'checkpointed', reason: 'Waiting question and worker ownership visible.', next: 'Resolve and resume / replan; attempt history preserved.', ui: <span className="ol-small ol-mono">lease worker-02 · expired 10:41 · recoverable</span> },
  { t: 'Stale snapshot / changed base', st: 'stale', reason: 'Pinned inputs differ from authoritative versions.', next: 'Revalidate, or create a new contract / snapshot / attempt.', ui: <span className="ol-small ol-mono">SNAP-203 pins TC-104 v1 · current v2</span> },
  { t: 'Integration conflict', st: 'failed', reason: 'Conflict is a Finding — not a hidden autonomous merge success.', next: 'Create remediation work and reintegrate.', ui: <span className="ol-small ol-mono">F-207 conflict app/models/ticket.py</span> },
  { t: 'Missing or old-SHA evidence', st: 'missing', reason: 'The obligation, the wrong SHA and the current SHA are all visible.', next: 'Request exact-target verification.', ui: <span className="ol-small"><Sha value="4a871dc" /> → needs <Sha value="c83a12d" /></span> },
  { t: 'Assurance failure', st: 'failed', reason: 'Gate cannot pass; the finding links to its proof.', next: 'Repair loop, then targeted revalidation.' },
  { t: 'Approval pending / rejected', st: 'rejected', reason: 'Technical readiness does not imply eligibility.', next: 'Review the decision; revise scope when rejected.', ui: <span className="ol-chips"><StatusBadge status="approval-pending" size="sm" /></span> },
  { t: 'Connector outcome unknown', st: 'pending', reason: 'Possible external mutation. No blind retry.', next: 'Reconcile provider state using the external correlation ID.', ui: <span className="ol-small ol-mono">ci.trigger_e2e · CORR-882 · reconciliation required</span> },
  { t: 'Event stream disconnected', st: 'stale', reason: 'Last authoritative refresh time and disconnected state shown.', next: 'Refetch current state. No optimistic green completion.', ui: <span className="ol-stream is-off"><span className="ol-stream-dot" />Disconnected · last refresh 10:41:07</span> },
  { t: 'Empty / loading / forbidden', st: 'n-a', reason: 'Explains the unavailable object or action and keeps context.', next: 'Upload / register a source, retry the fetch, or use an authorized account.', ui: <span className="ol-small ol-muted">You need release_approver on SupportDesk to decide APR-302.</span> },
];
export function ExceptionStates() {
  return (
    <div className="ol-page">
      <div className="ol-page-h">
        <Label>Exceptional states</Label>
        <h1 className="ol-title">Every failure has a visible reason and a permitted next action</h1>
        <p className="ol-muted">Same anatomy everywhere: textual state chip → reason → consequence → the command you may issue. Never colour alone; never a silent retry.</p>
      </div>
      <div className="ol-exc">
        {EXC.map((x) => (
          <div key={x.t} className="ol-exc-c">
            <div className="ol-row-b"><span className="ol-exc-t">{x.t}</span><StatusBadge status={x.st} size="sm" /></div>
            {x.ui && <div className="ol-exc-ui">{x.ui}</div>}
            <p className="ol-small">{x.reason}</p>
            <div className="ol-exc-n"><Label>Permitted next action</Label><span className="ol-small">{x.next}</span></div>
          </div>
        ))}
      </div>
    </div>
  );
}

export { WhyPanel, Button };
