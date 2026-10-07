import { React, useRef, useState, useLayoutEffect, useEffect, useMemo } from './react';
import { LANES, laneIndex, statusAt, meta, lineage, attentionFor, whyFor, type Journey, type GNode, type Lens, type LaneId, screenById } from './model';
import { StatusBadge, ProvenanceBadge, cx, Button } from './primitives';
import { JourneySpine } from './shell';

export const IMPACT_EXTRA: Record<string, Record<string, 'direct' | 'inferred' | 'scope'>> = {
  GF: { 'ARCH-001': 'scope', 'IMPL-001': 'direct', 'CODE-117': 'direct', 'CODE-118': 'direct' },
  BF: { 'UNC-004': 'scope', 'REC-017': 'inferred', 'OB-011': 'direct', 'RDY-001': 'direct' },
  FC: {},
  BG: { 'RC-004': 'inferred', 'IMPL-017R': 'scope' },
};
export const impactOf = (j: Journey, n: GNode) => n.impact ?? IMPACT_EXTRA[j.id]?.[n.id];

export function ObjectNode({ node, status, selected, dim, onClick, impact, innerRef, compact }: { node: GNode; status: string; selected?: boolean; dim?: boolean; onClick?: () => void; impact?: string; innerRef?: any; compact?: boolean }) {
  const m = meta(status);
  const future = status === 'future';
  return (
    <button
      type="button"
      ref={innerRef}
      className={cx('ol-node', 'ol-nt-' + m.t, future && 'is-future', selected && 'is-sel', dim && 'is-dim', node.stack && 'is-stack', compact && 'is-compact')}
      onClick={onClick}
      aria-pressed={selected}
      aria-label={`${node.kind} ${node.ref}: ${node.title}. ${m.l}`}
    >
      <span className="ol-node-k">{node.kind}</span>
      <span className="ol-node-id">{node.ref}</span>
      <span className="ol-node-t">{node.title}</span>
      {node.sub && !compact && <span className="ol-node-sub">{node.sub}</span>}
      <span className="ol-node-f">
        <StatusBadge status={status} size="sm" />
        {node.stack && <span className="ol-node-count">×{node.stack.length}</span>}
      </span>
      {impact && <span className={cx('ol-node-imp', 'is-' + impact)}>{impact === 'scope' ? 'scope' : impact}</span>}
    </button>
  );
}

type Rect = { x: number; y: number; w: number; h: number };

function edgeGeom(a: Rect, b: Rect, la: number, lb: number) {
  let p0: number[], p3: number[], c1: number[], c2: number[];
  if (la === lb) {
    p0 = [a.x, a.y + a.h / 2];
    p3 = [b.x, b.y + b.h / 2];
    const off = 10 + Math.min(8, Math.abs(p3[1] - p0[1]) / 30);
    c1 = [p0[0] - off, p0[1]];
    c2 = [p3[0] - off, p3[1]];
  } else if (la < lb) {
    p0 = [a.x + a.w, a.y + a.h / 2];
    p3 = [b.x, b.y + b.h / 2];
    const dx = Math.max(24, (p3[0] - p0[0]) * 0.5);
    c1 = [p0[0] + dx, p0[1]];
    c2 = [p3[0] - dx, p3[1]];
  } else {
    p0 = [a.x, a.y + a.h / 2];
    p3 = [b.x + b.w, b.y + b.h / 2];
    const dx = Math.max(24, (p0[0] - p3[0]) * 0.5);
    c1 = [p0[0] - dx, p0[1]];
    c2 = [p3[0] + dx, p3[1]];
  }
  const t = 0.5;
  const bz = (i: number) => (1 - t) ** 3 * p0[i] + 3 * (1 - t) ** 2 * t * c1[i] + 3 * (1 - t) * t * t * c2[i] + t ** 3 * p3[i];
  return { d: `M ${p0[0]} ${p0[1]} C ${c1[0]} ${c1[1]}, ${c2[0]} ${c2[1]}, ${p3[0]} ${p3[1]}`, mid: [bz(0), bz(1)] };
}

