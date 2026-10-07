"use client";

import { CommandList, type CommandPreview } from "@/components/inspector/CommandList";
import { WhyPanel, type WhyView } from "@/components/inspector/WhyPanel";
import { ExceptionState } from "@/components/truth/ExceptionState";
import { Button, IdRef, KV, Label, Sha, StatusBadge } from "@/components/primitives";
import type { ControlPlaneGraphEdge, ControlPlaneGraphNode } from "@/src/control-plane/graph-types";
import { LANE_BY_ID, type LensId } from "@/src/control-plane/lanes";
import { cn } from "@/lib/utils";
import Link from "next/link";

export function ObjectInspector({
  node,
  edges,
  nodesById,
  why,
  commands,
  projectId,
  cycleId,
  lens,
  onSelect,
  onHoverEdge,
  onCommand,
}: {
  node?: ControlPlaneGraphNode;
  edges: ControlPlaneGraphEdge[];
  nodesById: Map<string, ControlPlaneGraphNode>;
  why?: WhyView;
  commands: CommandPreview[];
  projectId: string;
  cycleId: string;
  lens: LensId;
  onSelect: (id: string) => void;
  onHoverEdge?: (key: string | null) => void;
  onCommand?: (c: CommandPreview) => void;
}) {
  if (!node) {
    if (why || commands.length) {
      return (
        <aside className="ol-insp" aria-label="Cycle state inspector">
          <div className="ol-insp-h">
            <Label>Delivery cycle</Label>
            <div className="ol-insp-t">Why this state?</div>
          </div>
          {why && (
            <div className="ol-insp-sec">
              <WhyPanel why={why} onRef={onSelect} />
            </div>
          )}
          <div className="ol-insp-sec">
            <h3 className="ol-insp-st">Permitted commands</h3>
            <CommandList cmds={commands} onCommand={onCommand} />
          </div>
        </aside>
      );
    }
    return (
      <aside className="ol-insp">
        <div className="ol-insp-empty">
          <Label>Object inspector</Label>
          <p>
            Select a record on the map to see its state, the reason for it, its provenance and the
            commands you may issue.
          </p>
        </div>
      </aside>
    );
  }

  const lane = LANE_BY_ID[node.lane];
  const rels = edges.filter((e) => e.from === node.id || e.to === node.id);

  const drillHref = drillPath(projectId, cycleId, node);

  return (
    <aside className="ol-insp" aria-label={`Inspector: ${node.ref}`}>
      <div className="ol-insp-h">
        <Label>
          {node.kind} · {lane.name}
        </Label>
        <div className="ol-insp-id">{node.ref}</div>
        <div className="ol-insp-t">{node.title}</div>
        <div className="ol-chips">
          <StatusBadge status={node.status} />
        </div>
      </div>
      <div className="ol-insp-sec">
        <h3 className="ol-insp-st">Why this state?</h3>
        {why ? (
          <WhyPanel why={why} onRef={(id) => onSelect(id)} />
        ) : (
          <ExceptionState
            status="pending"
            statusLabel="Why unavailable"
            reason="The Control API does not expose guard evaluation for this record type yet."
            consequence="Open the lane drill-down or use cycle transition preview for authoritative reasons."
          />
        )}
      </div>
      <div className="ol-insp-sec">
        <h3 className="ol-insp-st">Provenance and SHA scope</h3>
        <KV
          rows={[
            ["Commit scope", node.sha ? <Sha key="sha" value={node.sha} /> : "—"],
            ["Backend status", node.backendStatus ?? "—"],
          ]}
        />
      </div>
      <div className="ol-insp-sec">
        <h3 className="ol-insp-st">
          Relations ({rels.length}) · hover to highlight edge
        </h3>
        <ul className="ol-rels">
          {rels.map((e) => {
            const other = e.from === node.id ? e.to : e.from;
            const otherNode = nodesById.get(other);
            const edgeKey = `${e.from}>${e.to}>${e.rel}`;
            return (
              <li
                key={edgeKey}
                className={cn("ol-rel", e.kind === "inferred" && "is-inf")}
                onMouseEnter={() => onHoverEdge?.(edgeKey)}
                onMouseLeave={() => onHoverEdge?.(null)}
              >
                <IdRef id={otherNode?.ref ?? other} onNavigate={() => onSelect(other)} />
                <span className="ol-rel-t">{e.rel}</span>
                <IdRef id={node.ref} />
              </li>
            );
          })}
        </ul>
      </div>
      <div className="ol-insp-sec">
        <h3 className="ol-insp-st">Permitted commands</h3>
        <CommandList cmds={commands} onCommand={onCommand} />
      </div>
      <div className="ol-insp-f">
        {drillHref && (
          <Button variant="primary" asChild>
            <Link href={drillHref}>Open in {lane.screen} →</Link>
          </Button>
        )}
        {lens === "trace" && (
          <Button variant="quiet" asChild>
            <Link href={`/projects/${projectId}/lineage?cycle=${cycleId}`}>Open Traceability</Link>
          </Button>
        )}
        {lens === "impact" && (
          <Button variant="quiet" asChild>
            <Link href={`/projects/${projectId}/cycles/${cycleId}/impact`}>Open Impact</Link>
          </Button>
        )}
      </div>
    </aside>
  );
}

function drillPath(projectId: string, cycleId: string, node: ControlPlaneGraphNode): string | null {
  switch (node.lane) {
    case "work":
      return `/projects/${projectId}/cycles/${cycleId}/tasks?selected=${encodeURIComponent(node.id.split(":")[1] ?? "")}`;
    case "exec":
      return `/executions/${encodeURIComponent(node.id.split(":")[1] ?? "")}`;
    case "code":
      return `/projects/${projectId}/code?cycle=${cycleId}`;
    case "evidence":
      return `/projects/${projectId}/cycles/${cycleId}/assurance`;
    case "outcome":
      return `/projects/${projectId}/cycles/${cycleId}/outcome`;
    case "intent":
      return `/projects/${projectId}/product?cycle=${cycleId}`;
    default:
      return null;
  }
}
