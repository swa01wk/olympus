import { cn } from "@/lib/utils";

export type ProvenanceKind = "FACT" | "INFERENCE" | "UNCERTAINTY" | "ASSUMPTION" | "DECISION";

const PROV: Record<ProvenanceKind, { glyph: string; className: string; description: string }> = {
  FACT: { glyph: "■", className: "", description: "Deterministically observed" },
  INFERENCE: {
    glyph: "◐",
    className: "ol-prov-inference",
    description: "Reasoned from evidence",
  },
  UNCERTAINTY: {
    glyph: "?",
    className: "ol-prov-uncertainty",
    description: "Unresolved — may block",
  },
  ASSUMPTION: {
    glyph: "○",
    className: "ol-prov-assumption",
    description: "Temporary, never canonical",
  },
  DECISION: {
    glyph: "◆",
    className: "ol-prov-decision",
    description: "Approved, versioned, attributable",
  },
};

export type ProvenanceBadgeProps = {
  kind: ProvenanceKind;
  confidence?: number;
  source?: string;
};

export function ProvenanceBadge({ kind, confidence, source }: ProvenanceBadgeProps) {
  const p = PROV[kind];
  const title = p.description + (source ? ` · ${source}` : "");
  return (
    <span className={cn("ol-prov", p.className)} title={title}>
      <span aria-hidden="true">{p.glyph}</span>
      {kind}
      {confidence != null && <span className="ol-prov-conf">{confidence.toFixed(2)}</span>}
    </span>
  );
}