const LENSES: { k: Lens; label: string; hint: string }[] = [
  { k: 'lifecycle', label: 'Lifecycle', hint: 'Current stage and selected neighbourhood' },
  { k: 'trace', label: 'Trace', hint: 'Bidirectional lineage of the selected record → S07' },
  { k: 'impact', label: 'Impact', hint: 'Direct vs inferred impact and scope → S08' },
  { k: 'blockers', label: 'Blockers', hint: 'What stands between now and the next stage' },
];

export function GraphToolbar({ lens, onLens, view, onView }: any) {
  return (
    <div className="ol-gtool">
      <div className="ol-seg" role="radiogroup" aria-label="Lens">
        {LENSES.map((l) => (
          <button key={l.k} type="button" role="radio" aria-checked={lens === l.k} className={cx('ol-seg-i', lens === l.k && 'is-on')} onClick={() => onLens?.(l.k)} title={l.hint}>
            {l.label}
          </button>
        ))}
      </div>
      <div className="ol-legend" aria-label="Legend">
        <span><svg width="22" height="8" aria-hidden="true"><line x1="0" y1="4" x2="22" y2="4" className="ol-lg-auth" /></svg>authoritative</span>
        <span><svg width="22" height="8" aria-hidden="true"><line x1="0" y1="4" x2="22" y2="4" className="ol-lg-inf" /></svg>inferred</span>
        <span><svg width="22" height="8" aria-hidden="true"><line x1="0" y1="4" x2="22" y2="4" className="ol-lg-obl" /></svg>obligation</span>
        <span><span className="ol-lg-future" aria-hidden="true" />future record</span>
        <span title="Numbered dots above the lanes: the order this journey's lifecycle stages move through the lanes"><svg width="34" height="12" aria-hidden="true"><path d="M5 8 Q 17 -2 29 8" className="ol-spine-arc is-done" /><circle cx="5" cy="8" r="3.5" className="ol-lg-dot" /><circle cx="29" cy="8" r="3.5" className="ol-lg-dot is-now" /></svg>journey spine</span>
      </div>
      <div className="ol-seg" role="radiogroup" aria-label="View">
        {['graph', 'list'].map((v) => (
          <button key={v} type="button" role="radio" aria-checked={view === v} className={cx('ol-seg-i', view === v && 'is-on')} onClick={() => onView?.(v)}>
            {v === 'graph' ? 'Graph' : 'List'}
          </button>
        ))}
      </div>
    </div>
  );
}

export function highlightSet(j: Journey, stage: number, selected: string | undefined, lens: Lens): Set<string> | null {
  if (lens === 'lifecycle' || !selected) {
    if (lens === 'impact') return new Set(j.nodes.filter((n) => impactOf(j, n)).map((n) => n.id));
    if (lens === 'blockers') return blockerSet(j, stage, selected);
    return null;
  }
  if (lens === 'trace') {
    const { up, down } = lineage(j, selected);
    return new Set([selected, ...up, ...down]);
  }
  if (lens === 'impact') return new Set(j.nodes.filter((n) => impactOf(j, n)).map((n) => n.id));
  return blockerSet(j, stage, selected);
}

function blockerSet(j: Journey, stage: number, selected?: string) {
  const set = new Set<string>();
  const resolve = (ref: string) => j.nodes.find((n) => n.id === ref || n.ref === ref || n.ref.startsWith(ref + ' '))?.id;
  const add = (id?: string) => {
    if (!id) return;
    const n = j.nodes.find((x) => x.id === id);
    if (!n) return;
    set.add(id);
    (whyFor(j, n, stage).blocking ?? []).forEach((b) => {
      const r = resolve(b);
      if (r && !set.has(r)) add(r);
    });
  };
  attentionFor(j, stage).forEach((a) => add(a.n.id));
  j.nodes.forEach((n) => {
    const s = statusAt(n, stage);
    if (s === 'blocked' || s === 'missing' || s === 'not-eligible') add(n.id);
  });
  if (selected) add(selected);
  return set;
}

