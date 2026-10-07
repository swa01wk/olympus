import { React, useState } from './react';
import { LANES, SCREENS, laneIndex, statusAt, whyFor, screenById, attentionFor, meta, type Journey, type ScreenId, type LaneId, type Lens, type Cmd } from './model';
import { JOURNEYS, journeyById } from './data';
import { DETAIL } from './detail';
import { Button, StatusBadge, ProvenanceBadge, IdRef, Panel, KV, Label, ShaScopeBanner, EmptyState, cx, Sha } from './primitives';
import { AppShell, CycleHeader, AttentionStrip, LaneStrip, SnapshotBanner, JourneySpine, LifecycleRibbon } from './shell';
import { ControlPlaneGraph } from './graph';
import { ObjectInspector, WhyPanel } from './inspector';
import { EvidenceMatrix, EligibilityChecklist, TaskContractCard, ExecutionTimeline, AttemptHistory, VersionDiff, TaskDag, ApprovalDialog, CheckpointDialog, IntakeForm, Drawer, type ApprovalSubject } from './parts';

// ───────── shared context passed to every screen ─────────
type Ctx = {
  j: Journey; stage: number; sel: string; lens: Lens; view: 'graph' | 'list';
  setStage: (i: number) => void; select: (id: string) => void; setLens: (l: Lens) => void; setView: (v: any) => void;
  nav: (s: ScreenId) => void; open: (s: ScreenId, id?: string) => void; openLane: (l: LaneId) => void;
  command: (c: Cmd, id: string) => void; why: (id: string) => void; approval: (id: string) => void; intake: (k?: string) => void;
};

const pick = (c: Ctx, lane: LaneId, screen: ScreenId) => {
  const n = c.j.nodes.find((x) => x.id === c.sel);
  return n && n.lane === lane ? n.id : c.j.defaults[screen] ?? c.j.nodes.find((x) => x.lane === lane)?.id ?? '';
};
const node = (j: Journey, id: string) => j.nodes.find((n) => n.id === id || n.ref === id || n.ref.startsWith(id + ' '));

function DrillHeader({ c, screen, lane, right }: { c: Ctx; screen: ScreenId; lane?: LaneId; right?: any }) {
  const s = screenById(screen);
  return (
    <>
      <CycleHeader
        journey={c.j}
        stage={c.stage}
        onStage={c.setStage}
        onBack={() => c.nav('S02')}
        crumbs={['SupportDesk', `${c.j.cycle} · ${c.j.name}`, s.name]}
        title={s.name}
        right={right ?? <Button onClick={() => c.why(c.sel)}>Why this state?</Button>}
      />
      <LaneStrip journey={c.j} stage={c.stage} current={lane ?? s.lane} onLane={c.openLane} lens={s.lens} />
      <SnapshotBanner journey={c.j} stage={c.stage} onLive={() => c.setStage(c.j.live)} />
    </>
  );
}

function NotYet({ c, anchor, what }: { c: Ctx; anchor: string; what: string }) {
  const n = node(c.j, anchor);
  if (!n || statusAt(n, c.stage) !== 'future') return null;
  return (
    <Panel>
      <EmptyState
        title={`No ${what} yet at ${c.j.stages[c.stage].k}`}
        body={`These records materialize during ${c.j.stages[n.at].k}. Olympus never draws a future obligation as a completed artifact.`}
        action={<Button onClick={() => c.nav('S02')}>Back to cycle map</Button>}
      />
    </Panel>
  );
}

