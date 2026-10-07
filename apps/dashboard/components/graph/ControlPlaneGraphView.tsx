"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { GraphToolbar } from "@/components/graph/GraphToolbar";
import { JourneySpine, type SpineStage } from "@/components/graph/JourneySpine";
import { ObjectNode } from "@/components/graph/ObjectNode";
import { edgeGeometry } from "@/components/graph/edge-geom";
import { highlightNodeIds } from "@/components/graph/lens-highlight";
import { StatusBadge } from "@/components/primitives";
import type { AttentionItem } from "@/src/control-plane/attention";
import type {
  ControlPlaneGraph,
  ControlPlaneGraphEdge,
} from "@/src/control-plane/graph-types";
import { LANES, laneIndex, type LaneId, type LensId } from "@/src/control-plane/lanes";
import { presentationForUiKey } from "@/src/adapters/status";
import { cn } from "@/lib/utils";

type Rect = { x: number; y: number; w: number; h: number };

export function ControlPlaneGraphView({
  graph,
  stages,
  stageIndex,
  currentLaneId,
  lens,
  onLens,
  view,
  onView,
  selectedId,
  onSelect,
  onOpenLane,
  attention,
  focusEdgeKey,
}: {
  graph: ControlPlaneGraph;
  stages: SpineStage[];
  stageIndex: number;
  currentLaneId: LaneId;
  lens: LensId;
  onLens: (l: LensId) => void;
  view: "graph" | "list";
  onView: (v: "graph" | "list") => void;
  selectedId?: string;
  onSelect: (id: string) => void;
  onOpenLane: (lane: LaneId) => void;
  attention: AttentionItem[];
  focusEdgeKey?: string | null;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const laneRefs = useRef<(HTMLDivElement | null)[]>([]);
  const [geo, setGeo] = useState({ w: 0, h: 0, rects: {} as Record<string, Rect>, centers: [] as number[] });

  const measure = () => {
    const root = wrapRef.current;
    if (!root) return;
    const rb = root.getBoundingClientRect();
    const rects: Record<string, Rect> = {};
    for (const id of Object.keys(nodeRefs.current)) {
      const el = nodeRefs.current[id];
      if (!el?.isConnected) continue;
      const r = el.getBoundingClientRect();
      rects[id] = { x: r.left - rb.left, y: r.top - rb.top, w: r.width, h: r.height };
    }
    const centers = laneRefs.current.map((el) => {
      if (!el) return 0;
      const r = el.getBoundingClientRect();
      return r.left - rb.left + r.width / 2;
    });
    const next = { w: rb.width, h: rb.height, rects, centers };
    setGeo((g) => (JSON.stringify(g) === JSON.stringify(next) ? g : next));
  };

  useLayoutEffect(() => {
    measure();
  });

  useEffect(() => {
    const root = wrapRef.current;
    if (!root) return;
    const ro = new ResizeObserver(() => measure());
    ro.observe(root);
    const t = setTimeout(measure, 120);
    document.fonts?.ready?.then(() => measure());
    return () => {
      ro.disconnect();
      clearTimeout(t);
    };
  }, [graph.nodes.length, view]);

  const hi = useMemo(
    () => highlightNodeIds(lens, graph.nodes, graph.edges, selectedId, attention),
    [lens, graph.nodes, graph.edges, selectedId, attention],
  );

  const byId = (id: string) => graph.nodes.find((n) => n.id === id);

  if (view === "list") {
    return (
      <div className="ol-graph">
        <GraphToolbar lens={lens} onLens={onLens} view={view} onView={onView} />
        <div className="ol-glist" role="table" aria-label="Control-plane records">
          <div className="ol-glist-h" role="row">
            <span role="columnheader">Lane</span>
            <span role="columnheader">Record</span>
            <span role="columnheader">Type</span>
            <span role="columnheader">Title</span>
            <span role="columnheader">State</span>
            <span role="columnheader">Scope</span>
          </div>
          {LANES.map((l) =>
            graph.nodes
              .filter((n) => n.lane === l.id)
              .map((n, i) => {
                const dim = hi ? !hi.has(n.id) : false;
                return (
                  <button
                    key={n.id}
                    type="button"
                    role="row"
                    className={cn(
                      "ol-glist-r",
                      selectedId === n.id && "is-sel",
                      dim && "is-dim",
                      n.future && "is-future",
                    )}
                    onClick={() => onSelect(n.id)}
                  >
                    <span role="cell" className="ol-ls-code">
                      {i === 0 ? l.code : ""}
                    </span>
                    <span role="cell" className="ol-id">
                      {n.ref}
                    </span>
                    <span role="cell" className="ol-label">
                      {n.kind}
                    </span>
                    <span role="cell">{n.title}</span>
                    <span role="cell">
                      <StatusBadge status={n.status} size="sm" />
                    </span>
                    <span role="cell" className="ol-muted">
                      {n.sha ?? "—"}
                    </span>
                  </button>
                );
              }),
          )}
        </div>
      </div>
    );
  }

  const edgesRendered = graph.edges
    .filter((e) => geo.rects[e.from] && geo.rects[e.to])
    .map((e, i) => {
      const a = byId(e.from);
      const b = byId(e.to);
      if (!a || !b) return null;
      const obligation = a.future || b.future || b.status === "missing";
      const kind = obligation ? "obl" : e.kind === "inferred" ? "inf" : "auth";
      const touches = selectedId && (e.from === selectedId || e.to === selectedId);
      const inHi = hi ? hi.has(e.from) && hi.has(e.to) : false;
      const strong = lens === "lifecycle" ? !!touches : inHi;
      const faded = hi && !inHi;
      const g = edgeGeometry(
        geo.rects[e.from],
        geo.rects[e.to],
        laneIndex(a.lane),
        laneIndex(b.lane),
      );
      const edgeKey = `${e.from}>${e.to}>${e.rel}`;
      const focused = focusEdgeKey === edgeKey;
      return { e, i, g, kind, strong: strong || focused, faded: faded && !focused, focused };
    })
    .filter(Boolean) as {
    e: ControlPlaneGraphEdge;
    i: number;
    g: ReturnType<typeof edgeGeometry>;
    kind: string;
    strong: boolean;
    faded: boolean;
    focused: boolean;
  }[];

  return (
    <div className="ol-graph">
      <GraphToolbar lens={lens} onLens={onLens} view={view} onView={onView} />
      <div className="ol-gwrap" ref={wrapRef}>
        <div className="ol-gspine">
          {geo.w > 0 && geo.centers.length === 6 && (
            <JourneySpine
              stages={stages}
              stageIndex={stageIndex}
              centers={geo.centers}
              width={geo.w}
              height={52}
            />
          )}
        </div>
        <svg className="ol-gedges" width={geo.w} height={geo.h} aria-hidden="true">
          <defs>
            <marker id="ol-ah" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L8,4 L0,8 z" className="ol-ah" />
            </marker>
            <marker id="ol-ah-s" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L8,4 L0,8 z" className="ol-ah-s" />
            </marker>
            <marker id="ol-ah-f" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L8,4 L0,8 z" className="ol-ah-f" />
            </marker>
          </defs>
          {edgesRendered
            .filter((x) => !x.strong)
            .map((x) => (
              <path
                key={x.i}
                d={x.g.d}
                className={cn("ol-edge", `is-${x.kind}`, x.faded && "is-faded")}
                markerEnd="url(#ol-ah)"
              />
            ))}
          {edgesRendered
            .filter((x) => x.strong)
            .map((x) => (
              <path
                key={`s${x.i}`}
                d={x.g.d}
                className={cn("ol-edge", `is-${x.kind}`, "is-strong", x.focused && "is-focus")}
                markerEnd={x.focused ? "url(#ol-ah-f)" : "url(#ol-ah-s)"}
              />
            ))}
        </svg>
        <div className="ol-lanes">
          {LANES.map((l, li) => {
            const nodes = graph.nodes.filter((n) => n.lane === l.id);
            const mat = nodes.filter((n) => !n.future).length;
            const flags = attention.filter((a) => {
              const n = graph.nodes.find(
                (node) => node.ref === a.recordRef || node.id.includes(a.id),
              );
              return n?.lane === l.id;
            });
            const isNow = currentLaneId === l.id;
            return (
              <div key={l.id} className={cn("ol-lane", isNow && "is-now")} ref={(el) => { laneRefs.current[li] = el; }}>
                <button
                  type="button"
                  className="ol-lane-h"
                  onClick={() => onOpenLane(l.id)}
                  title={`${l.question} Open ${l.screen} →`}
                >
                  <span className="ol-lane-top">
                    <span className="ol-ls-code">{l.code}</span>
                    <span className="ol-lane-n">
                      {mat}/{nodes.length}
                    </span>
                    {flags.length > 0 && (
                      <span className={cn("ol-lane-flag", `ol-tc-${presentationForUiKey(flags[0].uiStatusKey).tone}`)}>
                        {presentationForUiKey(flags[0].uiStatusKey).glyph}
                      </span>
                    )}
                  </span>
                  <span className="ol-lane-name">{l.name}</span>
                  <span className="ol-lane-open">
                    {isNow ? <>● {stages[stageIndex]?.state.replace(/_/g, " ")}</> : <>Open {l.short.toLowerCase()} →</>}
                  </span>
                </button>
                <div className="ol-lane-b">
                  {nodes.map((n) => {
                    const dim = hi ? !hi.has(n.id) : false;
                    return (
                      <ObjectNode
                        key={n.id}
                        node={n}
                        selected={selectedId === n.id}
                        dim={dim}
                        onClick={() => onSelect(n.id)}
                        innerRef={(el) => {
                          nodeRefs.current[n.id] = el;
                        }}
                      />
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="ol-ghint">
        Select a record → inspect reason and provenance → open contextual detail. Viewing never issues a command.
        {lens !== "lifecycle" && hi && (
          <>
            {" "}
            · <strong>{hi.size}</strong> records in the {lens} lens
          </>
        )}
      </div>
    </div>
  );
}
