import { React } from './react';
import { LANES, SCREENS, laneIndex, statusAt, meta, attentionFor, type Journey, type ScreenId, type LaneId } from './model';
import { JOURNEYS } from './data';
import { Button, StatusBadge, cx, Glyph } from './primitives';

// ───────── Top bar ─────────
export function TopBar({ journey, onCycle, onAsk, onNew, stream = 'live' }: { journey: Journey; onCycle?: (id: string) => void; onAsk?: () => void; onNew?: () => void; stream?: 'live' | 'disconnected' }) {
  return (
    <header className="ol-top">
      <div className="ol-brand">
        <span className="ol-wordmark">Olympus</span>
      </div>
      <div className="ol-top-ctx">
        <span className="ol-top-proj">SupportDesk</span>
        <span className="ol-top-sep" aria-hidden="true">/</span>
        <label className="ol-cycle">
          <span className="ol-visually-hidden">Delivery cycle</span>
          <select value={journey.cycle} onChange={(ev: any) => onCycle?.(ev.target.value)} aria-label="Delivery cycle">
            {JOURNEYS.map((j) => (
              <option key={j.cycle} value={j.cycle}>
                {j.cycle} · {j.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="ol-top-r">
        <span className={cx('ol-stream', stream === 'disconnected' && 'is-off')} title="Event stream (SSE) — invalidates and refetches server state">
          <span className="ol-stream-dot" aria-hidden="true" />
          {stream === 'live' ? 'Live · refreshed 10:53:12' : 'Disconnected · last refresh 10:41:07'}
        </span>
        <Button variant="quiet" onClick={onNew}>New delivery cycle</Button>
        <Button variant="quiet" onClick={onAsk}>Ask Olympus</Button>
        <span className="ol-avatar" title="Engineering lead · project operator">EL</span>
      </div>
    </header>
  );
}

// ───────── Navigation rail ─────────
export function NavRail({ screen, onNav, journey, stage }: { screen: ScreenId; onNav?: (s: ScreenId) => void; journey?: Journey; stage?: number }) {
  const laneFlag = (lane?: LaneId) => {
    if (!journey || lane == null) return null;
    const items = attentionFor(journey, stage ?? journey.live).filter((a) => a.n.lane === lane);
    return items.length ? items[0].s : null;
  };
  const item = (id: ScreenId) => {
    const s = SCREENS.find((x) => x.id === id)!;
    const flag = laneFlag(s.lane);
    return (
      <button key={id} type="button" className={cx('ol-rail-i', screen === id && 'is-on', id === 'S02' && 'is-hub')} aria-current={screen === id ? 'page' : undefined} onClick={() => onNav?.(id)} title={`${s.num} · ${s.name}`}>
        <span className="ol-rail-mono">{s.mono}</span>
        <span className="ol-rail-t">{s.short}</span>
        {flag && <span className={cx('ol-rail-flag', 'ol-tc-' + meta(flag).t)} aria-label="needs attention">{meta(flag).g}</span>}
      </button>
    );
  };
  return (
    <nav className="ol-rail" aria-label="Workspace">
      {item('S01')}
      {item('S02')}
      <div className="ol-rail-div" aria-hidden="true">
        <span>drill</span>
      </div>
      {(['S03', 'S04', 'S05', 'S06', 'S07', 'S08', 'S09', 'S10'] as ScreenId[]).map(item)}
      <div className="ol-rail-spacer" />
      <button type="button" className={cx('ol-rail-i', 'ol-rail-util', screen === 'INT' && 'is-on')} onClick={() => onNav?.('INT')} title="Integrations">
        <span className="ol-rail-mono">IO</span>
        <span className="ol-rail-t">Integr.</span>
      </button>
      <button type="button" className={cx('ol-rail-i', 'ol-rail-util', screen === 'AUD' && 'is-on')} onClick={() => onNav?.('AUD')} title="Audit history">
        <span className="ol-rail-mono">AU</span>
        <span className="ol-rail-t">Audit</span>
      </button>
    </nav>
  );
}

export function AppShell({ children, screen, onNav, journey, stage, onCycle, onAsk, onNew, overlay, stream }: any) {
  return (
    <div className="ol-app">
      <TopBar journey={journey} onCycle={onCycle} onAsk={onAsk} onNew={onNew} stream={stream} />
      <div className="ol-body">
        <NavRail screen={screen} onNav={onNav} journey={journey} stage={stage} />
        <main className="ol-main">{children}</main>
      </div>
      {overlay}
    </div>
  );
}

// ───────── Lifecycle ribbon ─────────
export function LifecycleRibbon({ journey, stage, onStage, compact }: { journey: Journey; stage: number; onStage?: (i: number) => void; compact?: boolean }) {
  return (
    <ol className={cx('ol-ribbon', compact && 'is-compact')} aria-label={`${journey.name} lifecycle`}>
      {journey.stages.map((s, i) => {
        const state = i < stage ? 'done' : i === stage ? 'now' : 'next';
        const lane = LANES[laneIndex(s.lane)];
        return (
          <li key={s.k}>
            <button type="button" className={cx('ol-rib', 'is-' + state, i === journey.live && 'is-live')} onClick={() => onStage?.(i)} aria-current={i === stage ? 'step' : undefined} title={`${s.k} · ${lane.name} lane · ${s.out}`}>
              <span className="ol-rib-g" aria-hidden="true">{state === 'done' ? '✓' : state === 'now' ? '●' : '○'}</span>
              <span className="ol-rib-k">{s.k.replace(/_/g, ' ')}</span>
              <span className="ol-rib-lane">{lane.code}</span>
              {i === journey.live && stage !== journey.live && <span className="ol-rib-live">LIVE</span>}
            </button>
          </li>
        );
      })}
    </ol>
  );
}

// ───────── Journey spine: the order a lifecycle moves through the lanes ─────────
export function spinePoints(journey: Journey, centers: number[], y: number) {
  const perLane: Record<string, number[]> = {};
  journey.stages.forEach((s, i) => (perLane[s.lane] = [...(perLane[s.lane] ?? []), i]));
  return journey.stages.map((s, i) => {
    const arr = perLane[s.lane];
    const k = arr.indexOf(i);
    const m = arr.length;
    const li = laneIndex(s.lane);
    const laneW = centers.length > 1 ? Math.abs(centers[1] - centers[0]) : 120;
    const step = Math.min(24, (laneW * 0.92) / Math.max(1, m));
    return { i, x: centers[li] + (k - (m - 1) / 2) * step, y, lane: s.lane, k: s.k, r: Math.min(9.5, step / 2.3) };
  });
}

export function JourneySpine({ journey, stage, centers, width, height = 56, onStage, showLanes }: { journey: Journey; stage: number; centers?: number[]; width: number; height?: number; onStage?: (i: number) => void; showLanes?: boolean }) {
  const cs = centers ?? LANES.map((_, i) => ((i + 0.5) * width) / LANES.length);
  const y = showLanes ? height / 2 + 6 : height / 2;
  const pts = spinePoints(journey, cs, y);
  const arcs = pts.slice(1).map((p, idx) => {
    const a = pts[idx];
    const dx = p.x - a.x;
    const fwd = dx >= 0;
    const h = Math.min(fwd ? y - (showLanes ? 18 : 5) : height - y - 5, Math.abs(dx) * 0.18 + 7);
    const cy = fwd ? y - h * 2 : y + h * 2;
    const done = p.i <= stage;
    return <path key={p.i} d={`M ${a.x} ${a.y} Q ${(a.x + p.x) / 2} ${cy} ${p.x} ${p.y}`} className={cx('ol-spine-arc', done ? 'is-done' : 'is-next', !fwd && 'is-back')} />;
  });
  return (
    <svg className="ol-spine" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${journey.name} journey spine: ${journey.stages.map((s) => s.k).join(' → ')}`}>
      {showLanes && LANES.map((l, i) => (
        <text key={l.id} x={cs[i]} y={10} className="ol-spine-lane" textAnchor="middle">{l.code}</text>
      ))}
      {arcs}
      {pts.map((p) => {
        const st = p.i < stage ? 'done' : p.i === stage ? 'now' : 'next';
        return (
          <g key={p.i} className={cx('ol-spine-dot', 'is-' + st)} onClick={() => onStage?.(p.i)} style={{ cursor: onStage ? 'pointer' : 'default' }}>
            <title>{`${p.i + 1}. ${p.k}`}</title>
            <circle cx={p.x} cy={p.y} r={p.r} />
            {p.r >= 8 && <text x={p.x} y={p.y + 3.6} textAnchor="middle">{p.i + 1}</text>}
          </g>
        );
      })}
    </svg>
  );
}

// ───────── Cycle header (title + ribbon) ─────────
export function CycleHeader({ journey, stage, onStage, crumbs, title, right, onBack }: any) {
  return (
    <div className="ol-ch">
      <div className="ol-ch-row">
        <div className="ol-ch-l">
          <div className="ol-crumbs">
            {onBack && (
              <button type="button" className="ol-back" onClick={onBack}>
                ← Back to cycle map
              </button>
            )}
            {crumbs?.map((c: string, i: number) => (
              <span key={i} className="ol-crumb">{c}</span>
            ))}
          </div>
          <h1 className="ol-title">{title ?? journey.objective}</h1>
          <div className="ol-ch-meta">
            <span className="ol-id">{journey.cycle}</span>
            <span>{journey.name}</span>
            <span className="ol-dotsep" aria-hidden="true">·</span>
            <span>{title ? journey.objective : journey.direction}</span>
            <span className="ol-dotsep" aria-hidden="true">·</span>
            <span>Outcome: {journey.outcome}</span>
          </div>
        </div>
        {right}
      </div>
      <LifecycleRibbon journey={journey} stage={stage} onStage={onStage} />
    </div>
  );
}

// ───────── Attention strip ─────────
export function AttentionStrip({ journey, stage, onSelect, onWhy, onAction }: { journey: Journey; stage: number; onSelect?: (id: string) => void; onWhy?: (id: string) => void; onAction?: (id: string) => void }) {
  const items = attentionFor(journey, stage);
  const top = items[0];
  if (!top) {
    const next = journey.stages[stage + 1];
    return (
      <div className="ol-attn is-calm" role="status">
        <StatusBadge status="running" label="Nothing needs you" />
        <div className="ol-attn-t">
          <strong>Olympus is progressing {journey.stages[stage].k.replace(/_/g, ' ')} on its own.</strong>
          <span className="ol-attn-sub">{next ? `${next.k.replace(/_/g, ' ')} begins when its preconditions pass.` : 'Cycle complete.'}</span>
        </div>
      </div>
    );
  }
  return (
    <div className="ol-attn" role="status">
      <StatusBadge status={top.s} label={items.length > 1 ? `${items.length} need you` : 'Needs you'} />
      <div className="ol-attn-t">
        <strong>{top.text}</strong>
        <span className="ol-attn-sub">
          State → reason → evidence → allowed action → lineage
          {items.length > 1 && (
            <>
              {' · also: '}
              {items.slice(1, 3).map((it, i) => (
                <button key={it.n.id} type="button" className="ol-idlink ol-id" onClick={() => onSelect?.(it.n.id)}>
                  {it.n.ref}
                  {i < Math.min(items.length - 1, 2) - 1 ? ', ' : ''}
                </button>
              ))}
            </>
          )}
        </span>
      </div>
      <div className="ol-attn-a">
        <Button onClick={() => onWhy?.(top.n.id)}>Why this state?</Button>
        <Button variant="primary" onClick={() => onAction?.(top.n.id)}>Inspect {top.n.ref}</Button>
      </div>
    </div>
  );
}

// ───────── Lane strip: compact map shown on every drill-down ─────────
export function LaneStrip({ journey, stage, current, onLane, lens }: { journey: Journey; stage: number; current?: LaneId; onLane?: (l: LaneId) => void; lens?: string }) {
  const stageLane = journey.stages[stage].lane;
  return (
    <div className="ol-lanestrip" role="navigation" aria-label="Control-plane lanes">
      <span className="ol-label ol-lanestrip-l">Map</span>
      {LANES.map((l) => {
        const nodes = journey.nodes.filter((n) => n.lane === l.id);
        const mat = nodes.filter((n) => statusAt(n, stage) !== 'future');
        const flags = attentionFor(journey, stage).filter((a) => a.n.lane === l.id);
        return (
          <button key={l.id} type="button" className={cx('ol-ls', current === l.id && 'is-on', stageLane === l.id && 'is-now')} onClick={() => onLane?.(l.id)} title={l.question}>
            <span className="ol-ls-code">{l.code}</span>
            <span className="ol-ls-name">{l.short}</span>
            <span className="ol-ls-n">
              {mat.length}/{nodes.length}
            </span>
            {flags.length > 0 && <Glyph status={flags[0].s} />}
          </button>
        );
      })}
      {lens && <span className="ol-ls-lens">{lens} lens</span>}
    </div>
  );
}

export function SnapshotBanner({ journey, stage, onLive }: any) {
  if (stage === journey.live) return null;
  return (
    <div className="ol-snap" role="note">
      <span className="ol-label">Stage snapshot</span>
      <span>
        Showing <strong>{journey.stages[stage].k}</strong> for design review. Production shows recorded history for past stages only — never a future state.
      </span>
      <Button size="sm" onClick={onLive}>Return to live ({journey.stages[journey.live].k})</Button>
    </div>
  );
}
