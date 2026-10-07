import { React } from './react';
import { meta, STATUS, type Prov } from './model';

const cx = (...a: any[]) => a.filter(Boolean).join(' ');
export { cx };

export function Button({ variant = 'quiet', size, disabled, onClick, children, title, type = 'button', className, ...rest }: any) {
  return (
    <button type={type} title={title} disabled={disabled} onClick={onClick} className={cx('ol-btn', 'ol-btn-' + variant, size && 'ol-btn-' + size, className)} {...rest}>
      {children}
    </button>
  );
}

export function StatusBadge({ status, label, size }: { status: string; label?: string; size?: 'sm' }) {
  const m = meta(status);
  return (
    <span className={cx('ol-chip', 'ol-tone-' + m.t, size === 'sm' && 'ol-chip-sm')} data-status={status}>
      <span className="ol-chip-g" aria-hidden="true">{m.g}</span>
      <span>{label ?? m.l}</span>
    </span>
  );
}

const PROV: Record<Prov, { g: string; t: string; d: string }> = {
  FACT: { g: '■', t: 'fact', d: 'Deterministically observed' },
  INFERENCE: { g: '◐', t: 'inference', d: 'Reasoned from evidence' },
  UNCERTAINTY: { g: '?', t: 'uncertainty', d: 'Unresolved — may block' },
  ASSUMPTION: { g: '○', t: 'assumption', d: 'Temporary, never canonical' },
  DECISION: { g: '◆', t: 'decision', d: 'Approved, versioned, attributable' },
};
export function ProvenanceBadge({ kind, conf, source }: { kind: Prov; conf?: number; source?: string }) {
  const p = PROV[kind];
  return (
    <span className={cx('ol-prov', 'ol-prov-' + p.t)} title={p.d + (source ? ' · ' + source : '')}>
      <span aria-hidden="true">{p.g}</span>
      {kind}
      {conf != null && <span className="ol-prov-conf">{conf.toFixed(2)}</span>}
    </span>
  );
}

export function IdRef({ id, onClick, muted }: { id: string; onClick?: (id: string) => void; muted?: boolean }) {
  if (!onClick) return <span className={cx('ol-id', muted && 'ol-muted')}>{id}</span>;
  return (
    <button type="button" className="ol-id ol-idlink" onClick={() => onClick(id)}>
      {id}
    </button>
  );
}

export function Sha({ value, label }: { value: string; label?: string }) {
  return (
    <span className="ol-sha">
      {label && <span className="ol-sha-l">{label}</span>}
      {value}
    </span>
  );
}

export function Label({ children, className }: any) {
  return <div className={cx('ol-label', className)}>{children}</div>;
}

export function Panel({ title, sub, actions, children, className, pad = true, footer }: any) {
  return (
    <section className={cx('ol-panel', className)}>
      {(title || actions) && (
        <header className="ol-panel-h">
          <div>
            {title && <h2 className="ol-section">{title}</h2>}
            {sub && <div className="ol-panel-sub">{sub}</div>}
          </div>
          {actions && <div className="ol-panel-actions">{actions}</div>}
        </header>
      )}
      <div className={cx('ol-panel-b', !pad && 'ol-nopad')}>{children}</div>
      {footer && <footer className="ol-panel-f">{footer}</footer>}
    </section>
  );
}

export function KV({ rows }: { rows: [string, any][] }) {
  return (
    <dl className="ol-kv">
      {rows.map(([k, v], i) => (
        <div key={i} className="ol-kv-r">
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export type ShaScope = { k: string; label: string; ref: string; sha: string; note: string };
export function ShaScopeBanner({ scopes, active, onChange, message }: { scopes: ShaScope[]; active: string; onChange?: (k: string) => void; message?: string }) {
  return (
    <div className="ol-scope">
      <div className="ol-scope-tabs" role="tablist" aria-label="Index scope">
        {scopes.map((s) => (
          <button key={s.k} role="tab" aria-selected={s.k === active} disabled={s.sha === '—'} className={cx('ol-scope-tab', s.k === active && 'is-on')} onClick={() => onChange?.(s.k)}>
            <span className="ol-label">{s.label}</span>
            <span className="ol-scope-val">
              <span className="ol-id">{s.ref}</span> <span className="ol-sha">{s.sha}</span>
            </span>
            <span className="ol-scope-note">{s.note}</span>
          </button>
        ))}
      </div>
      {message && <p className="ol-scope-msg">{message}</p>}
    </div>
  );
}

export function EmptyState({ title, body, action }: any) {
  return (
    <div className="ol-empty">
      <div className="ol-empty-mark" aria-hidden="true">○</div>
      <div className="ol-section">{title}</div>
      <p>{body}</p>
      {action}
    </div>
  );
}

export function Glyph({ status }: { status: string }) {
  const m = meta(status);
  return <span className={cx('ol-glyph', 'ol-tc-' + m.t)} aria-label={m.l} title={m.l}>{m.g}</span>;
}

export const ALL_STATUSES = Object.keys(STATUS);
