import { React, useRef, useEffect, useState } from './react';
import { statusAt, meta, type Journey } from './model';
import type { Contract, ExecEvent } from './detail';
import { StatusBadge, Button, Label, cx, IdRef, ProvenanceBadge } from './primitives';

// ───────── Evidence matrix ─────────
export function EvidenceMatrix({ groups, target, onRef }: { groups: { name: string; rows: [string, string, string, string, string?][] }[]; target: string; onRef?: (id: string) => void }) {
  const tsha = target.split('·').pop()!.trim();
  return (
    <table className="ol-table ol-matrix">
      <thead>
        <tr><th>Obligation</th><th>Evidence</th><th>Target SHA</th><th>Result</th></tr>
      </thead>
      {groups.map((g) => (
        <tbody key={g.name}>
          <tr className="ol-tgroup"><th colSpan={4}>{g.name}</th></tr>
          {g.rows.map(([ob, ev, sha, st, note], i) => {
            const old = sha !== '—' && sha !== tsha && st !== 'future';
            return (
              <tr key={i} className={cx(old && 'is-hist')}>
                <td>{ob}{note && <div className="ol-cell-note">{note}</div>}</td>
                <td>{ev === '—' ? <span className="ol-muted">none</span> : <IdRef id={ev} onClick={onRef} />}</td>
                <td><span className={cx('ol-sha', old && 'is-old')}>{sha}</span>{old && <div className="ol-cell-note">not current target</div>}</td>
                <td><StatusBadge status={st} size="sm" /></td>
              </tr>
            );
          })}
        </tbody>
      ))}
    </table>
  );
}

// ───────── Eligibility checklist ─────────
export function EligibilityChecklist({ items, title }: { items: [string, string, string][]; title?: string }) {
  const unmet = items.filter(([, s]) => !['passed', 'approved', 'n-a', 'eligible', 'completed'].includes(s)).length;
  return (
    <div className="ol-elig">
      {title && <div className="ol-elig-h"><Label>{title}</Label><span className="ol-elig-sum">{unmet === 0 ? 'All predicates pass' : `${unmet} of ${items.length} unmet`}</span></div>}
      <ul>
        {items.map(([label, st, detail], i) => (
          <li key={i} className="ol-elig-r">
            <span className="ol-elig-l"><code>{label}</code></span>
            <span className="ol-elig-d">{detail}</span>
            <StatusBadge status={st} size="sm" />
          </li>
        ))}
      </ul>
    </div>
  );
}

// ───────── Task contract ─────────
export function TaskContractCard({ contract: c, taskId }: { contract: Contract; taskId: string }) {
  const sec = (k: string, v: string[], mono = true) => (
    <div className="ol-tc-s">
      <Label>{k}</Label>
      {v.length ? <ul>{v.map((x) => <li key={x} className={mono ? 'ol-mono' : ''}>{x}</li>)}</ul> : <div className="ol-muted">none</div>}
    </div>
  );
  return (
    <div className="ol-tc">
      <div className="ol-tc-h">
        <div>
          <Label>Task contract · immutable</Label>
          <div className="ol-insp-id">{c.version}</div>
        </div>
        <span className="ol-wt">{c.workType}</span>
      </div>
      <p className="ol-tc-obj">{c.objective}</p>
      <div className="ol-tc-grid">
        {sec('Inputs (pinned versions)', c.inputs)}
        {sec('Base commit', [c.base])}
        {sec('Allowed scope', c.allowed)}
        {sec('Prohibited', c.prohibited, false)}
        {sec('Constraints', c.constraints, false)}
        {sec('Required outputs', c.outputs)}
        {sec('Verification', c.verification)}
        {sec('Escalation', c.escalation)}
      </div>
      <p className="ol-small ol-muted">{taskId} is durable work. Each attempt pins this contract in an immutable snapshot.</p>
    </div>
  );
}