// ═════════ S01 · Project Overview ═════════
export function S01({ c }: { c: Ctx }) {
  const d = DETAIL[c.j.id].overview;
  const items = attentionFor(c.j, c.stage);
  return (
    <div className="ol-screen">
      <div className="ol-ch">
        <div className="ol-crumbs"><span className="ol-crumb">SupportDesk</span><span className="ol-crumb">Project overview</span></div>
        <h1 className="ol-title">SupportDesk</h1>
        <div className="ol-ch-meta"><span>Persistent project</span><span className="ol-dotsep">·</span><span>Python · FastAPI · PostgreSQL</span><span className="ol-dotsep">·</span><span>{d.cycles.length} delivery cycle{d.cycles.length > 1 ? 's' : ''} as of {c.j.cycle}</span></div>
      </div>
      <div className="ol-truth">
        {d.truth.map(([k, v, note]) => (
          <div key={k} className="ol-tile">
            <Label>{k}</Label>
            <div className="ol-stat">{v}</div>
            <div className="ol-small ol-muted">{note}</div>
          </div>
        ))}
      </div>
      <div className="ol-cols ol-cols-ov">
        <Panel title="Active delivery cycle" sub={`${c.j.cycle} · ${c.j.name} · ${c.j.direction}`} actions={<Button variant="primary" onClick={() => c.nav('S02')}>Open control-plane map →</Button>}>
          <div className="ol-ov-obj">{c.j.objective}</div>
          <div className="ol-ov-spine">
            <JourneySpine journey={c.j} stage={c.stage} width={720} height={78} showLanes onStage={c.setStage} />
          </div>
          <LifecycleRibbon journey={c.j} stage={c.stage} onStage={c.setStage} compact />
          <div className="ol-ov-q">
            <Label>Attention queue</Label>
            {items.length === 0 && <p className="ol-muted">Nothing needs you. Olympus is progressing {c.j.stages[c.stage].k}.</p>}
            <ul className="ol-q">
              {items.map((it) => (
                <li key={it.n.id}>
                  <StatusBadge status={it.s} size="sm" />
                  <span className="ol-q-t">{it.text}</span>
                  <Button size="sm" onClick={() => c.open('S02', it.n.id)}>Inspect {it.n.ref}</Button>
                </li>
              ))}
            </ul>
          </div>
        </Panel>
        <Panel title="Coverage" sub="Explicit denominators. No invented overall completion percentage.">
          <ul className="ol-cov">
            {d.coverage.map(([k, a, b, note]) => (
              <li key={k}>
                <div className="ol-cov-h"><span>{k}</span><span className="ol-id">{b === 0 ? 'n/a' : `${a} / ${b}`}</span></div>
                <div className="ol-bar" role="img" aria-label={`${a} of ${b}`}><span style={{ width: b ? `${(a / b) * 100}%` : '0%' }} /></div>
                <div className="ol-small ol-muted">{note}</div>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
      <Panel title="Project continuity" sub="Every cycle stays reachable. Releases advance only through a recorded release." pad={false}>
        <table className="ol-table">
          <thead><tr><th>Cycle</th><th>Journey</th><th>Intent</th><th>Outcome</th><th>State</th></tr></thead>
          <tbody>
            {d.cycles.map((r) => (
              <tr key={r.id} className={r.id === c.j.cycle ? 'is-sel' : ''}>
                <td className="ol-id">{r.id}</td><td>{r.j}</td><td>{r.intent}</td><td className="ol-mono">{r.outcome}</td><td><StatusBadge status={r.st} size="sm" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

// ═════════ S02 · Delivery Cycle (the hub) ═════════
export function S02({ c }: { c: Ctx }) {
  const [rel, setRel] = useState(null as null | string);
  return (
    <div className="ol-screen">
      <CycleHeader journey={c.j} stage={c.stage} onStage={c.setStage} crumbs={['SupportDesk', 'Delivery cycle']} right={<span className="ol-stagechip"><span className="ol-label">Stage</span> {c.j.stages[c.stage].k}</span>} />
      <AttentionStrip journey={c.j} stage={c.stage} onSelect={c.select} onWhy={c.why} onAction={c.select} />
      <SnapshotBanner journey={c.j} stage={c.stage} onLive={() => c.setStage(c.j.live)} />
      <div className="ol-mapgrid">
        <section className="ol-panel ol-mappanel" aria-label="Control-plane map">
          <ControlPlaneGraph journey={c.j} stage={c.stage} selected={c.sel} onSelect={c.select} lens={c.lens} onLens={c.setLens} view={c.view} onView={c.setView} onOpenLane={c.openLane} onStage={c.setStage} focusEdge={rel} />
        </section>
        <ObjectInspector journey={c.j} stage={c.stage} id={c.sel} onSelect={c.select} onOpen={c.open} onCommand={c.command} lens={c.lens} onHoverRel={setRel} />
      </div>
    </div>
  );
}

// ═════════ S03 · Product / Specs ═════════
export function S03({ c }: { c: Ctx }) {
  const d = DETAIL[c.j.id].specs;
  const anchor = c.j.defaults.S03!;
  const n = node(c.j, anchor)!;
  const st = statusAt(n, c.stage);
  const b = d.body;
  return (
    <div className="ol-screen">
      <DrillHeader c={c} screen="S03" />
      {(NotYet({ c, anchor, what: 'specifications' })) ?? (
        <div className="ol-cols ol-cols-3">
          <Panel title="Product model" sub="Capability → feature → spec" pad={false}>
            <ul className="ol-tree">
              {d.tree.map((g) => (
                <li key={g.cap}>
                  <div className="ol-tree-cap">{g.cap}</div>
                  <ul>
                    {g.items.map(([id, name, s]) => {
                      const live = node(c.j, id);
                      const status = live ? statusAt(live, c.stage) : s;
                      return (
                        <li key={id}>
                          <button type="button" className={cx('ol-tree-i', (id === n.id || id === n.ref.split(' ')[0]) && 'is-on')} onClick={() => live && c.select(live.id)}>
                            <span className="ol-id">{id}</span><span>{name}</span><StatusBadge status={status} size="sm" />
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title={d.title} sub={<><span className="ol-id">{d.id}</span> · {d.mode === 'recovered' ? 'Observed vs recovered vs canonical intent' : d.mode === 'delta' ? 'Stable feature identity · immutable approved versions' : d.mode === 'expected' ? 'Expected behaviour resolved from authoritative sources' : 'Behavioural specification · proposed by Kira from PS-001'}</>} actions={<StatusBadge status={st} />}>
            {d.mode === 'review' && (
              <div className="ol-stack">
                <blockquote className="ol-quote"><Label>Source · DERIVED_FROM</Label>{b.source}</blockquote>
                <div><Label>Rules</Label><ul className="ol-list">{b.rules.map((r: string) => <li key={r} className="ol-mono">{r}</li>)}</ul></div>
                <AcTable rows={b.acs} />
                <div className="ol-callout is-attention">
                  <StatusBadge status="checkpointed" size="sm" label={b.question.id} />
                  <span>{b.question.text}</span>
                  <Button size="sm" onClick={() => c.command({ label: 'Answer', cmd: '', dialog: 'checkpoint' }, 'EX-104')}>Answer checkpoint</Button>
                </div>
              </div>
            )}
            {d.mode === 'recovered' && (
              <div className="ol-stack">
                <table className="ol-table ol-3way">
                  <thead><tr><th>Behaviour</th><th>Observed</th><th>Recovered</th><th>Canonical</th></tr></thead>
                  <tbody>
                    {b.rows.map((r: string[]) => (
                      <tr key={r[0]}>
                        <td>{r[0]}</td>
                        <td><ProvLine text={r[1]} /></td>
                        <td><ProvLine text={r[2]} /></td>
                        <td><span className={cx('ol-small', r[3] === 'Needs decision' ? 'ol-tc-attention' : 'ol-muted')}>{r[3]}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div><Label>Supporting code and test evidence</Label><ul className="ol-list">{b.evidence.map((e: string) => <li key={e} className="ol-mono">{e}</li>)}</ul></div>
                <p className="ol-small ol-muted">Recovered intent stays proposed until reviewed. A defect or accidental behaviour must not become product intent simply because it exists in code.</p>
              </div>
            )}
            {d.mode === 'delta' && (
              <div className="ol-stack">
                <VersionDiff left={b.v1} right={b.v2} leftLabel="FeatureSpec v1 · approved · historical" rightLabel="FeatureSpec v2 · approved (APR-301)" />
                <AcTable rows={b.acs} />
              </div>
            )}
            {d.mode === 'expected' && (
              <div className="ol-stack">
                <div className="ol-diff">
                  <div className="ol-obs"><Label>Observed (EV-901)</Label><p>{b.observed}</p><ProvenanceBadge kind="FACT" /></div>
                  <div className="ol-obs is-expected"><Label>Expected (AC-017-04)</Label><p>{b.expected}</p><ProvenanceBadge kind="DECISION" source={b.source} /></div>
                </div>
                <div><Label>Provenance</Label><p className="ol-mono ol-small">{b.source}</p></div>
                <div>
                  <Label>Authoritative sources checked</Label>
                  <ul className="ol-checks">{b.checked.map(([k, v, ok]: any) => <li key={k} className={cx('ol-check', ok === true ? 'is-ok' : 'is-na')}><span className="ol-check-g">{ok ? '✓' : '—'}</span><span className="ol-check-l">{k}</span><span className="ol-check-d">{v}</span></li>)}</ul>
                </div>
                <p className="ol-small ol-muted">{b.fallback}</p>
              </div>
            )}
            <div className="ol-actions">
              {d.mode === 'review' && <><Button variant="primary" onClick={() => c.approval('SPEC-001')}>Review and approve scope</Button><Button>Request changes</Button></>}
              {d.mode === 'recovered' && <><Button variant="primary" onClick={() => c.approval('REC-017')}>Review and promote</Button><Button>Request more evidence</Button><Button>Reject inference</Button></>}
              {d.mode === 'delta' && <><Button onClick={() => c.open('S07', 'CODE-117')}>Trace to code</Button><Button>Compare with v1 lineage</Button></>}
              {d.mode === 'expected' && <><Button variant="primary" onClick={() => c.open('S08')}>Open probable cause</Button><Button onClick={() => c.open('S07', 'DEF-017')}>Trace defect</Button></>}
            </div>
          </Panel>

          <Panel title="Technical realization">
            <div className="ol-stack">
              <div>
                <div className="ol-row-b"><span className="ol-id">{d.impl.title}</span><StatusBadge status={d.impl.status} size="sm" /></div>
                <ul className="ol-list">{d.impl.lines.map((l) => <li key={l}>{l}</li>)}</ul>
              </div>
              <div>
                <Label>Project architecture</Label>
                <div className="ol-id">{d.arch.title}</div>
                <ul className="ol-list">{d.arch.lines.map((l) => <li key={l}>{l}</li>)}</ul>
                <p className="ol-small ol-muted">{d.arch.note}</p>
              </div>
              <Button onClick={() => c.open('S08')}>Inspect impact scope →</Button>
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}
function AcTable({ rows }: { rows: string[][] }) {
  return (
    <table className="ol-table">
      <thead><tr><th>Criterion</th><th>Behaviour</th><th>Required proof</th></tr></thead>
      <tbody>{rows.map((r) => <tr key={r[0]}><td className="ol-id">{r[0]}</td><td>{r[1]}</td><td className="ol-small">{r[2]}</td></tr>)}</tbody>
    </table>
  );
}
function ProvLine({ text }: { text: string }) {
  const [k, ...rest] = text.split(' · ');
  const kind = k as any;
  return <span className="ol-provline">{['FACT', 'INFERENCE', 'UNCERTAINTY', 'DECISION', 'ASSUMPTION'].includes(k) ? <ProvenanceBadge kind={kind} /> : <span>{k}</span>}<span className="ol-small">{rest.join(' · ')}</span></span>;
}

// ═════════ S04 · Task DAG ═════════
export function S04({ c }: { c: Ctx }) {
  const tid = pick(c, 'work', 'S04');
  const t = node(c.j, tid)!;
  const contract = DETAIL[c.j.id].contracts[tid];
  const attempts = c.j.edges.filter((e) => e.from === tid && e.rel === 'EXECUTED_AS').map((e) => node(c.j, e.to)!).filter(Boolean);
  const [mode, setMode] = useState('graph');
  const why = whyFor(c.j, t, c.stage);
  return (
    <div className="ol-screen">
      <DrillHeader c={c} screen="S04" />
      {NotYet({ c, anchor: tid, what: 'planned work' }) ?? (
        <div className="ol-cols ol-cols-2w">
          <Panel title="Task dependency graph" sub="Durable planned work is distinct from each attempt" actions={<div className="ol-seg">{['graph', 'list'].map((m) => <button key={m} type="button" className={cx('ol-seg-i', mode === m && 'is-on')} onClick={() => setMode(m)}>{m === 'graph' ? 'Graph' : 'List'}</button>)}</div>}>
            {mode === 'graph' ? <TaskDag journey={c.j} stage={c.stage} selected={tid} onSelect={c.select} /> : (
              <table className="ol-table">
                <thead><tr><th>Task</th><th>Work type</th><th>Depends on</th><th>State</th></tr></thead>
                <tbody>{c.j.nodes.filter((n) => n.lane === 'work').map((n) => (
                  <tr key={n.id} className={n.id === tid ? 'is-sel' : ''} onClick={() => c.select(n.id)}>
                    <td><span className="ol-id">{n.ref}</span> {n.title}</td>
                    <td className="ol-mono ol-small">{DETAIL[c.j.id].contracts[n.id]?.workType ?? '—'}</td>
                    <td className="ol-mono ol-small">{c.j.edges.filter((e) => e.rel === 'DEPENDS_ON' && e.to === n.id).map((e) => e.from).join(', ') || '—'}</td>
                    <td><StatusBadge status={statusAt(n, c.stage)} size="sm" /></td>
                  </tr>))}</tbody>
              </table>
            )}
            <div className="ol-why-box">
              <div className="ol-row-b"><span><Label>Why is {t.ref} {meta(statusAt(t, c.stage)).l.toLowerCase()}?</Label></span><StatusBadge status={statusAt(t, c.stage)} size="sm" /></div>
              <WhyPanel why={why} onRef={(r) => { const x = node(c.j, r); if (x) c.select(x.id); }} />
            </div>
          </Panel>
          <div className="ol-colstack">
            {contract ? <Panel pad><TaskContractCard contract={contract} taskId={t.ref} /></Panel> : <Panel title="Task contract"><p className="ol-muted">Contract for {t.ref} is not part of the fixture set.</p></Panel>}
            <Panel title="Attempt history" sub="A task is durable; an execution is one attempt">
              {attempts.length === 0 ? <p className="ol-muted ol-small">No attempts yet. The scheduler creates an Execution only when eligibility passes.</p> : (
                <AttemptHistory items={attempts.map((a) => ({ id: a.id, st: statusAt(a, c.stage), note: a.sub ?? a.title }))} current={attempts[attempts.length - 1].id} onSelect={(id) => c.open('S05', id)} />
              )}
              <div className="ol-actions"><Button onClick={() => attempts.length && c.open('S05', attempts[attempts.length - 1].id)} disabled={!attempts.length}>Open execution →</Button></div>
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}

// ═════════ S05 · Execution Inspector ═════════
export function S05({ c }: { c: Ctx }) {
  const eid = pick(c, 'exec', 'S05');
  const x = node(c.j, eid)!;
  const d = DETAIL[c.j.id].execs[eid];
  const st = statusAt(x, c.stage);
  const all = c.j.nodes.filter((n) => n.lane === 'exec');
  return (
    <div className="ol-screen">
      <DrillHeader c={c} screen="S05" />
      {NotYet({ c, anchor: eid, what: 'execution attempts' }) ?? (
        <div className="ol-cols ol-cols-3">
          <Panel title="Attempts in this cycle" sub="Failures and retries stay reachable">
            <AttemptHistory items={all.map((a) => ({ id: a.id, st: statusAt(a, c.stage), note: a.title }))} current={eid} onSelect={c.select} />
          </Panel>
          <Panel
            title={<>{x.ref} · bounded execution</>}
            sub={d ? <><span className="ol-id">{d.contract}</span> · <span className="ol-id">{d.snapshot}</span> · base <Sha value={d.base} /> · {d.attempt} of <span className="ol-id">{d.task}</span></> : x.title}
            actions={<StatusBadge status={st} />}
          >
            {d ? (
              <div className="ol-stack">
                <div className="ol-row-b ol-small"><span><Label>Capability</Label>{d.capability} · {d.runtime}</span><span className="ol-muted">Agent names appear only in execution context</span></div>
                {d.checkpoint && st === 'checkpointed' && (
                  <div className="ol-callout is-attention">
                    <StatusBadge status="checkpointed" size="sm" label={d.checkpoint.id} />
                    <span>{d.checkpoint.q}</span>
                    <Button size="sm" variant="primary" onClick={() => c.command({ label: '', cmd: '', dialog: 'checkpoint' }, eid)}>Answer</Button>
                  </div>
                )}
                <div><Label>Governed tool events · each crosses ToolGateway</Label><ExecutionTimeline events={d.events} /></div>
                {d.diff && (
                  <div>
                    <Label>Candidate diff · provisional</Label>
                    <table className="ol-table ol-diffstat"><tbody>{d.diff.map(([f, a, r]) => <tr key={f}><td className="ol-mono">{f}</td><td className="ol-tc-success ol-mono">+{a}</td><td className="ol-tc-failure ol-mono">−{r}</td></tr>)}</tbody></table>
                  </div>
                )}
              </div>
            ) : (
              <div className="ol-stack"><WhyPanel why={whyFor(c.j, x, c.stage)} /><p className="ol-muted ol-small">The event log for {x.ref} is not part of the fixture set.</p></div>
            )}
            <div className="ol-actions">
              <Button onClick={() => c.open('S04', d?.task)}>Inspect contract</Button>
              <Button disabled={st !== 'running'} onClick={() => c.command({ label: 'Request cancellation', cmd: `POST /executions/${eid}/cancel` }, eid)}>Request cancellation</Button>
            </div>
          </Panel>
          <Panel title="Execution boundary">
            {d ? (
              <div className="ol-stack">
                <KV rows={[['Lease', d.lease], ['Snapshot hash', <span className="ol-sha">{d.snapHash}</span>], ['Workspace', <span className="ol-mono">{d.workspace}</span>], ['Model policy', d.model], ['Observed provider metadata', <span className="ol-small">{d.observed}</span>]]} />
                <div><Label>Permitted tools</Label><div className="ol-chips">{d.tools.map((t) => <span key={t} className="ol-id ol-chipid">{t}</span>)}</div></div>
                <p className="ol-small ol-muted">Configured model alias and observed provider metadata are shown — never a hard-coded model name. Retry creates a new attempt; this one stays immutable.</p>
              </div>
            ) : <p className="ol-muted">—</p>}
            <div className="ol-actions"><Button onClick={() => c.open('S07', eid)}>Open attempt lineage →</Button></div>
          </Panel>
        </div>
      )}
    </div>
  );
}

// ═════════ S06 · Code Intelligence ═════════
export function S06({ c }: { c: Ctx }) {
  const d = DETAIL[c.j.id].code;
  const [scope, setScope] = useState(d.active);
  const sc = d.scopes.find((s) => s.k === scope)!;
  const msg = scope === d.active ? d.banner : scope === 'provisional' ? `Provisional execution index ${sc.ref} @ ${sc.sha}. Execution-scoped and disposable — never implies a released or canonical baseline.` : scope === 'released' ? `Released baseline ${sc.ref} @ ${sc.sha}. It advances only when a release is recorded, not when a candidate integrates.` : `Canonical assurance target ${sc.ref} @ ${sc.sha}. Independent gates and final proof target this SHA.`;
  const sym = d.symbol;
  const anchor = c.j.defaults.S06!;
  return (
    <div className="ol-screen">
      <DrillHeader c={c} screen="S06" />
      {NotYet({ c, anchor, what: 'canonical code' }) ?? (
        <>
          <ShaScopeBanner scopes={d.scopes} active={scope} onChange={(k: any) => setScope(k)} message={msg} />
          <div className="ol-cols ol-cols-3">
            <Panel title="Files and symbols" sub={<>{sc.label} · <Sha value={sc.sha} /></>} pad={false}>
              <ul className="ol-tree">
                {d.tree.map((f) => (
                  <li key={f.file}>
                    <div className="ol-tree-cap ol-mono">{f.file}</div>
                    <ul>{f.symbols.map(([s, tag]) => <li key={s}><span className={cx('ol-tree-i', s === sym.name && 'is-on')}><span className="ol-mono">{s}</span>{tag && <span className="ol-tag">{tag}</span>}</span></li>)}</ul>
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title={<span className="ol-mono">{sym.name}</span>} sub={<><span className="ol-mono">{sym.file}</span> · {sym.kind}</>}>
              <div className="ol-stack">
                {sym.delta && <div className="ol-callout"><Label>Index delta</Label><span>{sym.delta}</span></div>}
                <pre className="ol-code">{sym.excerpt.map((l, i) => <div key={i} className={l.startsWith('+') ? 'is-add' : ''}>{l}</div>)}</pre>
                <p className="ol-small ol-muted">Illustrative symbol excerpt · not extracted code.</p>
                <table className="ol-table">
                  <thead><tr><th>Relation</th><th>Target</th><th>Origin</th><th>Confidence</th></tr></thead>
                  <tbody>{sym.relations.map(([r, t, o, cf]) => <tr key={r + t}><td className="ol-id">{r}</td><td>{t}</td><td><span className={cx('ol-origin', 'is-' + o.toLowerCase().replace(/[^a-z]/g, ''))}>{o}</span></td><td className="ol-mono">{cf}</td></tr>)}</tbody>
                </table>
              </div>
            </Panel>
            <Panel title="Spec ↔ code links">
              <div className="ol-stack">
                {sym.links.map((l) => (
                  <div key={l.spec} className="ol-linkcard">
                    <div className="ol-row-b"><span className="ol-id">{l.spec}</span><span className={cx('ol-origin', 'is-' + l.origin.toLowerCase().replace(/[^a-z]/g, ''))}>{l.origin}</span></div>
                    <KV rows={[['Confidence', <span className="ol-mono">{l.conf}</span>], ['Evidence', <span className="ol-mono ol-small">{l.evidence}</span>]]} />
                  </div>
                ))}
                <p className="ol-small ol-muted">Principal symbols map to specifications. Helpers inherit context through structural relations instead of receiving duplicate feature links.</p>
                <div className="ol-actions ol-actions-col">
                  <Button variant="primary" onClick={() => c.open('S07', anchor)}>Trace symbol to intent →</Button>
                  <Button onClick={() => c.open('S08')}>Show impact</Button>
                </div>
              </div>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}

// ═════════ S07 · Traceability ═════════
export function S07({ c }: { c: Ctx }) {
  const d = DETAIL[c.j.id].trace;
  const [dir, setDir] = useState('fwd');
  const [hist, setHist] = useState(true);
  const chain = dir === 'fwd' ? d.chain : [...d.chain].reverse();
  return (
    <div className="ol-screen">
      <DrillHeader c={c} screen="S07" right={<Button onClick={() => { c.setLens('trace'); c.nav('S02'); }}>Show on map (trace lens)</Button>} />
      <div className="ol-cols ol-cols-2w">
        <Panel title="Narrative lineage" sub={`${d.direction} · every record and relation is traversable in both directions`} actions={
          <div className="ol-row">
            <div className="ol-seg"><button type="button" className={cx('ol-seg-i', dir === 'fwd' && 'is-on')} onClick={() => setDir('fwd')}>Origin → outcome</button><button type="button" className={cx('ol-seg-i', dir === 'back' && 'is-on')} onClick={() => setDir('back')}>Outcome → origin</button></div>
            <label className="ol-toggle"><input type="checkbox" checked={hist} onChange={() => setHist(!hist)} /> history</label>
          </div>
        }>
          <ol className="ol-chain">
            {chain.map((s, i) => {
              const first = node(c.j, s.ids[0]);
              const stt = first ? statusAt(first, c.stage) : 'recorded';
              const rel = dir === 'fwd' ? s.rel : chain[i + 1]?.rel;
              return (
                <li key={s.layer} className={cx('ol-chain-s', stt === 'future' && 'is-future')}>
                  <div className="ol-chain-l"><Label>{s.layer}</Label>{s.prov && <ProvenanceBadge kind={s.prov as any} />}</div>
                  <div className="ol-chain-b">
                    <div className="ol-chain-t">{s.text}</div>
                    <div className="ol-chips">
                      {s.ids.map((id) => { const nn = node(c.j, id); return nn ? <button key={id} type="button" className="ol-idchip" onClick={() => c.open('S02', nn.id)}><span className="ol-id">{nn.ref}</span><StatusBadge status={statusAt(nn, c.stage)} size="sm" /></button> : <span key={id} className="ol-id">{id}</span>; })}
                    </div>
                    {hist && s.hist && <div className="ol-chain-h">↳ {s.hist}</div>}
                  </div>
                  {i < chain.length - 1 && rel && <div className="ol-chain-rel"><span>{dir === 'fwd' ? '↓' : '↑'}</span> <span className="ol-id">{rel}</span></div>}
                </li>
              );
            })}
          </ol>
        </Panel>
        <Panel title={d.title}>
          <div className="ol-stack">
            {d.answer.map((p, i) => <p key={i}>{p}</p>)}
            <div>
              <Label>Link origins</Label>
              <ul className="ol-legendlist">
                <li><span className="ol-origin is-generatedlineage">GENERATED_LINEAGE</span> Olympus produced the code through traced work · 1.0</li>
                <li><span className="ol-origin is-discovered">DISCOVERED</span> found in an existing repository · carries confidence</li>
                <li><span className="ol-origin is-humanconfirmed">HUMAN_CONFIRMED</span> discovered, then reviewed and promoted</li>
              </ul>
            </div>
            <div className="ol-actions ol-actions-col"><Button onClick={() => c.open('S06')}>Inspect code →</Button><Button onClick={() => c.open('S09')}>Inspect proof →</Button></div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

// ═════════ S08 · Impact Explorer ═════════
export function S08({ c }: { c: Ctx }) {
  const d = DETAIL[c.j.id].impact;
  return (
    <div className="ol-screen">
      <DrillHeader c={c} screen="S08" right={<Button onClick={() => { c.setLens('impact'); c.nav('S02'); }}>Show on map (impact lens)</Button>} />
      <div className="ol-cols ol-cols-2w">
        <Panel title={d.title} sub={d.mode}>
          <div className="ol-stack">
            <p>{d.lead}</p>
            <div>
              <div className="ol-row-b"><Label>{d.directLabel}</Label><ProvenanceBadge kind="FACT" /></div>
              <table className="ol-table">
                <thead><tr><th>Path / obligation</th><th>Selection rationale</th><th>Source</th></tr></thead>
                <tbody>{d.direct.map(([p, r, s]) => <tr key={p}><td className="ol-mono">{p}</td><td>{r}</td><td className="ol-small ol-muted">{s}</td></tr>)}</tbody>
              </table>
            </div>
            <div>
              <div className="ol-row-b"><Label>{d.inferredLabel}</Label><ProvenanceBadge kind="INFERENCE" /></div>
              <table className="ol-table is-inferred">
                <thead><tr><th>Candidate</th><th>Rationale</th><th>Confidence / class</th></tr></thead>
                <tbody>{d.inferred.map(([p, r, s]) => <tr key={p}><td className="ol-mono">{p}</td><td>{r}</td><td className="ol-mono ol-small">{s}</td></tr>)}</tbody>
              </table>
            </div>
          </div>
        </Panel>
        <Panel title="Proposed scope">
          <div className="ol-stack">
            {d.scope.map((s) => <div key={s.label}><Label>{s.label}</Label><ul className="ol-list">{s.lines.map((l) => <li key={l} className="ol-mono ol-small">{l}</li>)}</ul></div>)}
            <p className="ol-small ol-muted">{d.note}</p>
            <div className="ol-actions ol-actions-col"><Button variant="primary" onClick={() => c.open('S04')}>Review bounded plan →</Button><Button>Escalate architecture delta</Button></div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

// ═════════ S09 · Assurance ═════════
export function S09({ c }: { c: Ctx }) {
  const d = DETAIL[c.j.id].assurance;
  const anchor = c.j.defaults.S09!;
  return (
    <div className="ol-screen">
      <DrillHeader c={c} screen="S09" />
      <div className="ol-target">
        <Label>{d.mode === 'readiness' ? 'Readiness target' : 'Exact assurance target'}</Label>
        <span className="ol-id">{d.target}</span>
        <span className="ol-target-msg">{d.banner}</span>
      </div>
      <div className="ol-cols ol-cols-2w">
        <Panel title={d.mode === 'readiness' ? 'Baseline and promotion evidence' : 'Exact-SHA evidence matrix'} sub={d.mode === 'repair' ? 'Before-failure evidence is retained; after-proof must be independent' : 'Agents provide evidence and recommendations; Olympus finalizes'} pad={false}>
          <EvidenceMatrix groups={d.groups} target={d.target} onRef={(r) => { const x = node(c.j, r); if (x) c.open('S02', x.id); }} />
          <div className="ol-panel-pad">
            <p className="ol-small ol-muted">{d.note}</p>
            <div className="ol-actions"><Button variant="primary" onClick={() => c.why(anchor)}>Inspect blocking proof</Button><Button onClick={() => c.command({ label: 'Request verification', cmd: `POST /delivery-cycles/${c.j.cycle}/commands/request_verification` }, anchor)}>Request verification</Button></div>
          </div>
        </Panel>
        <div className="ol-colstack">
          <Panel title={d.mode === 'readiness' ? 'Readiness conditions' : 'Deterministic gate finalization'} sub={d.mode === 'readiness' ? 'Not release gates' : 'Server computation · policy gate.release@v2'}>
            <ul className="ol-checks">
              {d.checks.map(([l, ok, det], i) => (
                <li key={i} className={cx('ol-check', ok === true ? 'is-ok' : ok === false ? 'is-no' : 'is-na')}>
                  <span className="ol-check-g">{ok === true ? '✓' : ok === false ? '✕' : '○'}</span><span className="ol-check-l">{l}</span>{det && <span className="ol-check-d">{det}</span>}
                </li>
              ))}
            </ul>
          </Panel>
          <Panel title="Findings" sub="Finding → remediation task → new execution → targeted revalidation">
            {d.findings.length === 0 ? <p className="ol-muted ol-small">No findings recorded at this target.</p> : (
              <ul className="ol-findings">{d.findings.map(([id, t, s]) => <li key={id}><span className="ol-id">{id}</span><span>{t}</span><span className={cx('ol-tag', s === 'needs decision' && 'is-attn')}>{s}</span></li>)}</ul>
            )}
            <div className="ol-actions"><Button onClick={() => c.open('S10')}>Open release eligibility →</Button></div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

// ═════════ S10 · Release / outcome ═════════
export function S10({ c }: { c: Ctx }) {
  const d = DETAIL[c.j.id].release;
  const rel = node(c.j, d.id)!;
  const rs = statusAt(rel, c.stage);
  const eligible = d.eligibility.every(([, s]) => ['passed', 'approved', 'n-a'].includes(s));
  const handoff = d.mode === 'handoff';
  const ready = handoff && statusAt(rel, c.stage) === 'rfc';
  return (
    <div className="ol-screen">
      <DrillHeader c={c} screen="S10" />
      <div className="ol-cols ol-cols-2w">
        <Panel title={d.title} sub={handoff ? 'Readiness handoff · no new release or deployment' : 'Release is independent of optional deployment'} actions={<StatusBadge status={rs === 'future' ? (handoff ? 'not-ready' : 'not-eligible') : rs} />}>
          <div className="ol-stack">
            <KV rows={d.manifest.map(([k, v]) => [k, <span className="ol-mono ol-small">{v}</span>])} />
            <EligibilityChecklist title={handoff ? 'READY_FOR_CHANGE predicates' : 'Release eligibility · release.eligibility@v3'} items={d.eligibility} />
            <div className="ol-actions">
              {handoff ? (
                <>
                  <Button variant="primary" disabled={!ready} title={ready ? '' : 'READY_FOR_CHANGE not reached'} onClick={() => c.intake('FC')}>Start Feature Change</Button>
                  <Button disabled={!ready} onClick={() => c.intake('BG')}>Start Bug Fix</Button>
                  {!ready && <span className="ol-small ol-muted">Available once READY_FOR_CHANGE is reached.</span>}
                </>
              ) : (
                <>
                  <Button onClick={() => c.approval(c.j.id === 'FC' ? 'APR-302' : c.j.id === 'GF' ? 'APR-103' : 'APR-401')}>Review release approval</Button>
                  <Button variant="primary" disabled={!eligible} title={eligible ? '' : 'All server eligibility conditions must pass'}>Execute release{eligible ? '' : ' · blocked'}</Button>
                  <Button onClick={() => c.open('S07')}>Open complete lineage</Button>
                </>
              )}
            </div>
          </div>
        </Panel>
        <div className="ol-colstack">
          <Panel title={handoff ? 'Repository truth' : 'Release truth'}>
            <KV rows={d.truth.map(([k, v]) => [k, <span className="ol-mono ol-small">{v}</span>])} />
            <p className="ol-small ol-muted">{handoff ? 'Brownfield ends at readiness. The existing release is unchanged.' : 'Approval cannot substitute for proof. Eligibility includes all required approvals. Only a server-accepted execute command records a release.'}</p>
          </Panel>
          <Panel title="Approvals">
            <ul className="ol-findings">{d.approvals.map(([id, t, s]) => { const nn = node(c.j, id); return <li key={id}><span className="ol-id">{id}</span><span>{t}</span><StatusBadge status={nn ? statusAt(nn, c.stage) : s} size="sm" /></li>; })}</ul>
          </Panel>
          <Panel title="Outcome history">
            {d.history.length === 0 ? <p className="ol-muted ol-small">No prior outcomes. This cycle creates the first.</p> : <ul className="ol-findings">{d.history.map(([r, cy, sha]) => <li key={r}><span className="ol-id">{r}</span><span>{cy}</span><span className="ol-sha">{sha}</span></li>)}</ul>}
            <div className="ol-deploy"><Label>Deployment (Stratos)</Label><span>Separate and optional. No green deployment badge without an independent deployment result.</span></div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

// ═════════ Utilities: Integrations, Audit ═════════
export function INT({ c }: { c: Ctx }) {
  return (
    <div className="ol-screen">
      <div className="ol-ch"><div className="ol-crumbs"><span className="ol-crumb">SupportDesk</span><span className="ol-crumb">Integrations</span></div><h1 className="ol-title">Integrations</h1><div className="ol-ch-meta"><span>Authenticated inbound events · governed outbound actions · reconciliation</span></div></div>
      <div className="ol-cols ol-cols-2w">
        <Panel title="Outbound actions" sub="Every connector mutation runs inside an Execution / TaskContract context" pad={false}>
          <table className="ol-table">
            <thead><tr><th>Action</th><th>Execution · scope</th><th>Policy</th><th>Result</th></tr></thead>
            <tbody>
              <tr><td className="ol-mono">git.create_pull_request</td><td className="ol-mono ol-small">EX-204 · TC-104 v2</td><td className="ol-small">risk R2 · allowed</td><td><StatusBadge status="passed" size="sm" label="PR #418" /></td></tr>
              <tr><td className="ol-mono">ci.trigger_e2e</td><td className="ol-mono ol-small">SN-003 · IC-003</td><td className="ol-small">exact SHA c83a12d</td><td><StatusBadge status="pending" size="sm" label="Outcome unknown" /></td></tr>
              <tr><td className="ol-mono">tracker.comment</td><td className="ol-mono ol-small">DC-003</td><td className="ol-small">scoped to cycle</td><td><StatusBadge status="passed" size="sm" label="Posted" /></td></tr>
              <tr><td className="ol-mono">git.push protected main</td><td className="ol-mono ol-small">EX-205</td><td className="ol-small">protected branch</td><td><StatusBadge status="denied" size="sm" /></td></tr>
            </tbody>
          </table>
          <div className="ol-panel-pad">
            <div className="ol-callout is-attention">
              <StatusBadge status="pending" size="sm" label="Reconciliation required" />
              <span><span className="ol-id">ci.trigger_e2e</span> timed out after the provider accepted the request. A blind retry could start a duplicate run. Olympus queries provider state with correlation <span className="ol-id">CORR-882</span> first.</span>
              <Button size="sm" variant="primary">Reconcile provider state</Button>
            </div>
          </div>
        </Panel>
        <Panel title="Inbound events" sub="Signature verified · idempotency key · correlation ID" pad={false}>
          <table className="ol-table">
            <thead><tr><th>Source</th><th>Event</th><th>State</th></tr></thead>
            <tbody>
              <tr><td>GitHub</td><td className="ol-mono ol-small">push main 9e31ab7 · sig ✓</td><td><StatusBadge status="recorded" size="sm" /></td></tr>
              <tr><td>Tracker</td><td className="ol-mono ol-small">ISSUE-311 → CR-004 · key i-311</td><td><StatusBadge status="recorded" size="sm" /></td></tr>
              <tr><td>Tracker</td><td className="ol-mono ol-small">ISSUE-311 duplicate · key i-311</td><td><StatusBadge status="superseded" size="sm" label="Deduplicated" /></td></tr>
              <tr><td>CI</td><td className="ol-mono ol-small">e2e result @ 4a871dc</td><td><StatusBadge status="historical" size="sm" label="Old SHA · not evidence" /></td></tr>
            </tbody>
          </table>
        </Panel>
      </div>
    </div>
  );
}

export function AUD({ c }: { c: Ctx }) {
  const rows: string[][] = [
    ['10:53:12', 'control-api', 'release.eligibility recomputed', 'R2', 'v14 → v15', 'CORR-901'],
    ['10:52:40', 'Engineering lead', 'approval.requested', 'APR-302', '—', 'CORR-899'],
    ['10:47:03', 'ToolGateway', 'test.run → FAILED (evidence retained)', 'EX-204', '—', 'CORR-882'],
    ['10:41:55', 'scheduler', 'execution.created', 'EX-204 · SNAP-204', 'TC-104 v2', 'CORR-882'],
    ['10:41:50', 'control-api', 'execution.stale', 'EX-203', 'TC-104 v1 ≠ v2', 'CORR-877'],
    ['10:12:09', 'Engineering lead', 'spec.approved', 'SPEC-011 v2', 'v1 → v2', 'CORR-861'],
  ];
  return (
    <div className="ol-screen">
      <div className="ol-ch"><div className="ol-crumbs"><span className="ol-crumb">SupportDesk</span><span className="ol-crumb">Audit history</span></div><h1 className="ol-title">Audit history</h1><div className="ol-ch-meta"><span>Attributable, immutable. Failures, approvals and connector results stay traversable.</span></div></div>
      <Panel pad={false}>
        <table className="ol-table">
          <thead><tr><th>Time</th><th>Actor / service</th><th>Command / event</th><th>Record</th><th>Version</th><th>Correlation</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r[0] + r[2]}><td className="ol-sha">{r[0]}</td><td>{r[1]}</td><td className="ol-mono ol-small">{r[2]}</td><td className="ol-id">{r[3]}</td><td className="ol-mono ol-small">{r[4]}</td><td className="ol-id">{r[5]}</td></tr>)}</tbody>
        </table>
      </Panel>
    </div>
  );
}

const SCREEN_MAP: Record<ScreenId, any> = { S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, INT, AUD };

// ═════════ Approval subjects ═════════
export function approvalFor(j: Journey, id: string): ApprovalSubject {
  const M: Record<string, ApprovalSubject> = {
    'APR-302': { type: 'Release approval', id: 'APR-302', scope: 'R2 · DC-003', version: 'R2 manifest v1', sha: 'c83a12d', reason: 'Release “Add ticket priority” as R2.', impact: 'R2 becomes the persistent project baseline; R1 remains reachable as history.', risk: 'MEDIUM. AC-011-03 E2E evidence is missing — approving does not make R2 eligible.', records: ['IC-003', 'EV-501', 'EV-601…603', 'WR-003', 'AC-011-03 (missing)'], cmd: 'POST /approvals/APR-302/decision' },
    'SPEC-001': { type: 'Scope approval', id: 'APR-101', scope: 'SPEC-001 v1 · SPEC-002 v1', version: 'v1', sha: 'PS-001 sha256:4be1…', reason: 'Approve the proposed behavioural scope for SupportDesk R1.', impact: 'Unlocks ImplementationSpec derivation and architecture review.', risk: 'LOW. One open clarification (CHK-012) remains on SPEC-002.', records: ['PS-001 v1', 'SPEC-001 v1', 'SPEC-002 v1'], cmd: 'POST /specs/SPEC-001/approve' },
    'REC-017': { type: 'Recovered spec promotion', id: 'APR-201', scope: 'REC-017 → SPEC-017', version: 'REC-017 r1', sha: '9e31ab7', reason: 'Promote the recovered ticket lifecycle to trusted intent.', impact: 'Becomes canonical product truth and a baseline source for future changes.', risk: 'MEDIUM. Confidence 0.84; UNC-004 still open — promotion should wait for DEC-004.', records: ['REC-017', 'CODE-117', 'OB-009', 'tests/test_ticket_status.py', 'UNC-004'], cmd: 'POST /delivery-cycles/DC-002/commands/promote_recovered_spec' },
    'UNC-004': { type: 'Product decision', id: 'DEC-004', scope: 'UNC-004 · Ticket lifecycle', version: 'REC-017 r1', sha: '9e31ab7', reason: 'Decide whether updates to CLOSED tickets are rejected (409).', impact: 'Versions REC-017 into SPEC-017 v3. OB-011 (HTTP 500) stays an observed defect, not a baseline.', risk: 'Product decision. Existing clients may rely on the current behaviour.', records: ['UNC-004', 'OB-011', 'REC-017', 'CODE-130'], cmd: 'POST /delivery-cycles/DC-002/commands/record_decision' },
    'APR-103': { type: 'Release approval', id: 'APR-103', scope: 'R1 · DC-001', version: 'R1 manifest v1', sha: '9e31ab7', reason: 'Release SupportDesk R1.', impact: 'First persistent release.', risk: 'LOW once all ACs carry evidence.', records: ['IC-001', 'EV-1xx', 'WR-001'], cmd: 'POST /approvals/APR-103/decision' },
    'APR-401': { type: 'Release approval', id: 'APR-401', scope: 'R3 · DC-004', version: 'R3 manifest v1', sha: 'e5d1c04', reason: 'Release the CLOSED-ticket repair as R3.', impact: 'R3 replaces R2 as the project baseline.', risk: 'LOW. Minimal repair; failure evidence retained.', records: ['EV-901', 'EV-951', 'EV-952', 'IC-004'], cmd: 'POST /approvals/APR-401/decision' },
  };
  if (M[id]) return M[id];
  const n = j.nodes.find((x) => x.id === id);
  return { type: 'Approval review', id, scope: n?.ref ?? id, version: n?.ref ?? '—', sha: n?.sha ?? j.base.canonical, reason: n?.title ?? '', impact: '—', risk: '—', records: [n?.ref ?? id], cmd: `POST /approvals/${id}/decision` };
}

const ASK: Record<string, { q: string; a: string[]; refs: string[]; cmd?: { label: string; api: string; id: string } }> = {
  GF: { q: 'Why hasn’t TASK-104 started?', a: ['TASK-104 integrates candidates from TASK-102 and TASK-103. Both are still running, so scheduler eligibility fails on “dependencies complete” and “required artifacts exist”.', 'TASK-103’s attempt EX-104 is checkpointed on CHK-012 — answering it is the fastest way forward.'], refs: ['TASK-104', 'EX-104', 'CHK-012'], cmd: { label: 'Answer CHK-012', api: 'POST /delivery-cycles/DC-001/commands/answer_checkpoint', id: 'EX-104' } },
  BF: { q: 'Can I start a feature change yet?', a: ['Not yet. READY_FOR_CHANGE requires trusted baselines, promoted intent and no critical uncertainty.', 'UNC-004 (CLOSED immutability) is open and blocks REC-017 promotion and readiness.'], refs: ['UNC-004', 'REC-017', 'RDY-001'], cmd: { label: 'Record decision for UNC-004', api: 'POST /delivery-cycles/DC-002/commands/record_decision', id: 'UNC-004' } },
  FC: { q: 'Why can’t R2 be released?', a: ['Release eligibility (release.eligibility@v3) has two unmet predicates: mandatory AC evidence and required approvals.', 'AC-011-03 has an E2E result only at 4a871dc, a provisional worktree SHA. Old-SHA proof cannot satisfy IC-003 @ c83a12d.', 'APR-302 is pending. Approving it alone will not make R2 eligible.'], refs: ['AC-011-03', 'APR-302', 'GATE-003', 'R2'], cmd: { label: 'Request exact-target verification', api: 'POST /delivery-cycles/DC-003/commands/request_verification', id: 'AC-011-03' } },
  BG: { q: 'Is the bug actually fixed?', a: ['The original reproduction now returns 409 at e5d1c04 (EV-951). EV-901 — the 500 before repair — stays on record.', 'Regression test EV-952 is still running and impacted baselines are queued. Until Sentinel evidence lands and gates finalize, the fix is supported, not proven.'], refs: ['EV-901', 'EV-951', 'EV-952', 'RC-004'] },
};

// ═════════ The app (all screens share state) ═════════
export function OlympusApp({ screen: s0 = 'S02', cycle = 'DC-003', stage: st0, lens: l0 = 'lifecycle', select: sel0, view: v0 = 'graph', dialog: d0, drawer: dr0, stream }: { screen?: ScreenId; cycle?: string; stage?: number; lens?: Lens; select?: string; view?: 'graph' | 'list'; dialog?: string; drawer?: string; stream?: 'live' | 'disconnected' }) {
  const [jid, setJid] = useState(journeyById(cycle).id);
  const j = journeyById(jid);
  const [stageBy, setStageBy] = useState(st0 != null ? { [journeyById(cycle).id]: st0 } : {});
  const [selBy, setSelBy] = useState(sel0 ? { [journeyById(cycle).id]: sel0 } : {});
  const [screen, setScreen] = useState(s0);
  const [lens, setLens] = useState(l0);
  const [view, setView] = useState(v0);
  const [dialog, setDialog] = useState(d0 ? { kind: d0, id: sel0 ?? j.focus } : (null as null | { kind: string; id: string }));
  const [drawer, setDrawer] = useState(dr0 ? { kind: dr0, id: sel0 ?? j.focus } : (null as null | { kind: string; id: string }));
  const [toast, setToast] = useState(null as null | string);
  const stage = (stageBy as any)[jid] ?? j.live;
  const sel = (selBy as any)[jid] ?? j.focus;

  const c: Ctx = {
    j, stage, sel, lens, view,
    setStage: (i) => setStageBy({ ...stageBy, [jid]: i }),
    select: (id) => setSelBy({ ...selBy, [jid]: id }),
    setLens, setView,
    nav: (s) => setScreen(s),
    open: (s, id) => { if (id) setSelBy({ ...selBy, [jid]: id }); setScreen(s); },
    openLane: (l) => { const s = LANES[laneIndex(l)].screen; setScreen(s); },
    command: (cm, id) => {
      if (cm.dialog === 'approval') setDialog({ kind: 'approval', id: j.nodes.find((n) => n.id === id)?.id ?? id });
      else if (cm.dialog === 'checkpoint') setDialog({ kind: 'checkpoint', id });
      else { setToast(`Preview only — would send ${cm.cmd || cm.label}. The server validates expected state and authorization.`); setTimeout(() => setToast(null), 3600); }
    },
    why: (id) => setDrawer({ kind: 'why', id }),
    approval: (id) => setDialog({ kind: 'approval', id }),
    intake: (k) => setDialog({ kind: 'intake', id: k ?? 'FC' }),
  };
  const Screen = SCREEN_MAP[screen as ScreenId] ?? S02;
  const wn = drawer ? j.nodes.find((n) => n.id === drawer.id) : null;
  const ask = ASK[jid];
  const cp = DETAIL.GF.execs['EX-104'].checkpoint!;

  const overlay = (
    <>
      {dialog?.kind === 'approval' && <ApprovalDialog open onClose={() => setDialog(null)} subject={approvalFor(j, dialog.id)} />}
      {dialog?.kind === 'checkpoint' && <CheckpointDialog open onClose={() => setDialog(null)} c={cp} />}
      {dialog?.kind === 'intake' && <IntakeForm open onClose={() => setDialog(null)} initial={dialog.id} />}
      {drawer?.kind === 'why' && wn && (
        <Drawer open onClose={() => setDrawer(null)} title={`${wn.ref} · ${meta(statusAt(wn, stage)).l}`} label="Why this state?">
          <WhyPanel why={whyFor(j, wn, stage)} onRef={(r) => { const x = j.nodes.find((n) => n.id === r || n.ref === r); if (x) setDrawer({ kind: 'why', id: x.id }); }} />
          <p className="ol-small ol-muted ol-mt">This is the server’s evaluation record. A model explanation may summarize it but cannot replace it.</p>
          <div className="ol-actions"><Button variant="primary" onClick={() => { setDrawer(null); c.open('S02', wn.id); }}>Show on map</Button><Button onClick={() => { setDrawer(null); c.open(LANES[laneIndex(wn.lane)].screen, wn.id); }}>Open {screenById(LANES[laneIndex(wn.lane)].screen).name}</Button></div>
        </Drawer>
      )}
      {drawer?.kind === 'ask' && (
        <Drawer open onClose={() => setDrawer(null)} title="Ask Olympus" label={`Scope · ${j.cycle} · ${j.stages[stage].k}`}>
          <div className="ol-ask-q"><Label>You asked</Label><p>{ask.q}</p></div>
          <div className="ol-ask-a">
            <Label>Answer · built from authoritative records</Label>
            {ask.a.map((p, i) => <p key={i}>{p}</p>)}
            <div className="ol-chips">{ask.refs.map((r) => { const x = j.nodes.find((n) => n.id === r || n.ref === r); return x ? <button key={r} type="button" className="ol-idchip" onClick={() => { setDrawer(null); c.open('S02', x.id); }}><span className="ol-id">{x.ref}</span><StatusBadge status={statusAt(x, stage)} size="sm" /></button> : <span key={r} className="ol-id ol-chipid">{r}</span>; })}</div>
          </div>
          {ask.cmd && (
            <div className="ol-ask-cmd">
              <Label>Suggested command · not yet sent</Label>
              <code className="ol-cmd-api">{ask.cmd.api}</code>
              <Button variant="primary" onClick={() => { setDrawer(null); c.command({ label: ask.cmd!.label, cmd: ask.cmd!.api, dialog: ask.cmd!.id === 'EX-104' ? 'checkpoint' : ask.cmd!.id === 'UNC-004' ? 'approval' : undefined }, ask.cmd!.id); }}>{ask.cmd.label}</Button>
              <p className="ol-small ol-muted">Ask Olympus explains existing records. Any mutation becomes an explicit typed command with normal authorization.</p>
            </div>
          )}
          <label className="ol-field"><span className="ol-label">Ask about this cycle</span><input placeholder="e.g. What changed since R1?" /></label>
        </Drawer>
      )}
      {toast && <div className="ol-toast" role="status">{toast}</div>}
    </>
  );

  return (
    <AppShell screen={screen} onNav={setScreen} journey={j} stage={stage} stream={stream} onCycle={(id: string) => setJid(journeyById(id).id)} onAsk={() => setDrawer({ kind: 'ask', id: '' })} onNew={() => setDialog({ kind: 'intake', id: 'FC' })} overlay={overlay}>
      <Screen c={c} />
    </AppShell>
  );
}

export { JOURNEYS, SCREENS };
