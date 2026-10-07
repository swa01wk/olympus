import { React } from './react';
import { statusAt, whyFor, cmdsFor, neighbours, sentence, LANES, laneIndex, screenById, type Journey, type Why, type Cmd, type ScreenId } from './model';
import { StatusBadge, ProvenanceBadge, IdRef, Button, KV, Label, cx } from './primitives';

export function WhyPanel({ why, onRef, evaluated = '10:53:12 · control API' }: { why: Why; onRef?: (id: string) => void; evaluated?: string }) {
  return (
    <div className="ol-why">
      <p className="ol-why-sum">{why.summary}</p>
      {why.checks && (
        <ul className="ol-checks">
          {why.checks.map(([label, ok, detail], i) => (
            <li key={i} className={cx('ol-check', ok === true ? 'is-ok' : ok === false ? 'is-no' : 'is-na')}>
              <span className="ol-check-g" aria-label={ok === true ? 'passed' : ok === false ? 'unmet' : 'not applicable'}>{ok === true ? '✓' : ok === false ? '✕' : '—'}</span>
              <span className="ol-check-l">{label}</span>
              {detail && <span className="ol-check-d">{detail}</span>}
            </li>
          ))}
        </ul>
      )}
      {why.blocking && why.blocking.length > 0 && (
        <div className="ol-why-row">
          <Label>Blocking records</Label>
          <div className="ol-chips">{why.blocking.map((b) => <IdRef key={b} id={b} onClick={onRef} />)}</div>
        </div>
      )}
      <div className="ol-why-meta">
        {why.policy && <span><span className="ol-label">Policy</span> <span className="ol-id">{why.policy}</span></span>}
        {why.inputs && <span><span className="ol-label">Inputs</span> <span className="ol-id">{why.inputs}</span></span>}
        <span><span className="ol-label">Evaluated</span> <span className="ol-sha">{evaluated}</span></span>
      </div>
      {why.next && <p className="ol-why-next"><span className="ol-label">Next</span> {why.next}</p>}
    </div>
  );
}

export function CommandList({ cmds, onCommand }: { cmds: Cmd[]; onCommand?: (c: Cmd) => void }) {
  if (!cmds.length) return <p className="ol-muted ol-small">No operator command is available in this state.</p>;
  return (
    <ul className="ol-cmds">
      {cmds.map((c, i) => (
        <li key={i} className={cx('ol-cmd', c.enabled === false && 'is-off')}>
          <Button size="sm" variant={i === 0 && c.enabled !== false ? 'primary' : 'quiet'} disabled={c.enabled === false} onClick={() => onCommand?.(c)}>
            {c.label}
          </Button>
          <code className="ol-cmd-api">{c.cmd}</code>
          {c.reason && <span className="ol-cmd-why">{c.reason}</span>}
        </li>
      ))}
    </ul>
  );
}

export function ObjectInspector({ journey: j, stage, id, onSelect, onOpen, onCommand, lens, onHoverRel }: { onHoverRel?: (k: string | null) => void; journey: Journey; stage: number; id?: string; onSelect?: (id: string) => void; onOpen?: (s: ScreenId, id: string) => void; onCommand?: (c: Cmd, id: string) => void; lens?: string }) {
  const n = j.nodes.find((x) => x.id === id);
  if (!n) {
    return (
      <aside className="ol-insp">
        <div className="ol-insp-empty">
          <Label>Object inspector</Label>
          <p>Select a record on the map to see its state, the reason for it, its provenance and the commands you may issue.</p>
        </div>
      </aside>
    );
  }
  const s = statusAt(n, stage);
  const why = whyFor(j, n, stage);
  const cmds = cmdsFor(j, n, stage);
  const { ins, outs } = neighbours(j, n.id);
  const lane = LANES[laneIndex(n.lane)];
  const screen = screenById(lane.screen);
  const resolve = (ref: string) => j.nodes.find((x) => x.id === ref || x.ref === ref || x.ref.startsWith(ref + ' '))?.id;
  const go = (ref: string) => { const r = resolve(ref); if (r) onSelect?.(r); };
  return (
    <aside className="ol-insp" aria-label={`Inspector: ${n.ref}`}>
      <div className="ol-insp-h">
        <Label>{n.kind} · {lane.name}</Label>
        <div className="ol-insp-id">{n.ref}</div>
        <div className="ol-insp-t">{n.title}</div>
        <div className="ol-chips">
          <StatusBadge status={s} />
          {n.prov && <ProvenanceBadge kind={n.prov} conf={n.conf} source={n.origin} />}
        </div>
      </div>
      <div className="ol-insp-sec">
        <h3 className="ol-insp-st">Why this state?</h3>
        <WhyPanel why={why} onRef={go} />
      </div>
      <div className="ol-insp-sec">
        <h3 className="ol-insp-st">Provenance and scope</h3>
        <KV rows={[
          ['Authority', n.authority ?? 'Olympus control-plane record'],
          ['Origin', n.origin ?? (n.prov === 'FACT' ? 'Deterministic observation' : 'Olympus-created record')],
          ['Commit scope', <span className="ol-sha">{n.sha ?? (n.lane === 'code' || n.lane === 'evidence' ? j.base.canonical : '—')}</span>],
          ...(n.workspace ? [['Workspace', n.workspace] as [string, any]] : []),
          ...(n.hist ? [['History', n.hist] as [string, any]] : []),
        ]} />
        {n.stack && (
          <ul className="ol-stack-list">
            {n.stack.map((m) => <li key={m}><span className="ol-id">{m.split(' ')[0]}</span> {m.split(' ').slice(1).join(' ')}</li>)}
          </ul>
        )}
      </div>
      <div className="ol-insp-sec">
        <h3 className="ol-insp-st">Relations <span className="ol-muted">({ins.length + outs.length}) · hover to locate on map</span></h3>
        <ul className="ol-rels">
          {[...ins, ...outs].map((e, i) => {
            const [a, rel, b] = sentence(e);
            return (
              <li key={i} className={cx('ol-rel', e.kind === 'inferred' && 'is-inf')} onMouseEnter={() => onHoverRel?.(`${e.from}>${e.to}>${e.rel}`)} onMouseLeave={() => onHoverRel?.(null)} onFocus={() => onHoverRel?.(`${e.from}>${e.to}>${e.rel}`)} onBlur={() => onHoverRel?.(null)}>
                <IdRef id={j.nodes.find((x) => x.id === a)?.ref ?? a} onClick={() => onSelect?.(a)} />
                <span className="ol-rel-t">{rel}</span>
                <IdRef id={j.nodes.find((x) => x.id === b)?.ref ?? b} onClick={() => onSelect?.(b)} />
                {(e.note || e.kind === 'inferred') && <span className="ol-rel-n">{e.note ?? 'inferred'}</span>}
              </li>
            );
          })}
        </ul>
      </div>
      <div className="ol-insp-sec">
        <h3 className="ol-insp-st">Permitted commands</h3>
        <CommandList cmds={cmds} onCommand={(c) => onCommand?.(c, n.id)} />
      </div>
      <div className="ol-insp-f">
        <Button variant="primary" onClick={() => onOpen?.(lane.screen, n.id)}>Open in {screen.name} →</Button>
        {lens === 'trace' && <Button onClick={() => onOpen?.('S07', n.id)}>Open Traceability</Button>}
        {lens === 'impact' && <Button onClick={() => onOpen?.('S08', n.id)}>Open Impact Explorer</Button>}
      </div>
    </aside>
  );
}