export function ControlPlaneGraph({ journey: j, stage, selected, onSelect, lens = 'lifecycle', onLens, view = 'graph', onView, onOpenLane, onStage, hideToolbar, focusEdge }: { focusEdge?: string | null; journey: Journey; stage: number; selected?: string; onSelect?: (id: string) => void; lens?: Lens; onLens?: (l: Lens) => void; view?: 'graph' | 'list'; onView?: (v: string) => void; onOpenLane?: (l: LaneId) => void; onStage?: (i: number) => void; hideToolbar?: boolean }) {
  const wrap = useRef(null);
  const nodeRefs = useRef({} as Record<string, any>);
  const laneRefs = useRef([] as any[]);
  const [geo, setGeo] = useState({ w: 0, h: 0, rects: {} as Record<string, Rect>, centers: [] as number[] });

  const measure = () => {
    const root: any = wrap.current;
    if (!root) return;
    const rb = root.getBoundingClientRect();
    const rects: Record<string, Rect> = {};
    for (const id of Object.keys(nodeRefs.current)) {
      const el = nodeRefs.current[id];
      if (!el || !el.isConnected) continue;
      const r = el.getBoundingClientRect();
      rects[id] = { x: r.left - rb.left, y: r.top - rb.top, w: r.width, h: r.height };
    }
    const centers = laneRefs.current.map((el: any) => {
      if (!el) return 0;
      const r = el.getBoundingClientRect();
      return r.left - rb.left + r.width / 2;
    });
    const next = { w: rb.width, h: rb.height, rects, centers };
    setGeo((g: any) => (JSON.stringify(g) === JSON.stringify(next) ? g : next));
  };
  useLayoutEffect(measure);
  useEffect(() => {
    const RO = (window as any).ResizeObserver;
    if (!RO || !wrap.current) return;
    const ro = new RO(() => measure());
    ro.observe(wrap.current);
    const t = setTimeout(measure, 120);
    (document as any).fonts?.ready?.then?.(() => measure());
    return () => { ro.disconnect(); clearTimeout(t); };
  }, []);

  const hi = useMemo(() => highlightSet(j, stage, selected, lens), [j, stage, selected, lens]);
  const nb = useMemo(() => {
    const s = new Set<string>();
    if (selected) j.edges.forEach((e) => { if (e.from === selected) s.add(e.to); if (e.to === selected) s.add(e.from); });
    return s;
  }, [j, selected]);
  const stageLane = j.stages[stage].lane;
  const byId = (id: string) => j.nodes.find((n) => n.id === id)!;

  if (view === 'list') {
    return (
      <div className="ol-graph">
        {!hideToolbar && <GraphToolbar lens={lens} onLens={onLens} view={view} onView={onView} />}
        <div className="ol-glist" role="table" aria-label="Control-plane records">
          <div className="ol-glist-h" role="row">
            <span role="columnheader">Lane</span><span role="columnheader">Record</span><span role="columnheader">Type</span><span role="columnheader">Title</span><span role="columnheader">State</span><span role="columnheader">Provenance</span>
          </div>
          {LANES.map((l) =>
            j.nodes.filter((n) => n.lane === l.id).map((n, i) => {
              const s = statusAt(n, stage);
              const dim = hi && !hi.has(n.id);
              return (
                <button key={n.id} type="button" role="row" className={cx('ol-glist-r', selected === n.id && 'is-sel', dim && 'is-dim', s === 'future' && 'is-future')} onClick={() => onSelect?.(n.id)}>
                  <span role="cell" className="ol-ls-code">{i === 0 ? l.code : ''}</span>
                  <span role="cell" className="ol-id">{n.ref}</span>
                  <span role="cell" className="ol-label">{n.kind}</span>
                  <span role="cell">{n.title}</span>
                  <span role="cell"><StatusBadge status={s} size="sm" /></span>
                  <span role="cell">{n.prov ? <ProvenanceBadge kind={n.prov} conf={n.conf} /> : <span className="ol-muted">—</span>}</span>
                </button>
              );
            })
          )}
        </div>
      </div>
    );
  }

  const edges = j.edges
    .filter((e) => geo.rects[e.from] && geo.rects[e.to])
    .map((e, i) => {
      const a = byId(e.from), b = byId(e.to);
      const sa = statusAt(a, stage), sb = statusAt(b, stage);
      const obligation = sa === 'future' || sb === 'future' || sb === 'missing';
      const kind = obligation ? 'obl' : e.kind === 'inferred' ? 'inf' : 'auth';
      const touches = selected && (e.from === selected || e.to === selected);
      const inHi = hi ? hi.has(e.from) && hi.has(e.to) : false;
      const strong = lens === 'lifecycle' ? !!touches : inHi;
      const faded = hi && !inHi;
      const g = edgeGeom(geo.rects[e.from], geo.rects[e.to], laneIndex(a.lane), laneIndex(b.lane));
      const focused = focusEdge === `${e.from}>${e.to}>${e.rel}`;
      return { e, i, g, kind, strong: strong || focused, faded: faded && !focused, label: focused, focused };
    });

  return (
    <div className="ol-graph">
      {!hideToolbar && <GraphToolbar lens={lens} onLens={onLens} view={view} onView={onView} />}
      <div className="ol-gwrap" ref={wrap}>
        <div className="ol-gspine">
          {geo.w > 0 && geo.centers.length === 6 && <JourneySpine journey={j} stage={stage} centers={geo.centers} width={geo.w} height={52} onStage={onStage} />}
        </div>
        <svg className="ol-gedges" width={geo.w} height={geo.h} aria-hidden="true">
          <defs>
            <marker id="ol-ah" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" className="ol-ah" /></marker>
            <marker id="ol-ah-s" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" className="ol-ah-s" /></marker>
            <marker id="ol-ah-f" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" className="ol-ah-f" /></marker>
          </defs>
          {edges.filter((x) => !x.strong).map((x) => (
            <path key={x.i} d={x.g.d} className={cx('ol-edge', 'is-' + x.kind, x.faded && 'is-faded')} markerEnd="url(#ol-ah)" />
          ))}
          {edges.filter((x) => x.strong).map((x) => (
            <path key={'s' + x.i} d={x.g.d} className={cx('ol-edge', 'is-' + x.kind, 'is-strong', x.focused && 'is-focus')} markerEnd={x.focused ? 'url(#ol-ah-f)' : 'url(#ol-ah-s)'} />
          ))}
        </svg>
        <div className="ol-lanes">
          {LANES.map((l, li) => {
            const nodes = j.nodes.filter((n) => n.lane === l.id);
            const mat = nodes.filter((n) => statusAt(n, stage) !== 'future').length;
            const flags = attentionFor(j, stage).filter((a) => a.n.lane === l.id);
            const isNow = stageLane === l.id;
            return (
              <div key={l.id} className={cx('ol-lane', isNow && 'is-now')} ref={(el: any) => (laneRefs.current[li] = el)}>
                <button type="button" className="ol-lane-h" onClick={() => onOpenLane?.(l.id)} title={`${l.question} Open ${screenById(l.screen).name}`}>
                  <span className="ol-lane-top">
                    <span className="ol-ls-code">{l.code}</span>
                    <span className="ol-lane-n">{mat}/{nodes.length}</span>
                    {flags.length > 0 && <span className={cx('ol-lane-flag', 'ol-tc-' + meta(flags[0].s).t)}>{meta(flags[0].s).g} {flags.length}</span>}
                  </span>
                  <span className="ol-lane-name">{l.name}</span>
                  <span className="ol-lane-open">{isNow ? <>● {j.stages[stage].k.replace(/_/g, ' ')}</> : <>Open {screenById(l.screen).short.toLowerCase()} →</>}</span>
                </button>
                <div className="ol-lane-b">
                  {nodes.map((n) => {
                    const s = statusAt(n, stage);
                    const dim = hi ? !hi.has(n.id) : false;
                    return (
                      <ObjectNode
                        key={n.id}
                        node={n}
                        status={s}
                        selected={selected === n.id}
                        dim={dim}
                        impact={lens === 'impact' ? impactOf(j, n) : undefined}
                        onClick={() => onSelect?.(n.id)}
                        innerRef={(el: any) => (nodeRefs.current[n.id] = el)}
                      />
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
        {edges.filter((x) => x.label).map((x) => (
          <span key={'l' + x.i} className={cx('ol-elabel', 'is-' + x.kind)} style={{ left: x.g.mid[0], top: x.g.mid[1] }}>
            {x.e.rel}
            {x.e.conf != null && <span className="ol-elabel-c"> {x.e.conf.toFixed(2)}</span>}
          </span>
        ))}
      </div>
      <div className="ol-ghint">
        Select a record → inspect reason and provenance → open contextual detail. Viewing never issues a command.
        {lens !== 'lifecycle' && hi && <> · <strong>{hi.size}</strong> records in the {lens} lens</>}
      </div>
    </div>
  );
}