// ───────── Execution timeline ─────────
export function ExecutionTimeline({ events }: { events: ExecEvent[] }) {
  return (
    <ol className="ol-tl">
      {events.map(([t, text, action, d], i) => (
        <li key={i} className={cx('ol-tl-r', 'is-' + d)}>
          <span className="ol-sha ol-tl-t">{t}</span>
          <span className="ol-tl-x">{text}</span>
          <span className="ol-id ol-tl-a">{action}</span>
          <span className="ol-tl-d">
            {d === 'platform' ? <span className="ol-muted ol-small">platform</span> : <StatusBadge status={d === 'failed' ? 'failed' : d === 'passed' ? 'passed' : d} size="sm" label={d === 'allowed' ? 'Allowed' : d === 'denied' ? 'Denied · logged' : undefined} />}
          </span>
        </li>
      ))}
    </ol>
  );
}

export function AttemptHistory({ items, current, onSelect }: { items: { id: string; st: string; note: string }[]; current: string; onSelect?: (id: string) => void }) {
  return (
    <ol className="ol-attempts">
      {items.map((a, i) => (
        <li key={a.id}>
          <button type="button" className={cx('ol-attempt', a.id === current && 'is-on')} onClick={() => onSelect?.(a.id)}>
            <span className="ol-label">Attempt {i + 1}</span>
            <span className="ol-id">{a.id}</span>
            <StatusBadge status={a.st} size="sm" />
            <span className="ol-small ol-muted">{a.note}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}

// ───────── Version diff ─────────
export function VersionDiff({ left, right, leftLabel, rightLabel }: { left: string[]; right: string[]; leftLabel: string; rightLabel: string }) {
  return (
    <div className="ol-diff">
      <div>
        <Label>{leftLabel}</Label>
        <pre className="ol-code">{left.map((l) => <div key={l}>{l}</div>)}</pre>
      </div>
      <div>
        <Label>{rightLabel}</Label>
        <pre className="ol-code">{right.map((l) => <div key={l} className={l.startsWith('+') ? 'is-add' : l.startsWith('-') ? 'is-del' : ''}>{l}</div>)}</pre>
      </div>
    </div>
  );
}

// ───────── Task DAG (layered) ─────────
export function TaskDag({ journey: j, stage, selected, onSelect }: { journey: Journey; stage: number; selected?: string; onSelect?: (id: string) => void }) {
  const tasks = j.nodes.filter((n) => n.lane === 'work');
  const deps = j.edges.filter((e) => e.rel === 'DEPENDS_ON' && tasks.some((t) => t.id === e.from) && tasks.some((t) => t.id === e.to));
  const level: Record<string, number> = {};
  const lv = (id: string): number => {
    if (level[id] != null) return level[id];
    const pre = deps.filter((d) => d.to === id).map((d) => lv(d.from) + 1);
    return (level[id] = pre.length ? Math.max(...pre) : 0);
  };
  tasks.forEach((t) => lv(t.id));
  const rows: string[][] = [];
  tasks.forEach((t) => (rows[level[t.id]] = [...(rows[level[t.id]] ?? []), t.id]));
  const W = 680, BW = 200, BH = 70, GY = 54, GX = 36;
  const pos: Record<string, [number, number]> = {};
  rows.forEach((r, ri) => { const tot = r.length * BW + (r.length - 1) * GX; r.forEach((id, k) => (pos[id] = [(W - tot) / 2 + k * (BW + GX), 16 + ri * (BH + GY)])); });
  const H = 16 + rows.length * (BH + GY) - GY + 16;
  return (
    <div className="ol-dag" style={{ height: H }}>
      <svg width={W} height={H} className="ol-dag-svg" aria-hidden="true">
        <defs><marker id="ol-dah" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8 z" className="ol-ah-s" /></marker></defs>
        {deps.map((d, i) => {
          const [ax, ay] = pos[d.from], [bx, by] = pos[d.to];
          const x1 = ax + BW / 2, y1 = ay + BH, x2 = bx + BW / 2, y2 = by;
          const blocked = statusAt(j.nodes.find((n) => n.id === d.to)!, stage) === 'blocked';
          return <path key={i} d={`M ${x1} ${y1} C ${x1} ${y1 + 26}, ${x2} ${y2 - 26}, ${x2} ${y2}`} className={cx('ol-edge', 'is-strong', blocked ? 'is-obl' : 'is-auth')} markerEnd="url(#ol-dah)" />;
        })}
      </svg>
      {tasks.map((t) => {
        const s = statusAt(t, stage);
        const [x, y] = pos[t.id];
        return (
          <button key={t.id} type="button" className={cx('ol-node', 'ol-dag-n', 'ol-nt-' + meta(s).t, s === 'future' && 'is-future', selected === t.id && 'is-sel')} style={{ left: x, top: y, width: BW, height: BH }} onClick={() => onSelect?.(t.id)}>
            <span className="ol-node-k">{t.kind}</span>
            <span className="ol-node-id">{t.ref} · <span className="ol-node-t-inline">{t.title}</span></span>
            <span className="ol-node-f"><StatusBadge status={s} size="sm" /></span>
          </button>
        );
      })}
    </div>
  );
}

// ───────── Dialog primitives (focus containment + restoration) ─────────
export function Dialog({ open, onClose, title, label, children, footer, wide }: any) {
  const ref = useRef(null);
  const prev = useRef(null as any);
  useEffect(() => {
    if (!open) return;
    prev.current = document.activeElement;
    const el: any = ref.current;
    const f = el?.querySelector('textarea, input, select, button');
    f?.focus();
    const onKey = (ev: any) => {
      if (ev.key === 'Escape') onClose?.();
      if (ev.key === 'Tab' && el) {
        const all = Array.from(el.querySelectorAll('button:not([disabled]), textarea, input, select')) as any[];
        if (!all.length) return;
        const first = all[0], last = all[all.length - 1];
        if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
        else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); prev.current?.focus?.(); };
  }, [open]);
  if (!open) return null;
  return (
    <div className="ol-scrim" onMouseDown={(ev: any) => ev.target === ev.currentTarget && onClose?.()}>
      <div className={cx('ol-dialog', wide && 'is-wide')} role="dialog" aria-modal="true" aria-labelledby="ol-dlg-t" ref={ref}>
        <header className="ol-dialog-h">
          <div>
            {label && <Label>{label}</Label>}
            <h2 id="ol-dlg-t" className="ol-section">{title}</h2>
          </div>
          <button type="button" className="ol-x" onClick={onClose} aria-label="Close">×</button>
        </header>
        <div className="ol-dialog-b">{children}</div>
        {footer && <footer className="ol-dialog-f">{footer}</footer>}
      </div>
    </div>
  );
}

export type ApprovalSubject = { type: string; id: string; scope: string; version: string; sha: string; reason: string; impact: string; risk: string; records: string[]; cmd: string; prov?: any };

export function ApprovalDialog({ open, onClose, subject: a, inline }: { open: boolean; onClose?: () => void; subject: ApprovalSubject; inline?: boolean }) {
  const [why, setWhy] = useState('');
  const [sent, setSent] = useState(null as null | string);
  const body = (
    <div className="ol-appr">
      <div className="ol-appr-scope">
        <div><Label>Decision type</Label><div>{a.type}</div></div>
        <div><Label>Scope</Label><div className="ol-id">{a.scope}</div></div>
        <div><Label>Exact version / SHA</Label><div className="ol-id">{a.version} · <span className="ol-sha">{a.sha}</span></div></div>
      </div>
      <div className="ol-appr-2">
        <div><Label>Reason and impact</Label><p>{a.reason}</p><p className="ol-muted">{a.impact}</p></div>
        <div><Label>Risk</Label><p>{a.risk}</p></div>
      </div>
      <div><Label>Supporting records</Label><div className="ol-chips">{a.records.map((r) => <span key={r} className="ol-id ol-chipid">{r}</span>)}</div></div>
      <label className="ol-field">
        <span className="ol-label">Rationale (required)</span>
        <textarea rows={3} value={why} onChange={(ev: any) => setWhy(ev.target.value)} placeholder="Why you are approving, rejecting or asking for changes. Stored with the decision." />
      </label>
      <code className="ol-cmd-api">{a.cmd} · expected_version={a.version} · idempotency_key=…</code>
      {sent && <div className="ol-sent" role="status">Preview only — “{sent}” would be sent as a typed command; the server validates the expected version and your authorization. Nothing was recorded.</div>}
    </div>
  );
  const footer = (
    <>
      <Button onClick={() => setSent('reject')} disabled={!why.trim()}>Reject</Button>
      <Button onClick={() => setSent('request_changes')} disabled={!why.trim()}>Request changes</Button>
      <Button variant="primary" onClick={() => setSent('approve')} disabled={!why.trim()}>Approve</Button>
    </>
  );
  if (inline) return <div className="ol-dialog ol-dialog-inline" role="group" aria-label={`Approval review ${a.id}`}><header className="ol-dialog-h"><div><Label>Approval review · {a.id}</Label><h2 className="ol-section">{a.type}</h2></div></header><div className="ol-dialog-b">{body}</div><footer className="ol-dialog-f">{footer}</footer></div>;
  return <Dialog open={open} onClose={onClose} title={a.type} label={`Approval review · ${a.id}`} footer={footer} wide>{body}</Dialog>;
}

export type CheckpointSubject = { id: string; q: string; unknown: string; checked: string[]; answer: string; waiting: string };
export function CheckpointDialog({ open, onClose, c, inline }: { open: boolean; onClose?: () => void; c: CheckpointSubject; inline?: boolean }) {
  const [ans, setAns] = useState('');
  const [sent, setSent] = useState(false);
  const body = (
    <div className="ol-appr">
      <p className="ol-why-sum">{c.q}</p>
      <div className="ol-appr-2">
        <div><Label>Unknown intent</Label><p>{c.unknown}</p></div>
        <div><Label>Waiting execution</Label><p className="ol-id">{c.waiting}</p></div>
      </div>
      <div><Label>Authoritative sources already checked</Label><ul className="ol-checks">{c.checked.map((x) => <li key={x} className="ol-check is-na"><span className="ol-check-g">—</span><span className="ol-check-l">{x}</span></li>)}</ul></div>
      <div><Label>Required answer</Label><p>{c.answer}</p></div>
      <label className="ol-field"><span className="ol-label">Your answer</span><textarea rows={3} value={ans} onChange={(ev: any) => setAns(ev.target.value)} placeholder="e.g. CLOSED is terminal; reopening creates a new ticket." /></label>
      <code className="ol-cmd-api">POST /delivery-cycles/:id/commands/answer_checkpoint · checkpoint={c.id}</code>
      {sent && <div className="ol-sent" role="status">Preview only. The answer would create a durable decision (and a new spec version if required), then resume or replan under policy.</div>}
    </div>
  );
  const footer = <><Button onClick={onClose}>Not now</Button><Button variant="primary" disabled={!ans.trim()} onClick={() => setSent(true)}>Record answer</Button></>;
  if (inline) return <div className="ol-dialog ol-dialog-inline" role="group"><header className="ol-dialog-h"><div><Label>Clarification checkpoint · {c.id}</Label><h2 className="ol-section">Answer to resume</h2></div></header><div className="ol-dialog-b">{body}</div><footer className="ol-dialog-f">{footer}</footer></div>;
  return <Dialog open={open} onClose={onClose} title="Answer to resume" label={`Clarification checkpoint · ${c.id}`} footer={footer} wide>{body}</Dialog>;
}

const INTAKE: Record<string, { label: string; fields: [string, string, string?][] }> = {
  GF: { label: 'Greenfield Build', fields: [['Product source', 'Upload PRD / BRD / product brief', 'Stored as an immutable ProductSource version and hash'], ['Project name', 'SupportDesk']] },
  BF: { label: 'Brownfield Onboarding', fields: [['Repository', 'github.com/acme/supportdesk'], ['Branch', 'main'], ['Exact SHA', '9e31ab7', 'Pinned. Onboarding never follows a moving branch.']] },
  FC: { label: 'Feature Change', fields: [['Requested behaviour', 'Tickets carry a priority: LOW, MEDIUM or HIGH'], ['Source reference', 'ISSUE-311 (optional)'], ['Baseline', 'R1 · 9e31ab7']] },
  BG: { label: 'Bug Fix', fields: [['Observed result', 'PATCH /tickets/{id} on a CLOSED ticket returns HTTP 500'], ['Reproduction steps', '1. Create ticket  2. Close it  3. PATCH status'], ['Severity', 'S2'], ['Baseline', 'R2 · c83a12d']] },
};
export function IntakeForm({ open, onClose, inline, initial = 'FC' }: any) {
  const [k, setK] = useState(initial);
  const [sent, setSent] = useState(false);
  const f = INTAKE[k];
  const body = (
    <div className="ol-appr">
      <div className="ol-seg ol-seg-wide" role="radiogroup" aria-label="Journey">
        {Object.entries(INTAKE).map(([id, v]) => (
          <button key={id} type="button" role="radio" aria-checked={k === id} className={cx('ol-seg-i', k === id && 'is-on')} onClick={() => { setK(id); setSent(false); }}>{v.label}</button>
        ))}
      </div>
      <div className="ol-field"><span className="ol-label">Project</span><input value="SupportDesk" readOnly /></div>
      {f.fields.map(([l, v, hint]) => (
        <label key={l} className="ol-field">
          <span className="ol-label">{l}</span>
          {l === 'Product source' ? <div className="ol-drop">Drop a file or choose · PDF, DOCX, MD</div> : <input defaultValue={v} />}
          {hint && <span className="ol-small ol-muted">{hint}</span>}
        </label>
      ))}
      <code className="ol-cmd-api">POST /projects/SupportDesk/delivery-cycles · journey={k === 'GF' ? 'GREENFIELD_BUILD' : k === 'BF' ? 'BROWNFIELD_ONBOARDING' : k === 'FC' ? 'FEATURE_CHANGE' : 'BUG_FIX'}</code>
      {sent && <div className="ol-sent" role="status">Preview only. The server would validate inputs, persist the cycle and acknowledge it; the UI then navigates to its control-plane map.</div>}
    </div>
  );
  const footer = <><Button onClick={onClose}>Cancel</Button><Button variant="primary" onClick={() => setSent(true)}>Create delivery cycle</Button></>;
  if (inline) return <div className="ol-dialog ol-dialog-inline" role="group"><header className="ol-dialog-h"><div><Label>New delivery cycle</Label><h2 className="ol-section">Intent-specific intake</h2></div></header><div className="ol-dialog-b">{body}</div><footer className="ol-dialog-f">{footer}</footer></div>;
  return <Dialog open={open} onClose={onClose} title="Intent-specific intake" label="New delivery cycle" footer={footer} wide>{body}</Dialog>;
}

export function Drawer({ open, onClose, title, label, children }: any) {
  useEffect(() => {
    if (!open) return;
    const k = (ev: any) => { if (ev.key === 'Escape') onClose?.(); };
    document.addEventListener('keydown', k);
    return () => document.removeEventListener('keydown', k);
  }, [open]);
  if (!open) return null;
  return (
    <div className="ol-scrim is-drawer" onMouseDown={(ev: any) => ev.target === ev.currentTarget && onClose?.()}>
      <aside className="ol-drawer" role="dialog" aria-modal="true" aria-label={title}>
        <header className="ol-dialog-h"><div>{label && <Label>{label}</Label>}<h2 className="ol-section">{title}</h2></div><button type="button" className="ol-x" onClick={onClose} aria-label="Close">×</button></header>
        <div className="ol-dialog-b">{children}</div>
      </aside>
    </div>
  );
}

export { ProvenanceBadge };
